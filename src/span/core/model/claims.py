"""Claim and relationship vocabulary, values, and carriers.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import types as _types
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.primitives import (
    AuthorityBinding,
    ClaimId,
    ClaimRef,
    DeclaredPrecedence,
    DerivationKind,
    EvidenceRef,
    Freshness,
    FreshnessState,
    RelationshipId,
    RelationshipRef,
    SemanticBasis,
    SubjectId,
    TrustState,
    _require_non_empty,
)


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


class AssertionNature(_enum.Enum):
    """Descriptive vs normative modality ([design note I](docs/design-references.md#i) S6 §5.6).

    DESCRIPTIVE observes behavior; NORMATIVE asserts assigned custody,
    contracts, or governance. Trust derivation is unchanged for both
    natures (MI-05).
    """

    DESCRIPTIVE = "DESCRIPTIVE"
    NORMATIVE = "NORMATIVE"


CandidateAssertionNature = _typing.Literal[
    AssertionNature.DESCRIPTIVE, AssertionNature.NORMATIVE
]
NORMATIVE_ONLY_CLAIM_KINDS: tuple[ClaimKind, ...] = (
    ClaimKind.OWNERSHIP_CUSTODY,
    ClaimKind.TRANSFORMATION_OWNERSHIP,
    ClaimKind.INVARIANT_CONSTRAINT,
)
NORMATIVE_ONLY_RELATIONSHIP_KINDS: tuple[str, ...] = (
    "GOVERNED_BY",
    "SUPERSEDES",
)


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


class AttestedCurrency(_enum.Enum):
    """What an agent may say about a verification it did not execute.

    A pass cannot be expressed: the only choices are "candidate" and
    "unknown". Currency is derived from an execution record instead.
    """

    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"


class DerivedCurrency(_enum.Enum):
    """Currency projected from a VerificationRecord against current state."""

    CURRENT_PASS = "CURRENT_PASS"
    CURRENT_FAIL = "CURRENT_FAIL"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@_dataclass(frozen=True)
class VerificationValue:
    """The link: a claim that something is verified, not that it passed."""

    verification_ref: SubjectId
    kind: VerificationKind
    attested_currency: AttestedCurrency = AttestedCurrency.CANDIDATE


@_dataclass(frozen=True)
class VerificationStatus:
    """One carried verification link with its derived currency."""

    verification_ref: SubjectId
    kind: VerificationKind
    currency: DerivedCurrency


@_dataclass(frozen=True)
class ExecutedVerification:
    """An agent-attested execution, before its scope identity is derived.

    The verified scope is the matching verification link's evidence scope,
    so the agent supplies facts it observed and never an internal
    fingerprint. Validation maps this candidate to one
    :class:`VerificationRecord` or rejects it.
    """

    repository_id: str
    subject: SubjectId
    command: str | None
    exit_status: int
    observed_revision: str | None
    observed_at: _datetime.datetime
    observer: str | None

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        if self.subject.repository_id != self.repository_id:
            raise ValueError("execution subject belongs to another repository")
        if isinstance(self.exit_status, bool) or not isinstance(self.exit_status, int):
            raise ValueError("exit_status must be an integer")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@_dataclass(frozen=True)
class VerificationRecord:
    """One executed verification run for a (subject, verified scope).

    A State, not an observation: the natural key is
    ``(repository_id, subject, scope_fingerprint)`` and a rerun is an
    upsert on that key. Currency is derived by comparing the recorded
    revision and scope to current state; it is never stored here.
    """

    repository_id: str
    subject: SubjectId
    scope_fingerprint: str
    command: str | None
    exit_status: int
    observed_revision: str | None
    observed_at: _datetime.datetime
    observer: str | None

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        _require_non_empty("scope_fingerprint", self.scope_fingerprint)
        if self.subject.repository_id != self.repository_id:
            raise ValueError(
                "verification record subject belongs to another repository"
            )
        if isinstance(self.exit_status, bool) or not isinstance(self.exit_status, int):
            raise ValueError("exit_status must be an integer")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


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
CLAIM_VALUE_TYPE: _typing.Mapping[ClaimKind, type] = _types.MappingProxyType(
    {
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
)


def _require_claim_value(kind: ClaimKind, value: TypedClaimValue) -> TypedClaimValue:
    expected = CLAIM_VALUE_TYPE[kind]
    if not isinstance(value, expected):
        raise ValueError(
            f"value for {kind.value} must be {expected.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


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


@_dataclass(frozen=True)
class SemanticClaim:
    claim_id: ClaimId
    subject: SubjectId
    kind: ClaimKind
    value: TypedClaimValue
    assertion_nature: AssertionNature = _field(kw_only=True)
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
    assertion_nature: AssertionNature = _field(kw_only=True)
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
