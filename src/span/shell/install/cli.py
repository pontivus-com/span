"""Installer command flow (stdlib only; no span imports at import time).

The entry point resolves install locations, runs one-shot maintenance commands,
then provisions, registers hosts, and writes one receipt. Each stage is a named
function so the flow reads as the documented install contract.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from dataclasses import dataclass as _dataclass
from pathlib import Path

from span.shell.install.arguments import parse_args
from span.shell.install.backup import (
    backup_data_dir,
    compare_census,
    snapshot_census,
    target_artifact_snapshot,
    _clean_build_staging,
)
from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.host_inspect import detect_hosts
from span.shell.install.hosts import (
    _hook_bin,
    merge_opencode_config,
    register_claude,
    register_codex,
    wire_claude_hooks,
    wire_codex_hooks,
)
from span.shell.install.indexer import (
    check_prereqs,
    ensure_structural_indexer,
    write_indexer_pointer,
)
from span.shell.install.paths import (
    distribution_version,
    git_rev,
    install_mode,
    platform_paths,
)
from span.shell.install.preflight import load_seeds, preflight_facts
from span.shell.install.receipt import write_receipt
from span.shell.install.skills import deploy_agents_rules, deploy_skills
from span.shell.install.uninstall import list_orphans, purge_repository, uninstall
from span.shell.install.venv import (
    distribution_venv_in_sync,
    ensure_venv,
    expose_binary,
    pip_install,
    source_venv_in_sync,
    verify_installed,
)
from span.shell.install.verify import doctor, verify_installation

__all__ = ["main"]


@_dataclass(frozen=True)
class _Environment:
    """Resolved install locations and targets for one invocation."""

    args: argparse.Namespace
    venv_dir: Path
    data_dir: Path
    bin_dir: Path
    span_repo: Path
    targets: tuple[Path, ...]
    dry: bool


@_dataclass(frozen=True)
class _RuntimeState:
    """What provisioning produced, carried into the receipt."""

    target_census: dict[str, object]
    seeds: list[object]
    preflight: dict[str, object]
    venv_python: Path
    indexer_pointer: dict[str, object] | None
    source_venv_sync: dict[str, object]
    data_backup: str | None
    post_install_verified: str | None


def _environment(args: argparse.Namespace) -> _Environment:
    paths = platform_paths()
    venv_dir = Path(args.venv_dir) if args.venv_dir else paths["venv_dir"]
    data_dir = Path(args.data_dir) if args.data_dir else paths["data_dir"]
    bin_dir = Path(args.bin_dir) if args.bin_dir else paths["bin_dir"]
    span_repo = Path(args.span_repo).resolve()
    targets = tuple(Path(r).resolve() for r in args.repo)
    for target in targets:
        if data_dir == target or str(data_dir).startswith(str(target) + "/"):
            raise SystemExit(
                f"data dir must live outside every target repo: {data_dir}"
            )
    return _Environment(
        args, venv_dir, data_dir, bin_dir, span_repo, targets, args.dry_run
    )


def _run_one_shot(env: _Environment) -> bool:
    """Run a maintenance command that exits without a full install."""
    args = env.args
    if args.list_orphans:
        list_orphans(env.data_dir)
        return True
    if args.migrate_store is not None:
        raise SystemExit(
            "--migrate-store was removed in 0.9.0. Use "
            "`span-install --transition-store <repository-id> "
            "--transition-phase inspect` for a read-only assessment, then "
            "`--transition-phase apply` with --transition-root for the "
            "authorized offline transition. Nothing was changed."
        )
    if args.transition_phase is not None or args.transition_root is not None:
        if args.transition_store is None:
            raise SystemExit(
                "--transition-phase/--transition-root require "
                "--transition-store <repository-id>. Nothing was changed."
            )
    if args.transition_store is not None:
        if args.transition_phase is None:
            raise SystemExit(
                "--transition-store requires --transition-phase "
                "inspect|apply|verify|rollback. Nothing was changed."
            )
        from span.shell.store_transition import (
            TransitionConfig,
            TransitionError,
            TransitionPhase,
            dispatch,
            parse_phase,
            report_payload,
        )

        config = TransitionConfig(
            data_dir=env.data_dir,
            repository_id=args.transition_store,
            root=args.transition_root,
        )
        phase = parse_phase(args.transition_phase)
        if env.dry and phase not in {TransitionPhase.INSPECT, TransitionPhase.VERIFY}:
            print(
                f"+ transition {phase.value} (dry-run, not executed): "
                f"{env.data_dir}",
                file=sys.stderr,
            )
            phase = TransitionPhase.INSPECT
        try:
            report = dispatch(config, phase)
        except TransitionError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from None
        print(json.dumps(report_payload(report), sort_keys=True))
        return True
    if args.uninstall:
        uninstall(
            env.data_dir,
            env.targets,
            args.opencode_config,
            dry_run=env.dry,
        )
        return True
    if args.purge is not None:
        purge_repository(env.data_dir, args.purge, dry_run=env.dry)
        return True
    if args.verify_only:
        venv_python = env.venv_dir / "bin" / "python"
        doctor(
            venv_python,
            env.data_dir,
            env.targets,
            args.opencode_config,
            env.dry,
        )
        return True
    if args.snapshot_census is not None:
        snapshot_census(env.targets, args.snapshot_census, dry_run=env.dry)
        return True
    if args.compare_census is not None:
        compare_census(*args.compare_census)
        return True
    return False


def _provision_runtime(env: _Environment) -> _RuntimeState:
    """Install or reuse the runtime, then verify it before recording anything."""
    args = env.args
    check_prereqs()
    target_census: dict[str, object] = {
        str(target): target_artifact_snapshot(target) for target in env.targets
    }
    # Early seed-shape validation before any mutation, plus read-only
    # non-gating preflight facts. Shape failure closes before mutation;
    # locator resolution stays at provisioning.
    seeds = load_seeds(args.authority_seeds_file, dry_run=env.dry)
    preflight = preflight_facts(env.targets, args.authority_seeds_file)
    print(f"preflight facts: {json.dumps(preflight, sort_keys=True)}")
    venv_python = ensure_venv(env.venv_dir, dry_run=env.dry)
    indexer_binary = ensure_structural_indexer(env.venv_dir, dry_run=env.dry)
    indexer_pointer = write_indexer_pointer(
        env.data_dir, indexer_binary, dry_run=env.dry
    )
    # Tier-1 verify-fast-path: skip reinstall when the venv already matches
    # the install source, with proof. The check is read-only and runs on
    # dry-run too; backup precedes mutation only. A distribution install
    # proves version equality because it has no source tree to hash.
    mode = install_mode(env.span_repo)
    if mode == "checkout":
        in_sync, files_checked, extra_files = source_venv_in_sync(
            env.span_repo, venv_python
        )
        match_detail = f"source ({files_checked} files)"
    else:
        in_sync, files_checked, extra_files = distribution_venv_in_sync(venv_python)
        match_detail = f"span-mcp {distribution_version()}"
    data_backup = None
    post_install_verified = None
    if in_sync:
        print(f"venv matches {match_detail}; skipping reinstall with proof.")
        reinstalled = False
    else:
        data_backup = backup_data_dir(env.data_dir, dry_run=env.dry)
        if mode == "checkout":
            # Build staging only exists for a source build; cleaning it in a
            # distribution install would touch whatever `build/` happens to
            # sit in the caller's working directory.
            _clean_build_staging(env.span_repo, dry_run=env.dry)
        pip_install(venv_python, env.span_repo, dry_run=env.dry)
        reinstalled = not env.dry
        if reinstalled:
            ok, detail = verify_installed(env.span_repo, venv_python)
            if not ok:
                raise SystemExit(
                    f"installed runtime failed verification: {detail}. "
                    "The install is refused rather than recorded; "
                    "fix the build and rerun."
                )
            print(f"installed runtime verified: {detail}.")
            post_install_verified = detail
    if extra_files:
        print(
            "warning: stale files in venv pip reinstall never removes: "
            + ", ".join(extra_files)
            + ". Recreate the venv to clear them."
        )
    source_venv_sync = {
        "in_sync_before_install": bool(in_sync),
        "files_checked": files_checked,
        "extra_venv_files": list(extra_files),
        "reinstalled": bool(reinstalled),
    }
    expose_binary(env.venv_dir, env.bin_dir, dry_run=env.dry)
    if seeds:
        # Verification provisions without seeds; seeds enter through a
        # setup-session initialize_repository call with authority_seeds.
        print(
            f"loaded {len(seeds)} authority seeds "
            "(provision them via a setup-session "
            "initialize_repository call; verification "
            "provisions without seeds)"
        )
    return _RuntimeState(
        target_census=target_census,
        seeds=seeds,
        preflight=preflight,
        venv_python=venv_python,
        indexer_pointer=indexer_pointer,
        source_venv_sync=source_venv_sync,
        data_backup=data_backup,
        post_install_verified=post_install_verified,
    )


def _span_command(env: _Environment) -> list[str]:
    resolved_mcp = shutil.which("span-mcp")
    if resolved_mcp is None:
        # Not yet on PATH in this process; the server entry needs an absolute
        # path, so resolve the just-linked binary directly.
        resolved_mcp = str(env.bin_dir / "span-mcp")
    command = [resolved_mcp, "--data-dir", str(env.data_dir)]
    for target in env.targets:
        command += ["--repo", str(target)]
    return command


def _register_hosts(env: _Environment) -> dict[str, object]:
    """Register hosts and deploy skills; each host's refusal stays typed."""
    args = env.args
    span_cmd = _span_command(env)
    host_registration: dict[str, object] = {}
    opencode_config = args.opencode_config
    if opencode_config is None and Path("opencode.json").exists():
        opencode_config = "opencode.json"
    if opencode_config is not None:
        try:
            host_registration["opencode"] = merge_opencode_config(
                opencode_config, span_cmd, dry_run=env.dry
            )
        except SystemExit as exc:
            host_registration["opencode"] = {
                "status": "failed",
                "error": str(exc),
            }
            raise
    else:
        print(
            "no opencode.json found; skipping host registration "
            "(pass --opencode-config PATH)."
        )
        host_registration["opencode"] = {
            "status": "skipped",
            "reason": "no opencode.json found (pass --opencode-config PATH)",
        }
    if args.with_codex is None:
        args.with_codex = detect_hosts()["codex"] and not args.no_codex
    elif args.no_codex:
        args.with_codex = False
    if args.with_hooks is None:
        args.with_hooks = not args.no_hooks
    if args.with_codex:
        host_registration["codex"] = register_codex(span_cmd, dry_run=env.dry)
    else:
        _codex_reason = (
            "codex disabled (--no-codex)" if args.no_codex else "codex CLI not detected"
        )
        print(f"skipping codex registration ({_codex_reason}).")
        host_registration["codex"] = {
            "status": "skipped",
            "reason": _codex_reason,
        }
    if args.with_claude is None:
        args.with_claude = detect_hosts()["claude"] and not args.no_claude
    elif args.no_claude:
        args.with_claude = False
    if args.with_claude:
        host_registration["claude"] = register_claude(span_cmd, dry_run=env.dry)
    else:
        _claude_reason = (
            "claude disabled (--no-claude)"
            if args.no_claude
            else "claude CLI not detected"
        )
        print(f"skipping claude registration ({_claude_reason}).")
        host_registration["claude"] = {
            "status": "skipped",
            "reason": _claude_reason,
        }
    host_registration["hooks"] = _wire_hooks(env)
    if not args.no_skills:
        host_registration["skills"] = deploy_skills(env.span_repo, dry_run=env.dry)
    else:
        print("skipping skill deployment (--no-skills).")
        host_registration["skills"] = []
    host_registration["agents"] = deploy_agents_rules(
        env.span_repo, env.targets, dry_run=env.dry
    )
    return host_registration


def _wire_hooks(env: _Environment) -> dict[str, object]:
    args = env.args
    if not args.with_hooks:
        print("skipping hook wiring (--no-hooks).")
        return {
            "codex": {"status": "skipped", "reason": "hooks disabled (--no-hooks)"},
            "claude": {"status": "skipped", "reason": "hooks disabled (--no-hooks)"},
            "opencode_plugin": {},
        }
    hook_bin = _hook_bin(env.venv_dir, env.bin_dir)
    try:
        codex_hooks = wire_codex_hooks(hook_bin, dry_run=env.dry)
    except SystemExit:
        raise
    if args.with_claude:
        try:
            claude_hooks = wire_claude_hooks(hook_bin, env.data_dir, dry_run=env.dry)
        except SystemExit:
            raise
    else:
        claude_hooks = {
            "status": "skipped",
            "reason": "claude integration not enabled",
        }
    # Per-target opencode plugin deployment would write into target
    # repositories and is therefore removed. Host hooks outside targets
    # remain allowed.
    plugin = {
        str(target): {
            "status": "skipped",
            "reason": "target writes prohibited (Span never writes into targets)",
        }
        for target in env.targets
    }
    print(
        "per-target opencode plugin deployment removed "
        "(Span never writes into targets)."
    )
    return {
        "codex": codex_hooks,
        "claude": claude_hooks,
        "opencode_plugin": plugin,
    }


def _build_receipt(
    env: _Environment,
    state: _RuntimeState,
    host_registration: dict[str, object],
    report: dict[str, object],
) -> dict[str, object]:
    return {
        "install_version": INSTALL_VERSION,
        "span_repo": str(env.span_repo),
        "span_rev": git_rev(env.span_repo) if not env.dry else "dry-run",
        "venv_dir": str(env.venv_dir),
        "data_dir": str(env.data_dir),
        "repos": [str(target) for target in env.targets],
        "verify": report,
        "host_registration": host_registration,
        "target_census": state.target_census,
        "structural_indexer": {
            # Neutral summary only: the managed binary path is internal
            # state and never part of the operator-facing receipt.
            "managed": bool(state.indexer_pointer),
            "version": (state.indexer_pointer or {}).get("version"),
        },
        "source_venv_sync": state.source_venv_sync,
        "post_install_verified": state.post_install_verified,
        "data_backup": state.data_backup,
        "seeds_file_supplied_and_readable": bool(state.seeds),
        "seeds_shape_valid": bool(state.seeds),
        "seeds_resolved_and_active": False,
        "preflight_facts": state.preflight,
        # Deterministic installer performs no host exchange (A1 only).
        "a2": "not_run",
        "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def main(argv=None):
    args = parse_args(argv)
    env = _environment(args)
    if _run_one_shot(env):
        return
    state = _provision_runtime(env)
    host_registration = _register_hosts(env)
    report = verify_installation(state.venv_python, env.data_dir, env.targets, env.dry)
    receipt = _build_receipt(env, state, host_registration, report)
    write_receipt(env.data_dir, receipt, dry_run=env.dry)
    print("install complete.")
