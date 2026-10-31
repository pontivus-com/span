"""Host-neutral hook contract (bounded, optional, never authoritative).

Host adapters map native lifecycle events onto ``HookIntent`` values. The
contract only names the event and its changed-path scope; the shell hook
runner performs one bounded readiness/dependent check. Hooks never
initialize, record, reassess, interpret, rebuild, or run repository-scale
work, and missing delivery can never establish freshness.
"""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass

__all__ = [
    "HookIntent",
    "MappedEvent",
    "map_to_intent",
]


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
    """Build the mapped event for an intent (pure)."""
    if intent is HookIntent.SESSION_START:
        return MappedEvent(intent=intent)
    return MappedEvent(
        intent=intent,
        changed_paths=tuple(changed_paths),
    )
