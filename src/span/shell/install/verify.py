"""Operational readiness verification (stdlib only)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from span.shell.install.host_inspect import (
    inspect_claude_registration,
    inspect_codex_registration,
    inspect_opencode_registration,
)
from span.shell.install.paths import (
    expected_span_command,
)
from span.shell.install.skills import (
    check_skills,
)
from span.shell.install.venv import (
    _run,
)


def verify_installation(venv_python, data_dir, repos, dry_run=False):
    """Provision + readiness via a helper module executed under the installed interpreter.

    Operational readiness only (A1): sequential per-target provisioning
    with the settled READY predicate. Never invokes ``explain`` and never
    establishes semantic knowledge.
    """
    cmd = [
        str(venv_python),
        "-m",
        "span.shell.install_verify",
        "--data-dir",
        str(data_dir),
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


def doctor(venv_python, data_dir, repos, opencode_config, dry_run=False):
    """Re-verify an existing installation without changing anything."""
    print("== span install doctor ==")
    resolved = shutil.which("span-mcp")
    print(f"span-mcp on PATH: {resolved}")
    if resolved is None and not dry_run:
        raise SystemExit("span-mcp not found on PATH")
    receipt_path = Path(data_dir) / "install.json"
    if receipt_path.exists() and not dry_run:
        print(f"receipt: {receipt_path}")
    else:
        print(f"no receipt at: {receipt_path}")
    check_skills(dry_run=dry_run)
    # Read-only host-registration inspection: file inspection only, no
    # MCP registry/process enumeration and no host configuration writes.
    selected_config = opencode_config
    if selected_config is None and Path("opencode.json").exists():
        selected_config = "opencode.json"
    span_cmd = expected_span_command(
        resolved if resolved is not None else "span-mcp", data_dir, repos
    )
    opencode_state = inspect_opencode_registration(selected_config, span_cmd)
    codex_state = inspect_codex_registration()
    claude_state = inspect_claude_registration(span_cmd)
    print(f"opencode registration: {opencode_state['status']}")
    if opencode_state.get("reason"):
        print(f"  {opencode_state['reason']}")
    print(
        f"codex registration: {codex_state['status']} "
        f"({codex_state.get('reason', '')})"
    )
    print(
        f"claude registration: {claude_state['status']} "
        f"({claude_state.get('config', '')})"
    )
    report = verify_installation(venv_python, data_dir, repos, dry_run)
    print(f"runtime verification: span-mcp={resolved}")
    readiness = report.get("repos", []) if isinstance(report, dict) else []
    print(f"repository store_readiness: {readiness}")
    return {
        "runtime_verification": {
            "span_mcp": resolved,
            "dry_run": bool(dry_run),
        },
        "store_readiness": report,
        "opencode_registration": opencode_state,
        "codex_registration": codex_state,
        "claude_registration": claude_state,
    }
