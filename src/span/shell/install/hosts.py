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


def deploy_opencode_plugin(
    plugin_source,
    plugin_dir,
    config_path,
    hook_bin,
    data_dir,
    dry_run=False,
):
    """Deploy the FD-58 notice plugin outside any target and register it.

    The plugin lives under Span's own data root; the host configuration gains
    one ``plugins`` entry. No target repository is written. The wrapper beside
    the plugin pins the hook binary and data directory, so the plugin does not
    depend on PATH.
    """
    print(f"+ deploy opencode plugin: {plugin_dir}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    source = Path(plugin_source)
    if not source.is_file():
        raise SystemExit(f"opencode plugin source missing: {source}")
    target_dir = Path(plugin_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target_dir / "index.js")
    wrapper = target_dir / "span-hooks"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{hook_bin}" --data-dir "{data_dir}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    path = Path(config_path)
    config: dict[str, object] = {}
    if path.is_file():
        try:
            config = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    plugins = config.get("plugins")
    if not isinstance(plugins, list):
        plugins = []
    entry = str(target_dir)
    if entry not in plugins:
        plugins.append(entry)
    config["plugins"] = plugins
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode plugin registered: {path}")
    return {"status": "wired", "plugin": str(target_dir), "config": str(path)}


def remove_opencode_plugin(config_path, plugin_dir, dry_run=False):
    """Remove the FD-58 plugin directory and its one ``plugins`` entry.

    Foreign plugins and every other configuration key are preserved. A missing
    entry or directory is already uninstalled.
    """
    print(f"+ remove opencode plugin: {plugin_dir}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    path = Path(config_path)
    entry = str(Path(plugin_dir))
    removed_entry = False
    if path.is_file():
        try:
            config = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
        plugins = config.get("plugins")
        if isinstance(plugins, list) and entry in plugins:
            config["plugins"] = [item for item in plugins if item != entry]
            path.write_text(json.dumps(config, indent=2) + "\n")
            removed_entry = True
    directory = Path(plugin_dir)
    removed_dir = False
    if directory.is_dir():
        shutil.rmtree(directory)
        removed_dir = True
    return {
        "status": "removed" if (removed_entry or removed_dir) else "absent",
        "config": str(path),
        "plugin": str(directory),
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
