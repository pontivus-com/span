"""Read-only host registration inspection (stdlib only)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def detect_hosts():
    """Detect supported agent hosts without changing anything."""
    hosts = {"opencode": True}  # MCP config merge is file-local.
    home = Path(os.path.expanduser("~"))
    hosts["codex"] = shutil.which("codex") is not None or (home / ".codex").exists()
    hosts["claude"] = (
        shutil.which("claude") is not None
        or (home / ".claude").exists()
        or (home / ".claude.json").exists()
    )
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


def inspect_claude_registration(span_cmd):
    """Read-only inspection of Claude Code's user-scope MCP entry.

    ``~/.claude.json`` is the documented user-scope store, so this check
    reads it directly and never runs the CLI. Missing file, missing
    entry, unreadable JSON, and a differing command are reported
    distinctly; nothing is written.
    """
    config_path = Path(os.path.expanduser("~")) / ".claude.json"
    expected = [str(part) for part in span_cmd]
    result = {
        "status": "missing",
        "config": str(config_path),
        "expected_command": expected,
    }
    try:
        raw = config_path.read_text()
    except OSError:
        return result
    try:
        config = json.loads(raw)
    except ValueError:
        result["status"] = "unreadable"
        return result
    servers = config.get("mcpServers")
    entry = servers.get("span") if isinstance(servers, dict) else None
    if not isinstance(entry, dict):
        return result
    actual = [str(entry.get("command", ""))] + [
        str(arg) for arg in entry.get("args", [])
    ]
    result["actual_command"] = actual
    result["status"] = "matched" if actual == expected else "mismatched"
    return result
