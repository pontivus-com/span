"""Answer envelopes and status content.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import enum as _enum
import types as _types
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    AnswerId,
    AuthorityBinding,
    BoundInfo,
    ChangeCondition,
    ClaimRef,
    DeclaredPrecedence,
    EvidenceRef,
    EvidenceScope,
    FreshnessItem,
    HandleLifespan,
    ImpactItem,
    RelationshipRef,
    SemanticIntent,
    SubjectId,
    SubjectResolution,
)
from span.core.model.claims import (
    AssertionNature,
    SemanticClaim,
    SemanticConflict,
    SemanticRelationship,
    VerificationStatus,
)
from span.core.model.semantics import (
    RepositoryCoverageReport,
    ResolutionRequirement,
    ScopedCoverageReport,
    SemanticCoverageDisposition,
    SemanticQuestionCoverageView,
)
from span.core.model.repository import (
    RepositoryState,
    StoreReadiness,
    StructuralEdge,
    StructuralLocation,
)
from span.core.model.targets import (
    TargetAssociation,
)
from span.core.model.exchange import (
    EvidenceDependency,
)


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
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


@_dataclass(frozen=True)
class AuthorityContent:
    governing_bindings: tuple[AuthorityBinding, ...] = ()
    supersession: tuple[RelationshipRef, ...] = ()
    precedence: tuple[DeclaredPrecedence, ...] = ()
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()


class StatusResolvedMode(_enum.Enum):
    """Which status behaviour produced this content.

    The operation has one name and several shapes; the response says which one
    answered so a caller never has to infer it from field presence.
    """

    REPOSITORY = "REPOSITORY"
    SCOPED = "SCOPED"
    CAMPAIGN = "CAMPAIGN"
    UNRESOLVED = "UNRESOLVED"


@_dataclass(frozen=True)
class StatusContent:
    resolved_mode: StatusResolvedMode = StatusResolvedMode.UNRESOLVED
    store_readiness: StoreReadiness = StoreReadiness.READY
    freshness_items: tuple[FreshnessItem, ...] = ()
    changed_dependencies: tuple[EvidenceDependency, ...] = ()
    verification_status: tuple[VerificationStatus, ...] = ()
    refresh_scope: EvidenceScope | None = None
    claims: tuple[SemanticClaim, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    conflicts: tuple[SemanticConflict, ...] = ()
    question_coverage: tuple[SemanticQuestionCoverageView, ...] = ()
    coverage_report: RepositoryCoverageReport | ScopedCoverageReport | None = None
    target_association: TargetAssociation | None = None
    target_disposition: SemanticCoverageDisposition | None = None
    target_total_count: int | None = None
    target_handle_lifespan: HandleLifespan | None = None
    """Read-only campaign counts from the disposition snapshot
    ([design note H](docs/design-references.md#h) §7): total/current-accounted/unaccounted inventory.
    ``None`` exactly on UNVERIFIABLE/UNASSESSED (unavailable, never
    zero-faked). Answer envelope only — never persisted."""


SemanticContent = _typing.Union[
    ExplainContent,
    TraceContent,
    ImpactContent,
    AuthorityContent,
    StatusContent,
]
INTENT_CONTENT_TYPE: _typing.Mapping[SemanticIntent, type] = _types.MappingProxyType(
    {
        SemanticIntent.EXPLAIN: ExplainContent,
        SemanticIntent.TRACE: TraceContent,
        SemanticIntent.IMPACT: ImpactContent,
        SemanticIntent.AUTHORITY: AuthorityContent,
        SemanticIntent.STATUS: StatusContent,
    }
)


@_dataclass(frozen=True)
class SemanticAnswer:
    answer_id: AnswerId
    intent: SemanticIntent
    repository_state: RepositoryState
    content: SemanticContent
    bound_info: BoundInfo
    subject_resolution: SubjectResolution | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    resolution_requirements: tuple[ResolutionRequirement, ...] = ()
    state_explanation: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        expected = INTENT_CONTENT_TYPE[self.intent]
        if not isinstance(self.content, expected):
            raise ValueError(
                f"content for {self.intent.value} must be {expected.__name__}, "
                f"got {type(self.content).__name__}"
            )
        if not self.state_explanation:
            claims = tuple(getattr(self.content, "claims", ()))
            relationships = tuple(getattr(self.content, "relationships", ()))
            items = (*claims, *relationships)
            if not items:
                object.__setattr__(
                    self,
                    "state_explanation",
                    ("returned assertions: none",),
                )
            else:
                descriptive = sum(
                    1
                    for i in items
                    if getattr(i, "assertion_nature", None)
                    is AssertionNature.DESCRIPTIVE
                )
                normative = sum(
                    1
                    for i in items
                    if getattr(i, "assertion_nature", None) is AssertionNature.NORMATIVE
                )
                if descriptive and not normative:
                    distribution = "descriptive-only"
                elif normative and not descriptive:
                    distribution = "normative-only"
                else:
                    distribution = "mixed"
                sentence = (
                    f"returned assertions: {distribution} "
                    f"({descriptive} descriptive, {normative} "
                    "normative); authority-unresolved items stay "
                    "qualified regardless of nature"
                )
                object.__setattr__(
                    self,
                    "state_explanation",
                    (sentence,),
                )
