"""Explicit repository setup (administrative, no semantic interpretation).

Setup establishes identity, root binding, declared authority seeds and
declared authority bindings. It never creates understanding, never runs a
question, and never treats structural inventory as semantic completeness.
Authority declarations are supplied by the caller and validated by exact
source locator; nothing about kind, status or precedence is inferred.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY

__all__ = ["initialize_repository"]


def _inventory_locators(
    requested: tuple[m.EvidenceRef, ...],
    *,
    repository_id: str,
    evidence: EvidenceSource,
) -> dict[str, m.EvidenceRef]:
    inventory = evidence.inventory_evidence(
        repository_id,
        m.EvidenceScope(paths=(), evidence_refs=requested),
        DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds,
    )
    return {item.evidence_ref.locator: item.evidence_ref for item in inventory.items}


def _resolve_seeds(
    requested: tuple[m.EvidenceRef, ...],
    *,
    repository_id: str,
    evidence: EvidenceSource,
) -> tuple[m.EvidenceRef, ...]:
    by_locator = _inventory_locators(
        requested, repository_id=repository_id, evidence=evidence
    )
    resolved: list[m.EvidenceRef] = []
    for seed in requested:
        try:
            found = by_locator[seed.locator]
        except KeyError:
            raise ValueError(
                "unknown authority seed locator: " f"{seed.locator}"
            ) from None
        if found.repository_id != repository_id:
            raise ValueError(
                f"authority seed {seed.locator!r} belongs to "
                f"{found.repository_id!r}"
            )
        resolved.append(found)
    return tuple(resolved)


def _validate_bindings(
    requested: tuple[m.AuthorityBinding, ...],
    *,
    repository_id: str,
    evidence: EvidenceSource,
) -> tuple[m.AuthorityBinding, ...]:
    by_locator = _inventory_locators(
        tuple(item.evidence_ref for item in requested),
        repository_id=repository_id,
        evidence=evidence,
    )
    ids: set[str] = set()
    for binding in requested:
        reference = binding.evidence_ref
        if reference.repository_id != repository_id:
            raise ValueError(
                f"authority binding {reference.locator!r} belongs to "
                f"{reference.repository_id!r}"
            )
        if reference.locator not in by_locator:
            raise ValueError(
                "unknown authority binding locator: " f"{reference.locator}"
            )
        key = reference.evidence_id.value
        if key in ids:
            raise ValueError(f"duplicate authority binding: {key}")
        ids.add(key)
    return requested


def initialize_repository(
    request: m.InitializeRepositoryRequest,
    *,
    repository_id: str,
    canonical_root: str,
    store: LifecycleStorePort,
    evidence: EvidenceSource,
    structural_status: str,
) -> m.InitializeRepositoryResult:
    """Bind one repository and its declared authority configuration.

    Semantics: omitted (``None``) preserves configured declarations, an
    explicit empty tuple clears them, and a non-empty tuple replaces them.
    """
    existing_seeds = store.load_authority_seeds(repository_id)
    existing_bindings = store.load_authority_bindings(repository_id)
    if request.authority_seeds is None:
        seeds = existing_seeds
    elif not request.authority_seeds:
        seeds = ()
    else:
        seeds = _resolve_seeds(
            request.authority_seeds,
            repository_id=repository_id,
            evidence=evidence,
        )
    if request.authority_bindings is None:
        bindings = existing_bindings
    elif not request.authority_bindings:
        bindings = ()
    else:
        bindings = _validate_bindings(
            request.authority_bindings,
            repository_id=repository_id,
            evidence=evidence,
        )
    store.register_repository(
        repository_id,
        canonical_root,
        authority_seeds=seeds,
        authority_bindings=bindings,
    )
    warnings: list[str] = []
    if seeds:
        warnings.append(
            "authority seeds are declared governance, not semantic conclusions"
        )
    if bindings:
        warnings.append(
            "authority bindings are declared governance, not semantic conclusions"
        )
    return m.InitializeRepositoryResult(
        repository_id=repository_id,
        canonical_root=canonical_root,
        schema_version=store.schema_version(),
        store_ready=True,
        structural_status=structural_status,
        authority_seeds=seeds,
        authority_bindings=bindings,
        warnings=tuple(warnings),
    )
