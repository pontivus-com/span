"""Authority-seed shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path


def _load_canonical_list(path, *, dry_run, label, model_name):
    if path is None:
        return []
    print(f"+ read authority {label}: {path}")
    if dry_run:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {label} file {path}: {exc}")
    if not isinstance(data, list):
        raise SystemExit(f"{label} file must hold a JSON list: {path}")
    # Validate with Span's canonical domain decoder before any mutation.
    # Locator/currentness validation remains at repository provisioning,
    # which owns evidence access and root binding.
    try:
        _m = importlib.import_module("span.core.model")
    except ImportError as exc:
        raise SystemExit(
            f"cannot validate {label} file {path}: canonical decoder "
            f"unavailable ({exc}); refusing to install with unchecked "
            f"authority {label}"
        ) from None
    model = getattr(_m, model_name)
    validated: list[object] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(
                f"{label} file {path}: {label}[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        payload = dict(item)
        payload.setdefault("$type", model_name)
        try:
            validated.append(_m.from_canonical(model, payload))
        except _m.CanonicalDecodeError as exc:
            raise SystemExit(
                f"{label} file {path}: {label}[{index}]: invalid "
                f"{model_name} arguments: {exc}"
            ) from None
    return validated


def load_seeds(path, dry_run=False):
    return _load_canonical_list(
        path, dry_run=dry_run, label="seeds", model_name="EvidenceRef"
    )


def load_bindings(path, dry_run=False):
    return _load_canonical_list(
        path, dry_run=dry_run, label="bindings", model_name="AuthorityBinding"
    )


def preflight_facts(targets, seeds_path=None, bindings_path=None):
    """Read-only non-gating preflight facts ([design note G](docs/design-references.md#g) §4.6).

    Reports git dirty/HEAD where available and authority-file facts. Never
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

    def file_fact(path):
        if path is None:
            return {
                "supplied": False,
                "readable": False,
                "shape_valid": False,
                "item_count": 0,
            }
        try:
            parsed = json.loads(Path(path).read_text())
            return {
                "supplied": True,
                "readable": True,
                "shape_valid": isinstance(parsed, list),
                "item_count": (len(parsed) if isinstance(parsed, list) else None),
            }
        except (OSError, ValueError):
            return {
                "supplied": True,
                "readable": False,
                "shape_valid": False,
                "item_count": None,
            }

    facts["seeds_file"] = file_fact(seeds_path)
    facts["bindings_file"] = file_fact(bindings_path)
    return facts
