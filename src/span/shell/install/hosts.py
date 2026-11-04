"""Host MCP registration and lifecycle hook wiring (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from span.shell.install.venv import (
    _run,
)

#: The plugin id the lifecycle plugin exports. OpenCode rejects a second
#: loaded plugin with the same id, so every Span-owned plugin location must
#: converge on exactly one copy.
SPAN_PLUGIN_ID = "span-hooks"

_SPAN_PLUGIN_ID_PATTERN = re.compile(
    rf"""\bid\s*:\s*['"]{re.escape(SPAN_PLUGIN_ID)}['"]"""
)

#: Explicit OpenCode plugin scopes. The installer never infers one from disk.
OPENCODE_PLUGIN_SCOPES = ("global", "local", "none")


def opencode_global_config_path() -> Path:
    """Return the fixed global OpenCode config used by plugin wiring."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "opencode" / "opencode.json"


def _absolute_path(value: str | Path) -> str:
    """Return a stable, non-resolving absolute path for a receipt."""
    return os.path.abspath(os.path.expanduser(str(value)))


def select_opencode_mcp_config(
    explicit: str | Path | None,
    scope: str | None,
    global_config: str | Path | None = None,
    receipt_config: str | Path | None = None,
) -> str | None:
    """Select and stabilize the MCP config without scanning the machine.

    An existing install owns the configuration recorded by its receipt. An
    explicit path is the only supported way to relocate that ownership.
    """
    if explicit is not None:
        return _absolute_path(explicit)
    if receipt_config is not None:
        return _absolute_path(receipt_config)
    if Path("opencode.json").exists():
        return _absolute_path("opencode.json")
    if scope == "global":
        return _absolute_path(global_config or opencode_global_config_path())
    return None


def _same_path(left, right) -> bool:
    """Compare two configured paths without requiring either to exist."""
    return os.path.abspath(os.path.expanduser(str(left))) == os.path.abspath(
        os.path.expanduser(str(right))
    )


def _is_under(path, root) -> bool:
    """True when ``path`` is ``root`` or a descendant, without resolving links."""
    candidate = os.path.abspath(os.path.expanduser(str(path)))
    base = os.path.abspath(os.path.expanduser(str(root)))
    if base == os.sep:
        return candidate.startswith(os.sep)
    return candidate == base or candidate.startswith(base + os.sep)


def _sha256_file(path) -> str:
    """Content hash of one plugin file for ownership comparison."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _is_span_managed_entry(item, canonical_dir, span_root) -> bool:
    """True when a global plugin entry is Span's own installed registration.

    An entry is provably Span's when it is the canonical directory, declares
    Span's plugin id, or is a stale registration under Span's data root whose
    directory is already gone. A foreign entry is never claimed.
    """
    if _same_path(item, canonical_dir):
        return True
    if not _is_under(item, span_root):
        return False
    if Path(item).name == Path(canonical_dir).name:
        return True
    return _span_plugin_file(item) is not None


def receipt_opencode_scope(receipt) -> str | None:
    """Read the current receipt's sole OpenCode plugin scope."""
    if not isinstance(receipt, dict):
        return None
    registration = receipt.get("host_registration")
    hooks = registration.get("hooks") if isinstance(registration, dict) else None
    plugin = hooks.get("opencode_plugin") if isinstance(hooks, dict) else None
    scope = plugin.get("scope") if isinstance(plugin, dict) else None
    return scope if scope in OPENCODE_PLUGIN_SCOPES else None


def receipt_opencode_mcp_config(receipt: object) -> str | None:
    """Return the stable config recorded for Span's MCP registration, if any."""
    if not isinstance(receipt, dict):
        return None
    registration = receipt.get("host_registration")
    opencode = registration.get("opencode") if isinstance(registration, dict) else None
    config = opencode.get("config") if isinstance(opencode, dict) else None
    if config is None or not os.path.isabs(config):
        return None
    return config


def receipt_opencode_plugin_config(receipt: object) -> str | None:
    """Return the config recorded for Span's lifecycle plugin, if any."""
    if not isinstance(receipt, dict):
        return None
    registration = receipt.get("host_registration")
    hooks = registration.get("hooks") if isinstance(registration, dict) else None
    plugin = hooks.get("opencode_plugin") if isinstance(hooks, dict) else None
    config = plugin.get("config") if isinstance(plugin, dict) else None
    if not isinstance(config, str) or not config or not os.path.isabs(config):
        return None
    return config


def resolve_opencode_scope(flag, receipt) -> tuple[str, str | None]:
    """Resolve the plugin scope: explicit flag, then receipt, else stop.

    A fresh install (no receipt) documents and prints ``global``. An upgrade
    whose receipt records no unambiguous scope stops and names the flag; the
    installer never guesses and never scans the machine.
    """
    receipt_scope = receipt_opencode_scope(receipt)
    if flag is not None:
        if receipt_scope is not None and receipt_scope != flag:
            print(f"opencode plugin scope: {receipt_scope} -> {flag}")
        else:
            print(f"opencode plugin scope: {flag}")
        return flag, receipt_scope
    if receipt is None:
        print("opencode plugin scope: global (default; no receipt)")
        return "global", None
    if receipt_scope is not None:
        print(f"opencode plugin scope: {receipt_scope} (receipt)")
        return receipt_scope, receipt_scope
    raise SystemExit(
        "the install receipt does not record an unambiguous OpenCode plugin "
        "scope; rerun with --opencode-plugin-scope global|local|none. "
        "Nothing was changed."
    )


def _span_plugin_file(candidate) -> Path | None:
    """Return the Span plugin source at ``candidate``, else ``None``.

    A configured plugin entry is either a directory holding ``index.js`` or
    a JavaScript file. Only content that declares Span's plugin id is
    recognised; a foreign plugin is never claimed or removed.
    """
    path = Path(candidate)
    if path.is_dir():
        path = path / "index.js"
    if not path.is_file() or path.suffix != ".js":
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return path if _SPAN_PLUGIN_ID_PATTERN.search(text) else None


def merge_opencode_config(config_path, span_cmd, dry_run=False):
    """Write the one supported OpenCode V2 Span registration.

    The only supported contract is ``mcp.servers.span`` with
    ``type: local``, the installed command, ``codemode: false``, and
    ``disabled`` absent or false. Unknown MCP entries are left untouched: Span owns only
    its own registration and performs no cross-server cleanup.
    """
    print(f"+ merge opencode config: {config_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    path = Path(_absolute_path(config_path))
    try:
        text = path.read_text()
    except FileNotFoundError:
        config = {}
    except OSError as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    else:
        try:
            config = json.loads(text)
        except ValueError as exc:
            raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    mcp = config.setdefault("mcp", {})
    servers = mcp.get("servers")
    if not isinstance(servers, dict):
        servers = {}
    servers["span"] = {
        "type": "local",
        "command": list(span_cmd),
        "codemode": False,
    }
    mcp["servers"] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode config updated: {config_path}")
    return {
        "status": "merged",
        "config": str(path),
    }


def validate_opencode_registration_removal(config_path) -> dict[str, object]:
    """Validate that an old MCP config can be safely removed before a move."""
    path = Path(_absolute_path(config_path))
    if not path.is_file():
        return {"status": "absent", "config": str(path)}
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    if not isinstance(config, dict):
        raise SystemExit(
            f"cannot read opencode config {config_path}: " "top level is not an object"
        )
    mcp = config.get("mcp")
    servers = mcp.get("servers") if isinstance(mcp, dict) else None
    if not isinstance(servers, dict) or "span" not in servers:
        return {"status": "absent", "config": str(path)}
    if not (path.stat().st_mode & 0o222) or not os.access(path, os.W_OK):
        raise SystemExit(
            f"cannot modify opencode config {config_path}: file is not writable"
        )
    parent = path.parent
    if not (parent.stat().st_mode & 0o222) or not os.access(parent, os.W_OK):
        raise SystemExit(
            f"cannot modify opencode config {config_path}: "
            "parent directory is not writable"
        )
    return {"status": "ready", "config": str(path)}


def deploy_opencode_plugin(
    plugin_source,
    plugin_dir,
    config_path,
    hook_bin,
    data_dir,
    dry_run=False,
    span_root=None,
):
    """Deploy the FD-58 notice plugin outside any target and register it.

    The plugin lives under Span's own data root; the host configuration gains
    one ``plugins`` entry. No target repository is written. The wrapper beside
    the plugin pins the hook binary and data directory, so the plugin does not
    depend on PATH.

    Only Span-managed registrations under ``span_root`` are removed. A
    Span-owned copy in a user-managed global directory is reported as a
    conflict and left untouched, because the operator owns that location.
    """
    print(f"+ deploy opencode plugin: {plugin_dir}")
    root = Path(data_dir).parent if span_root is None else Path(span_root)
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
    path = Path(_absolute_path(config_path))
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
    cleaned = []
    removed_entries = []
    user_managed = []
    canonical_seen = False
    for item in plugins:
        if not isinstance(item, str):
            cleaned.append(item)
            continue
        if _same_path(item, entry):
            if canonical_seen:
                removed_entries.append(item)
                continue
            canonical_seen = True
            cleaned.append(entry)
            continue
        # A Span-owned registration under Span's data root is stale; a copy
        # under a user-managed directory is reported, never modified.
        if _is_span_managed_entry(item, entry, root):
            removed_entries.append(item)
            continue
        if _span_plugin_file(item) is not None:
            user_managed.append(item)
        cleaned.append(item)
    if not canonical_seen:
        cleaned.append(entry)
    config["plugins"] = cleaned
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode plugin registered: {path}")
    if removed_entries:
        print(
            "opencode stale Span plugin registrations removed: "
            + ", ".join(removed_entries)
        )
    if user_managed:
        print(
            "opencode user-managed Span plugin copies left untouched: "
            + ", ".join(user_managed)
        )
    return {
        "status": "conflict" if user_managed else "wired",
        "plugin": str(target_dir),
        "config": str(path),
        "removed_config_entries": removed_entries,
        "user_managed": user_managed,
        "conflicts": user_managed,
    }


def inspect_target_opencode_plugins(
    targets,
) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    """Read-only Span-owned plugin discovery under explicitly named targets."""
    found: dict[str, list[dict[str, str]]] = {}
    unreadable: list[dict[str, str]] = []
    for target in targets:
        target_path = Path(target)
        entries: list[dict[str, str]] = []
        try:
            plugins_dir = target_path / ".opencode" / "plugins"
            if plugins_dir.is_dir():
                for candidate in sorted(plugins_dir.iterdir()):
                    plugin_file = _span_plugin_file(candidate)
                    if plugin_file is None:
                        continue
                    entries.append(
                        {
                            "path": str(candidate),
                            "sha256": _sha256_file(plugin_file),
                        }
                    )
        except OSError as exc:
            unreadable.append({"target": str(target), "error": str(exc)})
        found[str(target)] = entries
    return found, unreadable


def remove_opencode_plugin(config_path, plugin_dir, dry_run=False, span_root=None):
    """Remove Span's own plugin directory and managed ``plugins`` entries.

    Foreign plugins, user-managed Span copies, and every other configuration
    key are preserved. A missing entry or directory is already uninstalled.
    """
    print(f"+ remove opencode plugin: {plugin_dir}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    path = Path(_absolute_path(config_path))
    entry = str(Path(plugin_dir))
    root = Path(plugin_dir).parent if span_root is None else Path(span_root)
    removed_entries = []
    user_managed = []
    if path.is_file():
        try:
            config = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
        plugins = config.get("plugins")
        if isinstance(plugins, list):
            cleaned = []
            for item in plugins:
                if not isinstance(item, str):
                    cleaned.append(item)
                    continue
                if _is_span_managed_entry(item, entry, root):
                    removed_entries.append(item)
                    continue
                if _span_plugin_file(item) is not None:
                    user_managed.append(item)
                cleaned.append(item)
            config["plugins"] = cleaned
            path.write_text(json.dumps(config, indent=2) + "\n")
    directory = Path(plugin_dir)
    removed_dir = False
    if directory.is_dir():
        shutil.rmtree(directory)
        removed_dir = True
    return {
        "status": "removed" if (removed_entries or removed_dir) else "absent",
        "config": str(path),
        "plugin": str(directory),
        "removed_config_entries": removed_entries,
        "user_managed": user_managed,
        "conflicts": user_managed,
    }


def remove_opencode_registration(config_path, dry_run=False):
    """Remove only Span's own ``mcp.servers.span`` registration.

    Foreign servers and every other key are preserved. A file without the
    entry is already uninstalled, so the operation is idempotent and never
    rewrites unrelated configuration.
    """
    print(f"+ remove opencode registration: {config_path}")
    path = Path(_absolute_path(config_path))
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


def register_claude(span_cmd, dry_run=False) -> dict[str, object]:
    """Register Span with Claude Code at user scope through its CLI."""
    if shutil.which("claude") is None:
        print("claude CLI absent; skipping claude registration.")
        return {"status": "skipped", "reason": "claude CLI absent"}
    if dry_run:
        print("+ register claude (dry-run, skipped)")
        return {"status": "skipped", "reason": "dry-run"}
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
    # Converge on the installed hook binary: an entry from an earlier install
    # (different venv path or matcher) is replaced, not added beside. Foreign
    # hooks and matchers are untouched.
    replaced = _strip_span_hooks(config)
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
    print(f"codex hooks updated ({added} added, {replaced} replaced).")
    return {"status": "wired", "added": added, "replaced": replaced}


def wire_claude_hooks(hook_bin, data_dir, dry_run=False) -> dict[str, object]:
    """Converge Span-owned advisory hooks in Claude's user settings."""
    settings_path = Path(os.path.expanduser("~")) / ".claude" / "settings.json"
    print(f"+ wire claude hooks: {settings_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not settings_path.exists():
        print("no claude settings.json; skipping claude hook wiring.")
        return {"status": "skipped", "reason": "no claude settings.json"}
    try:
        config = json.loads(settings_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"cannot read claude settings.json: {exc}") from exc
    except ValueError as exc:
        raise SystemExit(f"cannot parse claude settings.json: {exc}") from exc
    if not isinstance(config, dict):
        raise SystemExit(
            "cannot parse claude settings.json: top level is not an object"
        )
    hooks = config.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise SystemExit("cannot parse claude settings.json: hooks is not an object")
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
    hooks = {} if hooks is None else hooks
    added = 0
    replaced = 0
    for event, matcher, command_parts in entries:
        group = hooks.get(event)
        if group is None:
            group = []
        if not isinstance(group, list):
            raise SystemExit(
                f"cannot parse claude settings.json: hooks.{event} is not a list"
            )
        command = " ".join(command_parts)
        kept_blocks = []
        for block in group:
            if not isinstance(block, dict):
                kept_blocks.append(block)
                continue
            block_hooks = block.get("hooks", [])
            if not isinstance(block_hooks, list):
                raise SystemExit(
                    f"cannot parse claude settings.json: hooks.{event} entry is invalid"
                )
            kept = [
                hook
                for hook in block_hooks
                if not isinstance(hook, dict)
                or not _span_hook_command(hook.get("command"))
            ]
            replaced += len(block_hooks) - len(kept)
            if kept:
                kept_blocks.append({**block, "hooks": kept})
        group = kept_blocks
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
        hooks[event] = group
        added += 1
    config["hooks"] = hooks
    backup = settings_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(settings_path, backup)
        print(f"claude settings backed up: {backup}")
    settings_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"claude hooks updated ({added} entries).")
    return {"status": "wired", "added": added, "replaced": replaced}


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


def remove_claude_registration(dry_run=False) -> dict[str, object]:
    """Remove only Span's user-scope Claude MCP registration."""
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


def _strip_span_hooks(config) -> int:
    """Remove every Span hook entry from a parsed host configuration.

    Returns the number of removed hooks. Foreign hooks, matchers, and every
    other setting are preserved; an emptied event or ``hooks`` map is dropped
    so a pre-install shape is restored.
    """
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return 0
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
    return removed


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
    removed = _strip_span_hooks(config)
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
    """Remove only Span-owned Claude lifecycle hook entries."""
    return _remove_span_hooks(
        Path(os.path.expanduser("~")) / ".claude" / "settings.json",
        dry_run=dry_run,
    )
