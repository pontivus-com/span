"""Functional Pyramid domain carriers.

Binding Version-2 document-placement carriers for the Functional Pyramid
integration (F11/F12, L12-L16, FD-61-FD-94). Import through
span.core.model rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import pathlib as _pathlib
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core.model.investigation import EvidenceRequest
from span.core.model.primitives import (
    AuthorityBinding,
    EvidenceRef,
    EvidenceScope,
    RequestId,
    _require_non_empty,
    _require_positive_int,
)


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


class FunctionalPyramidSourceKind(_enum.Enum):
    REPOSITORY = "repository"
    AREA = "area"


class FunctionalPyramidFindingReason(_enum.Enum):
    INVALID_DECLARATION = "INVALID_DECLARATION"
    INVALID_PLACEMENT_SCOPE = "INVALID_PLACEMENT_SCOPE"
    DUPLICATE_DOCUMENT_PLACEMENT = "DUPLICATE_DOCUMENT_PLACEMENT"
    DUPLICATE_DOCUMENT_SOURCE = "DUPLICATE_DOCUMENT_SOURCE"
    DUPLICATE_DOCUMENT_LAYER = "DUPLICATE_DOCUMENT_LAYER"
    DUPLICATE_DOCUMENT_SCOPE = "DUPLICATE_DOCUMENT_SCOPE"
    DOCUMENT_SCOPE_MISMATCH = "DOCUMENT_SCOPE_MISMATCH"
    MISSING_AREA_DOCUMENT = "MISSING_AREA_DOCUMENT"
    UNLISTED_AREA_DOCUMENT = "UNLISTED_AREA_DOCUMENT"
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


class FunctionalPyramidPublicReason(_enum.Enum):
    DECLARATION_INVALID = "DECLARATION_INVALID"
    DOCUMENT_SET_INCOMPLETE = "DOCUMENT_SET_INCOMPLETE"
    DOCUMENT_UNAVAILABLE = "DOCUMENT_UNAVAILABLE"
    DOCUMENT_AMBIGUOUS = "DOCUMENT_AMBIGUOUS"
    GOVERNANCE_UNAVAILABLE = "GOVERNANCE_UNAVAILABLE"
    UNREGISTERED_MEMBER = "UNREGISTERED_MEMBER"
    DUPLICATE_MEMBER = "DUPLICATE_MEMBER"
    MEMBER_ALREADY_ACTIVE = "MEMBER_ALREADY_ACTIVE"
    UNKNOWN_PYRAMID = "UNKNOWN_PYRAMID"
    STALE_PYRAMID_VERSION = "STALE_PYRAMID_VERSION"


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
class FunctionalDocumentIdentity:
    """Layer-independent canonical whole-document identity."""

    repository_id: str
    document_ref: str

    def __post_init__(self) -> None:
        _require_non_empty(
            "FunctionalDocumentIdentity.repository_id", self.repository_id
        )
        _require_canonical_repository_path(
            "FunctionalDocumentIdentity.document_ref", self.document_ref
        )


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

    @property
    def identity(self) -> FunctionalDocumentIdentity:
        return FunctionalDocumentIdentity(
            repository_id=self.repository_id,
            document_ref=self.document_ref,
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
            raise ValueError(
                "FunctionalDocumentDeclaration requires a governing parent"
            )
        for parent in self.governing_placements:
            if isinstance(parent, str) and parent != "ROOT":
                raise ValueError("the only string governing terminal is ROOT")
        if len(set(self.governing_placements)) != len(self.governing_placements):
            raise ValueError("governing placements must be distinct")


@_dataclass(frozen=True)
class FunctionalPyramidDeclaration:
    """One Version-3 canonical declaration source (FD-66, S1-S11)."""

    version: int
    source_id: str
    kind: FunctionalPyramidSourceKind
    scope: str
    documents: tuple[FunctionalDocumentIdentity, ...]
    placements: tuple[FunctionalDocumentDeclaration, ...] = ()

    def __post_init__(self) -> None:
        if self.version != 3:
            raise ValueError("FunctionalPyramidDeclaration.version must be 3")
        _require_non_empty("FunctionalPyramidDeclaration.source_id", self.source_id)
        _require_directory_scope("FunctionalPyramidDeclaration.scope", self.scope)
        if not isinstance(self.kind, FunctionalPyramidSourceKind):
            raise ValueError("FunctionalPyramidDeclaration.kind must be a source kind")


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
            raise ValueError(
                "FunctionalPyramidMemberIntent requires declaration sources"
            )


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
class FunctionalPyramidPath:
    """A usable location in a registered repository root's coordinates."""

    repository_id: str
    path: str

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalPyramidPath.repository_id", self.repository_id)
        _require_directory_scope("FunctionalPyramidPath.path", self.path)


@_dataclass(frozen=True)
class FunctionalPyramidPlacementView:
    """Public coordinates for a canonical declaration placement."""

    declaring_repository_id: str
    document_repository_id: str
    layer: FunctionalPyramidLayer
    document: FunctionalPyramidPath
    scope: FunctionalPyramidPath

    def __post_init__(self) -> None:
        _require_non_empty("declaring_repository_id", self.declaring_repository_id)
        _require_non_empty("document_repository_id", self.document_repository_id)
        _require_canonical_repository_path("placement document", self.document.path)


def public_pyramid_path(
    repository_id: str, path: str, roots: _typing.Mapping[str, str]
) -> FunctionalPyramidPath:
    """Rebase an owner-relative path to its outermost registered ancestor."""
    _require_directory_scope("public path", path)
    owner = _pathlib.PurePath(roots[repository_id])
    ancestors = [
        (len(base.parts), identity, base)
        for identity, root in roots.items()
        if owner.is_relative_to(base := _pathlib.PurePath(root))
    ]
    depth = min(item[0] for item in ancestors)
    outer = [item for item in ancestors if item[0] == depth]
    if len(outer) != 1:
        raise ValueError("public path has ambiguous registered root coordinates")
    _, identity, base = outer[0]
    return FunctionalPyramidPath(identity, (owner / path).relative_to(base).as_posix())


def public_pyramid_placement(
    placement: FunctionalDocumentPlacement, roots: _typing.Mapping[str, str]
) -> FunctionalPyramidPlacementView:
    return FunctionalPyramidPlacementView(
        declaring_repository_id=placement.declaring_repository_id,
        document_repository_id=placement.document.repository_id,
        layer=placement.document.layer,
        document=public_pyramid_path(
            placement.document.repository_id, placement.document.document_ref, roots
        ),
        scope=public_pyramid_path(
            placement.declaring_repository_id, placement.scope, roots
        ),
    )


@_dataclass(frozen=True)
class FunctionalPyramidParticipation:
    state: FunctionalPyramidParticipationState
    resolved_repository_id: str | None = None
    directory: FunctionalPyramidPath | None = None

    def __post_init__(self) -> None:
        if (self.resolved_repository_id is None) != (self.directory is None):
            raise ValueError("directory participation requires owner and path")
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
            _require_directory_scope(
                "FunctionalPyramidFinding.directory", self.directory
            )


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
class FunctionalPyramidPublicFinding:
    """Public governance finding (FD-88B); internal provenance stays private."""

    reason: FunctionalPyramidPublicReason
    detail: str
    recovery: str
    repository_id: str | None = None
    directory: FunctionalPyramidPath | None = None
    placement: FunctionalPyramidPlacementView | None = None
    pyramid_id: FunctionalPyramidId | None = None
    expected_version: FunctionalPyramidVersion | None = None
    current_version: FunctionalPyramidVersion | None = None


def public_pyramid_finding(
    finding: FunctionalPyramidFinding | FunctionalPyramidValidationFinding,
    roots: _typing.Mapping[str, str],
) -> FunctionalPyramidPublicFinding:
    """Project internal diagnostics onto the exact public vocabulary."""
    directory = (
        public_pyramid_path(finding.repository_id, finding.directory, roots)
        if finding.repository_id is not None
        and finding.repository_id in roots
        and finding.directory is not None
        else None
    )
    if isinstance(finding, FunctionalPyramidValidationFinding):
        reason = (
            FunctionalPyramidPublicReason.DECLARATION_INVALID
            if finding.reason
            in (
                FunctionalPyramidValidationReason.MISSING_DECLARATION_SOURCE,
                FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
            )
            else FunctionalPyramidPublicReason(finding.reason.value)
        )
        return FunctionalPyramidPublicFinding(
            reason=reason,
            detail=(
                "Declaration source is missing or invalid"
                if reason is FunctionalPyramidPublicReason.DECLARATION_INVALID
                else finding.detail
            ),
            recovery=(
                "Correct the classification and rerun governed installation"
                if reason is FunctionalPyramidPublicReason.DECLARATION_INVALID
                else finding.recovery
            ),
            repository_id=finding.repository_id,
            directory=directory,
            pyramid_id=finding.pyramid_id,
            expected_version=finding.expected_version,
            current_version=finding.current_version,
        )
    reason = {
        FunctionalPyramidFindingReason.INVALID_DECLARATION: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.DOCUMENT_SCOPE_MISMATCH: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.INVALID_DOCUMENT_REFERENCE: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.NONCANONICAL_DOCUMENT_AUTHORITY: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.DOCUMENT_CYCLE: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE: FunctionalPyramidPublicReason.DECLARATION_INVALID,
        FunctionalPyramidFindingReason.MISSING_AREA_DOCUMENT: FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE,
        FunctionalPyramidFindingReason.UNLISTED_AREA_DOCUMENT: FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE,
        FunctionalPyramidFindingReason.UNKNOWN_DOCUMENT: FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE,
        FunctionalPyramidFindingReason.UNRESOLVED_DOCUMENT_PARENT: FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE,
        FunctionalPyramidFindingReason.MISSING_ROOT_PLACEMENT: FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE,
        FunctionalPyramidFindingReason.DOCUMENT_UNAVAILABLE: FunctionalPyramidPublicReason.DOCUMENT_UNAVAILABLE,
        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_PLACEMENT: FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS,
        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_SOURCE: FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS,
        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_LAYER: FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS,
        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_SCOPE: FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS,
        FunctionalPyramidFindingReason.AMBIGUOUS_DOCUMENT_AUTHORITY: FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS,
        FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE: FunctionalPyramidPublicReason.GOVERNANCE_UNAVAILABLE,
        FunctionalPyramidFindingReason.MISSING_DOCUMENT_AUTHORITY: FunctionalPyramidPublicReason.GOVERNANCE_UNAVAILABLE,
    }[finding.reason]
    detail, recovery = {
        FunctionalPyramidPublicReason.DECLARATION_INVALID: (
            "Governance declaration is invalid",
            "Correct the classification and rerun governed installation",
        ),
        FunctionalPyramidPublicReason.DOCUMENT_SET_INCOMPLETE: (
            "Required governing documents are incomplete",
            "Supply the required documents and governing references in the classification",
        ),
        FunctionalPyramidPublicReason.DOCUMENT_UNAVAILABLE: (
            "A governing document is unavailable",
            "Restore the canonical governing document",
        ),
        FunctionalPyramidPublicReason.DOCUMENT_AMBIGUOUS: (
            "Governing document placement or authority is ambiguous",
            "Resolve conflicting classification or authority decisions",
        ),
        FunctionalPyramidPublicReason.GOVERNANCE_UNAVAILABLE: (
            "Required governance is unavailable",
            "Restore the participating repository and authority binding",
        ),
    }[reason]
    return FunctionalPyramidPublicFinding(
        reason=reason,
        detail=detail,
        recovery=recovery,
        repository_id=finding.repository_id,
        directory=directory,
        placement=(
            public_pyramid_placement(finding.placement, roots)
            if finding.placement is not None
            and finding.placement.declaring_repository_id in roots
            and finding.placement.document.repository_id in roots
            else None
        ),
    )


@_dataclass(frozen=True)
class FunctionalPyramidStatus:
    state: FunctionalPyramidParticipationState
    health: FunctionalPyramidHealth | None = None
    pyramid_id: FunctionalPyramidId | None = None
    version: FunctionalPyramidVersion | None = None
    member_repository_ids: tuple[str, ...] = ()
    findings: tuple[FunctionalPyramidPublicFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.state is FunctionalPyramidParticipationState.ACTIVE:
            if self.health is None or self.pyramid_id is None or self.version is None:
                raise ValueError(
                    "ACTIVE status requires health, pyramid_id, and version"
                )
            if not self.member_repository_ids:
                raise ValueError("ACTIVE status requires at least one member")
            if len(set(self.member_repository_ids)) != len(self.member_repository_ids):
                raise ValueError("ACTIVE status member identities must be distinct")
            if self.health is FunctionalPyramidHealth.VALID and self.findings:
                raise ValueError("VALID Functional Pyramid status has no findings")
            if self.health is FunctionalPyramidHealth.DEGRADED and not self.findings:
                raise ValueError("DEGRADED Functional Pyramid status requires findings")
            return
        if self.health is not None:
            raise ValueError("inactive Functional Pyramid status has no health")
        if (
            self.pyramid_id is not None
            or self.version is not None
            or self.member_repository_ids
        ):
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
    repository_id: str
    directory: str
    after: str | None = None

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
    activation_ready: bool
    validation_findings: tuple[FunctionalPyramidPublicFinding, ...] = ()
    graph_findings: tuple[FunctionalPyramidPublicFinding, ...] = ()
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
                finding.reason is FunctionalPyramidPublicReason.UNKNOWN_PYRAMID
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
    """The compact public governing projection (technical design §17.1)."""

    pyramid_id: FunctionalPyramidId
    version: FunctionalPyramidVersion
    status: FunctionalPyramidRouteStatus
    placements: tuple[FunctionalPyramidPlacementView, ...]
    declared_layers: tuple[FunctionalPyramidLayer, ...]
    absent_layers: tuple[FunctionalPyramidLayer, ...]
    resolved_repository_id: str | None = None
    directory: FunctionalPyramidPath | None = None
    semantic_scope: EvidenceScope | None = None
    unresolved: tuple[FunctionalPyramidPublicFinding, ...] = ()
    truncated: bool = False
    omitted: tuple[str, ...] = ()
    next_after: str | None = None

    def __post_init__(self) -> None:
        if (self.directory is None) == (self.semantic_scope is None):
            raise ValueError(
                "FunctionalPyramidView requires exactly one directory or semantic_scope"
            )
        if (self.resolved_repository_id is None) != (self.directory is None):
            raise ValueError("directory view requires resolved repository identity")
        if self.status is FunctionalPyramidRouteStatus.RESOLVED and self.unresolved:
            raise ValueError(
                "RESOLVED FunctionalPyramidView has no unresolved findings"
            )
        if (
            self.status is FunctionalPyramidRouteStatus.UNRESOLVED
            and not self.unresolved
        ):
            raise ValueError("UNRESOLVED FunctionalPyramidView requires findings")
        if len(set(self.placements)) != len(self.placements):
            raise ValueError("FunctionalPyramidView placements must be distinct")
        if self.next_after is not None and (
            not self.truncated or self.directory is None
        ):
            raise ValueError(
                "directory continuation requires a truncated directory view"
            )
        if self.truncated != bool(self.omitted):
            raise ValueError(
                "FunctionalPyramidView truncation requires exactly omitted entries"
            )
        if len(set(self.declared_layers)) != len(self.declared_layers):
            raise ValueError("declared_layers must be distinct")
        if len(set(self.absent_layers)) != len(self.absent_layers):
            raise ValueError("absent_layers must be distinct")
        if set(self.declared_layers) & set(self.absent_layers):
            raise ValueError("declared_layers and absent_layers must be disjoint")
        if set(self.declared_layers) | set(self.absent_layers) != set(
            FunctionalPyramidLayer
        ):
            raise ValueError("declared_layers and absent_layers must cover every layer")


@_dataclass(frozen=True)
class FunctionalPyramidResolution:
    """Internal routing state paired with the compact public view.

    Never serialized into an answer (technical design §17.1). Routes and
    provenance remain the owner of record-time authority support,
    reconsideration and multi-path identity.
    """

    view: FunctionalPyramidView
    identity: FunctionalRouteIdentity
    routes: tuple[FunctionalDocumentRoute, ...] = ()
    provenance: tuple[FunctionalRouteProvenance, ...] = ()
    findings: tuple[FunctionalPyramidFinding, ...] = ()


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
class FunctionalRouteSupport:
    """Server-derived support for exact governing applicability (FD-73/FD-75)."""

    repository_id: str
    pyramid_id: FunctionalPyramidId
    semantic_scope: EvidenceScope
    route_identity: FunctionalRouteIdentity

    def __post_init__(self) -> None:
        _require_non_empty("FunctionalRouteSupport.repository_id", self.repository_id)
