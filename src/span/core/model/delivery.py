"""Durable bound delivery coordinates (L1–L4, FD-54–57, TD §13).

Only selectors, exact selected coordinates and state fingerprints are stored.
No public result bodies, authority facts or source bytes are retained here.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.functional_pyramid import (
    FunctionalPyramidCandidateSelector,
    FunctionalPyramidDirectorySelector,
    FunctionalPyramidId,
    FunctionalPyramidPlacementView,
    FunctionalPyramidSelector,
    FunctionalPyramidVersion,
)
from span.core.model.primitives import (
    ContentDigest,
    _require_non_empty,
    _require_non_negative_int,
)


class DeliveryCollection(_enum.Enum):
    PLACEMENTS = "placements"
    UNRESOLVED = "unresolved"
    MEMBER_REPOSITORY_IDS = "member_repository_ids"
    STATUS_FINDINGS = "status_findings"
    VALIDATION_FINDINGS = "validation_findings"
    GRAPH_FINDINGS = "graph_findings"


GovernanceReadSelector = (
    FunctionalPyramidDirectorySelector
    | FunctionalPyramidSelector
    | FunctionalPyramidCandidateSelector
)


@_dataclass(frozen=True)
class DirectoryReadBinding:
    selector: FunctionalPyramidDirectorySelector
    owner_repository_id: str
    placements: tuple[FunctionalPyramidPlacementView, ...]
    unresolved_count: int

    def __post_init__(self) -> None:
        _require_non_empty("owner_repository_id", self.owner_repository_id)
        if self.selector.after is not None:
            raise ValueError("a selection binds the original obtain, not its cursor")
        _require_non_negative_int("unresolved_count", self.unresolved_count)
        if len(set(self.placements)) != len(self.placements):
            raise ValueError("directory placement coordinates must be distinct")


@_dataclass(frozen=True)
class PyramidStatusReadBinding:
    selector: FunctionalPyramidSelector
    pyramid_id: FunctionalPyramidId
    version: FunctionalPyramidVersion
    member_repository_ids: tuple[str, ...]
    findings_count: int

    def __post_init__(self) -> None:
        _require_non_negative_int("findings_count", self.findings_count)
        if not self.member_repository_ids or len(set(self.member_repository_ids)) != len(
            self.member_repository_ids
        ):
            raise ValueError("status binding requires distinct active member identities")


@_dataclass(frozen=True)
class PyramidCandidateReadBinding:
    selector: FunctionalPyramidCandidateSelector
    version: FunctionalPyramidVersion | None
    validation_count: int
    graph_count: int

    def __post_init__(self) -> None:
        _require_non_negative_int("validation_count", self.validation_count)
        _require_non_negative_int("graph_count", self.graph_count)


GovernanceReadBinding = (
    DirectoryReadBinding | PyramidStatusReadBinding | PyramidCandidateReadBinding
)


@_dataclass(frozen=True)
class DeliverySelection:
    """One pure-read selection, bound to exact evaluated coordinates and lifetime."""

    selection_id: str
    created_at: _datetime.datetime
    expires_at: _datetime.datetime
    state_fingerprint: ContentDigest
    binding: GovernanceReadBinding

    def __post_init__(self) -> None:
        _require_non_empty("selection_id", self.selection_id)
        if (
            self.created_at.utcoffset() is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.created_at
        ):
            raise ValueError("delivery lifetime must be positive and timezone-aware")


@_dataclass(frozen=True)
class DeliveryPosition:
    """One issued position in a collection at an exact evaluated state."""

    collection: DeliveryCollection
    offset: int
    state_fingerprint: ContentDigest

    def __post_init__(self) -> None:
        _require_non_negative_int("delivery offset", self.offset)


def delivery_extents(
    binding: GovernanceReadBinding,
) -> tuple[tuple[DeliveryCollection, int], ...]:
    """The exact ordered collections, with ordinal coordinates for findings."""
    if isinstance(binding, DirectoryReadBinding):
        return (
            (DeliveryCollection.PLACEMENTS, len(binding.placements)),
            (DeliveryCollection.UNRESOLVED, binding.unresolved_count),
        )
    if isinstance(binding, PyramidStatusReadBinding):
        return (
            (
                DeliveryCollection.MEMBER_REPOSITORY_IDS,
                len(binding.member_repository_ids),
            ),
            (DeliveryCollection.STATUS_FINDINGS, binding.findings_count),
        )
    return (
        (DeliveryCollection.VALIDATION_FINDINGS, binding.validation_count),
        (DeliveryCollection.GRAPH_FINDINGS, binding.graph_count),
    )


def delivery_position(
    selection: DeliverySelection, delivered: int
) -> DeliveryPosition | None:
    """Map a complete ordered prefix to its first undelivered coordinate."""
    _require_non_negative_int("delivered", delivered)
    for collection, total in delivery_extents(selection.binding):
        if delivered < total:
            return DeliveryPosition(collection, delivered, selection.state_fingerprint)
        delivered -= total
    if delivered:
        raise ValueError("delivery prefix exceeds its selection")
    return None


def delivery_offset(
    selection: DeliverySelection, position: DeliveryPosition
) -> tuple[int, int]:
    """Return absolute progress and remaining items in the named collection."""
    if position.state_fingerprint != selection.state_fingerprint:
        raise ValueError("delivery position belongs to a different evaluated state")
    preceding = 0
    for collection, total in delivery_extents(selection.binding):
        if collection is position.collection:
            if position.offset >= total:
                break
            return preceding + position.offset, total - position.offset
        preceding += total
    raise ValueError("delivery position is outside its selection")
