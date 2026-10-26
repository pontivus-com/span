"""Typing ratchet (plan §6, E3).

Runs mypy over ``src/span`` and compares per-module error counts with the
recorded baseline. The gate fails when any module regresses; ``--update``
rewrites the baseline after a wave lowers it.

Usage:
    python scripts/typecheck.py
    python scripts/typecheck.py --update
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "mypy_baseline.json"
TARGET = "src/span"
LINE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): error: (?P<message>.*)$")


def run_mypy() -> tuple[collections.Counter[str], int]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--python-version",
            "3.12",
            "--ignore-missing-imports",
            "--no-error-summary",
            "--show-error-codes",
            TARGET,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    counts: collections.Counter[str] = collections.Counter()
    total = 0
    for line in result.stdout.splitlines():
        match = LINE.match(line)
        if not match:
            continue
        counts[pathlib.Path(match["path"]).as_posix()] += 1
        total += 1
    if result.returncode not in (0, 1):
        raise SystemExit(result.stderr or result.stdout)
    return counts, total


def main(argv: list[str]) -> int:
    counts, total = run_mypy()
    current = {"total": total, "modules": dict(sorted(counts.items()))}
    if "--update" in argv:
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"mypy baseline updated: {total} errors")
        return 0
    if not BASELINE.exists():
        print("mypy baseline missing; run with --update once to record it")
        return 1
    baseline = json.loads(BASELINE.read_text())
    regressions = {
        module: (baseline["modules"].get(module, 0), count)
        for module, count in counts.items()
        if count > baseline["modules"].get(module, 0)
    }
    if total > baseline["total"]:
        regressions["total"] = (baseline["total"], total)
    if regressions:
        for module, (was, now) in sorted(regressions.items()):
            print(f"typing regression: {module}: {was} -> {now}")
        return 1
    print(f"typing ratchet holds: {total} errors (baseline {baseline['total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
