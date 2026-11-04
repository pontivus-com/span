"""Install receipt read/write (stdlib only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NoReturn

from span.shell.install.constants import INSTALL_VERSION
from span.shell.install.hosts import OPENCODE_PLUGIN_SCOPES


def _invalid(path: Path, reason: str) -> NoReturn:
    raise SystemExit(f"unsupported install receipt {path}: {reason}")


def _validate_current_receipt(path: Path, receipt: object) -> dict[str, object]:
    if not isinstance(receipt, dict):
        _invalid(path, "top level must be an object")
    if receipt.get("install_version") != INSTALL_VERSION:
        _invalid(path, "install_version is not current")
    repos = receipt.get("repos")
    if not isinstance(repos, list) or not all(
        isinstance(repo, str) and repo for repo in repos
    ):
        _invalid(path, "repos must be a list of non-empty strings")
    host_registration = receipt.get("host_registration")
    if not isinstance(host_registration, dict):
        _invalid(path, "host_registration must be an object")
    hooks = host_registration.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        _invalid(path, "host_registration.hooks must be an object")
    opencode = host_registration.get("opencode")
    if opencode is not None and not isinstance(opencode, dict):
        _invalid(path, "host_registration.opencode must be an object")
    claude = host_registration.get("claude")
    if claude is not None and not isinstance(claude, dict):
        _invalid(path, "host_registration.claude must be an object")
    if isinstance(opencode, dict) and opencode.get("config") is not None:
        config = opencode["config"]
        if not isinstance(config, str) or not os.path.isabs(config):
            _invalid(path, "host_registration.opencode.config must be absolute")
    if isinstance(hooks, dict):
        claude_hooks = hooks.get("claude")
        if claude_hooks is not None and not isinstance(claude_hooks, dict):
            _invalid(path, "host_registration.hooks.claude must be an object")
        plugin = hooks.get("opencode_plugin")
        if plugin is not None and not isinstance(plugin, dict):
            _invalid(path, "host_registration.hooks.opencode_plugin must be an object")
        if isinstance(plugin, dict):
            config = plugin.get("config")
            if config is not None and (
                not isinstance(config, str) or not os.path.isabs(config)
            ):
                _invalid(
                    path,
                    "host_registration.hooks.opencode_plugin.config must be absolute",
                )
            scope = plugin.get("scope")
            if scope is not None and scope not in OPENCODE_PLUGIN_SCOPES:
                _invalid(
                    path,
                    "host_registration.hooks.opencode_plugin.scope is unsupported",
                )
    return receipt


def write_receipt(data_dir, payload, dry_run=False):
    receipt = Path(data_dir) / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_receipt(data_dir):
    """Read the current install receipt, or None when it is absent."""
    path = Path(data_dir) / "install.json"
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_text())
    except OSError as exc:
        _invalid(path, f"cannot be read: {exc}")
    except ValueError as exc:
        _invalid(path, f"invalid JSON: {exc}")
    return _validate_current_receipt(path, receipt)
