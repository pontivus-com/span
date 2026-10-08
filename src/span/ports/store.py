"""SemanticStore port (plan §5.5).

Canonical domain types directly — no store DTO layer is permitted.
The SQLite implementation (Phase 1.7) may normalize physically, but no
second semantic model may be introduced.
"""

import typing as _typing

from span.core.model import (
    CanonicalIndexBatch,
    ClaimKind,
    ClaimPage,
    ClaimRef,
    CoverageDependency,
    EvidenceDependency,
    FreshnessUpdate,
    QueryBounds,
    RecordedConflict,
    RelationshipKind,
    RelationshipPage,
    RelationshipRef,
    RepositoryState,
    SchemaVersion,
    SemanticClaim,
    SemanticRelationship,
    StoreWriteResult,
    Subject,
    SubjectId,
)
from span.ports.structural import StructuralDirection


@_typing.runtime_checkable
class SemanticStore(_typing.Protocol):
    def load_subjects(
        self, repository_id: str, subject_ids: tuple[SubjectId, ...]
    ) -> tuple[Subject, ...]:
        ...

    def load_by_refs(
        self,
        repository_id: str,
        refs: tuple[ClaimRef | RelationshipRef, ...],
    ) -> tuple[SemanticClaim | SemanticRelationship, ...]:
        """Resolve tagged refs to canonical items (unknown ids fail closed)."""
        ...

    def load_claims(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
        claim_kinds: tuple[ClaimKind, ...],
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> ClaimPage:
        ...

    def load_relationships(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
        relationship_kinds: tuple[RelationshipKind, ...],
        direction: StructuralDirection,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> RelationshipPage:
        ...

    def load_evidence_dependencies(
        self,
        repository_id: str,
        claim_or_relationship_ids: tuple[ClaimRef | RelationshipRef, ...],
    ) -> tuple[EvidenceDependency, ...]:
        ...

    def load_coverage_dependencies(
        self,
        repository_id: str,
        scope_subjects: tuple[SubjectId, ...],
    ) -> tuple[CoverageDependency, ...]:
        ...

    def load_conflicts(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
    ) -> tuple[RecordedConflict, ...]:
        """Validated agent-proposed conflicts overlapping the scope."""
        ...

    def write_index_batch(self, batch: CanonicalIndexBatch) -> StoreWriteResult:
        """Atomic reconciliation (plan §4.11, I-37): write, coverage
        record, and exactly the listed retirements — or nothing."""
        ...

    def mark_freshness(
        self, updates: tuple[FreshnessUpdate, ...]
    ) -> StoreWriteResult:
        ...

    def schema_version(self) -> SchemaVersion:
        ...

    def record_repository_state(self, state: RepositoryState) -> None:
        """Persist repository identity/state metadata (plan §10.2).

        Written by explicit initialization; read by status/hook paths
        to distinguish UNINITIALIZED from READY without implicit
        bootstrap (I-27).
        """
        ...

    def load_repository_state(
        self, repository_id: str
    ) -> RepositoryState | None:
        """Current recorded state, or None when never initialized."""
        ...
