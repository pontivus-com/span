#!/usr/bin/env python3
"""Write ``src/span/BUILD_IDENTITY`` before a release build.

The file records the source revision and a deterministic digest of the
packaged source. ``span-install --verify-only`` reads it from an installed
distribution so a built package can report the source it came from.

The file is generated, not committed. Development installs without it fall
back to a git probe or to ``unknown``.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_SET = ("src", "pyproject.toml", "README.md")


def tree_digest() -> str:
    files: list[pathlib.Path] = []
    for entry in SOURCE_SET:
        path = ROOT / entry
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix not in {".pyc", ".pyo"}:
                    if "__pycache__" not in child.parts:
                        files.append(child)
        elif path.is_file():
            files.append(path)
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def source_revision() -> str:
    try:
        head = subprocess.run(
            ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if head.returncode != 0:
            return "unknown"
        dirty = subprocess.run(
            ("git", "-C", str(ROOT), "diff", "--quiet"),
            timeout=30,
        )
        return head.stdout.strip() + ("" if dirty.returncode == 0 else "-dirty")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def main() -> int:
    identity = {
        "source_revision": source_revision(),
        "source_digest": tree_digest(),
    }
    target = ROOT / "src" / "span" / "BUILD_IDENTITY"
    target.write_text(
        json.dumps(identity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
