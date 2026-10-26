"""SemanticStore port (plan §5.5).

Canonical domain types directly — no store DTO layer is permitted.
The SQLite implementation (Phase 1.7) may normalize physically, but no
second semantic model may be introduced.
"""

import dataclasses as _dataclasses
import enum as _enum
import typing as _typing

from span.core.model import (
    CanonicalIndexBatch,
    ClaimKind,
    ClaimPage,
    ClaimRef,
    CoverageDependency,
    EvidenceDependency,
    EvidenceRef,
    EvidenceScope,
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
    SemanticRelationship,
    StoreWriteResult,
    Subject,
    SubjectKind,
    SubjectPage,
    SubjectId,
    TargetAssociation,
    TargetId,
    VerificationRecord,
)
from span.ports.structural import StructuralDirection


class FactKind(_enum.Enum):
    """What kind of fact a stored row is (D17).

    The kind fixes identity, what supersede means, and what the terminal
    is. It is declared for every table and checked against the physical
    schema, so a carrier cannot be added without answering the question.
    """

    OBSERVATION = "OBSERVATION"
    STATE = "STATE"
    HANDLE = "HANDLE"


@_dataclasses.dataclass(frozen=True)
class FactDeclaration:
    """One table's declared fact kind, natural key, and writer.

    ``key_columns`` is the natural key for a STATE and empty for an
    OBSERVATION (content-addressed, no natural key). ``writer`` names the
    store-port method that produces the row: the upsert for a STATE, the
    insert for an OBSERVATION.
    """

    table: str
    kind: FactKind
    key_columns: tuple[str, ...]
    writer: str


#: Every table this store creates, with the kind of fact it holds.
STORE_FACT_DECLARATIONS: tuple[FactDeclaration, ...] = (
    FactDeclaration(
        "repositories",
        FactKind.STATE,
        ("repository_id",),
        "record_repository_initialization",
    ),
    FactDeclaration(
        "subjects",
        FactKind.STATE,
        ("repository_id", "locator", "kind"),
        "write_index_batch",
    ),
    FactDeclaration("claims", FactKind.OBSERVATION, (), "write_index_batch"),
    FactDeclaration("relationships", FactKind.OBSERVATION, (), "write_index_batch"),
    FactDeclaration(
        "evidence_dependencies",
        FactKind.STATE,
        ("semantic_id", "evidence_id"),
        "write_index_batch",
    ),
    FactDeclaration(
        "coverage_dependencies", FactKind.OBSERVATION, (), "write_index_batch"
    ),
    FactDeclaration(
        "question_coverages",
        FactKind.STATE,
        (
            "repository_id",
            "scope_root_locator",
            "scope_root_kind",
            "subject_locator",
            "subject_kind",
            "question_class",
            "question_slice",
        ),
        "write_index_batch",
    ),
    FactDeclaration(
        "premise_dependents",
        FactKind.STATE,
        ("repository_id", "premise_id", "dependent_id"),
        "write_index_batch",
    ),
    FactDeclaration(
        "question_result_refs",
        FactKind.STATE,
        (
            "repository_id",
            "scope_root_locator",
            "scope_root_kind",
            "subject_locator",
            "subject_kind",
            "question_class",
            "question_slice",
            "result_id",
        ),
        "write_index_batch",
    ),
    FactDeclaration(
        "conflict_records",
        FactKind.STATE,
        ("repository_id", "subject_locator", "left_id", "right_id"),
        "write_index_batch",
    ),
    # Store-owned operational state: the canonical root this store belongs
    # to. Schema version lives beside it as bootstrap metadata.
    FactDeclaration("meta", FactKind.STATE, ("key",), "record_repository_root"),
    FactDeclaration(
        "target_associations",
        FactKind.STATE,
        ("repository_id", "target_id"),
        "write_index_batch",
    ),
    FactDeclaration(
        "verification_records",
        FactKind.STATE,
        (
            "repository_id",
            "subject_locator",
            "subject_kind",
            "scope_fingerprint",
        ),
        "write_index_batch",
    ),
)


@_typing.runtime_checkable
class SemanticStore(_typing.Protocol):
    def load_subjects(
        self, repository_id: str, subject_ids: tuple[SubjectId, ...]
    ) -> tuple[Subject, ...]: ...

    def load_subjects_by_locator(
        self,
        repository_id: str,
        locator: str,
        expected_kinds: tuple[SubjectKind, ...],
        bounds: QueryBounds,
    ) -> SubjectPage:
        """Exact canonical-locator lookup ([design note I](docs/design-references.md#i) S1).

        Exact string equality against the stored canonical locator only.
        No normalization, no fuzzy matching. Kinds filtered before
        limiting, ordered by kind, one extra row to detect truncation.
        """
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

    def load_verification_record(
        self,
        repository_id: str,
        subject: SubjectId,
        scope_fingerprint: str,
    ) -> VerificationRecord | None:
        """The single current record for one (subject, verified scope)."""
        ...

    def repository_root(self, repository_id: str) -> str | None:
        """The canonical root recorded for this store, if any.

        One reader and one writer for provenance; no caller reads the store's
        metadata table directly.
        """
        ...

    def record_repository_root(self, repository_id: str, root: str) -> None:
        """Bind this store to a canonical root, or fail on a different one."""
        ...

    def load_subjects_in_scope(
        self,
        repository_id: str,
        scope: EvidenceScope,
        bounds: QueryBounds,
        after: tuple[str, str] | None = None,
    ) -> SubjectPage:
        """Load a bounded page of persisted subjects whose locator is in scope.

        Membership is the canonical ``evidence_scope_allows`` predicate:
        exact equality for evidence refs, and prefix membership on a path
        segment boundary for paths. Ordering is ``(locator, kind)`` and
        pagination is keyset, so consecutive pages are disjoint without an
        offset that can drift.

        ``after`` is the last ``(locator, kind)`` of the previous page; the
        caller derives it from the page it already received. No token is
        minted here: answer-level cursors belong to the service, which owns
        the single cursor grammar (D8).

        An empty scope is rejected. A scoped read is never a whole-repository
        read; use ``load_repository_subjects`` for that.
        """
        ...

    def count_subjects_in_scope(self, repository_id: str, scope: EvidenceScope) -> int:
        """Count persisted subjects whose locator is in ``scope``."""
        ...

    def count_question_dispositions(self, repository_id: str) -> dict[str, int]:
        """Persisted question-coverage counts by disposition (S8/D-10)."""
        ...

    def count_target_associations(self, repository_id: str) -> int:
        """Count active target associations (S8/D-10)."""
        ...

    def load_active_target_associations(
        self, repository_id: str
    ) -> tuple[TargetAssociation, ...]:
        """Load active target campaigns for bounded live inventory reads."""
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
    ) -> ClaimPage: ...

    def load_relationships(
        self,
        repository_id: str,
        subject_ids: tuple[SubjectId, ...],
        relationship_kinds: tuple[RelationshipKind, ...],
        direction: StructuralDirection,
        bounds: QueryBounds,
        page_token: str | None = None,
    ) -> RelationshipPage: ...

    def load_evidence_dependencies(
        self,
        repository_id: str,
        claim_or_relationship_ids: tuple[ClaimRef | RelationshipRef, ...],
    ) -> tuple[EvidenceDependency, ...]: ...

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
    ) -> tuple[CoverageDependency, ...]: ...

    def load_question_coverages(
        self,
        repository_id: str,
        scope_root: SubjectId | None,
        subject_ids: tuple[SubjectId, ...],
        bounds: QueryBounds,
    ) -> tuple[InterpretationCoverage, ...]:
        """Exact root/subject/question coverage reads ([design note B](docs/design-references.md#b) B-01)."""
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
        operation bounds ([design note B](docs/design-references.md#b) B-03).
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
    ) -> StoreWriteResult: ...

    def schema_version(self) -> SchemaVersion: ...

    def record_repository_initialization(
        self,
        state: RepositoryState,
        authority_seeds: tuple[EvidenceRef, ...],
    ) -> None:
        """Persist repository identity/state and configured authority seeds.

        One atomic row write by explicit initialization; read by status
        and hook paths to distinguish UNINITIALIZED from READY without
        implicit bootstrap (I-27), and by every later context open to
        rehydrate the repository's canonical authority seeds.
        """
        ...

    def load_repository_authority_seeds(
        self, repository_id: str
    ) -> tuple[EvidenceRef, ...]:
        """Persisted canonical authority seeds, or ``()`` when uninitialized.

        Malformed stored data fails closed; it never reads as empty.
        """
        ...

    def load_repository_state(self, repository_id: str) -> RepositoryState | None:
        """Current recorded state, or None when never initialized."""
        ...
