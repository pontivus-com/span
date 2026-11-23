"""Authority-configuration shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path


def _canonical_model():
    try:
        return importlib.import_module("span.core.model")
    except ImportError as exc:
        raise SystemExit(
            "cannot validate authority configuration: canonical decoder "
            f"unavailable ({exc}); refusing to install unchecked governance"
        ) from None


def _canonical_list(path, *, model_name, item_name, dry_run=False):
    print(f"+ read {item_name} file: {path}")
    if dry_run:
        return ()
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {item_name} file {path}: {exc}") from None
    if not isinstance(data, list):
        raise SystemExit(f"{item_name} file must hold a JSON list: {path}")
    model = _canonical_model()
    target = getattr(model, model_name)
    validated = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(
                f"{item_name} file {path}: {item_name}[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        payload = dict(item)
        payload.setdefault("$type", model_name)
        try:
            validated.append(model.from_canonical(target, payload))
        except model.CanonicalDecodeError as exc:
            raise SystemExit(
                f"{item_name} file {path}: {item_name}[{index}]: invalid "
                f"{model_name} arguments: {exc}"
            ) from None
    return tuple(validated)


def _repository_mapping(entries, *, selected_repository_ids, label):
    mapped = {}
    for repository_id, path in entries or ():
        if repository_id in mapped:
            raise SystemExit(
                f"duplicate {label} mapping for repository {repository_id!r}"
            )
        if repository_id not in selected_repository_ids:
            raise SystemExit(
                f"{label} mapping names unselected repository {repository_id!r}"
            )
        mapped[repository_id] = path
    return mapped


def load_authority_files(
    targets,
    seed_files,
    binding_files,
    *,
    dry_run=False,
):
    """Decode repository-qualified canonical authority configuration.

    Missing repository mappings are absent from the returned dictionaries so
    callers preserve the InitializeRepositoryRequest None tri-state. Explicit
    empty JSON lists decode to () and therefore mean clear; non-empty files
    decode to tuples of the existing canonical carriers.
    """
    try:
        structural = importlib.import_module("span.shell.structural")
    except ImportError as exc:
        raise SystemExit(
            f"cannot resolve repository identity for authority configuration: {exc}"
        ) from None

    selected_repository_ids = {
        structural.repository_id_from_config(str(target)) for target in targets
    }
    seed_paths = _repository_mapping(
        seed_files,
        selected_repository_ids=selected_repository_ids,
        label="authority seeds",
    )
    binding_paths = _repository_mapping(
        binding_files,
        selected_repository_ids=selected_repository_ids,
        label="authority bindings",
    )

    seeds = {}
    for repository_id, path in seed_paths.items():
        decoded = _canonical_list(
            path,
            model_name="EvidenceRef",
            item_name="authority seeds",
            dry_run=dry_run,
        )
        for item in decoded:
            if item.repository_id != repository_id:
                raise SystemExit(
                    "authority seeds repository mismatch: "
                    f"mapping={repository_id!r}, item={item.repository_id!r}"
                )
        seeds[repository_id] = decoded

    bindings = {}
    for repository_id, path in binding_paths.items():
        decoded = _canonical_list(
            path,
            model_name="AuthorityBinding",
            item_name="authority bindings",
            dry_run=dry_run,
        )
        for item in decoded:
            item_repository_id = item.evidence_ref.repository_id
            if item_repository_id != repository_id:
                raise SystemExit(
                    "authority bindings repository mismatch: "
                    f"mapping={repository_id!r}, item={item_repository_id!r}"
                )
        bindings[repository_id] = decoded

    return seeds, bindings


def load_seeds(path, dry_run=False):
    """Legacy internal helper retained for direct seed-decoder tests."""
    if path is None:
        return []
    decoded = _canonical_list(
        path,
        model_name="EvidenceRef",
        item_name="seeds",
        dry_run=dry_run,
    )
    if dry_run:
        return []
    return [item for item in decoded]


def preflight_facts(targets, seeds_path=None):
    """Read-only non-gating preflight facts.

    The optional seeds_path remains only for the existing direct helper
    contract. Beta-2 repository-qualified authority configuration is validated
    separately by load_authority_files.
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
            text_value = Path(seeds_path).read_text()
            parsed = json.loads(text_value)
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
