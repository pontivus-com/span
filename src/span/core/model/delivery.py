"""Durable bound delivery coordinates (L1–L4, FD-54–57, TD §13).

Only selectors, exact selected coordinates and state fingerprints are stored.
No public result bodies, authority facts or source bytes are retained here.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core.model.functional_pyramid import (
    FunctionalPyramidDirectorySelector,
    FunctionalPyramidPlacementView,
)
from span.core.model.primitives import (
    ContentDigest,
    _require_non_empty,
    _require_non_negative_int,
)


class DeliveryCollection(_enum.Enum):
    PLACEMENTS = "placements"
    UNRESOLVED = "unresolved"


@_dataclass(frozen=True)
class DirectoryDeliverySelection:
    """One installation-scoped pure read and its immutable ordered coordinates."""

    selection_id: str
    selector: FunctionalPyramidDirectorySelector
    owner_repository_id: str
    created_at: _datetime.datetime
    expires_at: _datetime.datetime
    state_fingerprint: ContentDigest
    placements: tuple[FunctionalPyramidPlacementView, ...]
    unresolved_count: int

    def __post_init__(self) -> None:
        _require_non_empty("selection_id", self.selection_id)
        _require_non_empty("owner_repository_id", self.owner_repository_id)
        if self.selector.after is not None:
            raise ValueError("a selection binds the original obtain, not its cursor")
        if (
            self.created_at.utcoffset() is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.created_at
        ):
            raise ValueError("delivery lifetime must be positive and timezone-aware")
        _require_non_negative_int("unresolved_count", self.unresolved_count)
        if len(set(self.placements)) != len(self.placements):
            raise ValueError("directory placement coordinates must be distinct")


@_dataclass(frozen=True)
class DeliveryPosition:
    """One issued position in a collection at an exact evaluated state."""

    collection: DeliveryCollection
    offset: int
    state_fingerprint: ContentDigest

    def __post_init__(self) -> None:
        _require_non_negative_int("delivery offset", self.offset)
