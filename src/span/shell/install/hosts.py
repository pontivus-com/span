"""Host MCP registration and lifecycle hook wiring (stdlib only)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from span.shell.install.venv import (
    _run,
)


def merge_opencode_config(config_path, span_cmd, dry_run=False):
    """Write the one supported OpenCode V2 Span registration.

    The only supported contract is ``mcp.servers.span`` with
    ``type: local``, the installed command, ``codemode: false``, and
    ``disabled`` absent or false. An unsupported flat ``mcp.span``
    registration is rejected, never migrated; the operator removes it
    and reruns. Unknown MCP entries are left untouched: Span owns only
    its own registration and performs no cross-server cleanup.
    """
    print(f"+ merge opencode config: {config_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    path = Path(config_path)
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    mcp = config.setdefault("mcp", {})
    servers = mcp.get("servers")
    if not isinstance(servers, dict):
        servers = {}
    if isinstance(mcp.get("span"), dict):
        raise SystemExit(
            f"unsupported flat mcp.span registration in {config_path}; "
            "remove it and register Span under mcp.servers.span"
        )
    servers["span"] = {
        "type": "local",
        "command": list(span_cmd),
        "codemode": False,
    }
    mcp["servers"] = servers
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode config updated: {config_path}")
    return {
        "status": "merged",
        "config": str(config_path),
    }


def remove_opencode_registration(config_path, dry_run=False):
    """Remove only Span's own ``mcp.servers.span`` registration.

    Foreign servers and every other key are preserved. A file without the
    entry is already uninstalled, so the operation is idempotent and never
    rewrites unrelated configuration.
    """
    print(f"+ remove opencode registration: {config_path}")
    path = Path(config_path)
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not path.is_file():
        return {"status": "absent", "config": str(path)}
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    mcp = config.get("mcp")
    servers = mcp.get("servers") if isinstance(mcp, dict) else None
    if not isinstance(servers, dict) or "span" not in servers:
        return {"status": "absent", "config": str(path)}
    servers.pop("span")
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode registration removed: {path}")
    return {"status": "removed", "config": str(path)}


def register_codex(span_cmd, dry_run=False):
    if shutil.which("codex") is None:
        print("codex CLI absent; skipping codex registration.")
        return {"status": "skipped", "reason": "codex CLI absent"}
    if dry_run:
        print("+ register codex (dry-run, skipped)")
        return {"status": "skipped", "reason": "dry-run"}
    try:
        _run(["codex", "mcp", "add", "span", "--"] + span_cmd, dry_run=dry_run)
    except SystemExit as exc:
        # The local Codex config itself can be broken (e.g. an
        # invalid service_tier); that error is outside Span. Warn
        # and continue instead of aborting the install.
        print(f"codex registration failed, continuing: {exc}")
        return {"status": "failed", "error": str(exc)}
    return {"status": "registered"}


def register_claude(span_cmd, dry_run=False):
    """Register Span with Claude Code at user scope.

    Claude Code owns its registration format, so the supported surface is
    its CLI rather than a config file Span writes itself. User scope makes
    the server available in every project instead of binding it to the
    directory the installer happened to run in.

    Span owns the ``span`` entry, so an existing one is removed before it
    is re-added: that is convergence on the exact command, and it never
    touches another server.
    """
    if shutil.which("claude") is None:
        print("claude CLI absent; skipping claude registration.")
        return {"status": "skipped", "reason": "claude CLI absent"}
    if dry_run:
        print("+ register claude (dry-run, skipped)")
        return {"status": "skipped", "reason": "dry-run"}
    # Absent entry is the normal first-install case; a non-zero exit
    # here is expected and carries no signal.
    subprocess.run(
        ["claude", "mcp", "remove", "span", "--scope", "user"],
        capture_output=True,
        text=True,
    )
    try:
        _run(
            [
                "claude",
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "stdio",
                "span",
                "--",
            ]
            + span_cmd,
            dry_run=dry_run,
        )
    except SystemExit as exc:
        # A broken Claude configuration is outside Span: warn and
        # continue instead of aborting the whole install.
        print(f"claude registration failed, continuing: {exc}")
        return {"status": "failed", "error": str(exc)}
    return {"status": "registered", "scope": "user"}


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
        return {"status": "skipped", "reason": "dry-run"}
    if not hooks_path.exists():
        print("no codex hooks.json; skipping codex hook wiring.")
        return {"status": "skipped", "reason": "no codex hooks.json"}
    try:
        config = json.loads(hooks_path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse codex hooks.json: {exc}")
    backup = hooks_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(hooks_path, backup)
        print(f"codex hooks backed up: {backup}")
    entries = [
        ("SessionStart", "startup|resume|compact", [hook_bin, "session-start"]),
        (
            "PostToolUse",
            "apply_patch|Write|Edit|MultiEdit",
            [hook_bin, "source-changed"],
        ),
        ("Stop", "", [hook_bin, "session-stop"]),
    ]
    added = 0
    hooks = config.setdefault("hooks", {})
    for event, matcher, cmd in entries:
        command = " ".join(cmd)
        group = hooks.setdefault(event, [])
        duplicate = any(
            block.get("matcher", "") == matcher
            and any(h.get("command", "") == command for h in block.get("hooks", []))
            for block in group
        )
        if duplicate:
            continue
        group.append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "statusMessage": "Span lifecycle notice",
                    }
                ],
            }
        )
        added += 1
    hooks_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"codex hooks updated ({added} entries).")
    return {"status": "wired", "added": added}


def wire_claude_hooks(hook_bin, data_dir, dry_run=False):
    """Append report-only span entries to Claude Code's user settings.

    Uses the same three lifecycle events the Claude-style adapter maps:
    ``SessionStart``, post-edit ``PostToolUse``, and ``Stop``. Only the
    ``hooks`` key is touched; every other setting and every foreign hook
    entry is preserved, and the file is backed up before the first write.

    ``--data-dir`` is part of every command: without it the runner falls
    back to the platform default and would inspect a different store than
    the one this install registered.
    """
    settings_path = Path(os.path.expanduser("~")) / ".claude" / "settings.json"
    print(f"+ wire claude hooks: {settings_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not settings_path.exists():
        print("no claude settings.json; skipping claude hook wiring.")
        return {"status": "skipped", "reason": "no claude settings.json"}
    try:
        config = json.loads(settings_path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse claude settings.json: {exc}")
    backup = settings_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(settings_path, backup)
        print(f"claude settings backed up: {backup}")
    entries = [
        (
            "SessionStart",
            "startup|resume|compact",
            [hook_bin, "session-start", "--data-dir", str(data_dir)],
        ),
        (
            "PostToolUse",
            "Write|Edit|MultiEdit",
            [hook_bin, "source-changed", "--data-dir", str(data_dir)],
        ),
        ("Stop", "", [hook_bin, "session-stop", "--data-dir", str(data_dir)]),
    ]
    added = 0
    hooks = config.setdefault("hooks", {})
    for event, matcher, cmd in entries:
        command = " ".join(cmd)
        group = hooks.setdefault(event, [])
        # Span owns every command that invokes this hook binary, so an
        # older Span entry is replaced instead of accumulating beside the
        # new one. Foreign commands and foreign matchers are untouched.
        kept_blocks = []
        for block in group:
            block_hooks = block.get("hooks", [])
            kept = [
                hook
                for hook in block_hooks
                if str(hook.get("command", "")).split()[:1] != [hook_bin]
            ]
            if kept:
                block = {**block, "hooks": kept}
                kept_blocks.append(block)
        group[:] = kept_blocks
        duplicate = any(
            block.get("matcher", "") == matcher
            and any(h.get("command", "") == command for h in block.get("hooks", []))
            for block in group
        )
        if duplicate:
            continue
        group.append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "statusMessage": "Span lifecycle notice",
                    }
                ],
            }
        )
        added += 1
    settings_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"claude hooks updated ({added} entries).")
    return {"status": "wired", "added": added}


def remove_codex_registration(dry_run=False):
    """Remove the Span entry through the Codex CLI when it is present."""
    if shutil.which("codex") is None:
        return {"status": "absent", "reason": "codex CLI absent"}
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    proc = subprocess.run(
        ["codex", "mcp", "remove", "span"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        # An absent entry is the normal already-uninstalled case.
        return {"status": "absent"}
    return {"status": "removed"}


def remove_claude_registration(dry_run=False):
    """Remove the Span entry through the Claude Code CLI when present."""
    if shutil.which("claude") is None:
        return {"status": "absent", "reason": "claude CLI absent"}
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    proc = subprocess.run(
        ["claude", "mcp", "remove", "span", "--scope", "user"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"status": "absent"}
    return {"status": "removed"}


def _span_hook_command(command: object) -> bool:
    """True for a command that invokes the Span hook binary."""
    if not isinstance(command, str) or not command.strip():
        return False
    executable = command.split()[0]
    return Path(executable).name == "span-hooks"


def _remove_span_hooks(path, dry_run=False):
    """Strip Span hook entries from one host configuration file.

    Span owns every command invoking the hook binary; foreign hooks,
    matchers, and unrelated settings are preserved. An empty event or
    ``hooks`` map is removed so a pre-install shape is restored.
    """
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not path.is_file():
        return {"status": "absent"}
    try:
        config = json.loads(path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse {path}: {exc}")
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return {"status": "absent"}
    removed = 0
    for event in list(hooks):
        group = hooks.get(event)
        if not isinstance(group, list):
            continue
        kept_blocks = []
        for block in group:
            if not isinstance(block, dict):
                kept_blocks.append(block)
                continue
            block_hooks = block.get("hooks", [])
            if not isinstance(block_hooks, list):
                kept_blocks.append(block)
                continue
            kept = [
                hook
                for hook in block_hooks
                if not _span_hook_command(hook.get("command"))
            ]
            removed += len(block_hooks) - len(kept)
            if kept:
                kept_blocks.append({**block, "hooks": kept})
        if kept_blocks:
            hooks[event] = kept_blocks
        else:
            hooks.pop(event)
    if not hooks:
        config.pop("hooks", None)
    if not removed:
        return {"status": "absent"}
    path.write_text(json.dumps(config, indent=2) + "\n")
    backup = path.with_suffix(".json.bak-span")
    if backup.exists():
        backup.unlink()
    print(f"span hooks removed from {path} ({removed} entries).")
    return {"status": "removed", "removed": removed}


def remove_codex_hooks(dry_run=False):
    return _remove_span_hooks(
        Path(os.path.expanduser("~")) / ".codex" / "hooks.json", dry_run=dry_run
    )


def remove_claude_hooks(dry_run=False):
    return _remove_span_hooks(
        Path(os.path.expanduser("~")) / ".claude" / "settings.json",
        dry_run=dry_run,
    )
