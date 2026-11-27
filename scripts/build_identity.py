#!/usr/bin/env python3
"""Generate or inspect the single packaging-time build identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

from sync_assets import asset_manifest

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDENTITY_PATH = ROOT / "src" / "span" / "BUILD_IDENTITY"


def tree_digest() -> str:
    """Hash canonical packaged sources, not generated build staging."""
    files = set((ROOT / "src" / "span").rglob("*.py"))
    files.update(source for source, _ in asset_manifest())
    files.update(
        ROOT / name
        for name in (
            "pyproject.toml",
            "README.md",
            "setup.py",
            "MANIFEST.in",
            "scripts/build_identity.py",
            "scripts/sync_assets.py",
        )
    )
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def source_revision() -> str:
    if not (ROOT / ".git").exists():
        return "unknown"
    try:
        head = subprocess.run(
            ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        status = subprocess.run(
            ("git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return head.stdout.strip() + ("-dirty" if status.stdout else "")


def build_identity() -> dict[str, str]:
    digest = tree_digest()
    revision = source_revision()
    # An unchanged source distribution retains its producer's identity.
    # Never borrow a surrounding Git checkout.
    if not (ROOT / ".git").exists():
        try:
            retained = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            retained = None
        if isinstance(retained, dict) and retained.get("source_digest") == digest:
            recorded = retained.get("source_revision")
            if isinstance(recorded, str) and recorded:
                revision = recorded
    return {"source_revision": revision, "source_digest": digest}


def generate_identity() -> None:
    IDENTITY_PATH.write_text(
        json.dumps(build_identity(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    if parser.parse_args().inspect:
        print(json.dumps(build_identity(), sort_keys=True))
    else:
        generate_identity()
        print("Generated Span build identity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
