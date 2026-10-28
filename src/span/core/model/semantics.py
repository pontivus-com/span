"""Resolution requirements, questions, and coverage carriers.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import types as _types
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.claims import RelationshipKind
from span.core.model.primitives import (
    ClaimRef,
    EvidenceRef,
    EvidenceScope,
    Freshness,
    ProposedChange,
    QueryBounds,
    RelationshipRef,
    SemanticBasis,
    SubjectId,
    SubjectSelector,
    _require_non_empty,
    _require_non_negative_int,
)
from span.core.model.repository import StructuralDirection


class ResolutionKind(_enum.Enum):
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
    MISSING_PRECEDENCE = "MISSING_PRECEDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    UNVERIFIABLE_FRESHNESS = "UNVERIFIABLE_FRESHNESS"
    UNSUPPORTED_STRUCTURAL_CAPABILITY = "UNSUPPORTED_STRUCTURAL_CAPABILITY"
    MISSING_SEMANTIC_COVERAGE = "MISSING_SEMANTIC_COVERAGE"
    INCOMPLETE_SEMANTIC_SCOPE = "INCOMPLETE_SEMANTIC_SCOPE"


@_dataclass(frozen=True)
class ResolutionRequirement:
    kind: ResolutionKind
    subject_or_claim: SubjectId | ClaimRef | RelationshipRef | None = None
    description: str = ""
    supporting_context: tuple[ClaimRef | RelationshipRef | EvidenceRef, ...] = ()


class SemanticQuestionClass(_enum.Enum):
    """Closed CQ identifiers for question-scoped coverage ([design note B](docs/design-references.md#b))."""

    CQ_01 = "CQ_01"
    CQ_02 = "CQ_02"
    CQ_03 = "CQ_03"
    CQ_04 = "CQ_04"
    CQ_05 = "CQ_05"
    CQ_06 = "CQ_06"
    CQ_07 = "CQ_07"
    CQ_08 = "CQ_08"
    CQ_09 = "CQ_09"


class SemanticQuestionDisposition(_enum.Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    OPEN = "OPEN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@_dataclass(frozen=True)
class SemanticQuestionScope:
    """Immutable question identity ([design note B](docs/design-references.md#b) B-01)."""

    scope_root: SubjectId
    subject: SubjectId
    question_class: SemanticQuestionClass
    question_slice: str
    materiality_basis: str

    def __post_init__(self) -> None:
        _require_non_empty("question_slice", self.question_slice)
        _require_non_empty("materiality_basis", self.materiality_basis)


@_dataclass(frozen=True)
class SemanticQuestionSelection:
    """Host-owned narrowed question selection ([design note I](docs/design-references.md#i) S4 §5.4).

    Carries only slice/basis/anchors; the service derives scope_root,
    subject, question_class and constructs the full scope server-side.
    Slice nonempty and immutable once admitted. Basis empty means the
    service records the operation-derived default basis; a supplied
    basis is stored verbatim as explanatory metadata. Anchors are at
    most 8 literal retrieval substrings, each nonempty of at most 120
    characters; more or longer anchors reject deterministically. The
    service canonicalizes the slice verbatim (no paraphrase equivalence
    or synonym guessing) and rejects full-scope supply.
    """

    question_slice: str
    materiality_basis: str = ""
    question_anchors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("question_slice", self.question_slice)
        if len(self.question_anchors) > 8:
            raise ValueError("question_anchors holds at most 8 anchors")
        for anchor in self.question_anchors:
            if not anchor or len(anchor) > 120:
                raise ValueError(
                    "question anchor must be nonempty of at most " "120 characters"
                )


@_dataclass(frozen=True)
class QuestionEvidenceObservation:
    evidence_ref: EvidenceRef
    observed_fingerprint: str


@_dataclass(frozen=True)
class CandidateSemanticWithdrawal:
    target: ClaimRef | RelationshipRef
    basis: SemanticBasis
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.basis.summary:
            raise ValueError("withdrawal basis summary is empty")


@_dataclass(frozen=True)
class SemanticQuestionCoverageView:
    question: SemanticQuestionScope
    recorded_disposition: SemanticQuestionDisposition
    effective_disposition: SemanticQuestionDisposition
    freshness: Freshness
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    recovery: QuestionRecovery | None = None


class SemanticCoverageDisposition(_enum.Enum):
    """Repository-report state for one persisted semantic subject."""

    CURRENT = "CURRENT"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"
    UNASSESSED = "UNASSESSED"


@_dataclass(frozen=True)
class SemanticCoverageEntry:
    """Bounded read projection for one persisted semantic subject.

    Carries no requirements. A requirement belongs to the page-level list and
    names its subject through ``ResolutionRequirement.subject_or_claim``, so
    there is one owner and no nested copy to disagree with it.
    """

    subject: SubjectId
    disposition: SemanticCoverageDisposition
    semantic_item_count: int = 0
    current_item_count: int = 0
    stale_item_count: int = 0
    unverifiable_item_count: int = 0
    question_count: int = 0
    answered_question_count: int = 0
    pending_question_count: int = 0
    open_question_count: int = 0
    not_applicable_question_count: int = 0
    stale_effective_question_count: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        for name in (
            "semantic_item_count",
            "current_item_count",
            "stale_item_count",
            "unverifiable_item_count",
            "question_count",
            "answered_question_count",
            "pending_question_count",
            "open_question_count",
            "not_applicable_question_count",
            "stale_effective_question_count",
        ):
            _require_non_negative_int(name, getattr(self, name))


@_dataclass(frozen=True)
class CoveragePage:
    """The frontier subjects one answer carries, and nothing else.

    Every count is derived from ``entries``, so no stored number can disagree
    with the payload. Whether the frontier was cut is stated by the answer's
    ``bound_info``, not by a second flag here.
    """

    entries: tuple[SemanticCoverageEntry, ...] = ()

    def _disposition_count(self, disposition: SemanticCoverageDisposition) -> int:
        return sum(1 for entry in self.entries if entry.disposition is disposition)

    @property
    def returned_subject_count(self) -> int:
        return len(self.entries)

    @property
    def current_subject_count(self) -> int:
        return self._disposition_count(SemanticCoverageDisposition.CURRENT)

    @property
    def incomplete_subject_count(self) -> int:
        return self._disposition_count(SemanticCoverageDisposition.INCOMPLETE)

    @property
    def stale_subject_count(self) -> int:
        return self._disposition_count(SemanticCoverageDisposition.STALE)

    @property
    def unverifiable_subject_count(self) -> int:
        return self._disposition_count(SemanticCoverageDisposition.UNVERIFIABLE)

    @property
    def unassessed_subject_count(self) -> int:
        return self._disposition_count(SemanticCoverageDisposition.UNASSESSED)

    @property
    def stale_effective_question_count(self) -> int:
        return sum(entry.stale_effective_question_count for entry in self.entries)


@_dataclass(frozen=True)
class RepositoryTotals:
    """Repository-wide numbers. Exact (SQL) unless a name says otherwise."""

    persisted_subject_count: int = 0
    pending_question_count: int = 0
    open_question_count: int = 0
    active_target_association_count: int = 0
    persisted_target_accounted_count: int = 0
    persisted_target_unresolved_count: int = 0
    #: Repository-wide, bounded-live. ``None`` means the live observation
    #: could not be established; the name carries the qualification.
    bounded_live_target_unaccounted_count: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "persisted_subject_count",
            "pending_question_count",
            "open_question_count",
            "active_target_association_count",
            "persisted_target_accounted_count",
            "persisted_target_unresolved_count",
        ):
            _require_non_negative_int(name, getattr(self, name))
        if self.bounded_live_target_unaccounted_count is not None:
            _require_non_negative_int(
                "bounded_live_target_unaccounted_count",
                self.bounded_live_target_unaccounted_count,
            )


@_dataclass(frozen=True)
class ScopeTotals:
    """Scope-wide numbers. Exact (scoped SQL) for the requested scope."""

    persisted_subject_count: int = 0

    def __post_init__(self) -> None:
        _require_non_negative_int(
            "persisted_subject_count", self.persisted_subject_count
        )


@_dataclass(frozen=True)
class RepositoryCoverageReport:
    """Repository coverage: global totals plus the current frontier page."""

    repository: RepositoryTotals = _field(default_factory=RepositoryTotals)
    page: CoveragePage = _field(default_factory=CoveragePage)


@_dataclass(frozen=True)
class ScopedCoverageReport:
    """Scoped coverage: scope totals plus the current frontier page.

    Has no repository-global field by construction, so a scoped answer cannot
    publish a repository-wide number.
    """

    scope: ScopeTotals = _field(default_factory=ScopeTotals)
    page: CoveragePage = _field(default_factory=CoveragePage)


QUESTION_CLASS_ASPECTS: _typing.Mapping[SemanticQuestionClass, tuple[str, ...]] = (
    _types.MappingProxyType(
        {
            SemanticQuestionClass.CQ_01: (
                "Purpose",
                "actual role",
                "principal participating subjects",
            ),
            SemanticQuestionClass.CQ_02: (
                "implementing components and associated subsystem responsibility",
            ),
            SemanticQuestionClass.CQ_03: (
                "actual producer/writer/judge/custodian",
                "contradictory or absent authority",
            ),
            SemanticQuestionClass.CQ_04: (
                "inputs/consumption",
                "transformation/production",
                "dependencies",
                "downstream consumers",
                "relevant branch/terminal paths",
            ),
            SemanticQuestionClass.CQ_05: (
                "crossing representation",
                "canonical governing contract",
                "transformation owner",
                "downstream receiver",
            ),
            SemanticQuestionClass.CQ_06: (
                "governing source",
                "declared status/precedence",
                "conflicts",
                "explicit absence when unestablished",
            ),
            SemanticQuestionClass.CQ_07: (
                "creation",
                "mutation",
                "persistence",
                "success",
                "failure",
                "abandonment/terminal behavior (as applicable)",
            ),
            SemanticQuestionClass.CQ_08: (
                "supported affected capabilities",
                "consumers/contracts",
                "relevant verification",
                "possible versus proven effects",
            ),
            SemanticQuestionClass.CQ_09: (
                "identified verification artifact and its actual execution currency",
                "or qualified missing proof",
            ),
        }
    )
)
QUESTION_CLASS_DEFAULT_SLICE: _typing.Mapping[SemanticQuestionClass, str] = (
    _types.MappingProxyType(
        {
            SemanticQuestionClass.CQ_01: (
                "What is this subject, what does it do, and what capability or "
                "concept does it belong to?"
            ),
            SemanticQuestionClass.CQ_02: (
                "Where and by which components is this subject implemented?"
            ),
            SemanticQuestionClass.CQ_03: (
                "Who or what owns, produces, writes, judges, or is responsible "
                "for this subject?"
            ),
            SemanticQuestionClass.CQ_04: (
                "What does this subject consume, produce, depend on, feed, "
                "contain, or participate in?"
            ),
            SemanticQuestionClass.CQ_05: (
                "Which meaningful boundaries does this subject cross, what "
                "representation crosses them, and who owns transformation?"
            ),
            SemanticQuestionClass.CQ_06: (
                "What authority, contract, invariant, decision, or configuration "
                "governs this subject?"
            ),
            SemanticQuestionClass.CQ_07: (
                "Where is this subject created, changed, persisted, terminated, "
                "failed, recovered, retained, or removed?"
            ),
            SemanticQuestionClass.CQ_08: (
                "What is materially affected by the proposed change to this " "subject?"
            ),
            SemanticQuestionClass.CQ_09: (
                "How is this subject proven or checked, and what verification is "
                "current?"
            ),
        }
    )
)


@_dataclass(frozen=True)
class ExplainReplay:
    """Recovery inputs for a question admitted by ``explain``."""

    target: SubjectSelector
    bounds: QueryBounds
    establish_baseline: bool = False
    question_selection: SemanticQuestionSelection | None = None


@_dataclass(frozen=True)
class ImpactReplay:
    """Recovery inputs for a question admitted by ``impact``."""

    target: SubjectSelector
    proposed_change: ProposedChange
    bounds: QueryBounds
    question_selection: SemanticQuestionSelection | None = None


@_dataclass(frozen=True)
class TraceReplay:
    """Recovery inputs for a question admitted by ``trace``."""

    target: SubjectSelector
    bounds: QueryBounds
    direction: StructuralDirection
    relationship_filter: tuple[RelationshipKind, ...] | None = None
    boundary_only: bool = False
    question_selection: SemanticQuestionSelection | None = None


@_dataclass(frozen=True)
class AuthorityReplay:
    """Recovery inputs for a question admitted by ``authority``."""

    target: SubjectSelector
    bounds: QueryBounds
    question_selection: SemanticQuestionSelection | None = None


QuestionRecovery = ExplainReplay | ImpactReplay | TraceReplay | AuthorityReplay


@_dataclass(frozen=True)
class InterpretationCoverage:
    """Single canonical persisted question record ([design note B](docs/design-references.md#b) B-01)."""

    subjects: tuple[SubjectId, ...] = ()
    question_slice: str = ""
    evidence_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    question: SemanticQuestionScope | None = None
    disposition: SemanticQuestionDisposition = SemanticQuestionDisposition.PENDING
    result_refs: tuple[ClaimRef | RelationshipRef, ...] = ()
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    disposition_basis: str = ""
    question_evidence: tuple[QuestionEvidenceObservation, ...] = ()
    recovery: QuestionRecovery | None = None

    def __post_init__(self) -> None:
        if self.disposition is SemanticQuestionDisposition.OPEN:
            if not self.resolution_requirements:
                raise ValueError("OPEN coverage requires resolution_requirements")
        if self.disposition is SemanticQuestionDisposition.NOT_APPLICABLE:
            if self.result_refs:
                raise ValueError("NOT_APPLICABLE coverage requires empty result_refs")
