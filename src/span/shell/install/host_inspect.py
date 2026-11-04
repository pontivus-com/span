"""Read-only host registration inspection (stdlib only)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from span.shell.install.hosts import (
    _is_span_managed_entry,
    _span_plugin_file,
    inspect_target_opencode_plugins,
)


def detect_hosts():
    """Detect supported agent hosts without changing anything."""
    hosts = {"opencode": True}  # MCP config merge is file-local.
    home = Path(os.path.expanduser("~"))
    hosts["codex"] = shutil.which("codex") is not None or (home / ".codex").exists()
    return hosts


def inspect_opencode_registration(config_path, span_cmd):
    """Read-only OpenCode ``mcp.servers.span`` registration inspection.

    Returns exactly one of ``matched``, ``mismatched``, ``missing``, or
    ``unreadable``. Never calls ``merge_opencode_config`` and never
    writes the config. A missing config path means no OpenCode config is
    available; an explicitly supplied but unreadable path is reported as
    unreadable rather than guessed.
    """
    expected = list(span_cmd)
    result = {
        "status": "missing",
        "config": None if config_path is None else str(config_path),
        "expected_command": expected,
    }
    if config_path is None:
        result["reason"] = "no OpenCode config available"
        return result
    path = Path(config_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["status"] = "unreadable"
        result["reason"] = f"cannot read OpenCode config: {exc}"
        return result
    try:
        config = json.loads(text)
    except ValueError as exc:
        result["status"] = "unreadable"
        result["reason"] = f"cannot parse OpenCode config: {exc}"
        return result
    mcp = config.get("mcp") if isinstance(config, dict) else None
    servers = mcp.get("servers") if isinstance(mcp, dict) else None
    nested = servers.get("span") if isinstance(servers, dict) else None
    flat = mcp.get("span") if isinstance(mcp, dict) else None
    if isinstance(flat, dict) and isinstance(nested, dict):
        result["status"] = "mismatched"
        result["reason"] = (
            "duplicate Span registrations: both mcp.span and "
            "mcp.servers.span exist; normalize to mcp.servers.span"
        )
        return result
    if isinstance(flat, dict):
        result["status"] = "mismatched"
        result["configured_command"] = flat.get("command")
        result["reason"] = (
            "unsupported flat mcp.span registration; use " "mcp.servers.span"
        )
        return result
    if not isinstance(nested, dict):
        result["reason"] = "no mcp.servers.span entry"
        return result
    result["configured_command"] = nested.get("command")
    if nested.get("type") != "local":
        result["status"] = "mismatched"
        result["reason"] = "mcp.servers.span type must be local"
        return result
    if nested.get("disabled") is True:
        result["status"] = "mismatched"
        result["reason"] = "mcp.servers.span entry is disabled"
        return result
    # OpenCode must expose Span's raw tool schemas; Code Mode wraps them
    # and makes the advertised grammar unusable.
    if nested.get("codemode") is not False:
        result["status"] = "mismatched"
        result["reason"] = (
            "mcp.servers.span entry has Code Mode enabled; codemode " "must be false"
        )
        return result
    if nested.get("command") == expected:
        result["status"] = "matched"
        return result
    result["status"] = "mismatched"
    result["reason"] = (
        "mcp.servers.span command does not match the installed invocation"
    )
    return result


def inspect_opencode_plugin_state(
    config_path, span_root, canonical_dir, targets
) -> dict[str, object]:
    """Read-only discovery of Span-owned plugin artifacts for one scope.

    Only the global configuration's ``plugins`` entries and the explicitly
    named targets' ``.opencode/plugins`` directories are inspected. Retired
    files under ``.opencode/span-retired`` are inert and never listed.
    """
    entries: list[dict[str, str]] = []
    unreadable: list[dict[str, str]] = []
    if config_path is not None:
        path = Path(config_path)
        if path.is_file():
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                unreadable.append(
                    {
                        "artifact": "global-config",
                        "path": str(path),
                        "reason": f"cannot read OpenCode config: {exc}",
                    }
                )
                config = {}
            plugins = config.get("plugins") if isinstance(config, dict) else None
            if isinstance(plugins, list):
                for item in plugins:
                    if not isinstance(item, str):
                        continue
                    if _is_span_managed_entry(item, canonical_dir, span_root):
                        entries.append({"artifact": "global-managed", "path": item})
                    elif _span_plugin_file(item) is not None:
                        entries.append({"artifact": "global-user", "path": item})
    targets_state, target_unreadable = inspect_target_opencode_plugins(targets)
    for target, found in targets_state.items():
        entries.extend(
            {
                "artifact": "target",
                "target": target,
                "path": item["path"],
                "sha256": item["sha256"],
            }
            for item in found
        )
    unreadable.extend(target_unreadable)
    return {
        "entries": entries,
        "unreadable": unreadable,
        "canonical": str(canonical_dir),
        "canonical_exists": Path(canonical_dir).is_dir(),
    }


def inspect_codex_registration():
    """Report Codex registration observability honestly.

    The repository establishes no stable Codex MCP configuration-file
    contract, so this read-only check never inspects or executes the
    Codex CLI: detection reports ``manual``, absence reports
    ``skipped``.
    """
    if detect_hosts()["codex"]:
        return {
            "status": "manual",
            "reason": (
                "installer receipt may record prior registration, but "
                "current Codex MCP registration is not deterministically "
                "inspectable by Span's read-only contract"
            ),
        }
    return {"status": "skipped", "reason": "codex CLI not detected"}
