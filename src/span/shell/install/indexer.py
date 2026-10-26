"""Managed structural-indexer provisioning (stdlib only)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from span.shell.install.constants import (
    STRUCTURAL_INDEXER_PACKAGE,
    STRUCTURAL_INDEXER_VERSION,
)
from span.shell.install.paths import (
    default_tools_dir,
    indexer_binary_path,
)


def check_prereqs():
    """Fail closed naming the first missing prerequisite."""
    errors = []
    if sys.version_info < (3, 12):
        errors.append(f"python >= 3.12 required, found {sys.version.split()[0]}")
    # Node and npm provision the managed structural indexer at install
    # time; the indexer itself is never a user prerequisite.
    for tool in ("node", "npm"):
        if shutil.which(tool) is None:
            errors.append(f"required tool missing from PATH: {tool}")
    if errors:
        raise SystemExit("prerequisites missing:\n- " + "\n- ".join(errors))


def _redact_provider(text):
    """Keep the managed provider name out of end-user output."""
    text = text.replace(STRUCTURAL_INDEXER_PACKAGE, "structural indexer")
    return text.replace("graft", "structural-indexer")


def ensure_structural_indexer(venv_dir, dry_run=False):
    """Provision the pinned structural indexer (auto-install, no bundle).

    Installs exactly ``STRUCTURAL_INDEXER_PACKAGE @ VERSION`` via npm
    into Span's tools directory (never global, never into targets).
    Idempotent: skips reinstall only when the managed binary and its
    installed package metadata both name this exact version. Returns the
    binary path.
    """
    tools_dir = default_tools_dir(venv_dir)
    binary = indexer_binary_path(tools_dir)
    package_json = (
        tools_dir / "node_modules" / STRUCTURAL_INDEXER_PACKAGE / "package.json"
    )
    installed_version = None
    try:
        metadata = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metadata = None
    if isinstance(metadata, dict):
        if metadata.get("name") == STRUCTURAL_INDEXER_PACKAGE:
            installed_version = metadata.get("version")
    if binary.is_file() and installed_version == STRUCTURAL_INDEXER_VERSION:
        return str(binary)
    print(
        f"+ provision structural indexer "
        f"{STRUCTURAL_INDEXER_VERSION} -> {tools_dir}"
    )
    if dry_run:
        return str(binary)
    cmd = [
        "npm",
        "install",
        "--prefix",
        str(tools_dir),
        "--no-audit",
        "--no-fund",
        f"{STRUCTURAL_INDEXER_PACKAGE}@{STRUCTURAL_INDEXER_VERSION}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = _redact_provider(proc.stderr.strip() or proc.stdout.strip())
        raise SystemExit(
            f"structural indexer provisioning failed " f"({proc.returncode}): {detail}"
        )
    if not binary.is_file():
        raise SystemExit(
            "structural indexer provisioning produced no binary in "
            "the managed tools directory"
        )
    return str(binary)


def write_indexer_pointer(data_dir, binary, dry_run=False):
    """Record the provisioned indexer pointer under the data dir."""
    payload = {
        "package": STRUCTURAL_INDEXER_PACKAGE,
        "version": STRUCTURAL_INDEXER_VERSION,
        "binary": str(binary),
    }
    print(f"+ write indexer pointer: {Path(data_dir) / 'structural-indexer.json'}")
    if dry_run:
        return payload
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / "structural-indexer.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    return payload
