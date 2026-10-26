"""Interpretation exchange carriers: decisions, candidates, requests.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.primitives import (
    BoundInfo,
    CandidateAuthority,
    ClaimRef,
    DeclaredPrecedence,
    DerivationKind,
    EvidenceId,
    EvidenceRef,
    EvidenceScope,
    Freshness,
    ProposedChange,
    QueryBounds,
    RelationshipRef,
    SemanticBasis,
    SemanticIntent,
    Subject,
    SubjectId,
    SubjectKind,
    _require_non_empty,
)
from span.core.model.claims import (
    CandidateAssertionNature,
    ClaimKind,
    ExecutedVerification,
    PurposeValue,
    RecordedConflict,
    RelationshipKind,
    SemanticClaim,
    SemanticRelationship,
    TypedClaimValue,
    VerificationRecord,
    _require_claim_value,
)
from span.core.model.semantics import (
    CandidateSemanticWithdrawal,
    InterpretationCoverage,
    ResolutionRequirement,
    SemanticQuestionDisposition,
    SemanticQuestionScope,
)
from span.core.model.repository import (
    EvidenceUnit,
    StructuralObservation,
)
from span.core.model.targets import (
    TargetAssociation,
    TargetId,
)


@_dataclass(frozen=True)
class SemanticQuestionDecision:
    """Agent-owned decision about one already-bound question.

    Carries only the semantics the interpreting agent owns: disposition,
    selected support scope, typed requirements, and the explicit basis.
    Question identity, subjects, slice, completion, result refs, and
    evidence observations are Span-owned and derived at materialization.
    """

    disposition: SemanticQuestionDisposition
    evidence_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    disposition_basis: str = ""


@_dataclass(frozen=True)
class ProposedSemanticQuestion:
    """Agent nomination of another material semantic question.

    The canonical scope expresses the identity/materiality the agent is
    introducing; the decision carries its disposition. Used only when the
    agent admits a new question or explicitly selects one already
    persisted. Not a persisted coverage type.
    """

    question: SemanticQuestionScope
    decision: SemanticQuestionDecision


@_dataclass(frozen=True)
class CandidateSubject:
    """Agent-proposed semantic-only subject (plan §4.11)."""

    provisional_locator: str = ""
    kind: SubjectKind = SubjectKind.OTHER
    display_name: str = ""
    declared_kind: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.SEMANTIC_INTERPRETATION)
    )


@_dataclass(frozen=True)
class CandidateSemanticClaim:
    candidate_key: str = ""
    subject: SubjectId = _field(
        default_factory=lambda: SubjectId(
            repository_id="unset",
            subject_kind=SubjectKind.OTHER,
            canonical_locator="unset",
        )
    )
    kind: ClaimKind = ClaimKind.PURPOSE
    value: TypedClaimValue = _field(default_factory=lambda: PurposeValue(summary=""))
    assertion_nature: CandidateAssertionNature = _field(kw_only=True)  # type: ignore[assignment]
    evidence: tuple[EvidenceRef, ...] = ()
    candidate_authority: CandidateAuthority | None = None
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.SEMANTIC_INTERPRETATION)
    )

    def __post_init__(self) -> None:
        _require_claim_value(self.kind, self.value)


@_dataclass(frozen=True)
class CandidateSemanticRelationship:
    candidate_key: str = ""
    source: SubjectId = _field(
        default_factory=lambda: SubjectId(
            repository_id="unset",
            subject_kind=SubjectKind.OTHER,
            canonical_locator="unset",
        )
    )
    kind: RelationshipKind = RelationshipKind.DEPENDS_ON
    target: SubjectId = _field(
        default_factory=lambda: SubjectId(
            repository_id="unset",
            subject_kind=SubjectKind.OTHER,
            canonical_locator="unset",
        )
    )
    assertion_nature: CandidateAssertionNature = _field(kw_only=True)  # type: ignore[assignment]
    evidence: tuple[EvidenceRef, ...] = ()
    candidate_authority: CandidateAuthority | None = None
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.SEMANTIC_INTERPRETATION)
    )


@_dataclass(frozen=True)
class CandidateSemanticConflict:
    """Agent-proposed free-text contradiction (plan §4.11/§6.4)."""

    left_key: str = ""
    right_key: str = ""
    candidate_precedence: DeclaredPrecedence | None = None
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.SEMANTIC_INTERPRETATION)
    )


@_dataclass(frozen=True)
class TaskBrief:
    """Slice-derived investigation brief (addendum D §8.1, ACT-D-13).

    Deterministic content only, drawn from two sources:

    - contract: C-04 material aspects for the bound question class and the
      compact SA-1–SA-7 analysis card;
    - instance: the exact admitted slice's recorded OPEN/PENDING
      requirements for this scope (quoted from store, never
      inferred) and the scope boundaries.

    Brief content guides the agent; it never classifies, scores, or
    validates — validation ignores the brief entirely.
    """

    objective: str = ""
    scope_boundaries: tuple[str, ...] = ()
    evidence_authority: tuple[str, ...] = ()
    material_path: tuple[str, ...] = ()
    semantic_result: tuple[str, ...] = ()
    adversarial_checks: tuple[str, ...] = ()
    readback: tuple[str, ...] = ()
    material_aspects: tuple[str, ...] = ()
    open_requirements: tuple[ResolutionRequirement, ...] = ()
    open_handling: tuple[str, ...] = ()
    submission_rules: tuple[str, ...] = ()


TASK_BRIEF_OPEN_HANDLING: tuple[str, ...] = (
    "Preserve unexamined or unsupported aspects as OPEN/PENDING with "
    "typed ResolutionRequirements; never narrow the slice silently.",
    "A deliberately narrowed question is a new exact "
    "SemanticQuestionScope; it must not silently replace or retire "
    "the broader original.",
)
TASK_BRIEF_SUBMISSION_RULES: tuple[str, ...] = (
    "ANSWERED only when the admitted slice has been examined and its "
    "material aspects are substantiated.",
    "Do not declare a parent question ANSWERED merely because OPEN "
    "follow-ups exist.",
    "Submit one strict canonical result with an explicit question " "disposition.",
)
TASK_BRIEF_MATERIAL_PATH: tuple[str, ...] = (
    "Trace input → producer → transformation/state → consumer/output → "
    "terminal/failure.",
    "Account only for legs material to this exact question slice.",
    "Request the material input, producer, transformation, carrier/state, "
    "consumer, failure branch, and terminal outcome for the execution path.",
)
TASK_BRIEF_SEMANTIC_RESULT: tuple[str, ...] = (
    "Use existing typed claims and relationships only.",
    "Give each asserted result admissible evidence and distinguish observed "
    "behavior from governing intent.",
    "When the admitted evidence establishes that the examined subject "
    "participates in a larger coherent semantic context, preserve that "
    "membership using the existing CAPABILITY_MEMBERSHIP claim or MEMBER_OF "
    "relationship. Never infer membership from directory structure alone.",
)
TASK_BRIEF_ADVERSARIAL_CHECKS: tuple[str, ...] = (
    "Check alternate owner or authority, contradiction, and omitted " "participants.",
    "Check terminal/failure paths, stale premises, unsupported routes, and "
    "missing verification.",
)
TASK_BRIEF_READBACK: tuple[str, ...] = (
    "State what a fresh query can retrieve and what still requires " "interpretation.",
    "Do not claim useful completion unless the canonical result is readable "
    "from a fresh interaction.",
)


@_dataclass(frozen=True)
class TaskEvidence:
    """The bounded material one task may interpret.

    Grouped so the request carries one evidence concern rather than three
    parallel collections that must always travel together.
    """

    evidence_units: tuple[EvidenceUnit, ...] = ()
    structural_observations: tuple[StructuralObservation, ...] = ()
    identity_bindings: tuple[SubjectId, ...] = ()


@_dataclass(frozen=True)
class PriorContext:
    """Persisted items the task reasons against."""

    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()


@_dataclass(frozen=True)
class AllowedKinds:
    """The vocabularies an agent may use for this task."""

    claim_kinds: tuple[ClaimKind, ...] = _field(
        default_factory=lambda: tuple(ClaimKind)
    )
    relationship_kinds: tuple[RelationshipKind, ...] = _field(
        default_factory=lambda: tuple(RelationshipKind)
    )


@_dataclass(frozen=True)
class SemanticInterpretationRequest:
    repository_id: str
    subjects: tuple[Subject, ...]
    task_evidence: TaskEvidence
    # Required, never defaulted: every interpretation task carries its
    # slice-derived brief (no brief-less path, no dual semantics).
    brief: TaskBrief
    # The exact user-directed boundary, when this task belongs to target
    # establishment. This is separate from ``subjects``: a structural
    # anchor is a bounded exchange input, not the semantic target.
    target_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    operation_intent: SemanticIntent = SemanticIntent.EXPLAIN
    question_slice: str = ""
    proposed_change: ProposedChange | None = None
    bounds: QueryBounds = _field(
        default_factory=lambda: QueryBounds(50, 2, 8, 24, 96_000, 64, 64)
    )
    question: SemanticQuestionScope | None = None
    prior_context: PriorContext = _field(default_factory=PriorContext)
    analysis_obligations: tuple[str, ...] = ()
    target_id: TargetId | None = None
    discovery_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    allowed_kinds: AllowedKinds = _field(default_factory=AllowedKinds)

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)


SA_ANALYSIS_OBLIGATIONS: tuple[str, ...] = (
    "SA-1: bind the exact SubjectId and SemanticQuestionScope; do not "
    "broaden or replace the admitted slice silently.",
    "SA-2: compare implementation with contracts, records, config, tests "
    "and authority; distinguish observed behavior from governing intent.",
    "SA-3: trace input, producer, transformations, state, consumer, "
    "error/terminal paths and execution conditions; no route from adjacency.",
    "SA-4: establish purpose, responsibility, ownership, representation, "
    "boundary, lifecycle, invariant, verification and dependencies in "
    "existing kinds only.",
    "SA-5: adversarially test against contradictions, alternate owners, "
    "missing participants, branch paths and stale premises; qualify "
    "uncertainty.",
    "SA-6: submit an explicit ANSWERED, OPEN, PENDING, or NOT_APPLICABLE "
    "disposition with typed requirements for gaps.",
    "SA-7: perform fresh readback and distinguish persisted answers from "
    "new interpretation.",
)


@_dataclass(frozen=True)
class SemanticInterpretationResult:
    claims: tuple[CandidateSemanticClaim, ...] = ()
    relationships: tuple[CandidateSemanticRelationship, ...] = ()
    governing_source_refs: tuple[EvidenceRef, ...] = ()
    diagnostics: tuple[str, ...] = ()
    candidate_subjects: tuple[CandidateSubject, ...] = ()
    candidate_conflicts: tuple[CandidateSemanticConflict, ...] = ()
    question_decision: SemanticQuestionDecision | None = None
    proposed_questions: tuple[ProposedSemanticQuestion, ...] = ()
    candidate_withdrawals: tuple[CandidateSemanticWithdrawal, ...] = ()
    proposed_target_questions: tuple[SemanticQuestionScope, ...] = ()
    #: Executed verification runs submitted with the links they support.
    verification_records: tuple[ExecutedVerification, ...] = ()


@_dataclass(frozen=True)
class ClaimPage:
    items: tuple[SemanticClaim, ...]
    bound_info: BoundInfo


@_dataclass(frozen=True)
class RelationshipPage:
    items: tuple[SemanticRelationship, ...]
    bound_info: BoundInfo


@_dataclass(frozen=True)
class SubjectPage:
    items: tuple[Subject, ...]
    bound_info: BoundInfo


@_dataclass(frozen=True)
class EvidenceDependency:
    semantic_id: ClaimRef | RelationshipRef
    evidence_ref: EvidenceRef
    observed_fingerprint: str


@_dataclass(frozen=True)
class FreshnessUpdate:
    semantic_id: ClaimRef | RelationshipRef
    freshness: Freshness


@_dataclass(frozen=True)
class SeedFingerprint:
    evidence_id: EvidenceId
    locator: str = ""
    fingerprint: str = ""


@_dataclass(frozen=True)
class CoverageDependency:
    """Discovery-scope record behind one materialized unit (plan §4.11/§8.5).

    `inventory_fingerprint` covers inventory MEMBERSHIP (which sources
    exist), not content: gained/lost sources invalidate discovery,
    while known-source content changes stay per-item (MI-07).
    """

    scope_subjects: tuple[SubjectId, ...] = ()
    discovery_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    inventory_fingerprint: str = ""
    seed_fingerprints: tuple[SeedFingerprint, ...] = ()
    observed_at: _datetime.datetime = _field(
        default_factory=lambda: _datetime.datetime.now(_datetime.timezone.utc)
    )
    question: SemanticQuestionScope | None = None


@_dataclass(frozen=True)
class CanonicalIndexBatch:
    subjects: tuple[Subject, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    evidence_dependencies: tuple[EvidenceDependency, ...] = ()
    coverage_dependencies: tuple[CoverageDependency, ...] = ()
    coverage: tuple[InterpretationCoverage, ...] = ()
    retires_claims: tuple[ClaimRef, ...] = ()
    retires_relationships: tuple[RelationshipRef, ...] = ()
    conflicts: tuple[RecordedConflict, ...] = ()
    target_associations: tuple[TargetAssociation, ...] = ()
    verification_records: tuple[VerificationRecord, ...] = ()


@_dataclass(frozen=True)
class StoreWriteResult:
    written_count: int = 0


@_dataclass(frozen=True)
class SchemaVersion:
    value: int = 0
