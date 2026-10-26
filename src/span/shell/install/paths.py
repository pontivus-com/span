"""Install locations and installation-mode resolution (stdlib only)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from span.shell.install.constants import (
    PLATFORM_PATHS,
)


def platform_paths(platform=None):
    """Resolve install locations for one platform key.

    Raises SystemExit with a clear message on unsupported platforms
    instead of guessing paths.
    """
    key = platform or sys.platform
    try:
        entry = PLATFORM_PATHS[key]
    except KeyError:
        raise SystemExit(f"unsupported platform for install: {key}")
    if not entry.get("supported", False):
        raise SystemExit(
            f"install paths reserved but not yet verified for: {key} "
            f"({entry.get('note', 'no note')})"
        )
    return {
        name: Path(os.path.expandvars(os.path.expanduser(value[0])))
        for name, value in entry.items()
        if isinstance(value, tuple)
    }


def default_tools_dir(venv_dir):
    """Span-owned tools directory holding the managed indexer install."""
    return Path(venv_dir).parent / "tools"


def indexer_binary_path(tools_dir):
    """Expected indexer binary inside a tools directory."""
    return Path(tools_dir) / "node_modules" / ".bin" / "graft"


def install_mode(span_repo):
    """Where the runtime comes from: a source checkout or a distribution.

    ``span-install`` is reachable in both cases. Only a checkout has
    ``src/span``, the build staging setuptools reuses, and the canonical
    ``skills`` and ``docs/agents-snippet.md``. A wheel install has none
    of them, so those steps resolve against the assets bundled inside the
    package instead of failing or guessing a path.
    """
    checkout = Path(span_repo) / "src" / "span"
    return "checkout" if checkout.is_dir() else "distribution"


def distribution_version():
    """Version of the ``span-mcp`` distribution this installer came from."""
    from importlib import metadata

    try:
        return metadata.version("span-mcp")
    except metadata.PackageNotFoundError:
        raise SystemExit(
            "span-install cannot determine its own distribution version; "
            "reinstall with `pip install span-mcp`."
        )


def bundled_assets_root():
    """Installer assets shipped inside the installed package."""
    return Path(__file__).resolve().parents[2] / "_assets"


def canonical_skills_dir(span_repo):
    """Directory holding the canonical skills for this installation mode."""
    if install_mode(span_repo) == "checkout":
        return Path(span_repo) / "skills"
    return bundled_assets_root() / "skills"


def agents_snippet_path(span_repo):
    """Canonical lifecycle snippet for this installation mode."""
    if install_mode(span_repo) == "checkout":
        return Path(span_repo) / "docs" / "agents-snippet.md"
    return bundled_assets_root() / "agents-snippet.md"


def git_rev(span_repo):
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(span_repo),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip()


def expected_span_command(span_mcp, data_dir, repos):
    """Installed invocation shape used for host-registration inspection."""
    command = [str(span_mcp), "--data-dir", str(data_dir)]
    for repo in repos:
        command += ["--repo", str(repo)]
    return command
