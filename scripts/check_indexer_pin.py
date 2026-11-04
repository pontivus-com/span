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
CONSTANTS = ROOT / "src" / "span" / "shell" / "install" / "constants.py"


def pinned_identity() -> tuple[str, str]:
    try:
        text = CONSTANTS.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"cannot read the indexer constants from {CONSTANTS}: {exc}")
    values: dict[str, str] = {}
    for name in ("STRUCTURAL_INDEXER_PACKAGE", "STRUCTURAL_INDEXER_VERSION"):
        match = re.search(rf"^{name} = \"([^\"]+)\"$", text, re.MULTILINE)
        if match is None:
            raise SystemExit(f"cannot read {name} from {CONSTANTS}")
        values[name] = match.group(1)
    return values["STRUCTURAL_INDEXER_PACKAGE"], values["STRUCTURAL_INDEXER_VERSION"]


def published_version(package: str) -> str:
    completed = subprocess.run(
        ["npm", "view", package, "version", "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise SystemExit(f"npm view failed: {completed.stderr.strip()}")
    return str(json.loads(completed.stdout))


def main() -> int:
    package, pinned = pinned_identity()
    published = published_version(package)
    if pinned == published:
        print(f"{package} pin is current at {pinned}")
        return 0
    print(
        f"{package} pin is {pinned}, npm publishes {published}.\n"
        "Review the upstream release, then update STRUCTURAL_INDEXER_VERSION in\n"
        "src/span/shell/install/constants.py and\n"
        "src/span/shell/structural/graft.py with the\n"
        "matching test fixture update."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
