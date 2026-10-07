"""SemanticStore port (plan §5.5).

Canonical domain types directly — no store DTO layer is permitted.
The SQLite implementation (Phase 1.7) may normalize physically, but no
second semantic model may be introduced.
"""

import typing as _typing

from span.core.model import (
    CanonicalIndexBatch,
    ClaimId,
    ClaimKind,
    ClaimPage,
    EvidenceDependency,
    FreshnessUpdate,
    QueryBounds,
    RelationshipId,
    RelationshipKind,
    RelationshipPage,
    SchemaVersion,
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

    def load_claims(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
        claim_kinds: tuple[ClaimKind, ...],
        bounds: QueryBounds,
    ) -> ClaimPage:
        ...

    def load_relationships(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
        relationship_kinds: tuple[RelationshipKind, ...],
        direction: StructuralDirection,
        bounds: QueryBounds,
    ) -> RelationshipPage:
        ...

    def load_evidence_dependencies(
        self,
        repository_id: str,
        claim_or_relationship_ids: tuple[ClaimId | RelationshipId, ...],
    ) -> tuple[EvidenceDependency, ...]:
        ...

    def write_index_batch(self, batch: CanonicalIndexBatch) -> StoreWriteResult:
        ...

    def mark_freshness(
        self, updates: tuple[FreshnessUpdate, ...]
    ) -> StoreWriteResult:
        ...

    def schema_version(self) -> SchemaVersion:
        ...
