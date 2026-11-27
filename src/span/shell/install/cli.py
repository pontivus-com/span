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
import typing as _typing
from dataclasses import dataclass as _dataclass
from pathlib import Path

if _typing.TYPE_CHECKING:
    from span.core import model as m

from span.shell.install.arguments import parse_args
from span.shell.install.backup import (
    backup_data_dir,
    compare_census,
    snapshot_census,
    target_artifact_snapshot,
    _clean_build_staging,
)
from span.shell.install.constants import HOST_RESPONSE_BUDGETS, INSTALL_VERSION
from span.shell.install.host_inspect import detect_hosts
from span.shell.install.hosts import (
    _hook_bin,
    _same_path,
    _sha256_file,
    _span_plugin_file,
    deploy_opencode_plugin,
    inspect_target_opencode_plugins,
    merge_opencode_config,
    opencode_global_config_path,
    register_claude,
    register_codex,
    remove_opencode_plugin,
    remove_opencode_registration,
    resolve_opencode_scope,
    receipt_opencode_mcp_config,
    select_opencode_mcp_config,
    validate_opencode_registration_removal,
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
    opencode_plugin_path,
    platform_paths,
)
from span.shell.install.preflight import (
    administrative_failure,
    load_authority_files,
    preflight_facts,
    validate_authority_files,
)
from span.shell.install import governed
from span.shell.install.receipt import (
    administrative_ownership,
    read_receipt,
    write_receipt,
)
from span.shell.install.recovery import (
    create_backup,
    reap_backups,
    restore_backup,
    verify_backup,
)
from span.shell.install.repository_backup import (
    create_repository_backup,
    load_repository_backup,
    reap_repository_backups,
    verify_repository_backup,
)
from span.shell.install.skills import deploy_agents_rules, deploy_skills
from span.shell.install.uninstall import list_orphans, purge_repository, uninstall
from span.shell.install.venv import (
    distribution_venv_in_sync,
    ensure_venv,
    expose_binary,
    pip_install,
    requested_build_identity,
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
    initializations: tuple[m.InitializeRepositoryResult, ...]
    preflight: dict[str, object]
    venv_python: Path
    indexer_pointer: dict[str, object] | None
    source_venv_sync: dict[str, object]
    data_backup: str | None
    post_install_verified: str | None
    expected_identity: dict[str, str] | None


def _environment(args: argparse.Namespace) -> _Environment:
    paths = platform_paths()
    venv_dir = Path(args.venv_dir) if args.venv_dir else paths["venv_dir"]
    data_dir = (Path(args.data_dir) if args.data_dir else paths["data_dir"]).resolve()
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


def _run_repository_command(env: _Environment) -> bool:
    """Run one repository-portable artifact command."""
    args = env.args
    repository_commands = [
        args.backup_repository is not None,
        args.verify_repository_backup is not None,
        args.load_repository_backup is not None,
        args.reap_repository_backups is not None,
    ]
    if sum(repository_commands) > 1:
        raise SystemExit(
            "run one repository command at a time: --backup-repository, "
            "--verify-repository-backup, --load-repository-backup or "
            "--reap-repository-backups. Nothing was changed."
        )
    if args.repository_artifact is not None and args.load_repository_backup is None:
        raise SystemExit(
            "--repository-artifact only applies to --load-repository-backup. "
            "Nothing was changed."
        )
    if args.backup_repository is not None:
        create_repository_backup(args.backup_repository, env.data_dir, dry_run=env.dry)
        return True
    if args.verify_repository_backup is not None:
        report = verify_repository_backup(args.verify_repository_backup)
        print(json.dumps(report.payload(), sort_keys=True))
        if not report.ok:
            raise SystemExit(2)
        return True
    if args.load_repository_backup is not None:
        load_repository_backup(
            args.load_repository_backup,
            env.data_dir,
            artifact=args.repository_artifact,
            dry_run=env.dry,
        )
        return True
    if args.reap_repository_backups is not None:
        root, keep_text = args.reap_repository_backups
        try:
            keep = int(keep_text)
        except ValueError:
            raise SystemExit(
                "--reap-repository-backups KEEP must be an integer"
            ) from None
        reap_repository_backups(root, keep, dry_run=env.dry)
        return True
    return False


def _run_recovery_command(env: _Environment) -> bool:
    """Run one full data-directory recovery command."""
    args = env.args
    recovery_commands = [
        bool(args.backup),
        args.verify_backup is not None,
        args.restore_backup is not None,
        args.reap_backups is not None,
    ]
    if sum(recovery_commands) > 1:
        raise SystemExit(
            "run one recovery command at a time: --backup, --verify-backup, "
            "--restore-backup or --reap-backups. Nothing was changed."
        )
    if args.restore_confirm is not None and args.restore_backup is None:
        raise SystemExit(
            "--restore-confirm only applies to --restore-backup. "
            "Nothing was changed."
        )
    if args.backup:
        create_backup(env.data_dir, backup_root=args.backup_root, dry_run=env.dry)
        return True
    if args.verify_backup is not None:
        report = verify_backup(args.verify_backup)
        print(json.dumps(report.payload(), sort_keys=True))
        if not report.ok:
            raise SystemExit(2)
        return True
    if args.restore_backup is not None:
        restore_backup(
            args.restore_backup,
            env.data_dir,
            confirm=args.restore_confirm,
            backup_root=args.backup_root,
            dry_run=env.dry,
        )
        return True
    if args.reap_backups is not None:
        reap_backups(
            args.backup_root or env.data_dir / "backups",
            args.reap_backups,
            dry_run=env.dry,
        )
        return True
    return False


def _run_one_shot(env: _Environment) -> bool:
    """Run a maintenance command that exits without a full install."""
    args = env.args
    if args.list_orphans:
        list_orphans(env.data_dir)
        return True
    if _run_repository_command(env):
        return True
    if _run_recovery_command(env):
        return True
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


def _initialize_repositories(
    env: _Environment,
    requests: tuple[m.InitializeRepositoryRequest, ...],
    *,
    pending: dict[str, object] | None = None,
) -> tuple[m.InitializeRepositoryResult, ...]:
    """Initialize selected repositories through the canonical setup owner."""
    if env.dry:
        return ()

    from span.shell.context import (
        close_repository_runtime,
        provision_repository_runtime,
    )
    from span.shell.structural import repository_id_from_config
    from span.shell.structural.graft import GraftUnavailableError

    results: list[m.InitializeRepositoryResult] = []
    for request in requests:
        repository_id = repository_id_from_config(request.repository_locator)
        try:
            if pending is not None and "setup_requests" in pending:
                from functools import partial
                from span.shell.install.governed_recovery import prepare_store

                runtime, result = provision_repository_runtime(
                    env.data_dir,
                    request,
                    prepare_store=partial(prepare_store, env.data_dir, pending),
                )
            else:
                runtime, result = provision_repository_runtime(env.data_dir, request)
        except (OSError, ValueError, GraftUnavailableError) as exc:
            raise administrative_failure(
                exc,
                action=f"Repository initialization failed for {repository_id!r}; check repository access and configuration before retrying.",
            ) from None
        try:
            results.append(result)
        finally:
            close_repository_runtime(runtime)
    return tuple(results)


def _sync_runtime_distribution(
    env: _Environment,
    venv_python: Path,
    *,
    data_backup: str | None = None,
    expected_identity: dict[str, str] | None = None,
) -> tuple[dict[str, object], str | None, str | None]:
    """Bring the installed runtime in sync without touching repository state."""
    mode = install_mode(env.span_repo)
    if mode == "checkout":
        in_sync, files_checked, extra_files = source_venv_in_sync(
            env.span_repo, venv_python, expected_identity=expected_identity
        )
        match_detail = f"source ({files_checked} files)"
    else:
        in_sync, files_checked, extra_files = distribution_venv_in_sync(
            venv_python, expected_identity=expected_identity
        )
        match_detail = f"span-mcp {distribution_version()}"

    post_install_verified = None
    if in_sync:
        print(f"venv matches {match_detail}; skipping reinstall with proof.")
        reinstalled = False
    else:
        if data_backup is None:
            data_backup = backup_data_dir(env.data_dir, dry_run=env.dry)
        if mode == "checkout":
            _clean_build_staging(env.span_repo, dry_run=env.dry)
        pip_install(venv_python, env.span_repo, dry_run=env.dry)
        reinstalled = not env.dry
        if reinstalled:
            ok, detail = verify_installed(
                env.span_repo, venv_python, expected_identity=expected_identity
            )
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
            + f"({len(extra_files)} files). Recreate the runtime environment to clear them."
        )
    source_venv_sync = {
        "in_sync_before_install": bool(in_sync),
        "files_checked": files_checked,
        "extra_venv_files": list(extra_files),
        "reinstalled": bool(reinstalled),
    }
    return source_venv_sync, data_backup, post_install_verified


def _provision_runtime(
    env: _Environment,
    prior: dict[str, object],
    pending: dict[str, object] | None,
    artifacts: dict[tuple[str, str], bytes],
) -> _RuntimeState:
    """Install/reuse runtime, then execute explicit repository initialization."""
    args = env.args
    check_prereqs()
    target_census: dict[str, object] = {
        str(target): target_artifact_snapshot(target) for target in env.targets
    }

    # T02: validate all authority configuration before installer mutation.
    authority_seeds, authority_bindings = load_authority_files(
        env.targets,
        args.authority_seeds_file,
        args.authority_bindings_file,
        dry_run=env.dry,
    )
    if pending is not None:
        authority_bindings.update(governed.bindings_for(pending))
    requests = (
        ()
        if env.dry
        else validate_authority_files(env.targets, authority_seeds, authority_bindings)
    )
    preflight = preflight_facts(
        env.targets,
        binding_files=args.authority_bindings_file,
    )
    print("Repository configuration preflight complete.")

    expected_identity = None if env.dry else requested_build_identity(env.span_repo)
    if not env.dry and expected_identity is None:
        raise SystemExit(
            "The requested Span build cannot be verified. Use a known source revision or verified distribution."
        )
    venv_python = ensure_venv(env.venv_dir, dry_run=env.dry)
    indexer_binary = ensure_structural_indexer(env.venv_dir, dry_run=env.dry)
    data_backup = None
    if pending is not None and not env.dry:
        from span.shell.install.governed_recovery import protect_setup
        from span.shell.install.indexer import indexer_pointer_payload

        data_backup = protect_setup(
            env.data_dir,
            prior,
            pending,
            requests,
            indexer_pointer_payload(indexer_binary),
        )
        governed.retain_pending(env.data_dir, prior, pending, data_backup)
    indexer_pointer = write_indexer_pointer(
        env.data_dir, indexer_binary, dry_run=env.dry
    )
    source_venv_sync, data_backup, post_install_verified = _sync_runtime_distribution(
        env, venv_python, data_backup=data_backup, expected_identity=expected_identity
    )
    expose_binary(env.venv_dir, env.bin_dir, dry_run=env.dry)

    # Protect existing installation state before the first repository mutation.
    if not env.dry and env.targets and data_backup is None:
        data_backup = backup_data_dir(env.data_dir, dry_run=False)

    if pending is not None and not env.dry:
        governed.publish(pending, artifacts, bootstrap=False)
    initializations = _initialize_repositories(env, requests, pending=pending)
    if pending is not None and not env.dry:
        governed.establish(env.data_dir, pending)
        governed.publish(pending, artifacts, bootstrap=True)
    return _RuntimeState(
        target_census=target_census,
        initializations=initializations,
        preflight=preflight,
        venv_python=venv_python,
        indexer_pointer=indexer_pointer,
        source_venv_sync=source_venv_sync,
        data_backup=data_backup,
        post_install_verified=post_install_verified,
        expected_identity=expected_identity,
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


def _host_command(command: list[str], host: str) -> list[str]:
    """Add the measured per-host response budget to one registration."""
    budget = HOST_RESPONSE_BUDGETS[host]
    return [*command, "--response-budget-bytes", str(budget)]


def _select_opencode_install_config(
    args: argparse.Namespace,
    scope: str | None,
    prior_receipt: dict[str, object] | None,
) -> tuple[str | None, str | None, bool]:
    """Resolve the MCP path and whether this invocation explicitly relocates it."""
    prior_mcp_config = receipt_opencode_mcp_config(prior_receipt)
    opencode_config = select_opencode_mcp_config(
        args.opencode_config,
        scope,
        global_config=opencode_global_config_path(),
        receipt_config=prior_mcp_config,
    )
    relocating = (
        args.opencode_config is not None
        and prior_mcp_config is not None
        and not _same_path(opencode_config, prior_mcp_config)
    )
    return prior_mcp_config, opencode_config, relocating


def _mcp_selection_scope(args: argparse.Namespace, scope: str | None) -> str | None:
    """Keep MCP registration active when lifecycle hooks are disabled."""
    if scope is not None:
        return scope
    return "global" if args.no_hooks else None


def _register_hosts(
    env: _Environment,
    scope: str | None,
    prior_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    """Register hosts and deploy skills; each host's refusal stays typed."""
    args = env.args
    span_cmd = _span_command(env)
    opencode_cmd = _host_command(span_cmd, "opencode")
    codex_cmd = _host_command(span_cmd, "codex")
    host_registration: dict[str, object] = {}
    mcp_scope = _mcp_selection_scope(args, scope)
    prior_mcp_config, opencode_config, relocating = _select_opencode_install_config(
        args, mcp_scope, prior_receipt
    )
    if opencode_config is not None:
        try:
            if relocating:
                validate_opencode_registration_removal(prior_mcp_config)
            host_registration["opencode"] = merge_opencode_config(
                opencode_config, opencode_cmd, dry_run=env.dry
            )
        except SystemExit as exc:
            host_registration["opencode"] = {
                "status": "failed",
                "error": str(exc),
            }
            raise
        if relocating:
            host_registration["opencode_transition"] = {
                "from": prior_mcp_config,
                "to": opencode_config,
                "removal": remove_opencode_registration(
                    prior_mcp_config, dry_run=env.dry
                ),
            }
    else:
        print(
            "no OpenCode MCP config selected; skipping host registration "
            "(pass --opencode-config PATH or create ./opencode.json)."
        )
        host_registration["opencode"] = {
            "status": "skipped",
            "reason": (
                "no OpenCode MCP config selected (pass --opencode-config PATH "
                "or create ./opencode.json)"
            ),
        }
    if args.with_codex is None:
        args.with_codex = detect_hosts()["codex"] and not args.no_codex
    elif args.no_codex:
        args.with_codex = False
    if args.with_hooks is None:
        args.with_hooks = not args.no_hooks
    if args.with_codex:
        host_registration["codex"] = register_codex(codex_cmd, dry_run=env.dry)
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
            else "claude host not detected"
        )
        print(f"skipping claude registration ({_claude_reason}).")
        host_registration["claude"] = {
            "status": "skipped",
            "reason": _claude_reason,
        }
    host_registration["hooks"] = _wire_hooks(env, scope)
    if not args.no_skills:
        host_registration["skills"] = deploy_skills(env.span_repo, dry_run=env.dry)
    else:
        print("skipping skill deployment (--no-skills).")
        host_registration["skills"] = []
    host_registration["agents"] = deploy_agents_rules(
        env.span_repo, env.targets, dry_run=env.dry
    )
    return host_registration


def _wire_hooks(env: _Environment, scope: str | None) -> dict[str, object]:
    args = env.args
    if not args.with_hooks:
        print("skipping hook wiring (--no-hooks).")
        return {
            "codex": {"status": "skipped", "reason": "hooks disabled (--no-hooks)"},
            "claude": {"status": "skipped", "reason": "hooks disabled (--no-hooks)"},
            "opencode_plugin": {
                "scope": scope,
                "status": "skipped",
                "reason": "hooks disabled (--no-hooks)",
            },
        }
    hook_bin = _hook_bin(env.venv_dir, env.bin_dir)
    codex_hooks = wire_codex_hooks(hook_bin, env.data_dir, dry_run=env.dry)
    claude_hooks = (
        wire_claude_hooks(hook_bin, env.data_dir, dry_run=env.dry)
        if args.with_claude
        else {"status": "skipped", "reason": "claude integration not enabled"}
    )
    receipt = read_receipt(env.data_dir) or {}
    selected = tuple(Path(target).resolve() for target in env.targets)
    receipt_targets = tuple(
        Path(repo).resolve()
        for repo in receipt.get("repos", [])
        if isinstance(repo, str) and repo
    )
    receipt_only = tuple(
        target for target in dict.fromkeys(receipt_targets) if target not in selected
    )
    plugin, target_plugins = _apply_opencode_scope(
        env,
        scope,
        opencode_global_config_path(),
        env.data_dir.parent / "opencode-plugin",
        env.data_dir.parent,
        selected,
        receipt_only,
        hook_bin,
    )
    return {
        "codex": codex_hooks,
        "claude": claude_hooks,
        "opencode_plugin": plugin,
        "opencode_target_plugins": target_plugins,
    }


def _apply_opencode_scope(
    env: _Environment,
    scope: str | None,
    global_config: Path,
    canonical_dir: Path,
    span_root: Path,
    selected: tuple[Path, ...],
    receipt_only: tuple[Path, ...],
    hook_bin: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Apply exactly the selected scope; never act outside it."""
    if scope == "global":
        return _apply_global_scope(
            env,
            global_config,
            canonical_dir,
            span_root,
            selected,
            receipt_only,
            hook_bin,
        )
    return _apply_user_managed_scope(
        env, scope, global_config, canonical_dir, span_root, selected, receipt_only
    )


def _apply_global_scope(
    env: _Environment,
    global_config: Path,
    canonical_dir: Path,
    span_root: Path,
    selected: tuple[Path, ...],
    receipt_only: tuple[Path, ...],
    hook_bin: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Deploy the canonical global plugin and report target conflicts."""
    plugin = deploy_opencode_plugin(
        opencode_plugin_path(env.span_repo),
        canonical_dir,
        global_config,
        hook_bin,
        env.data_dir,
        dry_run=env.dry,
        span_root=span_root,
    )
    selected_targets, selected_unreadable = inspect_target_opencode_plugins(selected)
    receipt_targets, receipt_unreadable = inspect_target_opencode_plugins(receipt_only)
    conflicts = list(plugin.get("conflicts", []))
    for target, entries in selected_targets.items():
        conflicts.extend(
            {
                "path": item["path"],
                "target": target,
                "reason": "target-local Span plugin conflicts with global scope",
                "manual_action": (
                    f"remove or manage {item['path']} manually before rerunning"
                ),
            }
            for item in entries
        )
    for target, entries in receipt_targets.items():
        conflicts.extend(
            {
                "path": item["path"],
                "reason": "receipt target was not selected with --repo",
                "manual_action": (
                    f"span-install --repo {target} --opencode-plugin-scope global"
                ),
            }
            for item in entries
        )
    unreadable = [*selected_unreadable, *receipt_unreadable]
    if unreadable:
        status = "unreadable"
    elif conflicts:
        status = "conflict"
    else:
        status = "wired"
    plugin.update(
        {
            "scope": "global",
            "status": status,
            "conflicts": conflicts,
            "unreadable": unreadable,
        }
    )
    return plugin, {
        "status": (
            "unreadable" if unreadable else ("conflict" if conflicts else "wired")
        ),
        "selected": {
            "targets": selected_targets,
            "unreadable": selected_unreadable,
        },
        "receipt_only": {
            "targets": receipt_targets,
            "unreadable": receipt_unreadable,
        },
    }


def _apply_user_managed_scope(
    env: _Environment,
    scope: str | None,
    global_config: Path,
    canonical_dir: Path,
    span_root: Path,
    selected: tuple[Path, ...],
    receipt_only: tuple[Path, ...],
) -> tuple[dict[str, object], dict[str, object]]:
    """Remove Span's global registration; report user-managed copies only."""
    plugin = remove_opencode_plugin(
        global_config, canonical_dir, dry_run=env.dry, span_root=span_root
    )
    selected_targets, selected_unreadable = inspect_target_opencode_plugins(selected)
    receipt_targets, receipt_unreadable = inspect_target_opencode_plugins(receipt_only)
    source = opencode_plugin_path(env.span_repo)
    expected_hash = _sha256_file(source) if source.is_file() else None
    copies = []
    for path in plugin.get("user_managed", []):
        plugin_file = _span_plugin_file(path)
        digest = _sha256_file(plugin_file) if plugin_file is not None else None
        copies.append(
            {
                "path": path,
                "sha256": digest,
                "matches_installed": (
                    None
                    if expected_hash is None or digest is None
                    else digest == expected_hash
                ),
            }
        )
    for target, entries in (
        *selected_targets.items(),
        *receipt_targets.items(),
    ):
        copies.extend(
            {
                "target": target,
                "path": item["path"],
                "sha256": item["sha256"],
                "matches_installed": (
                    None if expected_hash is None else item["sha256"] == expected_hash
                ),
            }
            for item in entries
        )
    unreadable = [*selected_unreadable, *receipt_unreadable]
    if unreadable:
        status = "unreadable"
    elif len(copies) > 1:
        status = "conflict"
    elif len(copies) == 1:
        status = "external"
    else:
        status = "absent" if scope == "local" else "disabled"
    plugin.update(
        {
            "scope": scope,
            "status": status,
            "user_managed": copies,
            "conflicts": copies if len(copies) > 1 else [],
            "unreadable": unreadable,
        }
    )
    return plugin, {
        "status": status,
        "selected": {
            "targets": selected_targets,
            "unreadable": selected_unreadable,
        },
        "receipt_only": {
            "targets": receipt_targets,
            "unreadable": receipt_unreadable,
        },
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
        "repository_initialization": [
            {
                "repository_id": result.repository_id,
                "canonical_root": result.canonical_root,
                "schema_version": result.schema_version,
                "store_ready": result.store_ready,
                "structural_status": result.structural_status,
                "authority_seed_count": len(result.authority_seeds),
                "authority_binding_count": len(result.authority_bindings),
                "warnings": list(result.warnings),
            }
            for result in state.initializations
        ],
        "preflight_facts": state.preflight,
        # Deterministic installer performs no host exchange (A1 only).
        "a2": "not_run",
        "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _mutating_invocation(env: _Environment) -> bool:
    """Classify administrative operations before acquiring ownership."""
    args = env.args
    if env.dry:
        return False
    if any(
        (
            args.backup,
            args.backup_repository is not None,
            args.load_repository_backup is not None,
            args.reap_repository_backups is not None,
            args.restore_backup is not None,
            args.reap_backups is not None,
            args.uninstall,
            args.purge is not None,
            args.transition_phase in ("apply", "rollback"),
        )
    ):
        return True
    return not any(
        (
            args.list_orphans,
            args.verify_repository_backup is not None,
            args.verify_backup is not None,
            args.transition_phase in ("inspect", "verify"),
            args.verify_only,
            args.snapshot_census is not None,
            args.compare_census is not None,
        )
    )


def _execute(env: _Environment) -> None:
    args = env.args
    prior_receipt = read_receipt(env.data_dir)
    prior = prior_receipt or {}
    mappings = args.functional_pyramid_classification_file
    if (
        governed.PENDING in prior
        and _mutating_invocation(env)
        and not mappings
        and args.restore_backup is None
    ):
        raise SystemExit(
            "incomplete governed initialization; resume the same classification input or explicitly restore a verified backup"
        )
    if _run_one_shot(env):
        return
    pending = None
    artifacts: dict[tuple[str, str], bytes] = {}
    if mappings:
        try:
            pending, artifacts = governed.prepare(
                env.data_dir, env.targets, mappings, args.authority_bindings_file, prior
            )
        except (OSError, ValueError, KeyError) as exc:
            raise administrative_failure(
                exc,
                action="Governed initialization cannot proceed; check the selected repositories and supplied classification. If installation was interrupted, resume the original request or restore its verified backup.",
            ) from None
    elif governed.PENDING in prior:
        print("incomplete governed initialization; observation only")
    scope = None
    if not args.no_hooks:
        scope_receipt = prior_receipt
        if governed.PENDING in prior and not prior.get("host_registration"):
            scope_receipt = None
        scope, _ = resolve_opencode_scope(args.opencode_plugin_scope, scope_receipt)
    try:
        state = _provision_runtime(env, prior, pending, artifacts)
    except (OSError, ValueError, KeyError) as exc:
        raise administrative_failure(
            exc,
            action="Installation could not complete; verify the current installation and follow the reported recovery action.",
        ) from None
    host_registration = _register_hosts(env, scope, prior_receipt)
    report = verify_installation(
        state.venv_python,
        env.data_dir,
        env.targets,
        env.dry,
        strict=pending is not None,
        pending_setup=pending is not None,
    )
    if not env.dry:
        identity = report.get("build_identity")
        expected = state.expected_identity
        if (
            expected is None
            or requested_build_identity(env.span_repo) != expected
            or not isinstance(identity, dict)
            or any(identity.get(key) != value for key, value in expected.items())
        ):
            raise SystemExit(
                "The requested Span build changed or could not be verified. Reinstall the intended revision."
            )
    receipt = _build_receipt(env, state, host_registration, report)
    if not env.dry:
        governed.finalize(receipt, prior, pending)
        from span.shell.install_verify import project_final_receipt

        project_final_receipt(env.data_dir, report, receipt, strict=pending is not None)
    write_receipt(env.data_dir, receipt, dry_run=env.dry)
    print("install plan only." if env.dry else "install complete.")


def main(argv=None):
    env = _environment(parse_args(argv))
    if not _mutating_invocation(env):
        _execute(env)
        return
    from span.shell.sqlite_ownership import StoreHeldError, store_use_ownership

    try:
        with administrative_ownership(env.data_dir):
            if env.args.restore_backup is not None:
                _execute(env)
            else:
                with store_use_ownership(env.data_dir):
                    _execute(env)
    except StoreHeldError as exc:
        raise administrative_failure(
            exc,
            action="Installation ownership is unavailable; stop other Span installation, recovery or runtime processes and retry.",
        ) from None
