"""Cross-platform-capable Span installer (Linux implemented).

Stdlib only. No ``span.*`` imports at module top level: this module
must run from a source checkout (via ``scripts/install-span.py``)
before Span is installed, and post-install as the ``span-install``
entry point. All Span imports are lazy inside verification paths.

OS specifics live exclusively in ``PLATFORM_PATHS``; ``linux`` is
fully specified, ``darwin``/``win32`` are structurally reserved.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_VERSION = 1

# Only this table varies by OS. Everything else is platform-neutral.
PLATFORM_PATHS = {
    "linux": {
        "venv_dir": ("~/.local/share/span/venv",),
        "data_dir": ("~/.local/share/span/data",),
        "bin_dir": ("~/.local/bin",),
        "supported": True,
    },
    "darwin": {
        "venv_dir": ("~/Library/Application Support/span/venv",),
        "data_dir": ("~/Library/Application Support/span/data",),
        "bin_dir": ("~/.local/bin",),
        "supported": False,
        "note": "paths reserved; runner verification pending",
    },
    "win32": {
        "venv_dir": ("%LOCALAPPDATA%/span/venv",),
        "data_dir": ("%LOCALAPPDATA%/span/data",),
        "bin_dir": ("%APPDATA%/span/bin",),
        "supported": False,
        "note": "paths reserved; shim strategy pending (.cmd, no symlink)",
    },
}

SCHEMA_SENTINEL = "SCHEMA_VERSION"


def platform_paths(platform=None):
    """Resolve install locations for one platform key.

    Raises SystemExit with a clear message on unsupported platforms
    instead of guessing paths.
    """
    key = platform or sys.platform
    try:
        entry = PLATFORM_PATHS[key]
    except KeyError:
        raise SystemExit(f"unsupported platform for install: {key}")
    if not entry.get("supported", False):
        raise SystemExit(
            f"install paths reserved but not yet verified for: {key} "
            f"({entry.get('note', 'no note')})"
        )
    return {
        name: Path(os.path.expandvars(os.path.expanduser(value[0])))
        for name, value in entry.items()
        if isinstance(value, tuple)
    }


def check_prereqs():
    """Fail closed naming the first missing prerequisite."""
    errors = []
    if sys.version_info < (3, 12):
        errors.append(
            f"python >= 3.12 required, found {sys.version.split()[0]}"
        )
    for tool in ("node", "graft"):
        if shutil.which(tool) is None:
            errors.append(f"required tool missing from PATH: {tool}")
    if errors:
        raise SystemExit("prerequisites missing:\n- " + "\n- ".join(errors))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="span-install",
        description=(
            "Install span-mcp, register host MCP entries, initialize "
            "target repositories, and verify readiness. Linux only; "
            "other platforms are structurally reserved, not silently attempted."
        ),
    )
    parser.add_argument(
        "--repo", action="append", default=[], metavar="TARGET_DIR",
        help=(
            "Target repository root (repeatable). Registered as "
            "graft:<dir>. Requires graft/.graph/wiring.json unless "
            "--build-index is given with explicit consent."
        ),
    )
    parser.add_argument(
        "--data-dir", default=None,
        help="SQLite store directory (default: platform data dir). "
        "Refused when inside any target repo.",
    )
    parser.add_argument(
        "--venv-dir", default=None,
        help="Virtualenv location (default: platform venv dir).",
    )
    parser.add_argument(
        "--bin-dir", default=None,
        help="Directory receiving the span-mcp symlink "
        "(default: platform bin dir).",
    )
    parser.add_argument(
        "--span-repo", default=".",
        help="Span source checkout to install (default: cwd).",
    )
    parser.add_argument(
        "--build-index", action="store_true",
        help="Run `graft build` inside targets missing an index. "
        "Writes into the target; requires this explicit flag.",
    )
    parser.add_argument(
        "--opencode-config", default=None,
        help="opencode.json to merge the span MCP entry into. "
        "Default: ./opencode.json when present, else skipped.",
    )
    parser.add_argument(
        "--with-codex", action="store_true", default=None,
        help="Register via `codex mcp add` (default: automatic when "
        "the codex CLI is present; --no-codex to skip).",
    )
    parser.add_argument(
        "--no-codex", action="store_true",
        help="Skip all Codex integration even when detected.",
    )
    parser.add_argument(
        "--with-hooks", action="store_true", default=None,
        help="Wire report-only lifecycle hooks (default: automatic "
        "when a supported host is detected; --no-hooks to skip). "
        "Hooks only report readiness/dependents/closure; they never "
        "write, interpret, refresh, or initialize.",
    )
    parser.add_argument(
        "--no-hooks", action="store_true",
        help="Skip hook wiring even when hosts are detected.",
    )
    parser.add_argument(
        "--no-skills", action="store_true",
        help="Skip skill deployment even when hosts are detected.",
    )
    parser.add_argument(
        "--authority-seeds-file", default=None,
        help="JSON file with canonical EvidenceRef items for init. "
        "Absent means no seeds; seeds are never invented.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned actions; execute nothing.",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Skip install; verify an existing installation and exit.",
    )
    return parser.parse_args(argv)


def _run(cmd, cwd=None, dry_run=False):
    print("+", " ".join(str(c) for c in cmd))
    if dry_run:
        return None
    proc = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def ensure_venv(venv_dir, dry_run=False):
    venv_dir = Path(venv_dir)
    if (venv_dir / "bin" / "python").exists():
        print(f"venv exists, reusing: {venv_dir}")
        return venv_dir / "bin" / "python"
    # Prefer `uv venv` when available: some system pythons ship
    # without pip bootstrap or with relocated stdlib layouts that
    # `python -m venv` cannot reproduce. Fall back to stdlib venv.
    uv = shutil.which("uv")
    if uv is not None:
        _run([uv, "venv", str(venv_dir)], dry_run=dry_run)
        return venv_dir / "bin" / "python"
    try:
        _run([sys.executable, "-m", "venv", str(venv_dir)],
             dry_run=dry_run)
    except SystemExit:
        # Debian-style pythons ship without pip bootstrap; retry
        # without pip and install through uv when available.
        print("venv pip bootstrap unavailable; retrying --without-pip")
        _run([sys.executable, "-m", "venv", "--without-pip",
              str(venv_dir)], dry_run=dry_run)
    return venv_dir / "bin" / "python"


def _has_venv_pip(venv_python, dry_run=False):
    if dry_run:
        return True
    proc = subprocess.run(
        [str(venv_python), "-m", "pip", "--version"],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def pip_install(venv_python, span_repo, dry_run=False):
    if _has_venv_pip(venv_python, dry_run):
        _run(
            [str(venv_python), "-m", "pip", "install", str(span_repo)],
            dry_run=dry_run,
        )
        return
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit(
            "venv has no pip and no `uv` on PATH; install pip or uv, "
            "then re-run."
        )
    _run(
        [uv, "pip", "install", "--python", str(venv_python),
         str(span_repo)],
        dry_run=dry_run,
    )


def expose_binary(venv_dir, bin_dir, dry_run=False):
    for name in ("span-mcp", "span-hooks"):
        src = Path(venv_dir) / "bin" / name
        dst = Path(bin_dir) / name
        print(f"+ link {dst} -> {src}")
        if dry_run:
            continue
        Path(bin_dir).mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(src)
    resolved = shutil.which("span-mcp")
    print(f"span-mcp resolves to: {resolved}")
    return Path(bin_dir) / "span-mcp"


def check_graft_index(target, build=False, dry_run=False):
    wiring = Path(target) / "graft" / ".graph" / "wiring.json"
    if wiring.exists():
        print(f"structural index present: {wiring}")
        return
    if not build:
        raise SystemExit(
            f"missing structural index: {wiring}. "
            "Re-run with --build-index to consent to `graft build` "
            "inside the target (writes graft/.graph there)."
        )
    _run(["graft", "build"], cwd=str(target), dry_run=dry_run)


def load_seeds(path, dry_run=False):
    if path is None:
        return []
    print(f"+ read authority seeds: {path}")
    if dry_run:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read seeds file {path}: {exc}")
    if not isinstance(data, list):
        raise SystemExit(f"seeds file must hold a JSON list: {path}")
    return data


def merge_opencode_config(config_path, span_cmd, dry_run=False):
    print(f"+ merge opencode config: {config_path}")
    if dry_run:
        return
    path = Path(config_path)
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    entry = {
        "type": "local",
        "command": span_cmd,
        "enabled": True,
    }
    mcp = config.setdefault("mcp", {})
    for key in ("span",):
        slot = mcp.get(key)
        if isinstance(slot, dict):
            slot["command"] = span_cmd
            slot["enabled"] = True
        else:
            mcp[key] = dict(entry)
    servers = mcp.get("servers")
    if isinstance(servers, dict) and "span" in servers:
        slot = servers["span"]
        if isinstance(slot, dict):
            slot["command"] = span_cmd
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode config updated: {config_path}")


def register_codex(span_cmd, dry_run=False):
    if shutil.which("codex") is None:
        print("codex CLI absent; skipping codex registration.")
        return
    try:
        _run(["codex", "mcp", "add", "span", "--"] + span_cmd,
             dry_run=dry_run)
    except SystemExit as exc:
        # The local Codex config itself can be broken (e.g. an
        # invalid service_tier); that error is outside Span. Warn
        # and continue instead of aborting the install.
        print(f"codex registration failed, continuing: {exc}")


def _hook_bin(venv_dir, bin_dir):
    direct = Path(bin_dir) / "span-hooks"
    if direct.exists():
        return str(direct)
    fallback = Path(venv_dir) / "bin" / "span-hooks"
    return str(fallback)


def wire_codex_hooks(hook_bin, dry_run=False):
    """Append report-only span entries to the user's codex hooks."""
    hooks_path = Path(os.path.expanduser("~")) / ".codex" / "hooks.json"
    print(f"+ wire codex hooks: {hooks_path}")
    if dry_run:
        return
    if not hooks_path.exists():
        print("no codex hooks.json; skipping codex hook wiring.")
        return
    try:
        config = json.loads(hooks_path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse codex hooks.json: {exc}")
    backup = hooks_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(hooks_path, backup)
        print(f"codex hooks backed up: {backup}")
    entries = [
        ("SessionStart", "startup|resume|compact",
         [hook_bin, "session-start"]),
        ("PostToolUse", "apply_patch|Write|Edit|MultiEdit",
         [hook_bin, "source-changed"]),
        ("Stop", "", [hook_bin, "session-stop"]),
    ]
    added = 0
    hooks = config.setdefault("hooks", {})
    for event, matcher, cmd in entries:
        command = " ".join(cmd)
        group = hooks.setdefault(event, [])
        duplicate = any(
            block.get("matcher", "") == matcher
            and any(
                h.get("command", "") == command
                for h in block.get("hooks", [])
            )
            for block in group
        )
        if duplicate:
            continue
        group.append({
            "matcher": matcher,
            "hooks": [{
                "type": "command",
                "command": command,
                "timeout": 10,
                "statusMessage": "Span lifecycle notice",
            }],
        })
        added += 1
    hooks_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"codex hooks updated ({added} entries).")


def wire_opencode_plugin(span_repo, project_dir, dry_run=False):
    """Deploy the report-only span plugin into a project .opencode."""
    src = Path(span_repo) / "integrations" / "hosts" / "opencode" / \
        "span-hooks.js"
    dst_dir = Path(project_dir) / ".opencode" / "plugins"
    print(f"+ deploy opencode plugin: {dst_dir / 'span-hooks.js'}")
    if dry_run:
        return
    if not src.exists():
        raise SystemExit(f"plugin source missing: {src}")
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "span-hooks.js"
    dst.write_text(src.read_text())
    print(f"opencode plugin deployed: {dst}")


def write_receipt(data_dir, payload, dry_run=False):
    receipt = Path(data_dir) / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def git_rev(span_repo):
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(span_repo),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip()


def verify_installation(venv_python, data_dir, repos, dry_run=False):
    """Provision + readiness + one explain round-trip via a helper
    module executed under the installed interpreter."""
    cmd = [
        str(venv_python), "-m", "span.shell.install_verify",
        "--data-dir", str(data_dir),
    ]
    for repo in repos:
        cmd += ["--repo", str(repo)]
    out = _run(cmd, dry_run=dry_run)
    if dry_run:
        return {"dry_run": True}
    try:
        return json.loads(out)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"verify step returned non-JSON output: {exc}")


def detect_hosts():
    """Detect supported agent hosts without changing anything."""
    hosts = {"opencode": True}  # MCP config merge is file-local.
    hosts["codex"] = shutil.which("codex") is not None or (
        Path(os.path.expanduser("~")) / ".codex"
    ).exists()
    return hosts


def deploy_skills(span_repo, dry_run=False):
    """Copy span skills into each detected host's skills directory.

    Skill directories are copied whole as opaque artifacts; content
    is never parsed or used for decisions here (implementation
    ignores skills as semantic authority). A `.span-origin.json`
    beside each skill records the source rev so doctor can detect
    drift. Nothing is merged into host-owned files.
    """
    import shutil as _shutil

    skills_root = Path(span_repo) / "skills"
    if not skills_root.is_dir():
        print(f"no skills directory in {span_repo}; skipping.")
        return []
    names = sorted(p.name for p in skills_root.iterdir() if p.is_dir())
    if not names:
        print("no skills found; skipping.")
        return []
    home = Path(os.path.expanduser("~"))
    destinations = [
        home / ".config" / "opencode" / "skills",
        home / ".codex" / "skills",
    ]
    deployed = []
    try:
        rev_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(span_repo),
            capture_output=True, text=True,
        )
        rev = rev_proc.stdout.strip() if rev_proc.returncode == 0 else "unknown"
    except OSError:
        rev = "unknown"
    for dest_root in destinations:
        if not dest_root.exists():
            print(f"host skills dir absent, skipping: {dest_root}")
            continue
        for name in names:
            src = skills_root / name
            dst_dir = dest_root / name
            print(f"+ deploy skill {name} -> {dst_dir}")
            if dry_run:
                continue
            shutil.copytree(src, dst_dir, dirs_exist_ok=True)
            (dst_dir / ".span-origin.json").write_text(json.dumps(
                {
                    "skill": name,
                    "span_repo": str(span_repo),
                    "span_rev": rev,
                    "installed_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                },
                indent=2, sort_keys=True,
            ) + "\n")
            deployed.append(str(dst_dir))
    return deployed


def check_skills(dry_run=False):
    """Doctor helper: report deployed skills and origin drift."""
    home = Path(os.path.expanduser("~"))
    for dest_root in (
        home / ".config" / "opencode" / "skills",
        home / ".codex" / "skills",
    ):
        if not dest_root.is_dir():
            continue
        for skill_dir in sorted(dest_root.iterdir()):
            origin = skill_dir / ".span-origin.json"
            if not origin.exists() or dry_run:
                continue
            try:
                record = json.loads(origin.read_text())
            except ValueError:
                print(f"skills: {skill_dir} has unreadable origin.")
                continue
            print(
                f"skills: {skill_dir} from "
                f"{record.get('span_repo')} rev {record.get('span_rev')}"
            )


def doctor(venv_python, data_dir, repos, opencode_config, dry_run=False):
    """Re-verify an existing installation without changing anything."""
    print("== span install doctor ==")
    resolved = shutil.which("span-mcp")
    print(f"span-mcp on PATH: {resolved}")
    if resolved is None and not dry_run:
        raise SystemExit("span-mcp not found on PATH")
    receipt_path = Path(data_dir) / "install.json"
    if receipt_path.exists() and not dry_run:
        print(f"receipt: {receipt_path.read_text().strip()[:400]}")
    else:
        print(f"no receipt at: {receipt_path}")
    check_skills(dry_run=dry_run)
    return verify_installation(venv_python, data_dir, repos, dry_run)


def main(argv=None):
    args = parse_args(argv)
    paths = platform_paths()
    venv_dir = Path(args.venv_dir) if args.venv_dir else paths["venv_dir"]
    data_dir = Path(args.data_dir) if args.data_dir else paths["data_dir"]
    bin_dir = Path(args.bin_dir) if args.bin_dir else paths["bin_dir"]
    span_repo = Path(args.span_repo).resolve()
    targets = [Path(r).resolve() for r in args.repo]
    dry = args.dry_run

    for target in targets:
        if str(data_dir).startswith(str(target) + os.sep) or data_dir == target:
            raise SystemExit(
                f"data dir must live outside every target repo: {data_dir}"
            )

    if args.verify_only:
        venv_python = venv_dir / "bin" / "python"
        return doctor(
            venv_python, data_dir, targets,
            args.opencode_config, dry,
        )

    check_prereqs()
    for target in targets:
        check_graft_index(target, build=args.build_index, dry_run=dry)
    venv_python = ensure_venv(venv_dir, dry_run=dry)
    pip_install(venv_python, span_repo, dry_run=dry)
    expose_binary(venv_dir, bin_dir, dry_run=dry)
    seeds = load_seeds(args.authority_seeds_file, dry_run=dry)
    if seeds:
        print(f"loaded {len(seeds)} authority seeds (validated at init)")

    data_cmd = ["--data-dir", str(data_dir)]
    resolved_mcp = shutil.which("span-mcp")
    if resolved_mcp is None:
        # Not yet on PATH in this process; the server entry needs an
        # absolute path, so resolve the just-linked binary directly.
        resolved_mcp = str(Path(bin_dir) / "span-mcp")
    span_cmd = [resolved_mcp] + data_cmd
    for target in targets:
        span_cmd += ["--repo", f"graft:{target}"]
    opencode_config = args.opencode_config
    if opencode_config is None and Path("opencode.json").exists():
        opencode_config = "opencode.json"
    if opencode_config is not None:
        merge_opencode_config(opencode_config, span_cmd, dry_run=dry)
    else:
        print("no opencode.json found; skipping host registration "
              "(pass --opencode-config PATH).")
    if args.with_codex is None:
        args.with_codex = detect_hosts()["codex"] and not args.no_codex
    elif args.no_codex:
        args.with_codex = False
    if args.with_hooks is None:
        args.with_hooks = not args.no_hooks
    if args.with_codex:
        register_codex(span_cmd, dry_run=dry)
    if args.with_hooks:
        hook_bin = _hook_bin(venv_dir, bin_dir)
        wire_codex_hooks(hook_bin, dry_run=dry)
        for target in targets:
            wire_opencode_plugin(span_repo, target, dry_run=dry)
    if not args.no_skills:
        deploy_skills(span_repo, dry_run=dry)

    report = verify_installation(venv_python, data_dir, targets, dry)
    receipt = {
        "install_version": INSTALL_VERSION,
        "span_repo": str(span_repo),
        "span_rev": git_rev(span_repo) if not dry else "dry-run",
        "venv_dir": str(venv_dir),
        "data_dir": str(data_dir),
        "repos": [str(t) for t in targets],
        "verify": report,
        "installed_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
    }
    write_receipt(data_dir, receipt, dry_run=dry)
    print("install complete.")
    return receipt


if __name__ == "__main__":
    main()
