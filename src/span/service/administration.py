"""Explicit repository setup (administrative, no semantic interpretation).

Setup establishes identity, root binding, declared authority seeds and
declared authority bindings. It never creates understanding, never runs a
question, and never treats structural inventory as semantic completeness.
Authority declarations are supplied by the caller and validated by exact
source locator; nothing about kind, status or precedence is inferred.
"""

from __future__ import annotations

from dataclasses import replace

from span.core import model as m
from span.core.rejection import Rejection
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort

__all__ = [
    "initialize_repository",
    "register_authority_configuration",
    "validate_authority_configuration",
]


def validate_authority_configuration(
    request: m.InitializeRepositoryRequest,
    *,
    repository_id: str,
    evidence: EvidenceSource,
) -> m.InitializeRepositoryRequest:
    """Validate every explicit locator; preserve omitted and empty families."""
    observed: dict[str, m.EvidenceRef] = {}

    def resolve(reference: m.EvidenceRef, family: str) -> m.EvidenceRef:
        locator = reference.locator
        if reference.repository_id != repository_id:
            raise Rejection(
                f"authority {family} {locator!r} belongs to "
                f"{reference.repository_id!r}, not {repository_id!r}",
                public_identity=f"{repository_id}/{locator}",
                public_cause="the authority document belongs to a different repository; correct the mapping and retry",
            )
        if locator not in observed:
            try:
                result = evidence.read_exact(
                    repository_id, m.EvidenceRequest(locator), None
                )
            except (OSError, ValueError) as exc:
                raise Rejection(
                    f"authority {family} provider failure: {exc}",
                    public_identity=f"{repository_id}/{locator}",
                    public_cause="the supplied authority document cannot be read; restore access and retry",
                ) from exc
            if isinstance(result, m.EvidenceSourceFailure):
                raise Rejection(
                    f"authority {family} {result.kind.value.lower()} locator "
                    f"{repository_id!r}/{locator!r}: {result.reason}",
                    public_identity=f"{repository_id}/{locator}",
                    public_cause=f"{result.kind.value.lower()} locator {repository_id}/{locator}; correct the authority configuration and retry",
                )
            found = result.evidence_ref
            if found.repository_id != repository_id or found.locator != locator:
                raise Rejection(
                    f"authority {family} provider identity mismatch for "
                    f"{repository_id!r}/{locator!r}",
                    public_identity=f"{repository_id}/{locator}",
                    public_cause="the authority document could not be verified; check its location and retry",
                )
            observed[locator] = found
        return observed[locator]

    seeds = request.authority_seeds
    if seeds is not None:
        seeds = tuple(resolve(seed, "seed") for seed in seeds)
    ids: set[str] = set()
    for binding in request.authority_bindings or ():
        reference = binding.evidence_ref
        resolve(reference, "binding")
        key = reference.evidence_id.value
        if key in ids:
            raise Rejection(
                f"duplicate authority binding: {repository_id!r}/{key}",
                public_identity=f"{repository_id}/{reference.locator}",
                public_cause="duplicate authority binding; remove the conflicting entry and retry",
            )
        ids.add(key)
    return replace(request, authority_seeds=seeds)


def register_authority_configuration(
    request: m.InitializeRepositoryRequest,
    *,
    repository_id: str,
    canonical_root: str,
    store: LifecycleStorePort,
) -> tuple[tuple[m.EvidenceRef, ...], tuple[m.AuthorityBinding, ...]]:
    """Apply validated authority through the canonical registration owner.

    Recovery uses this same operation only on its isolated baseline copy.
    """
    seeds = (
        store.load_authority_seeds(repository_id)
        if request.authority_seeds is None
        else request.authority_seeds
    )
    bindings = (
        store.load_authority_bindings(repository_id)
        if request.authority_bindings is None
        else request.authority_bindings
    )
    store.register_repository(
        repository_id,
        canonical_root,
        authority_seeds=seeds,
        authority_bindings=bindings,
    )
    return seeds, bindings


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
    validated = validate_authority_configuration(
        request, repository_id=repository_id, evidence=evidence
    )
    seeds, bindings = register_authority_configuration(
        validated,
        repository_id=repository_id,
        canonical_root=canonical_root,
        store=store,
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
