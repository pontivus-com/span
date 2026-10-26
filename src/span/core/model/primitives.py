"""Identities, evidence references, authority, and bounds.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import hashlib as _hashlib
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field


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
    exact_subject_id: SubjectId | None = None
    name_or_locator: str | None = None
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


class SemanticIntent(_enum.Enum):
    EXPLAIN = "EXPLAIN"
    TRACE = "TRACE"
    IMPACT = "IMPACT"
    AUTHORITY = "AUTHORITY"
    STATUS = "STATUS"


class HandleKind(_enum.Enum):
    """Whether a pointer survives the process that issued it."""

    EPHEMERAL = "EPHEMERAL"
    DURABLE = "DURABLE"


class HandleScope(_enum.Enum):
    """What the pointer is meaningful within."""

    PROCESS = "PROCESS"
    REPOSITORY = "REPOSITORY"


class HandleRecovery(_enum.Enum):
    """What a caller does when the handle is gone or stale."""

    REISSUE_OPERATION = "REISSUE_OPERATION"
    RESTART_LISTING = "RESTART_LISTING"
    REINITIALIZE_TARGET = "REINITIALIZE_TARGET"


@_dataclass(frozen=True)
class HandleLifespan:
    """What kind of pointer this is, and what happens when it is lost.

    A page cursor is a position: durable, repository-scoped, restarted on
    drift. An interpretation continuation is an assignment: ephemeral,
    process-scoped, recovered by re-running the originating operation. A
    campaign handle is durable with a retention window.

    The carrier states which one it is so a caller never infers it, and so a
    restart cannot be mistaken for a resumable page.
    """

    kind: HandleKind
    scope: HandleScope
    expires_at: str | None
    recovery: HandleRecovery


CURSOR_LIFESPAN = HandleLifespan(
    kind=HandleKind.DURABLE,
    scope=HandleScope.REPOSITORY,
    expires_at=None,
    recovery=HandleRecovery.RESTART_LISTING,
)
CONTINUATION_LIFESPAN = HandleLifespan(
    kind=HandleKind.EPHEMERAL,
    scope=HandleScope.PROCESS,
    expires_at=None,
    recovery=HandleRecovery.REISSUE_OPERATION,
)


@_dataclass(frozen=True)
class BoundInfo:
    requested_max_results: int
    requested_max_depth: int
    returned_results: int
    truncated: bool
    truncated_category: str | None = None
    continuation_token: str | None = None
    lifespan: HandleLifespan = CURSOR_LIFESPAN


@_dataclass(frozen=True)
class EvidenceScope:
    paths: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()


def evidence_scope_allows(locator: str, scope: EvidenceScope) -> bool:
    """Canonical scope-membership predicate for one locator (J-10).

    Scope paths are file-or-directory prefixes; refs are exact members.
    Provider-agnostic: matches ``path``, ``path/...``, ``path#...`` and
    ``path:...`` forms without knowing the provider's locator grammar.
    The single shared predicate used by every structural provider and by
    the service; never re-implemented per provider or in the service.
    """
    for ref in scope.evidence_refs:
        if locator == ref.locator:
            return True
    for prefix in scope.paths:
        stem = prefix.rstrip("/")
        if (
            locator == stem
            or locator.startswith(stem + "/")
            or locator.startswith(stem + "#")
            or locator.startswith(stem + ":")
        ):
            return True
    return False


def evidence_scope_fingerprint(scope: EvidenceScope) -> str:
    """Deterministic, order-normalized fingerprint of one scope (J-10).

    Used to bind continuation-token identity to the exact scope so a token
    issued for one scope never resumes another. Not an identity authority:
    it derives from the canonical scope only.
    """

    paths = tuple(sorted(set(scope.paths)))
    refs = tuple(sorted({ref.locator for ref in scope.evidence_refs}))
    return _hashlib.sha256(repr((paths, refs)).encode("utf-8")).hexdigest()[:16]


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
    max_delivered_evidence_bytes: int = 16_000


class CanonicalDecodeError(ValueError):
    """Raised when canonical data cannot be decoded into the target type.

    Carries append-only field-path context ([design note G](docs/design-references.md#g) §4.1b): `path` is
    a tuple of dotted field names with collection indices (for example
    `("target", "exact_subject_id", "canonical_locator")` or
    `("claims", "[3]")`). `reason` is the original failure text.
    `str()` renders `path: reason` when a path is present.
    """

    def __init__(self, message: str, path: tuple[str, ...] = ()) -> None:
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
