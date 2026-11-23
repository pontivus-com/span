"""Authority-configuration shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import json
import subprocess
import typing as _typing
from pathlib import Path

if _typing.TYPE_CHECKING:
    from span.core import model as m


def _json_object_list(path: str | Path, *, label: str) -> list[dict[str, object]]:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {label} file {path}: {exc}") from None
    if not isinstance(data, list):
        raise SystemExit(f"{label} file must hold a JSON list: {path}")
    items: list[dict[str, object]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(
                f"{label} file {path}: {label}[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        items.append(dict(item))
    return items


def _evidence_refs(
    path: str | Path,
    *,
    dry_run: bool,
) -> tuple[m.EvidenceRef, ...]:
    print(f"+ read authority seeds file: {path}")
    if dry_run:
        return ()
    try:
        from span.core import model as m
    except ImportError as exc:
        raise SystemExit(
            "cannot validate authority seeds: canonical decoder unavailable "
            f"({exc}); refusing to install unchecked governance"
        ) from None

    validated: list[m.EvidenceRef] = []
    for index, item in enumerate(_json_object_list(path, label="authority seeds")):
        payload = dict(item)
        payload.setdefault("$type", "EvidenceRef")
        try:
            validated.append(m.from_canonical(m.EvidenceRef, payload))
        except m.CanonicalDecodeError as exc:
            raise SystemExit(
                f"authority seeds file {path}: authority seeds[{index}]: "
                f"invalid EvidenceRef arguments: {exc}"
            ) from None
    return tuple(validated)


def _authority_bindings(
    path: str | Path,
    *,
    dry_run: bool,
) -> tuple[m.AuthorityBinding, ...]:
    print(f"+ read authority bindings file: {path}")
    if dry_run:
        return ()
    try:
        from span.core import model as m
    except ImportError as exc:
        raise SystemExit(
            "cannot validate authority bindings: canonical decoder unavailable "
            f"({exc}); refusing to install unchecked governance"
        ) from None

    validated: list[m.AuthorityBinding] = []
    for index, item in enumerate(_json_object_list(path, label="authority bindings")):
        payload = dict(item)
        payload.setdefault("$type", "AuthorityBinding")
        try:
            validated.append(m.from_canonical(m.AuthorityBinding, payload))
        except m.CanonicalDecodeError as exc:
            raise SystemExit(
                f"authority bindings file {path}: authority bindings[{index}]: "
                f"invalid AuthorityBinding arguments: {exc}"
            ) from None
    return tuple(validated)


def _repository_mapping(
    entries: _typing.Iterable[_typing.Sequence[str]],
    *,
    selected_repository_ids: set[str],
    label: str,
) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for entry in entries:
        if len(entry) != 2:
            raise SystemExit(f"{label} mapping requires REPOSITORY_ID PATH")
        repository_id, path = entry
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
    targets: _typing.Iterable[str | Path],
    seed_files: _typing.Iterable[_typing.Sequence[str]],
    binding_files: _typing.Iterable[_typing.Sequence[str]],
    *,
    dry_run: bool = False,
) -> tuple[
    dict[str, tuple[m.EvidenceRef, ...]],
    dict[str, tuple[m.AuthorityBinding, ...]],
]:
    """Decode repository-qualified canonical authority configuration.

    Missing mappings remain absent, preserving InitializeRepositoryRequest None.
    Explicit empty JSON lists decode to empty tuples (clear); non-empty lists
    decode to tuples of the existing canonical carriers (replace).
    """
    try:
        from span.shell.structural import repository_id_from_config
    except ImportError as exc:
        raise SystemExit(
            f"cannot resolve repository identity for authority configuration: {exc}"
        ) from None

    selected_repository_ids = {
        repository_id_from_config(str(target)) for target in targets
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

    seeds: dict[str, tuple[m.EvidenceRef, ...]] = {}
    for repository_id, path in seed_paths.items():
        decoded = _evidence_refs(path, dry_run=dry_run)
        for item in decoded:
            if item.repository_id != repository_id:
                raise SystemExit(
                    "authority seeds repository mismatch: "
                    f"mapping={repository_id!r}, item={item.repository_id!r}"
                )
        seeds[repository_id] = decoded

    bindings: dict[str, tuple[m.AuthorityBinding, ...]] = {}
    for repository_id, path in binding_paths.items():
        decoded = _authority_bindings(path, dry_run=dry_run)
        for item in decoded:
            item_repository_id = item.evidence_ref.repository_id
            if item_repository_id != repository_id:
                raise SystemExit(
                    "authority bindings repository mismatch: "
                    f"mapping={repository_id!r}, item={item_repository_id!r}"
                )
        bindings[repository_id] = decoded

    return seeds, bindings


def load_seeds(
    path: str | Path | None,
    dry_run: bool = False,
) -> list[m.EvidenceRef]:
    """Legacy internal helper retained for direct seed-decoder tests."""
    if path is None:
        return []
    return list(_evidence_refs(path, dry_run=dry_run))


def preflight_facts(
    targets: _typing.Iterable[str | Path],
    seeds_path: str | Path | None = None,
) -> dict[str, object]:
    """Return read-only non-gating repository and legacy seed-file facts."""
    facts: dict[str, object] = {}
    for target in targets:
        entry: dict[str, object] = {}
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
            parsed = json.loads(Path(seeds_path).read_text())
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
