"""Host-neutral hook contract (plan §11.11). Isolated-shell integration.

Host adapters map native lifecycle events onto `HookIntent` values and
build the one permitted automatic call: `status` with
`HOOK_FAST`. Automatic hooks perform only event-local deterministic
work proportional to the triggering scope (I-28): readiness plus
repository-state baseline comparison at session start, changed-evidence
fingerprint plus dependency lookup plus freshness classification after
source changes, closure classification at session stop. They never
initialize, explain, impact, trace, authority-check, refresh,
interpret, rebuild, or run repository-scale work (I-27/I-29/I-30).
"""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span import service_operations as ops

__all__ = [
    "HookIntent",
    "MappedEvent",
    "map_to_intent",
    "hook_status_request",
]


class HookIntent(_enum.Enum):
    """Canonical host-neutral hook intents (plan §11.11)."""

    SESSION_START = "SESSION_START"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    SESSION_STOP = "SESSION_STOP"


@_dataclass(frozen=True)
class MappedEvent:
    """One native event mapped onto the hook contract (exchange only)."""

    intent: HookIntent
    target: m.SubjectSelector | m.EvidenceScope | None


def map_to_intent(
    intent: HookIntent,
    changed_paths: tuple[str, ...] = (),
) -> MappedEvent:
    """Build the mapped event for an intent (pure).

    `SESSION_START` carries no target (readiness + baseline only).
    `SOURCE_CHANGED`/`SESSION_STOP` carry the changed evidence scope;
    an empty scope means session-local bookkeeping saw no changes.
    """
    if intent is HookIntent.SESSION_START:
        return MappedEvent(intent=intent, target=None)
    return MappedEvent(
        intent=intent,
        target=m.EvidenceScope(
            paths=tuple(changed_paths), evidence_refs=()
        ),
    )


def hook_status_request(
    repository_id: str,
    event: MappedEvent,
    bounds: m.QueryBounds,
) -> ops.SemanticStatusRequest:
    """The single permitted automatic call (plan §11.11).

    Always `HOOK_FAST`: read-only with respect to semantic truth.
    """
    return ops.SemanticStatusRequest(
        repository_id=repository_id,
        target=event.target,
        bounds=bounds,
        mode=m.StatusMode.HOOK_FAST,
    )
