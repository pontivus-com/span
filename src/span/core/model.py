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
    "ClaimPage",
    "RelationshipPage",
    "EvidenceDependency",
    "FreshnessUpdate",
    "SeedFingerprint",
    "CoverageDependency",
    "InterpretationCoverage",
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


@_dataclass(frozen=True)
class ResolutionRequirement:
    kind: ResolutionKind
    subject_or_claim: SubjectId | ClaimRef | RelationshipRef | None = None
    description: str = ""
    supporting_context: tuple[ClaimRef | RelationshipRef | EvidenceRef, ...] = ()


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


@_dataclass(frozen=True)
class TraceContent:
    relationships: tuple[SemanticRelationship, ...] = ()
    structural_edges: tuple[StructuralEdge, ...] = ()
    boundary_context: tuple[SubjectId, ...] = ()
    lifecycle_context: tuple[ClaimRef | RelationshipRef, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()


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


@_dataclass(frozen=True)
class AuthorityContent:
    governing_bindings: tuple[AuthorityBinding, ...] = ()
    supersession: tuple[RelationshipRef, ...] = ()
    precedence: tuple[DeclaredPrecedence, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    unresolved: tuple[ResolutionRequirement, ...] = ()


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


@_dataclass(frozen=True)
class EvidenceInventoryItem:
    evidence_ref: EvidenceRef
    content_fingerprint: str


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
class SemanticInterpretationRequest:
    repository_id: str
    subjects: tuple[Subject, ...]
    evidence_units: tuple[EvidenceUnit, ...]
    structural_observations: tuple[StructuralObservation, ...]
    allowed_claim_kinds: tuple[ClaimKind, ...]
    allowed_relationship_kinds: tuple[RelationshipKind, ...]
    identity_bindings: tuple[SubjectId, ...]
    operation_intent: SemanticIntent = SemanticIntent.EXPLAIN
    question_slice: str = ""
    proposed_change: ProposedChange | None = None
    bounds: QueryBounds = _field(
        default_factory=lambda: QueryBounds(50, 2, 8, 24, 96_000, 64, 64)
    )

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)


@_dataclass(frozen=True)
class SemanticInterpretationResult:
    claims: tuple[CandidateSemanticClaim, ...] = ()
    relationships: tuple[CandidateSemanticRelationship, ...] = ()
    governing_source_refs: tuple[EvidenceRef, ...] = ()
    diagnostics: tuple[str, ...] = ()
    candidate_subjects: tuple[CandidateSubject, ...] = ()
    candidate_conflicts: tuple[CandidateSemanticConflict, ...] = ()


@_dataclass(frozen=True)
class ClaimPage:
    items: tuple[SemanticClaim, ...]
    bound_info: BoundInfo


@_dataclass(frozen=True)
class RelationshipPage:
    items: tuple[SemanticRelationship, ...]
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


@_dataclass(frozen=True)
class InterpretationCoverage:
    """Scope one batch claims to reconcile (plan §4.11, I-37)."""

    subjects: tuple[SubjectId, ...] = ()
    question_slice: str = ""
    evidence_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    declared_complete: bool = False


@_dataclass(frozen=True)
class CanonicalIndexBatch:
    subjects: tuple[Subject, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    evidence_dependencies: tuple[EvidenceDependency, ...] = ()
    coverage_dependencies: tuple[CoverageDependency, ...] = ()
    coverage: InterpretationCoverage = _field(
        default_factory=InterpretationCoverage
    )
    retires_claims: tuple[ClaimRef, ...] = ()
    retires_relationships: tuple[RelationshipRef, ...] = ()
    conflicts: tuple[RecordedConflict, ...] = ()


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
    """Raised when canonical data cannot be decoded into the target type."""


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
        if origin is tuple or hint is tuple:
            return tuple(_decode_value(item_hint, item) for item in data)
        return [_decode_value(item_hint, item) for item in data]

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
        kwargs[f.name] = _decode_value(hints[f.name], data[f.name])
    try:
        return cls(**kwargs)  # type: ignore[arg-type]
    except (ValueError, TypeError) as exc:
        raise CanonicalDecodeError(f"invalid {cls.__name__}: {exc}") from exc


def from_canonical(cls: type, data: object) -> object:
    """Decode canonical data into the target model type (strict, exact)."""
    return _decode_value(cls, data)
