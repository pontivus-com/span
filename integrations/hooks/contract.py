"""Host-neutral hook contract (bounded, optional, never authoritative)."""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass

__all__ = ["HookIntent", "MappedEvent", "map_to_intent"]


class HookIntent(_enum.Enum):
    """Canonical host-neutral hook intents."""

    SESSION_START = "SESSION_START"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    SESSION_STOP = "SESSION_STOP"


@_dataclass(frozen=True)
class MappedEvent:
    """One native event mapped onto the hook contract (transport only)."""

    intent: HookIntent
    changed_paths: tuple[str, ...] = ()


def map_to_intent(
    intent: HookIntent,
    changed_paths: tuple[str, ...] = (),
) -> MappedEvent:
    """Build one mapped event without owning runtime or semantic behavior."""
    if intent is HookIntent.SESSION_START:
        return MappedEvent(intent=intent)
    return MappedEvent(intent=intent, changed_paths=tuple(changed_paths))
