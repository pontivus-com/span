"""Operational readiness verification (stdlib only)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from span.shell.install.host_inspect import (
    inspect_claude_registration,
    inspect_codex_registration,
    inspect_opencode_plugin_state,
    inspect_opencode_registration,
)
from span.shell.install.hosts import (
    _same_path,
    opencode_global_config_path,
    receipt_opencode_mcp_config,
    receipt_opencode_scope,
)
from span.shell.install.paths import (
    expected_span_command,
)
from span.shell.install.receipt import (
    read_receipt,
)
from span.shell.install.skills import (
    check_skills,
)
from span.shell.install.venv import (
    _run,
)


def verify_installation(venv_python, data_dir, repos, dry_run=False):
    """Observational readiness via a helper module under the installed interpreter.

    Never initializes, migrates, rebuilds or invokes a semantic operation.
    An absent or old store reports the explicit setup/transition action.
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


def _opencode_plugin_report(scope, state, canonical_dir) -> dict[str, object]:
    """The doctor's limited plugin verdict: duplicate, mismatch, unknown, absent."""
    entries = state["entries"]
    unreadable = state["unreadable"]
    if unreadable:
        return {
            "scope": scope,
            "status": "unreadable",
            "reason": "; ".join(
                str(item.get("reason", "unreadable")) for item in unreadable
            ),
            "observed": [item.get("path") for item in entries],
        }
    user = [item for item in entries if item["artifact"] in ("global-user", "target")]
    managed = [item for item in entries if item["artifact"] == "global-managed"]
    stale_managed = [
        item for item in managed if not _same_path(item["path"], canonical_dir)
    ]
    if scope is None:
        return {
            "scope": None,
            "status": "scope_unknown",
            "reason": (
                "the install receipt records no OpenCode plugin scope; rerun "
                "span-install --opencode-plugin-scope global|local|none"
            ),
            "observed": [item["path"] for item in entries],
        }
    if scope == "global":
        duplicates = [*stale_managed, *user]
        if duplicates:
            return {
                "scope": scope,
                "status": "conflict",
                "reason": (
                    "Span-owned plugin outside the canonical global registration"
                ),
                "observed": [item["path"] for item in duplicates],
            }
        return {"scope": scope, "status": "wired", "observed": []}
    global_present = bool(managed) or bool(state.get("canonical_exists"))
    if global_present:
        return {
            "scope": scope,
            "status": "conflict",
            "reason": (
                "scope mismatch: a Span-managed global plugin remains while the "
                f"configured scope is {scope}"
            ),
            "observed": [
                *[item["path"] for item in managed],
                *([str(canonical_dir)] if state.get("canonical_exists") else []),
            ],
        }
    if len(user) > 1:
        return {
            "scope": scope,
            "status": "conflict",
            "reason": ("more than one user-managed Span plugin declares span-hooks"),
            "observed": [item["path"] for item in user],
        }
    if scope == "local":
        status = "external" if user else "absent"
    else:
        status = "external" if user else "disabled"
    return {
        "scope": scope,
        "status": status,
        "observed": [item["path"] for item in user],
    }


def doctor(venv_python, data_dir, repos, opencode_config, dry_run=False):
    """Re-verify an existing installation without changing anything."""
    print("== span install doctor ==")
    resolved = shutil.which("span-mcp")
    print(f"span-mcp on PATH: {resolved}")
    if resolved is None and not dry_run:
        raise SystemExit("span-mcp not found on PATH")
    receipt_path = Path(data_dir) / "install.json"
    receipt = read_receipt(data_dir) or {}
    receipt_targets = tuple(
        Path(repo) for repo in receipt.get("repos", []) if isinstance(repo, str)
    )
    effective_repos = tuple(repos) or receipt_targets
    if receipt_path.exists() and not dry_run:
        print(f"receipt: {receipt_path}")
    else:
        print(f"no receipt at: {receipt_path}")
    check_skills(dry_run=dry_run)
    # Read-only host-registration inspection: file inspection only, no
    # MCP registry/process enumeration and no host configuration writes.
    selected_config = opencode_config or receipt_opencode_mcp_config(receipt)
    if selected_config is None and Path("opencode.json").exists():
        selected_config = "opencode.json"
    opencode_state = inspect_opencode_registration(
        selected_config,
        expected_span_command(
            resolved if resolved is not None else "span-mcp",
            data_dir,
            effective_repos,
            host="opencode",
        ),
    )
    codex_state = inspect_codex_registration()
    claude_state = inspect_claude_registration(
        expected_span_command(
            resolved if resolved is not None else "span-mcp",
            data_dir,
            repos,
        )
    )
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
    inspection_targets = tuple(dict.fromkeys([*effective_repos, *receipt_targets]))
    span_root = Path(data_dir).parent
    canonical_dir = span_root / "opencode-plugin"
    plugin_config = opencode_global_config_path()
    configs = tuple(
        dict.fromkeys(
            str(path) for path in (selected_config, plugin_config) if path is not None
        )
    )
    states = [
        inspect_opencode_plugin_state(
            path, span_root, canonical_dir, inspection_targets
        )
        for path in configs
    ]
    plugin_state = {
        "entries": [item for state in states for item in state["entries"]],
        "unreadable": [item for state in states for item in state["unreadable"]],
        "canonical_exists": Path(canonical_dir).is_dir(),
    }
    scope = receipt_opencode_scope(receipt) if receipt else None
    plugin_report = _opencode_plugin_report(scope, plugin_state, canonical_dir)
    print(f"opencode plugin scope: {scope if scope is not None else 'unknown'}")
    print(f"opencode plugin: {plugin_report['status']}")
    if plugin_report.get("reason"):
        print(f"  {plugin_report['reason']}")
    report = verify_installation(venv_python, data_dir, effective_repos, dry_run)
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
        "opencode_plugin": plugin_report,
        "codex_registration": codex_state,
        "claude_registration": claude_state,
    }
