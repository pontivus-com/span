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
    InterpretationCoverage,
    QueryBounds,
    RecordedConflict,
    RelationshipKind,
    RelationshipPage,
    RelationshipRef,
    RepositoryState,
    SchemaVersion,
    SemanticClaim,
    SemanticQuestionScope,
    SemanticRelationship,
    StoreWriteResult,
    Subject,
    SubjectPage,
    SubjectId,
    TargetAssociation,
    TargetId,
)
from span.ports.structural import StructuralDirection


@_typing.runtime_checkable
class SemanticStore(_typing.Protocol):
    def load_subjects(
        self, repository_id: str, subject_ids: tuple[SubjectId, ...]
    ) -> tuple[Subject, ...]:
        ...

    def load_repository_subjects(
        self,
        repository_id: str,
        bounds: QueryBounds,
        offset: int = 0,
    ) -> SubjectPage:
        """Load a bounded page of persisted semantic subjects.

        This reads the canonical semantic store only; it is not structural
        repository enumeration.
        """
        ...

    def count_repository_subjects(self, repository_id: str) -> int:
        """Count persisted semantic subjects for report bounds."""
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

    def load_evidence_records(
        self,
        repository_id: str,
        evidence_ids: tuple[str, ...],
    ) -> tuple[EvidenceDependency, ...]:
        """Dependency rows by evidence id (cross-unit citation support).

        Returns recorded rows for established evidence; unknown ids are
        simply absent (the service rejects them as unknown). No semantic
        judgment — rows carry previously validated observations.
        """
        ...

    def load_coverage_dependencies(
        self,
        repository_id: str,
        scope_subjects: tuple[SubjectId, ...],
    ) -> tuple[CoverageDependency, ...]:
        ...

    def load_question_coverages(
        self,
        repository_id: str,
        scope_root: SubjectId | None,
        subject_ids: tuple[SubjectId, ...],
        bounds: QueryBounds,
    ) -> tuple[InterpretationCoverage, ...]:
        """Exact root/subject/question coverage reads (Addendum B B-01)."""
        ...

    def load_all_question_coverages(
        self,
        repository_id: str,
        scope_root: SubjectId | None,
        subject_ids: tuple[SubjectId, ...],
    ) -> tuple[InterpretationCoverage, ...]:
        """Unbounded coverage reads for reconciliation decisions only.

        Query/paging paths must use the bounded variant. Retirement and
        withdrawal fanout must use this variant so no owning question
        is silently missed; callers defer when the total exceeds the
        operation bounds (Addendum B B-03).
        """
        ...

    def count_question_coverages(
        self,
        repository_id: str,
        scope_root: SubjectId | None,
        subject_ids: tuple[SubjectId, ...],
    ) -> int:
        """Count coverages matching the filter (bounds-safety check)."""
        ...

    def load_premise_dependents(
        self,
        repository_id: str,
        premise_refs: tuple[ClaimRef | RelationshipRef, ...],
    ) -> tuple[ClaimRef | RelationshipRef, ...]:
        """Reverse premise lookup derived from SemanticBasis.input_refs."""
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

    def load_target_association(
        self, repository_id: str, target_id: TargetId
    ) -> TargetAssociation | None:
        """Load one target-accounting association; expired reads as absent."""
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
