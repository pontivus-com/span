"""Authority-seed shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path


def load_seeds(path, dry_run=False):
    if path is None:
        return []
    print(f"+ read authority seeds: {path}")
    if dry_run:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read seeds file {path}: {exc}")
    if not isinstance(data, list):
        raise SystemExit(f"seeds file must hold a JSON list: {path}")
    # [design note G](docs/design-references.md#g) §4.6: early seed-shape validation via the canonical
    # decoder, before any mutation. The bootstrap shim
    # (scripts/install-span.py) puts `src/` on `sys.path`, and the
    # installed `span-install` entry point has Span installed, so the
    # canonical decoder is always obtainable in supported paths. Shape
    # only; no locator resolution against the store and no structural
    # provider contact. Unknown locators stay rejected at
    # initialize_repository provisioning, the authoritative boundary.
    # A missing decoder is a broken checkout or install and fails
    # closed here; validation is never skipped.
    try:
        _m = importlib.import_module("span.core.model")
    except ImportError as exc:
        raise SystemExit(
            f"cannot validate seeds file {path}: canonical decoder "
            f"unavailable ({exc}); refusing to install with unchecked "
            f"authority seeds"
        ) from None
    validated: list[object] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(
                f"seeds file {path}: seeds[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        payload = dict(item)
        payload.setdefault("$type", "EvidenceRef")
        try:
            validated.append(_m.from_canonical(_m.EvidenceRef, payload))
        except _m.CanonicalDecodeError as exc:
            raise SystemExit(
                f"seeds file {path}: seeds[{index}]: invalid "
                f"EvidenceRef arguments: {exc}"
            ) from None
    return data


def preflight_facts(targets, seeds_path=None):
    """Read-only non-gating preflight facts ([design note G](docs/design-references.md#g) §4.6).

    Reports git dirty/HEAD where available and seed-file facts. Never
    gates installation: provisioning triggers the single bounded
    provider build when the cache is missing or stale. Stdlib and git
    CLI only; no store, no provider writes.
    """
    facts: dict = {}
    for target in targets:
        entry: dict = {}
        try:
            head = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if head.returncode == 0:
                entry["git_head"] = head.stdout.strip() or None
                status = subprocess.run(
                    ["git", "-C", str(target), "status", "--short"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                entry["git_dirty"] = bool(status.stdout.strip())
                log = subprocess.run(
                    ["git", "-C", str(target), "log", "-1", "--format=%ct"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                try:
                    entry["git_head_time"] = int(log.stdout.strip())
                except (ValueError, AttributeError):
                    entry["git_head_time"] = None
            else:
                entry["git_head"] = None
                entry["git_dirty"] = None
                entry["git_head_time"] = None
        except (OSError, subprocess.SubprocessError):
            entry["git_head"] = None
            entry["git_dirty"] = None
            entry["git_head_time"] = None
        facts[str(target)] = entry
    if seeds_path is not None:
        try:
            text = Path(seeds_path).read_text()
            parsed = json.loads(text)
            facts["seeds_file"] = {
                "supplied": True,
                "readable": True,
                "shape_valid": isinstance(parsed, list),
                "item_count": (len(parsed) if isinstance(parsed, list) else None),
            }
        except (OSError, ValueError):
            facts["seeds_file"] = {
                "supplied": True,
                "readable": False,
                "shape_valid": False,
                "item_count": None,
            }
    else:
        facts["seeds_file"] = {
            "supplied": False,
            "readable": False,
            "shape_valid": False,
            "item_count": 0,
        }
    return facts
