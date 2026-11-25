"""Functional Pyramid domain carriers.

Binding Version-1 carriers for the Functional Pyramid integration (F11/F12,
L12-L14, FD-61-FD-94). Import through span.core.model rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.investigation import EvidenceRequest
from span.core.model.primitives import (
    AuthorityBinding,
    ConclusionRevisionRef,
    EvidenceRef,
    EvidenceScope,
    RequestId,
    _require_non_empty,
    _require_positive_int,
)
from span.core.model.recording import ContentDigest


class FunctionalScopeSelectorKind(_enum.Enum):
    REPOSITORY = "REPOSITORY"
    PATH = "PATH"
    PREFIX = "PREFIX"
    SYMBOL = "SYMBOL"


class FunctionalPyramidCoverage(_enum.Enum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class FunctionalPyramidParticipationState(_enum.Enum):
    UNCONFIGURED = "UNCONFIGURED"
    EXCLUDED = "EXCLUDED"
    ACTIVE = "ACTIVE"


class FunctionalPyramidHealth(_enum.Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"


class FunctionalScopeRelation(_enum.Enum):
    OUTSIDE_FUNCTIONAL_SCOPE = "OUTSIDE_FUNCTIONAL_SCOPE"
    COVERED = "COVERED"
    UNCOVERED = "UNCOVERED"
    MIXED = "MIXED"


class FunctionalPyramidRouteStatus(_enum.Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class FunctionalPyramidLayer(_enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2S = "P2S"
    P2W = "P2W"
    P3 = "P3"
    P4 = "P4"


class FunctionalPyramidAction(_enum.Enum):
    ACTIVATE = "activate"
    REVISE = "revise"
    DEACTIVATE = "deactivate"
    EXCLUDE = "exclude"


class FunctionalPyramidFindingReason(_enum.Enum):
    UNCOVERED_PATH = "UNCOVERED_PATH"
    INVALID_DECLARATION = "INVALID_DECLARATION"
    UNRESOLVED_SCOPE_INTERSECTION = "UNRESOLVED_SCOPE_INTERSECTION"
    DUPLICATE_CONTEXT_OWNER = "DUPLICATE_CONTEXT_OWNER"
    UNKNOWN_CONTEXT = "UNKNOWN_CONTEXT"
    CONTEXT_CYCLE = "CONTEXT_CYCLE"
    REPOSITORY_UNAVAILABLE = "REPOSITORY_UNAVAILABLE"
    DUPLICATE_DOCUMENT_PLACEMENT = "DUPLICATE_DOCUMENT_PLACEMENT"
    UNKNOWN_DOCUMENT = "UNKNOWN_DOCUMENT"
    DOCUMENT_CYCLE = "DOCUMENT_CYCLE"
    INVALID_GOVERNING_EDGE = "INVALID_GOVERNING_EDGE"
    UNRESOLVED_DOCUMENT_PARENT = "UNRESOLVED_DOCUMENT_PARENT"


class FunctionalPyramidValidationReason(_enum.Enum):
    UNREGISTERED_MEMBER = "UNREGISTERED_MEMBER"
    DUPLICATE_MEMBER = "DUPLICATE_MEMBER"
    MEMBER_ALREADY_ACTIVE = "MEMBER_ALREADY_ACTIVE"
    UNKNOWN_PYRAMID = "UNKNOWN_PYRAMID"
    STALE_PYRAMID_VERSION = "STALE_PYRAMID_VERSION"
    MISSING_DECLARATION_SOURCE = "MISSING_DECLARATION_SOURCE"
    INVALID_DECLARATION_SOURCE = "INVALID_DECLARATION_SOURCE"
    INVALID_FUNCTIONAL_SCOPE = "INVALID_FUNCTIONAL_SCOPE"
    INCOMPLETE_COMPLETE_COVERAGE = "INCOMPLETE_COMPLETE_COVERAGE"


@_dataclass(frozen=True)
class FunctionalPyramidId:
    """Opaque server-owned Functional Pyramid identity."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidId", self.value)


@_dataclass(frozen=True)
class FunctionalPyramidVersion:
    """Positive compare-and-set version of one Functional Pyramid instance."""

    value: int

    def __post_init__(self) -> None:
        _require_positive_int("FunctionalPyramidVersion", self.value)


@_dataclass(frozen=True)
class FunctionalRouteIdentity:
    """Canonical digest/value of FD-73 governing applicability."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalRouteIdentity", self.value)


def _require_canonical_repository_path(name: str, value: str) -> None:
    _require_non_empty(name, value)
    if value.startswith("/") or "\\" in value:
        raise ValueError(f"{name} must be canonical POSIX repository-relative path")
    if value.endswith("/"):
        raise ValueError(f"{name} must not use a trailing separator alias")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"{name} must not contain empty, dot, or traversal segments")


@_dataclass(frozen=True)
class FunctionalScopeSelector:
    """One strict Version-1 FunctionalScope selector."""

    kind: FunctionalScopeSelectorKind
    path: str | None = None
    locator: str | None = None

    def __post_init__(self) -> None:
        if self.kind is FunctionalScopeSelectorKind.REPOSITORY:
            if self.path is not None or self.locator is not None:
                raise ValueError("REPOSITORY selector has no path or locator")
            return

        if self.path is None:
            raise ValueError(f"{self.kind.value} selector requires path")
        _require_canonical_repository_path("FunctionalScopeSelector.path", self.path)

        if self.kind in (
            FunctionalScopeSelectorKind.PATH,
            FunctionalScopeSelectorKind.PREFIX,
        ):
            if self.locator is not None:
                raise ValueError(f"{self.kind.value} selector has no locator")
            return

        if self.kind is FunctionalScopeSelectorKind.SYMBOL:
            if self.locator is None:
                raise ValueError("SYMBOL selector requires locator")
            _require_non_empty("FunctionalScopeSelector.locator", self.locator)
            return

        raise ValueError(f"unsupported FunctionalScope selector kind: {self.kind!r}")


@_dataclass(frozen=True)
class FunctionalScope:
    """Non-empty FunctionalScope selector set shared by coverage and contexts."""

    selectors: tuple[FunctionalScopeSelector, ...]

    def __post_init__(self) -> None:
        if not self.selectors:
            raise ValueError("FunctionalScope requires at least one selector")
        if len(set(self.selectors)) != len(self.selectors):
            raise ValueError("FunctionalScope selectors must be distinct")


@_dataclass(frozen=True)
class FunctionalGraphRef:
    """Repository-qualified identity used by declaration edges."""

    repository_id: str
    identity: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalGraphRef.repository_id", self.repository_id)
        _require_non_empty("FunctionalGraphRef.identity", self.identity)


@_dataclass(frozen=True)
class FunctionalDocumentRef:
    """Stable repository-qualified placement of one canonical document."""

    repository_id: str
    document_ref: str
    layer: FunctionalPyramidLayer

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalDocumentRef.repository_id", self.repository_id)
        _require_non_empty("FunctionalDocumentRef.document_ref", self.document_ref)


@_dataclass(frozen=True)
class FunctionalContextDeclaration:
    context_id: str
    coverage: FunctionalScope
    inherits: tuple[FunctionalGraphRef, ...] = ()
    documents: tuple[FunctionalDocumentRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalContextDeclaration.context_id", self.context_id)
        if len(set(self.inherits)) != len(self.inherits):
            raise ValueError(
                "FunctionalContextDeclaration.inherits contains duplicates"
            )
        if len(set(self.documents)) != len(self.documents):
            raise ValueError(
                "FunctionalContextDeclaration.documents contains duplicates"
            )


@_dataclass(frozen=True)
class FunctionalDocumentDeclaration:
    document: FunctionalDocumentRef
    governing_documents: tuple[FunctionalDocumentRef | str, ...] = ()

    def __post_init__(self) -> None:
        for document_ref in self.governing_documents:
            if isinstance(document_ref, str) and document_ref != "ROOT":
                raise ValueError(
                    "FunctionalDocumentDeclaration string parent must be ROOT"
                )
        if len(set(self.governing_documents)) != len(self.governing_documents):
            raise ValueError(
                "FunctionalDocumentDeclaration.governing_documents contains duplicates"
            )


@_dataclass(frozen=True)
class FunctionalPyramidDeclaration:
    version: int
    contexts: tuple[FunctionalContextDeclaration, ...] = ()
    documents: tuple[FunctionalDocumentDeclaration, ...] = ()

    def __post_init__(self) -> None:
        if self.version != 2:
            raise ValueError("FunctionalPyramidDeclaration.version must be 2")
        if not (self.contexts or self.documents):
            raise ValueError("a Functional Pyramid declaration cannot be empty")


@_dataclass(frozen=True)
class FunctionalPyramidBootstrap:
    version: int
    functional_scope: FunctionalScope
    coverage: FunctionalPyramidCoverage
    declaration_sources: tuple[EvidenceRequest, ...]

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError("FunctionalPyramidBootstrap.version must be 1")
        if not self.declaration_sources:
            raise ValueError("FunctionalPyramidBootstrap requires declaration sources")


@_dataclass(frozen=True)
class FunctionalPyramidMemberIntent:
    repository_id: str
    declaration_sources: tuple[EvidenceRequest, ...]
    functional_scope: FunctionalScope
    coverage: FunctionalPyramidCoverage

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidMemberIntent.repository_id", self.repository_id
        )
        if not self.declaration_sources:
            raise ValueError(
                "FunctionalPyramidMemberIntent requires declaration sources"
            )


@_dataclass(frozen=True)
class FunctionalPyramidMemberView:
    repository_id: str
    declaration_refs: tuple[EvidenceRef, ...]
    functional_scope: FunctionalScope
    coverage: FunctionalPyramidCoverage

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidMemberView.repository_id", self.repository_id
        )
        if not self.declaration_refs:
            raise ValueError("FunctionalPyramidMemberView requires declaration refs")
        for ref in self.declaration_refs:
            if ref.repository_id != self.repository_id:
                raise ValueError(
                    "FunctionalPyramidMemberView declaration ref crosses repositories"
                )


@_dataclass(frozen=True)
class FunctionalPyramidParticipation:
    state: FunctionalPyramidParticipationState

    def __post_init__(self) -> None:
        if self.state is FunctionalPyramidParticipationState.ACTIVE:
            raise ValueError(
                "ACTIVE participation is projected as FunctionalPyramidView"
            )


@_dataclass(frozen=True)
class FunctionalPyramidParticipationEffect:
    repository_id: str
    state: FunctionalPyramidParticipationState

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidParticipationEffect.repository_id", self.repository_id
        )


@_dataclass(frozen=True)
class FunctionalPyramidFinding:
    reason: FunctionalPyramidFindingReason
    detail: str
    recovery: str
    repository_id: str | None = None
    declaration_locator: str | None = None
    context_id: str | None = None
    document: FunctionalDocumentRef | None = None

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidFinding.detail", self.detail)
        _require_non_empty("FunctionalPyramidFinding.recovery", self.recovery)
        for name, value in (
            ("repository_id", self.repository_id),
            ("declaration_locator", self.declaration_locator),
            ("context_id", self.context_id),
        ):
            if value is not None:
                _require_non_empty(f"FunctionalPyramidFinding.{name}", value)


@_dataclass(frozen=True)
class FunctionalPyramidValidationFinding:
    reason: FunctionalPyramidValidationReason
    detail: str
    recovery: str
    repository_id: str | None = None
    pyramid_id: FunctionalPyramidId | None = None
    declaration_locator: str | None = None
    expected_version: FunctionalPyramidVersion | None = None
    current_version: FunctionalPyramidVersion | None = None

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidValidationFinding.detail", self.detail)
        _require_non_empty("FunctionalPyramidValidationFinding.recovery", self.recovery)
        for name, value in (
            ("repository_id", self.repository_id),
            ("declaration_locator", self.declaration_locator),
        ):
            if value is not None:
                _require_non_empty(f"FunctionalPyramidValidationFinding.{name}", value)


@_dataclass(frozen=True)
class FunctionalPyramidStatus:
    state: FunctionalPyramidParticipationState
    health: FunctionalPyramidHealth | None = None
    pyramid_id: FunctionalPyramidId | None = None
    version: FunctionalPyramidVersion | None = None
    members: tuple[FunctionalPyramidMemberView, ...] = ()
    findings: tuple[FunctionalPyramidFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.state is FunctionalPyramidParticipationState.ACTIVE:
            if self.health is None or self.pyramid_id is None or self.version is None:
                raise ValueError(
                    "ACTIVE status requires health, pyramid_id, and version"
                )
            if not self.members:
                raise ValueError("ACTIVE status requires at least one member")
            if self.health is FunctionalPyramidHealth.VALID and self.findings:
                raise ValueError("VALID Functional Pyramid status has no findings")
            if self.health is FunctionalPyramidHealth.DEGRADED and not self.findings:
                raise ValueError("DEGRADED Functional Pyramid status requires findings")
            return

        if self.health is not None:
            raise ValueError("inactive Functional Pyramid status has no health")
        if self.pyramid_id is not None or self.version is not None or self.members:
            raise ValueError("inactive Functional Pyramid status has no live instance")
        if self.findings:
            raise ValueError(
                "inactive Functional Pyramid status has no health findings"
            )


@_dataclass(frozen=True)
class FunctionalPyramidSelector:
    repository_id: str | None = None
    pyramid_id: FunctionalPyramidId | None = None

    def __post_init__(self) -> None:
        if (self.repository_id is None) == (self.pyramid_id is None):
            raise ValueError(
                "FunctionalPyramidSelector requires exactly one repository_id or pyramid_id"
            )
        if self.repository_id is not None:
            _require_non_empty(
                "FunctionalPyramidSelector.repository_id", self.repository_id
            )


@_dataclass(frozen=True)
class FunctionalPyramidDirectorySelector:
    """Exact directory selection for governing-document orientation."""

    repository_id: str
    directory: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidDirectorySelector.repository_id", self.repository_id
        )
        _require_non_empty(
            "FunctionalPyramidDirectorySelector.directory", self.directory
        )
        if self.directory.startswith("/") or ".." in self.directory.split("/"):
            raise ValueError(
                "FunctionalPyramidDirectorySelector.directory must be repository-relative"
            )


@_dataclass(frozen=True)
class FunctionalPyramidCandidateSelector:
    action: FunctionalPyramidAction
    members: tuple[FunctionalPyramidMemberIntent, ...]
    pyramid_id: FunctionalPyramidId | None = None
    expected_version: FunctionalPyramidVersion | None = None

    def __post_init__(self) -> None:
        if self.action not in (
            FunctionalPyramidAction.ACTIVATE,
            FunctionalPyramidAction.REVISE,
        ):
            raise ValueError("candidate action must be activate or revise")
        if not self.members:
            raise ValueError("FunctionalPyramidCandidateSelector requires members")
        revising = self.action is FunctionalPyramidAction.REVISE
        if revising != (self.pyramid_id is not None):
            raise ValueError("revise candidate requires pyramid_id")
        if revising != (self.expected_version is not None):
            raise ValueError("revise candidate requires expected_version")


@_dataclass(frozen=True)
class FunctionalPyramidCandidate:
    action: FunctionalPyramidAction
    members: tuple[FunctionalPyramidMemberView, ...]
    activation_ready: bool
    validation_findings: tuple[FunctionalPyramidValidationFinding, ...] = ()
    graph_findings: tuple[FunctionalPyramidFinding, ...] = ()
    pyramid_id: FunctionalPyramidId | None = None
    version: FunctionalPyramidVersion | None = None

    def __post_init__(self) -> None:
        if self.action not in (
            FunctionalPyramidAction.ACTIVATE,
            FunctionalPyramidAction.REVISE,
        ):
            raise ValueError("candidate action must be activate or revise")
        revising = self.action is FunctionalPyramidAction.REVISE
        if revising != (self.pyramid_id is not None):
            raise ValueError("revise candidate requires pyramid_id")
        if revising and self.version is None:
            unknown_target = any(
                finding.reason is FunctionalPyramidValidationReason.UNKNOWN_PYRAMID
                for finding in self.validation_findings
            )
            if not unknown_target:
                raise ValueError(
                    "revise candidate requires target version unless target is unknown"
                )
        if not revising and self.version is not None:
            raise ValueError("activate candidate has no target version")
        expected_ready = not self.validation_findings and not self.graph_findings
        if self.activation_ready != expected_ready:
            raise ValueError(
                "FunctionalPyramidCandidate.activation_ready must match findings"
            )


@_dataclass(frozen=True)
class FunctionalContextRoute:
    context_id: str
    repository_id: str
    direct: bool
    coverage: FunctionalScope
    inherits: tuple[str, ...] = ()
    documents: tuple[FunctionalDocumentRef, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalContextRoute.context_id", self.context_id)
        _require_non_empty("FunctionalContextRoute.repository_id", self.repository_id)
        for value in self.inherits:
            _require_non_empty("FunctionalContextRoute.inherits", value)
        if len(set(self.inherits)) != len(self.inherits):
            raise ValueError("FunctionalContextRoute.inherits contains duplicates")
        if len(set(self.documents)) != len(self.documents):
            raise ValueError("FunctionalContextRoute.documents contains duplicates")


@_dataclass(frozen=True)
class FunctionalDocumentRoute:
    document: FunctionalDocumentRef
    authority: AuthorityBinding
    governing_documents: tuple[FunctionalDocumentRef | str, ...] = ()
    downstream_documents: tuple[FunctionalDocumentRef, ...] = ()
    downstream_context_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, values in (
            ("governing_documents", self.governing_documents),
            ("downstream_documents", self.downstream_documents),
            ("downstream_context_ids", self.downstream_context_ids),
        ):
            for value in values:
                if isinstance(value, str):
                    _require_non_empty(f"FunctionalDocumentRoute.{name}", value)
            if len(set(values)) != len(values):
                raise ValueError(
                    f"FunctionalDocumentRoute.{name} contains duplicates"
                )


@_dataclass(frozen=True)
class FunctionalRouteProvenance:
    semantic_scope: EvidenceScope | None
    directory: str | None
    relation: FunctionalScopeRelation
    context_ids: tuple[str, ...] = ()
    documents: tuple[FunctionalDocumentRef, ...] = ()

    def __post_init__(self) -> None:
        if (self.semantic_scope is None) == (self.directory is None):
            raise ValueError(
                "FunctionalRouteProvenance requires exactly one selection"
            )
        if self.relation is FunctionalScopeRelation.MIXED:
            raise ValueError("provenance portions cannot themselves be MIXED")
        for value in self.context_ids:
            _require_non_empty("FunctionalRouteProvenance.context_ids", value)
        if len(set(self.context_ids)) != len(self.context_ids):
            raise ValueError(
                "FunctionalRouteProvenance.context_ids contains duplicates"
            )
        if len(set(self.documents)) != len(self.documents):
            raise ValueError(
                "FunctionalRouteProvenance.documents contains duplicates"
            )


@_dataclass(frozen=True)
class FunctionalPyramidView:
    pyramid_id: FunctionalPyramidId
    version: FunctionalPyramidVersion
    health: FunctionalPyramidHealth
    coverage: FunctionalPyramidCoverage
    scope_relation: FunctionalScopeRelation
    status: FunctionalPyramidRouteStatus
    semantic_scope: EvidenceScope | None = None
    directory: str | None = None
    contexts: tuple[FunctionalContextRoute, ...] = ()
    documents: tuple[FunctionalDocumentRoute, ...] = ()
    provenance: tuple[FunctionalRouteProvenance, ...] = ()
    unresolved: tuple[FunctionalPyramidFinding, ...] = ()

    def __post_init__(self) -> None:
        if (self.semantic_scope is None) == (self.directory is None):
            raise ValueError("FunctionalPyramidView requires exactly one selection")
        if self.status is FunctionalPyramidRouteStatus.RESOLVED and self.unresolved:
            raise ValueError(
                "RESOLVED FunctionalPyramidView has no unresolved findings"
            )
        if (
            self.status is FunctionalPyramidRouteStatus.UNRESOLVED
            and not self.unresolved
        ):
            raise ValueError("UNRESOLVED FunctionalPyramidView requires findings")
        if self.scope_relation is FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE:
            if self.status is not FunctionalPyramidRouteStatus.RESOLVED:
                raise ValueError("outside FunctionalScope is a resolved empty route")
            if self.contexts or self.documents or self.unresolved:
                raise ValueError(
                    "outside FunctionalScope has no governing route members"
                )
        if self.scope_relation is FunctionalScopeRelation.UNCOVERED:
            if self.status is not FunctionalPyramidRouteStatus.UNRESOLVED:
                raise ValueError("UNCOVERED FunctionalPyramidView is unresolved")


@_dataclass(frozen=True)
class FunctionalPyramidUnavailable:
    failure: str
    recovery: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidUnavailable.failure", self.failure)
        _require_non_empty("FunctionalPyramidUnavailable.recovery", self.recovery)


@_dataclass(frozen=True)
class FunctionalPyramidReceiptSelector:
    request_id: RequestId


@_dataclass(frozen=True)
class RetrievedFunctionalPyramidReceipt:
    request_id: RequestId
    content_digest: ContentDigest
    committed_at: _datetime.datetime
    action: FunctionalPyramidAction
    pyramid_id: FunctionalPyramidId | None
    version: FunctionalPyramidVersion | None
    members: tuple[FunctionalPyramidMemberView, ...]
    participation_effects: tuple[FunctionalPyramidParticipationEffect, ...]
    dependent_effect_refs: tuple[ConclusionRevisionRef, ...]

    def __post_init__(self) -> None:
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            raise ValueError(
                "RetrievedFunctionalPyramidReceipt.committed_at must be aware"
            )
        if len({effect.repository_id for effect in self.participation_effects}) != len(
            self.participation_effects
        ):
            raise ValueError("participation effects must be unique per repository")
        if len(set(self.dependent_effect_refs)) != len(self.dependent_effect_refs):
            raise ValueError("dependent effect refs must be distinct")

        if self.action in (
            FunctionalPyramidAction.ACTIVATE,
            FunctionalPyramidAction.REVISE,
        ):
            if self.pyramid_id is None or self.version is None or not self.members:
                raise ValueError(
                    "activate/revise receipt requires live instance members"
                )
            return

        if self.members:
            raise ValueError("deactivate/exclude receipt has no active members")
        if self.action is FunctionalPyramidAction.DEACTIVATE:
            if self.pyramid_id is None or self.version is None:
                raise ValueError("deactivate receipt requires pyramid identity/version")
            return
        if self.action is FunctionalPyramidAction.EXCLUDE:
            if self.pyramid_id is not None or self.version is not None:
                raise ValueError("exclude receipt has no pyramid identity/version")


@_dataclass(frozen=True)
class FunctionalRouteSupport:
    """Server-derived support for exact governing applicability (FD-73/FD-75)."""

    repository_id: str
    pyramid_id: FunctionalPyramidId
    semantic_scope: EvidenceScope
    route_identity: FunctionalRouteIdentity

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalRouteSupport.repository_id", self.repository_id)
