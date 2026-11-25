"""Functional Pyramid domain carriers.

Binding Version-2 document-placement carriers for the Functional Pyramid
integration (F11/F12, L12-L16, FD-61-FD-94). Import through
span.core.model rather than this module.
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


class FunctionalPyramidParticipationState(_enum.Enum):
    UNCONFIGURED = "UNCONFIGURED"
    EXCLUDED = "EXCLUDED"
    ACTIVE = "ACTIVE"


class FunctionalPyramidHealth(_enum.Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"


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
    INVALID_DECLARATION = "INVALID_DECLARATION"
    INVALID_PLACEMENT_SCOPE = "INVALID_PLACEMENT_SCOPE"
    DUPLICATE_DOCUMENT_PLACEMENT = "DUPLICATE_DOCUMENT_PLACEMENT"
    INVALID_DOCUMENT_REFERENCE = "INVALID_DOCUMENT_REFERENCE"
    MISSING_DOCUMENT_AUTHORITY = "MISSING_DOCUMENT_AUTHORITY"
    AMBIGUOUS_DOCUMENT_AUTHORITY = "AMBIGUOUS_DOCUMENT_AUTHORITY"
    NONCANONICAL_DOCUMENT_AUTHORITY = "NONCANONICAL_DOCUMENT_AUTHORITY"
    DOCUMENT_UNAVAILABLE = "DOCUMENT_UNAVAILABLE"
    UNKNOWN_DOCUMENT = "UNKNOWN_DOCUMENT"
    DOCUMENT_CYCLE = "DOCUMENT_CYCLE"
    INVALID_GOVERNING_EDGE = "INVALID_GOVERNING_EDGE"
    UNRESOLVED_DOCUMENT_PARENT = "UNRESOLVED_DOCUMENT_PARENT"
    REPOSITORY_UNAVAILABLE = "REPOSITORY_UNAVAILABLE"
    MISSING_ROOT_PLACEMENT = "MISSING_ROOT_PLACEMENT"


class FunctionalPyramidValidationReason(_enum.Enum):
    UNREGISTERED_MEMBER = "UNREGISTERED_MEMBER"
    DUPLICATE_MEMBER = "DUPLICATE_MEMBER"
    MEMBER_ALREADY_ACTIVE = "MEMBER_ALREADY_ACTIVE"
    UNKNOWN_PYRAMID = "UNKNOWN_PYRAMID"
    STALE_PYRAMID_VERSION = "STALE_PYRAMID_VERSION"
    MISSING_DECLARATION_SOURCE = "MISSING_DECLARATION_SOURCE"
    INVALID_DECLARATION_SOURCE = "INVALID_DECLARATION_SOURCE"


@_dataclass(frozen=True)
class FunctionalPyramidId:
    value: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidId", self.value)


@_dataclass(frozen=True)
class FunctionalPyramidVersion:
    value: int

    def __post_init__(self) -> None:
        _require_positive_int("FunctionalPyramidVersion", self.value)


@_dataclass(frozen=True)
class FunctionalRouteIdentity:
    value: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalRouteIdentity", self.value)


def _require_canonical_repository_path(name: str, value: str) -> None:
    _require_non_empty(name, value)
    if value.startswith("/") or "\\" in value:
        raise ValueError(f"{name} must be a canonical POSIX repository-relative path")
    if value.endswith("/"):
        raise ValueError(f"{name} must not use a trailing separator alias")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"{name} must not contain empty, dot, or traversal segments")


def _require_directory_scope(name: str, value: str) -> None:
    _require_non_empty(name, value)
    if value == ".":
        return
    _require_canonical_repository_path(name, value)


@_dataclass(frozen=True)
class FunctionalDirectoryScope:
    """Strict canonical repository-relative directory scope."""

    value: str

    def __post_init__(self) -> None:
        _require_directory_scope("FunctionalDirectoryScope.value", self.value)


@_dataclass(frozen=True)
class FunctionalDocumentRef:
    repository_id: str
    document_ref: str
    layer: FunctionalPyramidLayer

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalDocumentRef.repository_id", self.repository_id)
        _require_canonical_repository_path(
            "FunctionalDocumentRef.document_ref", self.document_ref
        )


@_dataclass(frozen=True)
class FunctionalDocumentPlacement:
    declaring_repository_id: str
    document: FunctionalDocumentRef
    scope: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalDocumentPlacement.declaring_repository_id",
            self.declaring_repository_id,
        )
        _require_directory_scope("FunctionalDocumentPlacement.scope", self.scope)


@_dataclass(frozen=True)
class FunctionalDocumentDeclaration:
    placement: FunctionalDocumentPlacement
    governing_placements: tuple[FunctionalDocumentPlacement | str, ...]

    def __post_init__(self) -> None:
        if not self.governing_placements:
            raise ValueError("FunctionalDocumentDeclaration requires a governing parent")
        for parent in self.governing_placements:
            if isinstance(parent, str) and parent != "ROOT":
                raise ValueError("the only string governing terminal is ROOT")
        if len(set(self.governing_placements)) != len(self.governing_placements):
            raise ValueError("governing placements must be distinct")


@_dataclass(frozen=True)
class FunctionalPyramidDeclaration:
    version: int
    placements: tuple[FunctionalDocumentDeclaration, ...] = ()

    def __post_init__(self) -> None:
        if self.version != 2:
            raise ValueError("FunctionalPyramidDeclaration.version must be 2")


@_dataclass(frozen=True)
class FunctionalPyramidBootstrap:
    version: int
    declaration_sources: tuple[EvidenceRequest, ...]

    def __post_init__(self) -> None:
        if self.version != 2:
            raise ValueError("FunctionalPyramidBootstrap.version must be 2")
        if not self.declaration_sources:
            raise ValueError("FunctionalPyramidBootstrap requires declaration sources")


@_dataclass(frozen=True)
class FunctionalPyramidMemberIntent:
    repository_id: str
    declaration_sources: tuple[EvidenceRequest, ...]

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidMemberIntent.repository_id", self.repository_id
        )
        if not self.declaration_sources:
            raise ValueError("FunctionalPyramidMemberIntent requires declaration sources")


@_dataclass(frozen=True)
class FunctionalPyramidMemberView:
    repository_id: str
    declaration_refs: tuple[EvidenceRef, ...]

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
            raise ValueError("ACTIVE participation is projected as FunctionalPyramidView")


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
    placement: FunctionalDocumentPlacement | None = None
    directory: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidFinding.detail", self.detail)
        _require_non_empty("FunctionalPyramidFinding.recovery", self.recovery)
        for name, value in (
            ("repository_id", self.repository_id),
            ("declaration_locator", self.declaration_locator),
        ):
            if value is not None:
                _require_non_empty(f"FunctionalPyramidFinding.{name}", value)
        if self.directory is not None:
            _require_directory_scope("FunctionalPyramidFinding.directory", self.directory)


@_dataclass(frozen=True)
class FunctionalPyramidValidationFinding:
    reason: FunctionalPyramidValidationReason
    detail: str
    recovery: str
    repository_id: str | None = None
    pyramid_id: FunctionalPyramidId | None = None
    declaration_locator: str | None = None
    directory: str | None = None
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
        if self.directory is not None:
            _require_directory_scope(
                "FunctionalPyramidValidationFinding.directory", self.directory
            )


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
                raise ValueError("ACTIVE status requires health, pyramid_id, and version")
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
            raise ValueError("inactive Functional Pyramid status has no health findings")


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
    repository_id: str
    directory: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalPyramidDirectorySelector.repository_id", self.repository_id
        )
        _require_directory_scope(
            "FunctionalPyramidDirectorySelector.directory", self.directory
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
class FunctionalDocumentRoute:
    placement: FunctionalDocumentPlacement
    authority: AuthorityBinding
    governing_placements: tuple[FunctionalDocumentPlacement | str, ...] = ()
    downstream_placements: tuple[FunctionalDocumentPlacement, ...] = ()

    def __post_init__(self) -> None:
        for parent in self.governing_placements:
            if isinstance(parent, str) and parent != "ROOT":
                raise ValueError("the only string governing terminal is ROOT")
        if len(set(self.governing_placements)) != len(self.governing_placements):
            raise ValueError("governing placements must be distinct")
        if len(set(self.downstream_placements)) != len(self.downstream_placements):
            raise ValueError("downstream placements must be distinct")


@_dataclass(frozen=True)
class FunctionalRouteProvenance:
    directory: str
    placements: tuple[FunctionalDocumentPlacement, ...]
    semantic_scope: EvidenceScope | None = None

    def __post_init__(self) -> None:
        _require_directory_scope("FunctionalRouteProvenance.directory", self.directory)
        if len(set(self.placements)) != len(self.placements):
            raise ValueError("FunctionalRouteProvenance placements must be distinct")


@_dataclass(frozen=True)
class FunctionalPyramidView:
    pyramid_id: FunctionalPyramidId
    version: FunctionalPyramidVersion
    health: FunctionalPyramidHealth
    status: FunctionalPyramidRouteStatus
    placements: tuple[FunctionalDocumentPlacement, ...]
    routes: tuple[FunctionalDocumentRoute, ...]
    provenance: tuple[FunctionalRouteProvenance, ...]
    declared_layers: tuple[FunctionalPyramidLayer, ...]
    absent_layers: tuple[FunctionalPyramidLayer, ...]
    directory: str | None = None
    semantic_scope: EvidenceScope | None = None
    unresolved: tuple[FunctionalPyramidFinding, ...] = ()

    def __post_init__(self) -> None:
        if (self.directory is None) == (self.semantic_scope is None):
            raise ValueError(
                "FunctionalPyramidView requires exactly one directory or semantic_scope"
            )
        if self.directory is not None:
            _require_directory_scope("FunctionalPyramidView.directory", self.directory)
        if self.status is FunctionalPyramidRouteStatus.RESOLVED and self.unresolved:
            raise ValueError("RESOLVED FunctionalPyramidView has no unresolved findings")
        if self.status is FunctionalPyramidRouteStatus.UNRESOLVED and not self.unresolved:
            raise ValueError("UNRESOLVED FunctionalPyramidView requires findings")
        if len(set(self.placements)) != len(self.placements):
            raise ValueError("FunctionalPyramidView placements must be distinct")
        if len(set(self.declared_layers)) != len(self.declared_layers):
            raise ValueError("declared_layers must be distinct")
        if len(set(self.absent_layers)) != len(self.absent_layers):
            raise ValueError("absent_layers must be distinct")
        if set(self.declared_layers) & set(self.absent_layers):
            raise ValueError("declared_layers and absent_layers must be disjoint")
        if set(self.declared_layers) | set(self.absent_layers) != set(FunctionalPyramidLayer):
            raise ValueError("declared_layers and absent_layers must cover every layer")


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
            raise ValueError("RetrievedFunctionalPyramidReceipt.committed_at must be aware")
        if len({effect.repository_id for effect in self.participation_effects}) != len(
            self.participation_effects
        ):
            raise ValueError("participation effects must be unique per repository")
        if len(set(self.dependent_effect_refs)) != len(self.dependent_effect_refs):
            raise ValueError("dependent effect refs must be distinct")
        if self.action in (FunctionalPyramidAction.ACTIVATE, FunctionalPyramidAction.REVISE):
            if self.pyramid_id is None or self.version is None or not self.members:
                raise ValueError("activate/revise receipt requires live instance members")
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
