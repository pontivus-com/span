"""Install receipt read/write (stdlib only)."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Iterator, NoReturn

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


@contextlib.contextmanager
def administrative_ownership(data_dir: str | Path) -> Iterator[None]:
    """Hold the single installation-local administrative lock (TD §17.2)."""
    from span.shell.sqlite_ownership import StoreHeldError, stable_ownership

    with contextlib.ExitStack() as resources:
        try:
            resources.enter_context(
                stable_ownership(data_dir, ".install.lock", exclusive=True)
            )
        except StoreHeldError as exc:
            raise SystemExit(
                f"another installer owns or cannot acquire administrative ownership "
                f"of {Path(data_dir).resolve()}: {exc}"
            ) from None
        yield


def fsync_directory(path: Path) -> None:
    handle = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def durable_unlink(path: Path) -> None:
    path.unlink()
    fsync_directory(path.parent)


def publish_install_bytes(destination: Path, encoded: bytes, *, replace: bool) -> None:
    """Publish one installation artifact durably; immutable paths never overwrite."""
    import tempfile

    root = destination.parent
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".install-", suffix=".tmp", dir=root)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
        fsync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)


def write_receipt(data_dir, payload, dry_run=False):
    """Publish the existing installation receipt atomically."""
    receipt = Path(data_dir) / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    publish_install_bytes(receipt, encoded, replace=True)


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
