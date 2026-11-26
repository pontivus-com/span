"""Authority-configuration shape and read-only preflight facts (stdlib only)."""

from __future__ import annotations

import hashlib
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


def _sha256_bytes(path: Path) -> tuple[str | None, str | None]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        return None, str(exc)
    return hashlib.sha256(payload).hexdigest(), None


def _repository_locator(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _governed_inputs(
    root: Path,
    repository_id: str,
    bootstrap_source: str | Path | None,
    binding_source: str | Path | None,
) -> list[dict[str, object]]:
    """Record the exact reviewed bootstrap/declaration/binding inputs."""
    inputs: list[dict[str, object]] = []
    bootstrap_path: Path | None = None
    if bootstrap_source is not None:
        bootstrap_path = Path(bootstrap_source)
    else:
        conventional = root / ".span" / "functional-pyramid.json"
        if conventional.is_file():
            bootstrap_path = conventional
    if bootstrap_path is not None and bootstrap_path.is_file():
        digest, error = _sha256_bytes(bootstrap_path)
        inputs.append(
            {
                "role": "bootstrap",
                "locator": _repository_locator(root, bootstrap_path),
                "digest": digest,
                "error": error,
            }
        )
        try:
            from span.core import functional_pyramid as _fp

            bootstrap = _fp.decode_functional_pyramid_bootstrap(
                bootstrap_path.read_text()
            )
        except (ImportError, OSError, UnicodeError, ValueError):
            bootstrap = None
        if bootstrap is not None:
            for request in bootstrap.declaration_sources:
                declaration_path = root / request.locator
                declaration_digest, declaration_error = _sha256_bytes(declaration_path)
                inputs.append(
                    {
                        "role": "declaration_source",
                        "locator": request.locator,
                        "digest": declaration_digest,
                        "error": declaration_error,
                    }
                )
    if binding_source is not None:
        binding_path = Path(binding_source)
        digest, error = _sha256_bytes(binding_path)
        inputs.append(
            {
                "role": "authority_binding",
                "locator": _repository_locator(root, binding_path),
                "digest": digest,
                "error": error,
            }
        )
    return inputs


def preflight_facts(
    targets: _typing.Iterable[str | Path],
    seeds_path: str | Path | None = None,
    *,
    bootstrap_files: _typing.Iterable[_typing.Sequence[str]] = (),
    binding_files: _typing.Iterable[_typing.Sequence[str]] = (),
) -> dict[str, object]:
    """Return read-only repository facts and governed-input provenance.

    Provenance is recorded inside this existing fact map. It is not a second
    manifest authority; verification compares these exact bytes with current
    installed source state.
    """
    try:
        from span.shell.structural import repository_id_from_config
    except ImportError:
        repository_id_from_config = None  # type: ignore[assignment]

    target_paths = {str(target): Path(target) for target in targets}
    identities: dict[str, str] = {}
    if repository_id_from_config is not None:
        for target in target_paths:
            try:
                identities[target] = repository_id_from_config(target)
            except (OSError, ValueError):
                identities[target] = ""
    selected = set(identities.values())
    bootstrap_map = (
        _repository_mapping(
            bootstrap_files,
            selected_repository_ids=selected,
            label="Functional Pyramid bootstrap",
        )
        if bootstrap_files
        else {}
    )
    binding_map = (
        _repository_mapping(
            binding_files,
            selected_repository_ids=selected,
            label="authority bindings",
        )
        if binding_files
        else {}
    )

    facts: dict[str, object] = {}
    for target, root in target_paths.items():
        repository_id = identities.get(target, "")
        entry: dict[str, object] = {"repository_id": repository_id}
        governed_inputs = _governed_inputs(
            root,
            repository_id,
            bootstrap_map.get(repository_id),
            binding_map.get(repository_id),
        )
        entry["governed_inputs"] = governed_inputs
        try:
            head = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if head.returncode == 0:
                entry["git_head"] = head.stdout.strip() or None
                entry["repository_revision"] = head.stdout.strip() or None
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
                entry["repository_revision"] = None
                entry["git_dirty"] = None
                entry["git_head_time"] = None
        except (OSError, subprocess.SubprocessError):
            entry["git_head"] = None
            entry["repository_revision"] = None
            entry["git_dirty"] = None
            entry["git_head_time"] = None
        facts[target] = entry

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
