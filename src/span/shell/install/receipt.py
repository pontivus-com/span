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
    import fcntl
    import stat

    root = Path(data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".install.lock"
    try:
        handle = os.open(
            lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600
        )
    except OSError as exc:
        raise SystemExit(f"cannot open administrative lock {lock_path}: {exc}") from None
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise SystemExit(f"invalid administrative lock file: {lock_path}")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                f"another installer owns {root}; no administrative state changed"
            ) from None
        except OSError as exc:
            raise SystemExit(f"cannot acquire administrative ownership: {exc}") from None
        yield
    finally:
        os.close(handle)


def write_receipt(data_dir, payload, dry_run=False):
    """Publish a complete receipt atomically, preserving the previous on failure."""
    import tempfile

    root = Path(data_dir)
    receipt = root / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".install-", suffix=".tmp", dir=root)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, receipt)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


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
