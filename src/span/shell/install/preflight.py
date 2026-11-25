"""Authority-configuration shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import importlib
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
        try:
            validated.append(m.from_canonical(m.EvidenceRef, item))
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
        try:
            validated.append(m.from_canonical(m.AuthorityBinding, item))
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
        decoded_seeds = _evidence_refs(path, dry_run=dry_run)
        for seed in decoded_seeds:
            if seed.repository_id != repository_id:
                raise SystemExit(
                    "authority seeds repository mismatch: "
                    f"mapping={repository_id!r}, item={seed.repository_id!r}"
                )
        seeds[repository_id] = decoded_seeds

    bindings: dict[str, tuple[m.AuthorityBinding, ...]] = {}
    for repository_id, path in binding_paths.items():
        decoded_bindings = _authority_bindings(path, dry_run=dry_run)
        for binding in decoded_bindings:
            binding_repository_id = binding.evidence_ref.repository_id
            if binding_repository_id != repository_id:
                raise SystemExit(
                    "authority bindings repository mismatch: "
                    f"mapping={repository_id!r}, item={binding_repository_id!r}"
                )
        bindings[repository_id] = decoded_bindings

    return seeds, bindings


def load_functional_pyramid_bootstraps(
    targets: _typing.Iterable[str | Path],
    bootstrap_files: _typing.Iterable[_typing.Sequence[str]],
    *,
    dry_run: bool = False,
) -> dict[str, bytes]:
    """Validate explicit Version-2 bootstrap/declaration files before mutation."""
    try:
        from span.core import functional_pyramid as _fp
        from span.shell.structural import repository_id_from_config
    except ImportError as exc:
        raise SystemExit(
            "cannot validate Functional Pyramid bootstrap configuration: "
            f"{exc}; refusing to install unchecked governance"
        ) from None

    targets_by_id = {
        repository_id_from_config(str(target)): Path(target).resolve()
        for target in targets
    }
    mapped = _repository_mapping(
        bootstrap_files,
        selected_repository_ids=set(targets_by_id),
        label="Functional Pyramid bootstrap",
    )
    payloads: dict[str, bytes] = {}
    for repository_id, source_path in mapped.items():
        print(f"+ read Functional Pyramid bootstrap file: {source_path}")
        if dry_run:
            payloads[repository_id] = b""
            continue
        try:
            payload = Path(source_path).read_bytes()
            text = payload.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise SystemExit(
                f"cannot read Functional Pyramid bootstrap file {source_path}: {exc}"
            ) from None
        try:
            bootstrap = _fp.decode_functional_pyramid_bootstrap(text)
        except ValueError as exc:
            raise SystemExit(
                f"Functional Pyramid bootstrap file {source_path} is invalid: {exc}"
            ) from None

        root = targets_by_id[repository_id]
        for request in bootstrap.declaration_sources:
            if request.ranges:
                raise SystemExit(
                    "Functional Pyramid bootstrap declaration sources must be "
                    f"whole documents: {repository_id!r}:{request.locator}"
                )
            declaration_path = (root / request.locator).resolve()
            try:
                declaration_path.relative_to(root)
            except ValueError:
                raise SystemExit(
                    "Functional Pyramid declaration source escapes repository root: "
                    f"{repository_id!r}:{request.locator}"
                ) from None
            if not declaration_path.is_file():
                raise SystemExit(
                    "Functional Pyramid declaration source is not repository-owned "
                    f"and present: {repository_id!r}:{request.locator}"
                )
            try:
                declaration_text = declaration_path.read_text()
                _fp.decode_functional_pyramid_declaration(
                    declaration_text,
                    repository_id=repository_id,
                    declaration_locator=request.locator,
                )
            except (OSError, UnicodeError, ValueError) as exc:
                raise SystemExit(
                    "Functional Pyramid declaration source is not valid Version-2 "
                    f"content: {repository_id!r}:{request.locator}: {exc}"
                ) from None

        destination = root / ".span" / "functional-pyramid.json"
        if destination.exists():
            try:
                existing = destination.read_bytes()
            except OSError as exc:
                raise SystemExit(
                    f"cannot read existing Functional Pyramid bootstrap {destination}: {exc}"
                ) from None
            if existing != payload:
                raise SystemExit(
                    "existing Functional Pyramid bootstrap differs from explicit "
                    f"input: {destination}; refusing mutation"
                )
        payloads[repository_id] = payload
    return payloads


def load_seeds(
    path: str | Path | None,
    dry_run: bool = False,
) -> list[m.EvidenceRef]:
    """Legacy internal helper retained for direct seed-decoder tests."""
    if path is None:
        return []
    try:
        importlib.import_module("span.core.model")
    except ImportError as exc:
        raise SystemExit(
            "cannot validate authority seeds: canonical decoder unavailable "
            f"({exc}); refusing to install unchecked governance"
        ) from None
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
