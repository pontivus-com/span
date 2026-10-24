#!/usr/bin/env python3
"""Report when the managed structural indexer pin is behind npm.

The indexer version is a Python constant (``STRUCTURAL_INDEXER_VERSION``), so
Dependabot cannot track it. This check runs on a schedule and fails when npm
publishes a different version, which is the signal to test and bump the pin.

Usage: ``python3 scripts/check_indexer_pin.py`` (needs Node and npm).
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALL = ROOT / "src" / "span" / "shell" / "install.py"
PACKAGE = "@nanonets/graft"


def pinned_version() -> str:
    text = INSTALL.read_text(encoding="utf-8")
    match = re.search(r'STRUCTURAL_INDEXER_VERSION = "([^"]+)"', text)
    if match is None:
        raise SystemExit(f"cannot read the indexer pin from {INSTALL}")
    return match.group(1)


def published_version() -> str:
    completed = subprocess.run(
        ["npm", "view", PACKAGE, "version", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise SystemExit(f"npm view failed: {completed.stderr.strip()}")
    return str(json.loads(completed.stdout))


def main() -> int:
    pinned = pinned_version()
    published = published_version()
    if pinned == published:
        print(f"{PACKAGE} pin is current at {pinned}")
        return 0
    print(
        f"{PACKAGE} pin is {pinned}, npm publishes {published}.\n"
        "Review the upstream release, then update STRUCTURAL_INDEXER_VERSION in\n"
        "src/span/shell/install.py and src/span/shell/structural/graft.py with the\n"
        "matching test fixture update."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
