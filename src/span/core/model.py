"""Span canonical semantic vocabulary and typed model (plan §4).

This module closes the v0.2 claim-taxonomy ambiguity: every §4 enum and
carrier is defined here exactly once. Later phases implement *behavior*
over these types but must not invent competing shapes (plan I-03/I-04).

Scope notes (phase-boundary decisions, all documented):

- ``StructuralEdgeKind`` is defined in plan §5.2 but referenced by §4.11
  carriers, so it lives here as canonical vocabulary. Phase 1.2 ports
  reference it; they do not redefine it.
- ``QueryBounds`` / ``ServiceBoundsPolicy`` (plan §5.1) are shared *value*
  types, not port interfaces, so they live here. Phase 1.2 defines the
  port *operations* that consume them.
- The ``edges()`` direction vocabulary (``UPSTREAM | DOWNSTREAM | BOTH``)
  and the ``UNSUPPORTED_CAPABILITY`` outcome belong to port operations
  and are defined with the ports in Phase 1.2, not here.
- Anonymous inline vocabularies in §4 receive explicit Python names
  (``RepresentationDirection``, ``LifecyclePhase``, ``ResolutionAmbiguity``,
  ``CandidateRankBasis``, ``FreshnessState``). The *member sets* are
  exactly the plan's; only the container names are assigned.

Strict-typing rules (plan §3.4 / I-18):

- No ``Any`` for semantic values; no ``dict[str, Any]`` semantic state.
- ``tuple`` (immutable) for all collections; ``Optional`` only where the
  plan marks a field ``| None``.
- Constructor validation below enforces *stated* plan rules only
  (non-empty nominal ids, ``OTHER``/``declared_kind``, precedence shape
  rules, bound positivity, ``ClaimKind``↔value mapping, intent↔content
  correspondence). Semantic validation (authority/trust/conflict) is
  Phase 1.3+ behavior, not construction.

Canonical serialization (``to_canonical`` / ``from_canonical``) is a
deterministic, mechanical encoding owned by these carriers: dataclasses
encode with an explicit ``$type`` tag (never guessed), enums by value,
datetimes as ISO-8601 strings. It introduces no semantic decisions.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import hashlib as _hashlib
import json as _json
import types as _types
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from dataclasses import fields as _fields
from dataclasses import MISSING as _MISSING

__all__ = [
    # §4.1 subjects
    "SubjectKind",
    "SubjectId",
    "Subject",
    "SubjectSelector",
    "SubjectCandidate",
    "CandidateRankBasis",
    "ResolutionAmbiguity",
    "SubjectResolution",
    # §4.3 claim kinds
    "ClaimKind",
    # §4.4 typed claim values
    "PurposeValue",
    "CapabilityMembershipValue",
    "ResponsibilityValue",
    "OwnershipRole",
    "OwnershipExclusivity",
    "OwnershipCustodyValue",
    "RepresentationDirection",
    "RepresentationContractValue",
    "TransformationOwnershipValue",
    "InvariantConstraintValue",
    "ConfigurationEnvironmentValue",
    "LifecyclePhase",
    "LifecycleStateValue",
    "VerificationKind",
    "VerificationCurrency",
    "VerificationValue",
    "TypedClaimValue",
    "CLAIM_VALUE_TYPE",
    # §4.5 relationships
    "RelationshipKind",
    # §4.6 evidence / authority / trust / freshness
    "EvidenceSourceKind",
    "AuthorityKind",
    "AuthorityStatus",
    "AuthorityApplicability",
    "PrecedenceKind",
    "DeclaredPrecedence",
    "EvidenceRef",
    "AuthorityBinding",
    "FreshnessState",
    "Freshness",
    "TrustState",
    # §4.7 carriers, ids, refs
    "ClaimId",
    "RelationshipId",
    "AnswerId",
    "EvidenceId",
    "ClaimRef",
    "RelationshipRef",
    "AnswerRef",
    "EvidenceIdRef",
    "DerivationKind",
    "SemanticBasis",
    "SemanticClaim",
    "SemanticRelationship",
    "SemanticConflict",
    "RecordedConflict",
    # §4.8 readiness / hooks
    "RepositoryReadiness",
    "HookStatusNotice",
    # §4.9 basis / resolution / change
    "ResolutionKind",
    "ResolutionRequirement",
    "SemanticQuestionClass",
    "SemanticQuestionDisposition",
    "SemanticQuestionScope",
    "QuestionEvidenceObservation",
    "CandidateSemanticWithdrawal",
    "SemanticQuestionCoverageView",
    "SemanticCoverageDisposition",
    "SemanticCoverageEntry",
    "SemanticCoverageReport",
    "ChangeKind",
    "ProposedChange",
    "ChangeCondition",
    "ImpactEstablishment",
    "ImpactItem",
    "FreshnessItem",
    "AuthoritySupport",
    "CandidateAuthority",
    # §4.10 answer
    "SemanticIntent",
    "ExplainContent",
    "TraceContent",
    "ImpactContent",
    "AuthorityContent",
    "StatusContent",
    "SemanticContent",
    "SemanticAnswer",
    "INTENT_CONTENT_TYPE",
    # §4.11 supporting contracts
    "RepositoryState",
    "EvidenceUnit",
    "StructuralObservation",
    "StructuralEdgeKind",
    "StructuralEdge",
    "StructuralLocation",
    "StructuralReachNode",
    "BoundInfo",
    "EvidenceScope",
    "StatusMode",
    "SubjectPage",
    "StructuralLocationPage",
    "StructuralEdgePage",
    "StructuralReachPage",
    "EvidenceInventoryItem",
    "EvidenceInventoryPage",
    "EvidenceSelection",
    "CandidateSemanticClaim",
    "CandidateSemanticRelationship",
    "CandidateSubject",
    "CandidateSemanticConflict",
    "SemanticInterpretationRequest",
    "SemanticInterpretationResult",
    "SA_ANALYSIS_OBLIGATIONS",
    "TaskBrief",
    "QUESTION_CLASS_ASPECTS",
    "TASK_BRIEF_MATERIAL_PATH",
    "TASK_BRIEF_SEMANTIC_RESULT",
    "TASK_BRIEF_ADVERSARIAL_CHECKS",
    "TASK_BRIEF_READBACK",
    "TASK_BRIEF_OPEN_HANDLING",
    "TASK_BRIEF_SUBMISSION_RULES",
    "ClaimPage",
    "RelationshipPage",
    "EvidenceDependency",
    "FreshnessUpdate",
    "SeedFingerprint",
    "CoverageDependency",
    "InterpretationCoverage",
    "TargetId",
    "TargetInventoryAccount",
    "TargetAssociation",
    "canonicalize_target_scope",
    "derive_target_id",
    "target_inventory_fingerprint",
    "StructuralLocateMode",
    "StructuralLocateMatch",
    "ScopeCoverage",
    "COVERAGE_DETAIL_TOKENS",
    "StructuralLocateEntry",
    "StructuralLocateResult",
    "StructuralNeighborsResult",
    "StructuralSearchHit",
    "StructuralSearchPage",
    "StructuralOutlineEntry",
    "StructuralOutlinePage",
    "StructuralFreshnessReport",
    "CanonicalIndexBatch",
    "StoreWriteResult",
    "SchemaVersion",
    # §5.1 shared bounds value types
    "QueryBounds",
    "ServiceBoundsPolicy",
    # canonical serialization
    "to_canonical",
    "from_canonical",
    "CanonicalDecodeError",
]


# ---------------------------------------------------------------------------
# Construction-validation helpers (stated plan rules only)
# ---------------------------------------------------------------------------

def _require_non_empty(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive int")
    return value


def _require_non_negative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int")
    return value


# ---------------------------------------------------------------------------
# §4.1 Subject kinds
# ---------------------------------------------------------------------------

class SubjectKind(_enum.Enum):
    REPOSITORY = "REPOSITORY"
    SUBSYSTEM = "SUBSYSTEM"
    COMPONENT = "COMPONENT"
    CAPABILITY = "CAPABILITY"
    CODE_SYMBOL = "CODE_SYMBOL"
    CONTRACT = "CONTRACT"
    BOUNDARY = "BOUNDARY"
    REPRESENTATION = "REPRESENTATION"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENT = "DOCUMENT"
    TEST_OR_GATE = "TEST_OR_GATE"
    SURFACE = "SURFACE"
    FIELD = "FIELD"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    OTHER = "OTHER"


@_dataclass(frozen=True)
class SubjectId:
    """Canonical subject identity: repository_id + kind + locator (§4.2)."""

    repository_id: str
    subject_kind: SubjectKind
    canonical_locator: str

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        _require_non_empty("canonical_locator", self.canonical_locator)


@_dataclass(frozen=True)
class Subject:
    subject_id: SubjectId
    display_name: str
    declared_kind: str | None

    def __post_init__(self) -> None:
        # §4.1: OTHER is allowed only with a non-empty declared_kind.
        if self.subject_id.subject_kind is SubjectKind.OTHER:
            if self.declared_kind is None:
                raise ValueError("declared_kind is required when kind is OTHER")
            _require_non_empty("declared_kind", self.declared_kind)


@_dataclass(frozen=True)
class SubjectSelector:
    exact_subject_id: SubjectId | None
    name_or_locator: str | None
    expected_kinds: tuple[SubjectKind, ...] = ()
    retrieval_scope_hint: str | None = None


class CandidateRankBasis(_enum.Enum):
    EXACT_LOCATOR = "EXACT_LOCATOR"
    EXACT_DECLARATION = "EXACT_DECLARATION"
    EXACT_NAME = "EXACT_NAME"
    PARTIAL_NAME = "PARTIAL_NAME"
    STRUCTURAL_PROXIMITY = "STRUCTURAL_PROXIMITY"


class ResolutionAmbiguity(_enum.Enum):
    """Named container for the §4.11 SubjectResolution.ambiguity vocabulary."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@_dataclass(frozen=True)
class SubjectCandidate:
    subject: Subject
    structural_evidence: tuple[EvidenceRef, ...] = ()
    rank_basis: CandidateRankBasis = CandidateRankBasis.STRUCTURAL_PROXIMITY


@_dataclass(frozen=True)
class SubjectResolution:
    candidates: tuple[SubjectCandidate, ...]
    ambiguity: ResolutionAmbiguity
    bound_info: BoundInfo


# ---------------------------------------------------------------------------
# §4.3 Claim kinds (closed in v0.5)
# ---------------------------------------------------------------------------

class ClaimKind(_enum.Enum):
    PURPOSE = "PURPOSE"
    CAPABILITY_MEMBERSHIP = "CAPABILITY_MEMBERSHIP"
    RESPONSIBILITY = "RESPONSIBILITY"
    OWNERSHIP_CUSTODY = "OWNERSHIP_CUSTODY"
    REPRESENTATION_CONTRACT = "REPRESENTATION_CONTRACT"
    TRANSFORMATION_OWNERSHIP = "TRANSFORMATION_OWNERSHIP"
    INVARIANT_CONSTRAINT = "INVARIANT_CONSTRAINT"
    CONFIGURATION_ENVIRONMENT = "CONFIGURATION_ENVIRONMENT"
    LIFECYCLE_STATE = "LIFECYCLE_STATE"
    VERIFICATION = "VERIFICATION"


# ---------------------------------------------------------------------------
# §4.4 Typed claim values (exactly one carrier per ClaimKind)
# ---------------------------------------------------------------------------

@_dataclass(frozen=True)
class PurposeValue:
    summary: str
    capability_refs: tuple[SubjectId, ...] = ()


@_dataclass(frozen=True)
class CapabilityMembershipValue:
    parent: SubjectId
    membership_role: str | None = None


@_dataclass(frozen=True)
class ResponsibilityValue:
    responsibility: str
    scope: str | None = None


class OwnershipRole(_enum.Enum):
    OWNER = "OWNER"
    CUSTODIAN = "CUSTODIAN"
    WRITER = "WRITER"
    PRODUCER = "PRODUCER"
    JUDGE = "JUDGE"


class OwnershipExclusivity(_enum.Enum):
    EXCLUSIVE = "EXCLUSIVE"
    NON_EXCLUSIVE = "NON_EXCLUSIVE"
    UNKNOWN = "UNKNOWN"


@_dataclass(frozen=True)
class OwnershipCustodyValue:
    owner: SubjectId
    role: OwnershipRole
    exclusivity: OwnershipExclusivity
    scope: str | None = None


class RepresentationDirection(_enum.Enum):
    """Named container for the §4.4 representation direction vocabulary."""

    SOURCE = "SOURCE"
    DESTINATION = "DESTINATION"
    BIDIRECTIONAL = "BIDIRECTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@_dataclass(frozen=True)
class RepresentationContractValue:
    representation_name: str
    contract_ref: SubjectId | None = None
    direction: RepresentationDirection = RepresentationDirection.NOT_APPLICABLE
    serialization_or_shape_rule: str | None = None


@_dataclass(frozen=True)
class TransformationOwnershipValue:
    transformer: SubjectId
    source_representation: SubjectId | None = None
    destination_representation: SubjectId | None = None
    responsibility: str = ""


@_dataclass(frozen=True)
class InvariantConstraintValue:
    statement: str
    applicability: str | None = None


@_dataclass(frozen=True)
class ConfigurationEnvironmentValue:
    concern: str
    configuration_source: SubjectId | None = None
    applicability: str | None = None


class LifecyclePhase(_enum.Enum):
    """Named container for the §4.4 lifecycle phase vocabulary."""

    CREATE = "CREATE"
    USE = "USE"
    CHANGE = "CHANGE"
    PERSIST = "PERSIST"
    TERMINAL = "TERMINAL"
    FAIL = "FAIL"
    RECOVER = "RECOVER"
    ABANDON = "ABANDON"
    REPLAY = "REPLAY"
    RETAIN = "RETAIN"
    REMOVE = "REMOVE"
    OTHER = "OTHER"


@_dataclass(frozen=True)
class LifecycleStateValue:
    phase: LifecyclePhase
    description: str = ""
    persistence_ref: SubjectId | None = None
    retention_or_expiry: str | None = None


class VerificationKind(_enum.Enum):
    TEST = "TEST"
    GATE = "GATE"
    REVIEW = "REVIEW"
    OTHER = "OTHER"


class VerificationCurrency(_enum.Enum):
    CANDIDATE = "CANDIDATE"
    CURRENT_PASS = "CURRENT_PASS"
    CURRENT_FAIL = "CURRENT_FAIL"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@_dataclass(frozen=True)
class VerificationValue:
    verification_ref: SubjectId
    kind: VerificationKind
    currency: VerificationCurrency
    observed_revision: str | None = None


TypedClaimValue = _typing.Union[
    PurposeValue,
    CapabilityMembershipValue,
    ResponsibilityValue,
    OwnershipCustodyValue,
    RepresentationContractValue,
    TransformationOwnershipValue,
    InvariantConstraintValue,
    ConfigurationEnvironmentValue,
    LifecycleStateValue,
    VerificationValue,
]

#: §4.4: every ClaimKind maps to exactly one typed value carrier.
CLAIM_VALUE_TYPE: dict[ClaimKind, type] = {
    ClaimKind.PURPOSE: PurposeValue,
    ClaimKind.CAPABILITY_MEMBERSHIP: CapabilityMembershipValue,
    ClaimKind.RESPONSIBILITY: ResponsibilityValue,
    ClaimKind.OWNERSHIP_CUSTODY: OwnershipCustodyValue,
    ClaimKind.REPRESENTATION_CONTRACT: RepresentationContractValue,
    ClaimKind.TRANSFORMATION_OWNERSHIP: TransformationOwnershipValue,
    ClaimKind.INVARIANT_CONSTRAINT: InvariantConstraintValue,
    ClaimKind.CONFIGURATION_ENVIRONMENT: ConfigurationEnvironmentValue,
    ClaimKind.LIFECYCLE_STATE: LifecycleStateValue,
    ClaimKind.VERIFICATION: VerificationValue,
}


def _require_claim_value(kind: ClaimKind, value: TypedClaimValue) -> TypedClaimValue:
    expected = CLAIM_VALUE_TYPE[kind]
    if not isinstance(value, expected):
        raise ValueError(
            f"value for {kind.value} must be {expected.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


# ---------------------------------------------------------------------------
# §4.5 Relationship kinds (closed in v0.5)
# ---------------------------------------------------------------------------

class RelationshipKind(_enum.Enum):
    MEMBER_OF = "MEMBER_OF"
    IMPLEMENTS = "IMPLEMENTS"
    PRODUCES = "PRODUCES"
    CARRIES = "CARRIES"
    CONSUMES = "CONSUMES"
    DEPENDS_ON = "DEPENDS_ON"
    CROSSES_BOUNDARY = "CROSSES_BOUNDARY"
    REPRESENTS_AS = "REPRESENTS_AS"
    TRANSFORMS_TO = "TRANSFORMS_TO"
    GOVERNED_BY = "GOVERNED_BY"
    CONFIGURED_BY = "CONFIGURED_BY"
    PERSISTS_AT = "PERSISTS_AT"
    TRANSITIONS_TO = "TRANSITIONS_TO"
    VERIFIED_BY = "VERIFIED_BY"
    SUPERSEDES = "SUPERSEDES"


# ---------------------------------------------------------------------------
# §4.6 Evidence, authority, trust, freshness
# ---------------------------------------------------------------------------

class EvidenceSourceKind(_enum.Enum):
    SOURCE_CODE = "SOURCE_CODE"
    DOCUMENTATION = "DOCUMENTATION"
    DECISION_RECORD = "DECISION_RECORD"
    CONTRACT_SPECIFICATION = "CONTRACT_SPECIFICATION"
    CONFIGURATION = "CONFIGURATION"
    TEST_VERIFICATION = "TEST_VERIFICATION"
    USER_PROJECT_CONFIG = "USER_PROJECT_CONFIG"
    EXTERNAL_SPEC = "EXTERNAL_SPEC"
    OTHER = "OTHER"


class AuthorityKind(_enum.Enum):
    REPOSITORY_RULE = "REPOSITORY_RULE"
    DECISION_RECORD = "DECISION_RECORD"
    CONTRACT_SPECIFICATION = "CONTRACT_SPECIFICATION"
    PRODUCT_BUSINESS = "PRODUCT_BUSINESS"
    TERMINOLOGY = "TERMINOLOGY"
    LEGAL_METHOD_PROFESSIONAL = "LEGAL_METHOD_PROFESSIONAL"
    CONFIGURATION_RUNTIME = "CONFIGURATION_RUNTIME"
    SECURITY_OPERATIONAL = "SECURITY_OPERATIONAL"
    EXTERNAL_SPEC = "EXTERNAL_SPEC"
    OTHER = "OTHER"


class AuthorityStatus(_enum.Enum):
    ACCEPTED = "ACCEPTED"
    DRAFT = "DRAFT"
    SUPERSEDED = "SUPERSEDED"
    DECLARED = "DECLARED"
    UNKNOWN = "UNKNOWN"


@_dataclass(frozen=True)
class AuthorityApplicability:
    subject_scope: tuple[SubjectId, ...] = ()
    description: str | None = None


class PrecedenceKind(_enum.Enum):
    PRIORITY_RANK = "PRIORITY_RANK"
    OVERRIDES = "OVERRIDES"


@_dataclass(frozen=True)
class DeclaredPrecedence:
    kind: PrecedenceKind
    priority_rank: int | None = None
    overrides: tuple[EvidenceRef, ...] = ()
    precedence_scheme: str | None = None

    def __post_init__(self) -> None:
        # §4.6 validation rules (shape rules, enforced at construction).
        if self.kind is PrecedenceKind.PRIORITY_RANK:
            if self.priority_rank is None:
                raise ValueError("PRIORITY_RANK requires priority_rank")
            _require_positive_int("priority_rank", self.priority_rank)
            if not self.precedence_scheme:
                raise ValueError("PRIORITY_RANK requires precedence_scheme")
            if self.overrides:
                raise ValueError("PRIORITY_RANK requires empty overrides")
        else:  # OVERRIDES
            if not self.overrides:
                raise ValueError("OVERRIDES requires at least one referenced authority")
            if self.priority_rank is not None:
                raise ValueError("OVERRIDES requires no priority_rank")


@_dataclass(frozen=True)
class EvidenceRef:
    evidence_id: EvidenceId
    repository_id: str
    source_kind: EvidenceSourceKind
    locator: str
    revision_or_fingerprint: str | None = None
    section_or_span: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)


@_dataclass(frozen=True)
class AuthorityBinding:
    evidence_ref: EvidenceRef
    authority_kind: AuthorityKind
    status: AuthorityStatus
    applicability: AuthorityApplicability = _field(
        default_factory=AuthorityApplicability
    )
    declared_precedence: DeclaredPrecedence | None = None


class FreshnessState(_enum.Enum):
    """Named container for the §4.6 freshness-state vocabulary."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"


@_dataclass(frozen=True)
class Freshness:
    state: FreshnessState
    supporting_revision_or_fingerprint: str | None = None
    reason: str = ""


class TrustState(_enum.Enum):
    ESTABLISHED = "ESTABLISHED"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# §4.7 Canonical claim/relationship carriers, ids, refs
# ---------------------------------------------------------------------------

@_dataclass(frozen=True)
class ClaimId:
    """Nominal non-empty opaque claim identifier."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("ClaimId", self.value)


@_dataclass(frozen=True)
class RelationshipId:
    """Nominal non-empty opaque relationship identifier."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("RelationshipId", self.value)


@_dataclass(frozen=True)
class AnswerId:
    """Nominal non-empty opaque answer identifier."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("AnswerId", self.value)


@_dataclass(frozen=True)
class EvidenceId:
    """Nominal non-empty opaque evidence identifier."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("EvidenceId", self.value)


@_dataclass(frozen=True)
class ClaimRef:
    kind: _typing.Literal["CLAIM"] = "CLAIM"
    id: ClaimId = _field(default_factory=lambda: ClaimId("unset"))


@_dataclass(frozen=True)
class RelationshipRef:
    kind: _typing.Literal["RELATIONSHIP"] = "RELATIONSHIP"
    id: RelationshipId = _field(default_factory=lambda: RelationshipId("unset"))


@_dataclass(frozen=True)
class AnswerRef:
    kind: _typing.Literal["ANSWER"] = "ANSWER"
    id: AnswerId = _field(default_factory=lambda: AnswerId("unset"))


@_dataclass(frozen=True)
class EvidenceIdRef:
    kind: _typing.Literal["EVIDENCE"] = "EVIDENCE"
    id: EvidenceId = _field(default_factory=lambda: EvidenceId("unset"))


class DerivationKind(_enum.Enum):
    EXPLICIT_EVIDENCE = "EXPLICIT_EVIDENCE"
    SEMANTIC_INTERPRETATION = "SEMANTIC_INTERPRETATION"
    STRUCTURAL_OBSERVATION = "STRUCTURAL_OBSERVATION"
    DERIVED_JOIN = "DERIVED_JOIN"


@_dataclass(frozen=True)
class SemanticBasis:
    derivation: DerivationKind
    summary: str = ""
    input_refs: tuple[ClaimRef | RelationshipRef | EvidenceRef, ...] = ()


@_dataclass(frozen=True)
class SemanticClaim:
    claim_id: ClaimId
    subject: SubjectId
    kind: ClaimKind
    value: TypedClaimValue
    evidence: tuple[EvidenceRef, ...] = ()
    authority: AuthorityBinding | None = None
    trust: TrustState = TrustState.UNRESOLVED
    freshness: Freshness = _field(
        default_factory=lambda: Freshness(FreshnessState.UNVERIFIABLE)
    )
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.EXPLICIT_EVIDENCE)
    )

    def __post_init__(self) -> None:
        _require_claim_value(self.kind, self.value)


@_dataclass(frozen=True)
class SemanticRelationship:
    relationship_id: RelationshipId
    source: SubjectId
    kind: RelationshipKind
    target: SubjectId
    evidence: tuple[EvidenceRef, ...] = ()
    authority: AuthorityBinding | None = None
    trust: TrustState = TrustState.UNRESOLVED
    freshness: Freshness = _field(
        default_factory=lambda: Freshness(FreshnessState.UNVERIFIABLE)
    )
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.EXPLICIT_EVIDENCE)
    )


@_dataclass(frozen=True)
class SemanticConflict:
    left: ClaimRef | RelationshipRef
    right: ClaimRef | RelationshipRef
    declared_precedence: DeclaredPrecedence | None = None


@_dataclass(frozen=True)
class RecordedConflict:
    """Validated agent-proposed conflict, persisted (plan §6.4).

    Free-text contradictions the core cannot derive are proposed by the
    interpreting agent, validated (keys resolve, basis cites evidence),
    and recorded here so query-time answers show both sides. Never
    authority; resolved only by declared precedence or supersession.
    """

    subject: SubjectId
    left: ClaimRef | RelationshipRef
    right: ClaimRef | RelationshipRef
    declared_precedence: DeclaredPrecedence | None = None
    basis: SemanticBasis = _field(
        default_factory=lambda: SemanticBasis(DerivationKind.SEMANTIC_INTERPRETATION)
    )


# ---------------------------------------------------------------------------
# §4.8 Repository readiness and hook-safe lifecycle notices
# ---------------------------------------------------------------------------

class RepositoryReadiness(_enum.Enum):
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@_dataclass(frozen=True)
class HookStatusNotice:
    readiness: RepositoryReadiness
    affected_count: int = 0
    stale_count: int = 0
    unverifiable_count: int = 0
    affected_subject_ids: tuple[SubjectId, ...] = ()
    recommended_action: str | None = None


# ---------------------------------------------------------------------------
# §4.9 Semantic basis, uncertainty resolution, change conditions
# ---------------------------------------------------------------------------

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
    """Closed CQ identifiers for question-scoped coverage (Addendum B)."""

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
    """Immutable question identity (Addendum B B-01)."""

    scope_root: SubjectId
    subject: SubjectId
    question_class: SemanticQuestionClass
    question_slice: str
    materiality_basis: str

    def __post_init__(self) -> None:
        _require_non_empty("question_slice", self.question_slice)
        _require_non_empty("materiality_basis", self.materiality_basis)


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


class SemanticCoverageDisposition(_enum.Enum):
    """Repository-report state for one persisted semantic subject."""

    CURRENT = "CURRENT"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"
    UNASSESSED = "UNASSESSED"


@_dataclass(frozen=True)
class SemanticCoverageEntry:
    """Bounded read projection for one persisted semantic subject."""

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
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
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
        ):
            _require_non_negative_int(name, getattr(self, name))


@_dataclass(frozen=True)
class SemanticCoverageReport:
    """Bounded repository-level semantic coverage inventory.

    The report describes persisted semantic subjects only. It never implies
    that structural subjects outside the persisted frontier were enumerated.
    """

    entries: tuple[SemanticCoverageEntry, ...] = ()
    persisted_subject_count: int = 0
    returned_subject_count: int = 0
    current_subject_count: int = 0
    incomplete_subject_count: int = 0
    stale_subject_count: int = 0
    unverifiable_subject_count: int = 0
    unassessed_subject_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "persisted_subject_count",
            "returned_subject_count",
            "current_subject_count",
            "incomplete_subject_count",
            "stale_subject_count",
            "unverifiable_subject_count",
            "unassessed_subject_count",
        ):
            _require_non_negative_int(name, getattr(self, name))


class ChangeKind(_enum.Enum):
    """Proposed-change vocabulary (plan §11.10; hosted here as canonical
    vocabulary so both service requests and interpretation context share
    one carrier)."""

    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    REPRESENTATION = "REPRESENTATION"
    OWNERSHIP = "OWNERSHIP"
    CONFIGURATION = "CONFIGURATION"
    LIFECYCLE = "LIFECYCLE"
    OTHER = "OTHER"


@_dataclass(frozen=True)
class ProposedChange:
    """Typed proposal input (plan §4.11/§11.5.1, I-38)."""

    change_kind: ChangeKind
    change_description: str | None = None
    affected_assertions: tuple[ClaimRef | RelationshipRef, ...] = ()


class ChangeCondition(_enum.Enum):
    AUTHORITY_CHANGE = "AUTHORITY_CHANGE"
    OWNERSHIP_CHANGE = "OWNERSHIP_CHANGE"
    CANONICAL_REPRESENTATION_CHANGE = "CANONICAL_REPRESENTATION_CHANGE"
    BOUNDARY_CHANGE = "BOUNDARY_CHANGE"
    PUBLIC_CONTRACT_CHANGE = "PUBLIC_CONTRACT_CHANGE"
    INVARIANT_CHANGE = "INVARIANT_CHANGE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    LIFECYCLE_CHANGE = "LIFECYCLE_CHANGE"
    VERIFICATION_CHANGE = "VERIFICATION_CHANGE"


class ImpactEstablishment(_enum.Enum):
    STRUCTURAL_POSSIBILITY = "STRUCTURAL_POSSIBILITY"
    SEMANTICALLY_ESTABLISHED = "SEMANTICALLY_ESTABLISHED"
    PARTIAL_OR_UNRESOLVED = "PARTIAL_OR_UNRESOLVED"


@_dataclass(frozen=True)
class ImpactItem:
    subject: SubjectId
    establishment: ImpactEstablishment
    basis: SemanticBasis | None = None
    structural_evidence: tuple[EvidenceRef, ...] = ()
    relevant_claims: tuple[ClaimRef, ...] = ()
    relevant_relationships: tuple[RelationshipRef, ...] = ()


@_dataclass(frozen=True)
class FreshnessItem:
    """One per-item freshness record (plan §4.10, I-36)."""

    item: ClaimRef | RelationshipRef
    subject: SubjectId
    freshness: Freshness
    trust: TrustState


@_dataclass(frozen=True)
class AuthoritySupport:
    """Agent-supplied account of authority support (plan §4.11/§6.3)."""

    quoted_span: str = ""
    status_section: str | None = None
    applicability_section: str | None = None


@_dataclass(frozen=True)
class CandidateAuthority:
    binding: AuthorityBinding
    support: AuthoritySupport = _field(default_factory=AuthoritySupport)


# ---------------------------------------------------------------------------
# §4.10 Semantic answer (one canonical service response envelope)
# ---------------------------------------------------------------------------

class SemanticIntent(_enum.Enum):
    EXPLAIN = "EXPLAIN"
    TRACE = "TRACE"
    IMPACT = "IMPACT"
    AUTHORITY = "AUTHORITY"
    STATUS = "STATUS"


@_dataclass(frozen=True)
class ExplainContent:
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    implementation_locations: tuple[StructuralLocation, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


@_dataclass(frozen=True)
class TraceContent:
    relationships: tuple[SemanticRelationship, ...] = ()
    structural_edges: tuple[StructuralEdge, ...] = ()
    boundary_context: tuple[SubjectId, ...] = ()
    lifecycle_context: tuple[ClaimRef | RelationshipRef, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


@_dataclass(frozen=True)
class ImpactContent:
    target_context: tuple[ClaimRef | RelationshipRef, ...] = ()
    change_conditions: tuple[ChangeCondition, ...] = ()
    impacts: tuple[ImpactItem, ...] = ()
    verification: tuple[ClaimRef | RelationshipRef, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    unresolved: tuple[ResolutionRequirement, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


@_dataclass(frozen=True)
class AuthorityContent:
    governing_bindings: tuple[AuthorityBinding, ...] = ()
    supersession: tuple[RelationshipRef, ...] = ()
    precedence: tuple[DeclaredPrecedence, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    unresolved: tuple[ResolutionRequirement, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


@_dataclass(frozen=True)
class StatusContent:
    readiness: RepositoryReadiness = RepositoryReadiness.READY
    freshness_items: tuple[FreshnessItem, ...] = ()
    changed_dependencies: tuple[EvidenceDependency, ...] = ()
    verification_currency: tuple[VerificationValue, ...] = ()
    refresh_scope: EvidenceScope | None = None
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    unresolved: tuple[ResolutionRequirement, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()
    coverage_report: SemanticCoverageReport | None = None
    target_association: TargetAssociation | None = None
    target_disposition: SemanticCoverageDisposition | None = None


SemanticContent = _typing.Union[
    ExplainContent,
    TraceContent,
    ImpactContent,
    AuthorityContent,
    StatusContent,
]

#: §4.10/§11.3: the five intents correspond to the five question
#: operations; each intent carries exactly its content variant.
INTENT_CONTENT_TYPE: dict[SemanticIntent, type] = {
    SemanticIntent.EXPLAIN: ExplainContent,
    SemanticIntent.TRACE: TraceContent,
    SemanticIntent.IMPACT: ImpactContent,
    SemanticIntent.AUTHORITY: AuthorityContent,
    SemanticIntent.STATUS: StatusContent,
}


@_dataclass(frozen=True)
class SemanticAnswer:
    answer_id: AnswerId
    intent: SemanticIntent
    repository_state: RepositoryState
    subject_resolution: SubjectResolution | None
    content: SemanticContent
    evidence: tuple[EvidenceRef, ...] = ()
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    bound_info: BoundInfo = _field(default_factory=lambda: BoundInfo(0, 0, 0, False))

    def __post_init__(self) -> None:
        expected = INTENT_CONTENT_TYPE[self.intent]
        if not isinstance(self.content, expected):
            raise ValueError(
                f"content for {self.intent.value} must be {expected.__name__}, "
                f"got {type(self.content).__name__}"
            )


# ---------------------------------------------------------------------------
# §4.11 Supporting canonical contracts
# ---------------------------------------------------------------------------

@_dataclass(frozen=True)
class RepositoryState:
    repository_id: str
    revision_id: str | None
    dirty: bool
    state_fingerprint: str
    observed_at: _datetime.datetime

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        _require_non_empty("state_fingerprint", self.state_fingerprint)
        # Plan: "observed_at: UTC-aware datetime" — naive datetimes rejected.
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be a timezone-aware datetime")


@_dataclass(frozen=True)
class EvidenceUnit:
    evidence_ref: EvidenceRef
    content: str
    content_fingerprint: str


class StructuralEdgeKind(_enum.Enum):
    """Canonical vocabulary (defined plan §5.2, referenced §4.11)."""

    REFERENCES = "REFERENCES"
    IMPORTS = "IMPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    CALLS = "CALLS"
    DEFINES = "DEFINES"


@_dataclass(frozen=True)
class StructuralObservation:
    source_subject: SubjectId
    edge_kind: StructuralEdgeKind | None
    target_subject: SubjectId | None
    location: EvidenceRef | None
    repository_state: RepositoryState


@_dataclass(frozen=True)
class StructuralEdge:
    source: SubjectId
    kind: StructuralEdgeKind
    target: SubjectId
    evidence: EvidenceRef


@_dataclass(frozen=True)
class StructuralLocation:
    subject: SubjectId
    location: EvidenceRef


@_dataclass(frozen=True)
class StructuralReachNode:
    subject: SubjectId
    depth: int
    via: StructuralEdge | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int("depth", self.depth)


@_dataclass(frozen=True)
class BoundInfo:
    requested_max_results: int
    requested_max_depth: int
    returned_results: int
    truncated: bool
    truncated_category: str | None = None
    continuation_token: str | None = None


@_dataclass(frozen=True)
class EvidenceScope:
    paths: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()


class StatusMode(_enum.Enum):
    NORMAL = "NORMAL"
    HOOK_FAST = "HOOK_FAST"


@_dataclass(frozen=True)
class StructuralLocationPage:
    items: tuple[StructuralLocation, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False

    def __post_init__(self) -> None:
        # §4.11: unsupported:true requires empty items.
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")


@_dataclass(frozen=True)
class StructuralEdgePage:
    items: tuple[StructuralEdge, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False

    def __post_init__(self) -> None:
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")


@_dataclass(frozen=True)
class StructuralReachPage:
    items: tuple[StructuralReachNode, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False

    def __post_init__(self) -> None:
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")


class StructuralLocateMode(_enum.Enum):
    """Locate operation modes (Addendum F §4.1 — one field, not three tools)."""

    SYMBOL = "SYMBOL"
    FILE_OUTLINE = "FILE_OUTLINE"
    TARGET_MEMBERS = "TARGET_MEMBERS"


class StructuralLocateMatch(_enum.Enum):
    """Symbol match breadth (Addendum F §4.1)."""

    EXACT = "EXACT"
    CONTAINS = "CONTAINS"


class ScopeCoverage(_enum.Enum):
    """Search-scope currency (Addendum F §4.0 two-tier freshness).

    VERIFIED means the loaded index postdates the newest source in the
    queried scope with a clean tree and every touched file hash-verified.
    Anything else — including empty results — is UNVERIFIED, which proves
    nothing about absence.
    """

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


#: Closed structural diagnostic tokens (Addendum G §4.2a). Defined
#: beside `ScopeCoverage`; validated at construction. Fixed join order:
#: non-git-tree, injected-index, dirty-tree, touched-file-mismatch,
#: unverifiable-file, index-older-than-head. `clean-verified` is
#: exclusive and never joins.
COVERAGE_DETAIL_TOKENS: tuple[str, ...] = (
    "non-git-tree",
    "injected-index",
    "dirty-tree",
    "touched-file-mismatch",
    "unverifiable-file",
    "index-older-than-head",
    "clean-verified",
)

_COVERAGE_DETAIL_ORDER: dict[str, int] = {
    token: index for index, token in enumerate(COVERAGE_DETAIL_TOKENS)
}


def _validate_coverage_detail(
    name: str, value: str | None
) -> str | None:
    """Strict validation for structural diagnostic detail (Addendum G).

    `None` is allowed. Any string must be a non-empty `+` join of closed
    tokens in fixed order, with no duplicates, empty segments, or
    surrounding whitespace; `clean-verified` only alone.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be None or a non-empty string")
    if value != value.strip() or not value:
        raise ValueError(f"{name} must not have surrounding whitespace")
    parts = value.split("+")
    if any(not part for part in parts):
        raise ValueError(f"{name} has an empty token segment")
    if any(part != part.strip() for part in parts):
        raise ValueError(f"{name} tokens must not have whitespace")
    if any(part not in _COVERAGE_DETAIL_ORDER for part in parts):
        raise ValueError(f"{name} has an unknown token")
    if len(set(parts)) != len(parts):
        raise ValueError(f"{name} has duplicate tokens")
    if "clean-verified" in parts and len(parts) != 1:
        raise ValueError(f"{name}: clean-verified is exclusive")
    order = [_COVERAGE_DETAIL_ORDER[part] for part in parts]
    if order != sorted(order):
        raise ValueError(f"{name} tokens are in the wrong order")
    return value


@_dataclass(frozen=True)
class StructuralLocateEntry:
    """One located structural member (Addendum F §4.1).

    Identity is the stable evidence ref, not subjecthood: non-indexed
    members carry a null subject and remain full members.
    """

    evidence_ref: EvidenceRef
    content_fingerprint: str
    subject: SubjectId | None = None
    span_text: str | None = None
    signature_text: str | None = None


@_dataclass(frozen=True)
class StructuralLocateResult:
    """Locate answer (Addendum F §§4.1/4.3; detail per Addendum G §4.2a)."""

    entries: tuple[StructuralLocateEntry, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    stale_omitted: int = 0
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int("stale_omitted", self.stale_omitted)
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class StructuralNeighborsResult:
    """Neighbors answer (Addendum F §4.2; detail per Addendum G §4.2a).

    The four outcomes are wire-distinct: unsupported query
    (unsupported:true, empty), unresolved subject (NOT_FOUND, empty),
    resolved subject without edges (empty, RESOLVED), resolved subject
    with edges.
    """

    resolution: SubjectResolution
    repository_state: RepositoryState
    bound_info: BoundInfo
    edges: tuple[StructuralEdge, ...] = ()
    unsupported: bool = False
    stale_omitted: int = 0
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        if self.unsupported and self.edges:
            raise ValueError("unsupported result must carry empty edges")
        _require_non_negative_int("stale_omitted", self.stale_omitted)
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class StructuralSearchHit:
    """One search hit: ranked candidate plus transcribed node strings."""

    candidate: SubjectCandidate
    span_text: str | None = None
    signature_text: str | None = None


@_dataclass(frozen=True)
class StructuralSearchPage:
    """Paginated name/locator search page (Addendum F §4.0 port)."""

    items: tuple[StructuralSearchHit, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False
    stale_omitted: int = 0
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")
        _require_non_negative_int("stale_omitted", self.stale_omitted)
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class StructuralOutlineEntry:
    """One file-outline member: subject plus transcribed provider strings."""

    subject: Subject
    span_text: str | None = None
    signature_text: str | None = None


@_dataclass(frozen=True)
class StructuralOutlinePage:
    """Paginated file-outline page (Addendum F §4.0 port)."""

    items: tuple[StructuralOutlineEntry, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False
    stale_omitted: int = 0
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")
        _require_non_negative_int("stale_omitted", self.stale_omitted)
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class StructuralFreshnessReport:
    """File-set freshness verdict (Addendum F §4.0 port; detail per G §4.2a).

    Stale files hash-mismatch or are unreadable; unverifiable files have
    no recorded file hash to compare against. Coverage applies the §4.0
    rule to the given file set. `coverage_detail` projects the same facts
    as closed diagnostic tokens; it never changes the verdict.
    """

    stale_files: tuple[str, ...] = ()
    unverifiable_files: tuple[str, ...] = ()
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class EvidenceInventoryItem:
    evidence_ref: EvidenceRef
    content_fingerprint: str


@_dataclass(frozen=True)
class TargetId:
    """Nominal non-empty opaque target-campaign identifier (Addendum E)."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("TargetId", self.value)


@_dataclass(frozen=True)
class TargetInventoryAccount:
    """One target-membership accounting entry (Addendum E §4C.2).

    Exactly one outcome must be present: assignment, evidence-backed
    exclusion, or unresolved mapping. Membership only; no semantic meaning.
    Content fingerprints are excluded from target accounting by §§4C.6B/4C.6E;
    content freshness remains owned by the existing evidence/question/claim/
    relationship dependency machinery.
    """

    evidence_ref: EvidenceRef
    assigned_area_subjects: tuple[SubjectId, ...] = ()
    exclusion_basis: SemanticBasis | None = None
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()

    def __post_init__(self) -> None:
        has_assignment = bool(self.assigned_area_subjects)
        has_exclusion = self.exclusion_basis is not None
        has_unresolved = bool(self.resolution_requirements)
        count = int(has_assignment) + int(has_exclusion) + int(has_unresolved)
        if count != 1:
            raise ValueError(
                "TargetInventoryAccount requires exactly one outcome: "
                "assigned_area_subjects, exclusion_basis, "
                "or resolution_requirements"
            )
        if has_exclusion and not self.exclusion_basis.summary:
            raise ValueError("exclusion_basis summary is empty")


@_dataclass(frozen=True)
class TargetAssociation:
    """Durable target-accounting state (Addendum E §§4C.2/4C.6A–6C).

    Accounting only; area meaning stays in claims/relationships, question
    state stays in InterpretationCoverage.
    """

    target_id: TargetId
    repository_id: str
    target_scope: EvidenceScope
    objective: str
    area_subjects: tuple[SubjectId, ...] = ()
    target_questions: tuple[SemanticQuestionScope, ...] = ()
    inventory_accounting: tuple[TargetInventoryAccount, ...] = ()
    inventory_fingerprint: str = ""
    observed_repository_state_fingerprint: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        _require_non_empty("objective", self.objective)


def _canonicalize_path(path: str) -> str:
    if not path or path.startswith("/") or path == "":
        raise ValueError(f"invalid target path: {path!r}")
    parts = path.split("/")
    out: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"path escapes repository: {path!r}")
        if part == "":
            raise ValueError(f"invalid target path: {path!r}")
        out.append(part)
    if not out:
        return "."
    return "/".join(out)


def canonicalize_target_scope(
    repository_id: str, scope: EvidenceScope, objective: str
) -> tuple[EvidenceScope, str]:
    """Canonicalize scope/objective per Addendum E §4C.6A (deterministic)."""
    canonical_objective = objective.strip()
    if not canonical_objective:
        raise ValueError("objective is empty after strip")
    if not scope.paths and not scope.evidence_refs:
        raise ValueError("target scope is empty: no paths or evidence_refs")
    canonical_paths: list[str] = []
    for raw in scope.paths:
        if not raw:
            raise ValueError("empty path member")
        canonical_paths.append(_canonicalize_path(raw))
    canonical_paths = sorted(set(canonical_paths))
    canonical_refs: list[EvidenceRef] = []
    for ref in scope.evidence_refs:
        if ref.repository_id != repository_id:
            raise ValueError("evidence_ref repository mismatch")
        if ref.section_or_span is not None:
            raise ValueError("section-scoped refs are not inventory members")
        canonical_refs.append(
            EvidenceRef(
                evidence_id=ref.evidence_id,
                repository_id=ref.repository_id,
                source_kind=ref.source_kind,
                locator=_canonicalize_path(ref.locator),
                revision_or_fingerprint=None,
                section_or_span=None,
            )
        )
    canonical_refs.sort(
        key=lambda r: (
            r.evidence_id.value,
            r.source_kind.value,
            r.locator,
        )
    )
    seen: dict[str, EvidenceRef] = {}
    for ref in canonical_refs:
        key = ref.evidence_id.value
        if key in seen:
            prev = seen[key]
            if prev.locator != ref.locator or prev.source_kind != ref.source_kind:
                raise ValueError(
                    f"conflicting provider identity for {key!r}"
                )
            continue
        seen[key] = ref
    canonical_scope = EvidenceScope(
        paths=tuple(canonical_paths),
        evidence_refs=tuple(seen[k] for k in sorted(seen)),
    )
    return canonical_scope, canonical_objective


def derive_target_id(
    repository_id: str, canonical_scope: EvidenceScope, canonical_objective: str
) -> TargetId:
    """Derive tgt- ID from canonical identity only (no revision/content)."""
    payload = to_canonical(canonical_scope)
    canonical_json = _json.dumps(
        [repository_id, payload, canonical_objective],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = _hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
    return TargetId(value=f"tgt-{digest}")


def target_inventory_fingerprint(
    items: tuple[EvidenceInventoryItem, ...],
) -> str:
    """Membership fingerprint over sorted stable identity tuples."""
    members = sorted(
        (
            item.evidence_ref.evidence_id.value,
            item.evidence_ref.locator,
            item.evidence_ref.source_kind.value,
        )
        for item in items
    )
    payload = _json.dumps(
        [list(m) for m in members],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()


@_dataclass(frozen=True)
class EvidenceInventoryPage:
    items: tuple[EvidenceInventoryItem, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo


@_dataclass(frozen=True)
class EvidenceSelection:
    selected_refs: tuple[EvidenceRef, ...]
    bound_info: BoundInfo


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
    value: TypedClaimValue = _field(
        default_factory=lambda: PurposeValue(summary="")
    )
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


#: C-04 material aspects per question class, quoted as brief content
#: (addendum D §8.1, ACT-D-13). Static contract lookup by the service —
#: never runtime semantic judgment. CQ-10 has no enum member; its
#: cross-cutting substance (evidence/scope/uncertainty/adversarial
#: disciplines) rides in every brief via the SA obligations and the
#: static rules below.
QUESTION_CLASS_ASPECTS: dict[SemanticQuestionClass, tuple[str, ...]] = {
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

#: Static OPEN/PENDING handling rules attached to every brief (C-04,
#: addendum B reconciliation rules). Contract prose, not per-unit
#: invention.
TASK_BRIEF_OPEN_HANDLING: tuple[str, ...] = (
    "Preserve unexamined or unsupported aspects as OPEN/PENDING with "
    "typed ResolutionRequirements; never narrow the slice silently.",
    "A deliberately narrowed question is a new exact "
    "SemanticQuestionScope; it must not silently replace or retire "
    "the broader original.",
)

#: Static submission/disposition rules attached to every brief (C-04
#: disposition decision, SA-6). Contract prose, not per-unit invention.
TASK_BRIEF_SUBMISSION_RULES: tuple[str, ...] = (
    "ANSWERED only when the admitted slice has been examined and its "
    "material aspects are substantiated.",
    "Do not declare a parent question ANSWERED merely because OPEN "
    "follow-ups exist.",
    "Submit one strict canonical result with an explicit question "
    "disposition.",
)

# The following are the stable, compact projections of SA-3–SA-7. They are
# task guidance, not a second semantic schema or a deterministic correctness
# classifier. Instance-specific evidence and requirements are added by the
# service when it constructs the brief.
TASK_BRIEF_MATERIAL_PATH: tuple[str, ...] = (
    "Trace input → producer → transformation/state → consumer/output → "
    "terminal/failure.",
    "Account only for legs material to this exact question slice.",
)

TASK_BRIEF_SEMANTIC_RESULT: tuple[str, ...] = (
    "Use existing typed claims and relationships only.",
    "Give each asserted result admissible evidence and distinguish observed "
    "behavior from governing intent.",
)

TASK_BRIEF_ADVERSARIAL_CHECKS: tuple[str, ...] = (
    "Check alternate owner or authority, contradiction, and omitted "
    "participants.",
    "Check terminal/failure paths, stale premises, unsupported routes, and "
    "missing verification.",
)

TASK_BRIEF_READBACK: tuple[str, ...] = (
    "State what a fresh query can retrieve and what still requires "
    "interpretation.",
    "Do not claim useful completion unless the canonical result is readable "
    "from a fresh interaction.",
)


@_dataclass(frozen=True)
class SemanticInterpretationRequest:
    repository_id: str
    subjects: tuple[Subject, ...]
    evidence_units: tuple[EvidenceUnit, ...]
    structural_observations: tuple[StructuralObservation, ...]
    allowed_claim_kinds: tuple[ClaimKind, ...]
    allowed_relationship_kinds: tuple[RelationshipKind, ...]
    identity_bindings: tuple[SubjectId, ...]
    # Required, never defaulted: every interpretation task carries its
    # slice-derived brief (no brief-less legacy path, no dual semantics).
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
    prior_claims: tuple[SemanticClaim, ...] = ()
    prior_relationships: tuple[SemanticRelationship, ...] = ()
    analysis_obligations: tuple[str, ...] = ()
    target_id: TargetId | None = None
    target_inventory_item: EvidenceInventoryItem | None = None

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
    proposed_question_coverages: tuple[InterpretationCoverage, ...] = ()
    candidate_withdrawals: tuple[CandidateSemanticWithdrawal, ...] = ()
    proposed_target_inventory_accounting: tuple[TargetInventoryAccount, ...] = ()
    proposed_target_questions: tuple[SemanticQuestionScope, ...] = ()


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
    inventory_fingerprint: str = ""
    seed_fingerprints: tuple[SeedFingerprint, ...] = ()
    observed_at: _datetime.datetime = _field(
        default_factory=lambda: _datetime.datetime.now(_datetime.timezone.utc)
    )
    question: SemanticQuestionScope | None = None


@_dataclass(frozen=True)
class InterpretationCoverage:
    """Single canonical persisted question record (Addendum B B-01)."""

    subjects: tuple[SubjectId, ...] = ()
    question_slice: str = ""
    evidence_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    declared_complete: bool = False
    question: SemanticQuestionScope | None = None
    disposition: SemanticQuestionDisposition = SemanticQuestionDisposition.PENDING
    result_refs: tuple[ClaimRef | RelationshipRef, ...] = ()
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    disposition_basis: str = ""
    question_evidence: tuple[QuestionEvidenceObservation, ...] = ()

    def __post_init__(self) -> None:
        if self.disposition is SemanticQuestionDisposition.ANSWERED:
            # Addendum C C-05: an explicit ANSWERED submission may carry
            # empty result_refs as completion intent; the service derives
            # refs from validated candidates before persisting, and the
            # store rejects ANSWERED rows with empty refs. Only persisted
            # ANSWERED rows with derived refs count as examined.
            if not self.declared_complete:
                raise ValueError("ANSWERED coverage requires declared_complete")
        if self.disposition is SemanticQuestionDisposition.OPEN:
            if not self.resolution_requirements:
                raise ValueError("OPEN coverage requires resolution_requirements")
        if self.disposition is SemanticQuestionDisposition.NOT_APPLICABLE:
            if self.result_refs:
                raise ValueError("NOT_APPLICABLE coverage requires empty result_refs")


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


@_dataclass(frozen=True)
class StoreWriteResult:
    written_count: int = 0


@_dataclass(frozen=True)
class SchemaVersion:
    value: int = 0


# ---------------------------------------------------------------------------
# §5.1 Shared bounds (value types; port operations are Phase 1.2)
# ---------------------------------------------------------------------------

@_dataclass(frozen=True)
class QueryBounds:
    max_results: int
    max_depth: int
    max_subjects: int
    max_evidence_units: int
    max_evidence_bytes: int
    max_candidate_claims: int
    max_candidate_relationships: int

    def __post_init__(self) -> None:
        _require_positive_int("max_results", self.max_results)
        _require_non_negative_int("max_depth", self.max_depth)
        _require_positive_int("max_subjects", self.max_subjects)
        _require_positive_int("max_evidence_units", self.max_evidence_units)
        _require_positive_int("max_evidence_bytes", self.max_evidence_bytes)
        _require_positive_int("max_candidate_claims", self.max_candidate_claims)
        _require_positive_int(
            "max_candidate_relationships", self.max_candidate_relationships
        )


@_dataclass(frozen=True)
class ServiceBoundsPolicy:
    default_query_bounds: QueryBounds
    maximum_query_bounds: QueryBounds
    hook_fast_bounds: QueryBounds


# ---------------------------------------------------------------------------
# Canonical serialization (deterministic mechanical encoding)
# ---------------------------------------------------------------------------

class CanonicalDecodeError(ValueError):
    """Raised when canonical data cannot be decoded into the target type.

    Carries append-only field-path context (Addendum G §4.1b): `path` is
    a tuple of dotted field names with collection indices (for example
    `("target", "exact_subject_id", "canonical_locator")` or
    `("claims", "[3]")`). `reason` is the original failure text.
    `str()` renders `path: reason` when a path is present, preserving
    all existing reason substrings for backward compatibility.
    """

    def __init__(
        self, message: str, path: tuple[str, ...] = ()
    ) -> None:
        self.reason = message
        self.path = tuple(path)
        if self.path:
            rendered = ".".join(self.path).replace(".[", "[")
            super().__init__(f"{rendered}: {message}")
        else:
            super().__init__(message)

    def with_segment(self, segment: str) -> CanonicalDecodeError:
        """Return a copy with one outer path segment prepended (pure)."""
        return CanonicalDecodeError(self.reason, path=(segment,) + self.path)


def to_canonical(value: object) -> object:
    """Encode a canonical model value into plain JSON-compatible data."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, _enum.Enum):
        return value.value
    if isinstance(value, _datetime.datetime):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [to_canonical(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        payload: dict[str, object] = {"$type": type(value).__name__}
        for f in _fields(value):
            payload[f.name] = to_canonical(getattr(value, f.name))
        return payload
    raise TypeError(f"cannot encode {type(value).__name__} canonically")


def _decode_union(members: tuple[object, ...], data: object) -> object:
    # Dataclass members dispatch on the explicit $type tag (never guessed).
    if isinstance(data, dict) and isinstance(data.get("$type"), str):
        tag = data["$type"]
        for member in members:
            if (
                isinstance(member, type)
                and hasattr(member, "__dataclass_fields__")
                and member.__name__ == tag
            ):
                return _decode_dataclass(member, data)
        raise CanonicalDecodeError(f"unknown $type tag: {tag!r}")
    failures = []
    for member in members:
        if member is type(None):
            if data is None:
                return None
            continue
        try:
            return _decode_value(member, data)
        except (CanonicalDecodeError, TypeError, ValueError) as exc:
            failures.append(str(exc))
    raise CanonicalDecodeError(f"no union member matched {data!r}: {failures}")


def _decode_value(hint: object, data: object) -> object:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)

    if hint is None or hint is type(None):
        if data is None:
            return None
        raise CanonicalDecodeError(f"expected null, got {data!r}")

    if origin is _typing.Union or origin is _types.UnionType:
        return _decode_union(args, data)

    if origin is _typing.Literal:
        if data in args:
            return data
        raise CanonicalDecodeError(f"expected one of {args!r}, got {data!r}")

    if isinstance(hint, type) and issubclass(hint, _enum.Enum):
        try:
            return hint(data)
        except ValueError:
            raise CanonicalDecodeError(
                f"unknown {hint.__name__} value: {data!r}"
            ) from None

    if hint is _datetime.datetime:
        if isinstance(data, str):
            try:
                parsed = _datetime.datetime.fromisoformat(data)
            except ValueError:
                raise CanonicalDecodeError(
                    f"invalid datetime: {data!r}"
                ) from None
            return parsed
        raise CanonicalDecodeError(f"expected datetime string, got {data!r}")

    if hint is str:
        if isinstance(data, str):
            return data
        raise CanonicalDecodeError(f"expected string, got {data!r}")

    if hint is bool:
        if isinstance(data, bool):
            return data
        raise CanonicalDecodeError(f"expected bool, got {data!r}")

    if hint is int:
        if isinstance(data, int) and not isinstance(data, bool):
            return data
        raise CanonicalDecodeError(f"expected int, got {data!r}")

    if origin in (tuple, list) or hint in (tuple, list):
        if not isinstance(data, list):
            raise CanonicalDecodeError(f"expected list, got {data!r}")
        item_hint = args[0] if args else _typing.Any
        if item_hint is _typing.Any:
            raise CanonicalDecodeError("untyped collection decoding refused")
        decoded: list[object] = []
        for index, item in enumerate(data):
            try:
                decoded.append(_decode_value(item_hint, item))
            except CanonicalDecodeError as exc:
                raise exc.with_segment(f"[{index}]") from None
        if origin is tuple or hint is tuple:
            return tuple(decoded)
        return decoded

    if isinstance(hint, type) and hasattr(hint, "__dataclass_fields__"):
        if not isinstance(data, dict):
            raise CanonicalDecodeError(f"expected object, got {data!r}")
        return _decode_dataclass(hint, data)

    raise CanonicalDecodeError(f"unsupported decode target: {hint!r}")


def _decode_dataclass(cls: type, data: dict) -> object:
    tag = data.get("$type")
    if tag != cls.__name__:
        raise CanonicalDecodeError(
            f"expected $type {cls.__name__!r}, got {tag!r}"
        )
    try:
        hints = _typing.get_type_hints(cls)
    except Exception as exc:
        raise CanonicalDecodeError(f"cannot resolve {cls.__name__}: {exc}") from exc
    names = {f.name for f in _fields(cls)}
    unknown = sorted(key for key in data if key != "$type" and key not in names)
    if unknown:
        raise CanonicalDecodeError(
            f"unknown fields for {cls.__name__}: {unknown}"
        )
    kwargs: dict[str, object] = {}
    for f in _fields(cls):
        if f.name not in data:
            # Missing field is acceptable only when the dataclass supplies
            # a default; unknown fields are never accepted (strict).
            if f.default is _MISSING and f.default_factory is _MISSING:  # type: ignore[misc]
                raise CanonicalDecodeError(
                    f"missing field {f.name!r} for {cls.__name__}"
                )
            continue
        try:
            kwargs[f.name] = _decode_value(hints[f.name], data[f.name])
        except CanonicalDecodeError as exc:
            raise exc.with_segment(f.name) from None
    try:
        return cls(**kwargs)  # type: ignore[arg-type]
    except (ValueError, TypeError) as exc:
        raise CanonicalDecodeError(f"invalid {cls.__name__}: {exc}") from exc


def from_canonical(cls: type, data: object) -> object:
    """Decode canonical data into the target model type (strict, exact)."""
    return _decode_value(cls, data)
