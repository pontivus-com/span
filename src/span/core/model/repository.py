"""Repository state, structural observations, and evidence inventory.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.primitives import (
    BoundInfo,
    EvidenceRef,
    EvidenceScope,
    Subject,
    SubjectCandidate,
    SubjectId,
    SubjectResolution,
    _require_non_empty,
    _require_non_negative_int,
    _require_positive_int,
)


@_dataclass(frozen=True)
class RepositoryIdentity:
    """Canonical identity of one repository root.

    ``repositories`` are keyed by ``repository_id``; ``canonical_root`` is the
    realpath the ID was derived from, so two roots that share a basename can be
    told apart after the fact.
    """

    repository_id: str
    canonical_root: str
    nested_within: str | None = None


class RepositoryIdentityConflict(ValueError):
    """Two roots resolve to one ID, or a store belongs to another root."""

    def __init__(
        self,
        repository_id: str,
        existing_root: str,
        incoming_root: str,
        *,
        store_path: str | None = None,
    ) -> None:
        self.repository_id = repository_id
        self.existing_root = existing_root
        self.incoming_root = incoming_root
        self.store_path = store_path
        where = f" (store {store_path})" if store_path else ""
        super().__init__(
            f"repository id {repository_id!r} is already bound to "
            f"{existing_root!r}{where}; incoming root {incoming_root!r} "
            "conflicts. Purge the unattributable store and re-initialize, or "
            "resolve the root collision."
        )


class StoreReadiness(_enum.Enum):
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@_dataclass(frozen=True)
class HookNoticeScope(_enum.Enum):
    """Scope discriminator for hook notices ([design note G](docs/design-references.md#g) Stage 2).

    Hooks observe the triggering event's local scope only — never
    repository inventory. Single value today; the type (not prose) is
    what prevents misreading a silent notice as clean.
    """

    EVENT_LOCAL = "EVENT_LOCAL"


@_dataclass(frozen=True)
class HookStatusNotice:
    store_readiness: StoreReadiness
    affected_count: int = 0
    stale_count: int = 0
    unverifiable_count: int = 0
    affected_subject_ids: tuple[SubjectId, ...] = ()
    recommended_action: str | None = None
    scope: HookNoticeScope = HookNoticeScope.EVENT_LOCAL


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
class EvidenceLineRange:
    """Canonical excerpt range ([design note I](docs/design-references.md#i) S7 §5.7).

    One-based positive integers with start_line <= end_line <=
    total_lines. None on the unit means complete provider text.
    """

    start_line: int
    end_line: int
    total_lines: int

    def __post_init__(self) -> None:
        _require_positive_int("start_line", self.start_line)
        _require_positive_int("end_line", self.end_line)
        _require_positive_int("total_lines", self.total_lines)
        if not (self.start_line <= self.end_line <= self.total_lines):
            raise ValueError(
                "EvidenceLineRange requires start_line <= end_line <= " "total_lines"
            )


@_dataclass(frozen=True)
class EvidenceUnit:
    evidence_ref: EvidenceRef
    content: str
    content_fingerprint: str
    content_range: EvidenceLineRange | None = None


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


class StatusMode(_enum.Enum):
    NORMAL = "NORMAL"
    HOOK_FAST = "HOOK_FAST"


class StructuralLocateMode(_enum.Enum):
    """Locate operation modes ([design note F](docs/design-references.md#f) §4.1 — one field, not three tools)."""

    SYMBOL = "SYMBOL"
    FILE_OUTLINE = "FILE_OUTLINE"
    TARGET_MEMBERS = "TARGET_MEMBERS"


class StructuralLocateMatch(_enum.Enum):
    """Symbol match breadth ([design note F](docs/design-references.md#f) §4.1)."""

    EXACT = "EXACT"
    CONTAINS = "CONTAINS"


class ScopeCoverage(_enum.Enum):
    """Search-scope currency ([design note F](docs/design-references.md#f) §4.0 two-tier freshness).

    VERIFIED means the loaded index postdates the newest source in the
    queried scope with a clean tree and every touched file hash-verified.
    Anything else — including empty results — is UNVERIFIED, which proves
    nothing about absence.
    """

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


COVERAGE_DETAIL_TOKENS: tuple[str, ...] = (
    "non-git-tree",
    "injected-index",
    "dirty-tree",
    "touched-file-mismatch",
    "unverifiable-file",
    "index-older-than-head",
    "repository-population-unverified",
    "clean-verified",
)
_COVERAGE_DETAIL_ORDER: dict[str, int] = {
    token: index for index, token in enumerate(COVERAGE_DETAIL_TOKENS)
}


def _validate_coverage_detail(name: str, value: str | None) -> str | None:
    """Strict validation for structural diagnostic detail ([design note G](docs/design-references.md#g)).

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
    """One located structural member ([design note F](docs/design-references.md#f) §4.1).

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
    """Locate answer ([design note F](docs/design-references.md#f) §§4.1/4.3; detail per [design note G](docs/design-references.md#g) §4.2a)."""

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
    """Neighbors answer ([design note F](docs/design-references.md#f) §4.2; detail per [design note G](docs/design-references.md#g) §4.2a).

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
class StructuralOutlineEntry:
    """One file-outline member: subject plus transcribed provider strings."""

    subject: Subject
    span_text: str | None = None
    signature_text: str | None = None


_StructuralItemT = _typing.TypeVar("_StructuralItemT")


@_dataclass(frozen=True)
class StructuralResult(_typing.Generic[_StructuralItemT]):
    """One bounded structural page: items plus provenance and coverage.

    Every port page operation returns this envelope. Coverage is therefore
    part of the port contract rather than a per-operation convention: an
    operation cannot return items without stating how current the structure
    behind them is. ``stale_omitted`` counts entries the provider withheld
    as stale; operations that never withhold entries leave it at zero.
    """

    items: tuple[_StructuralItemT, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo
    unsupported: bool = False
    stale_omitted: int = 0
    coverage: ScopeCoverage = ScopeCoverage.UNVERIFIED
    coverage_detail: str | None = None

    def __post_init__(self) -> None:
        # §4.11: unsupported:true requires empty items.
        if self.unsupported and self.items:
            raise ValueError("unsupported page must carry empty items")
        _require_non_negative_int("stale_omitted", self.stale_omitted)
        _validate_coverage_detail("coverage_detail", self.coverage_detail)


@_dataclass(frozen=True)
class StructuralFreshnessReport:
    """File-set freshness verdict ([design note F](docs/design-references.md#f) §4.0 port; detail per G §4.2a).

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
class EvidenceInventoryPage:
    items: tuple[EvidenceInventoryItem, ...]
    repository_state: RepositoryState
    bound_info: BoundInfo


@_dataclass(frozen=True)
class EvidenceSelection:
    selected_refs: tuple[EvidenceRef, ...]
    bound_info: BoundInfo
    discovery_scope: EvidenceScope = _field(default_factory=EvidenceScope)
