"""Administrative repository setup contracts (explicit setup, not semantics)."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core.model.primitives import AuthorityBinding, EvidenceRef


@_dataclasses.dataclass(frozen=True)
class InitializeRepositoryRequest:
    """Explicit setup request: a plain locator and optional authority seeds.

    ``authority_seeds`` is tri-state: ``None`` preserves already configured
    seeds, ``()`` clears them, a non-empty tuple replaces them. Seeds are
    declared governance references, never inferred from repository structure.
    """

    repository_locator: str
    authority_seeds: tuple[EvidenceRef, ...] | None = None
    authority_bindings: tuple[AuthorityBinding, ...] | None = None

    def __post_init__(self) -> None:
        if not self.repository_locator or not self.repository_locator.strip():
            raise ValueError("initialize_repository needs a repository locator")


@_dataclasses.dataclass(frozen=True)
class InitializeRepositoryResult:
    """Operational readiness after explicit setup (no semantic completeness)."""

    repository_id: str
    canonical_root: str
    schema_version: int
    store_ready: bool
    structural_status: str
    authority_seeds: tuple[EvidenceRef, ...] = ()
    authority_bindings: tuple[AuthorityBinding, ...] = ()
    warnings: tuple[str, ...] = ()
