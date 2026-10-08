"""Claude-style host adapter (reference implementation, plan Phase 4.9).

Maps Claude-style lifecycle events onto the host-neutral hook
contract (`integrations/hooks/contract.py`):

- `SessionStart` → `SESSION_START` (readiness + baseline only);
- post-edit `Write`/`Edit`/`MultiEdit` → `SOURCE_CHANGED` with the
  changed-path evidence scope;
- `Stop` → `SESSION_STOP` with the session changed scope.

The adapter keeps only ephemeral session-local bookkeeping (changed
paths) required to build the scope. Such bookkeeping is not semantic
state, is not authoritative, and is never persisted. The adapter calls
canonical service operations only, and only `status` with
`HOOK_FAST` on automatic paths.
"""

from __future__ import annotations

from span.core import model as m
from span import service as ops
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

from integrations.hooks.contract import (
    HookIntent,
    MappedEvent,
    hook_status_request,
    map_to_intent,
)

__all__ = [
    "EDIT_TOOLS",
    "adapt_event",
    "run_automatic_hook",
]

#: Claude-style post-edit tool names that change source files.
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def adapt_event(event: dict) -> MappedEvent | None:
    """Map one native event dict onto the hook contract.

    Accepted shapes (all keys optional unless noted):
    - `{"hook": "SessionStart"}` → session start;
    - `{"hook": "PostToolUse", "tool": <name>, "paths": [...]}` →
      source-changed for edit tools, `None` otherwise (silent:
      irrelevant events produce no notice);
    - `{"hook": "Stop", "paths": [...]}` → session stop.
    Unknown hook names yield `None` (silent, never invented work).
    """
    if not isinstance(event, dict):
        return None
    hook = event.get("hook")
    if hook == "SessionStart":
        return map_to_intent(HookIntent.SESSION_START)
    if hook == "Stop":
        paths = event.get("paths", ())
        if not isinstance(paths, (list, tuple)):
            return None
        return map_to_intent(
            HookIntent.SESSION_STOP, tuple(str(p) for p in paths)
        )
    if hook == "PostToolUse":
        if event.get("tool") not in EDIT_TOOLS:
            return None
        paths = event.get("paths", ())
        if not isinstance(paths, (list, tuple)):
            return None
        return map_to_intent(
            HookIntent.SOURCE_CHANGED, tuple(str(p) for p in paths)
        )
    return None


def run_automatic_hook(
    event: dict,
    *,
    repository_id: str,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.HookStatusNotice | None:
    """Run the automatic hook path for one native event.

    Returns the compact lifecycle notice, or `None` when the event
    maps to nothing (irrelevant tool, unknown hook: silence). Only
    ever calls `status(..., mode=HOOK_FAST)`; anything else would
    be a second semantic authority and is structurally absent here.
    """
    mapped = adapt_event(event)
    if mapped is None:
        return None
    request = hook_status_request(repository_id, mapped, bounds)
    notice = ops.status(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=ContinuationStore(),
    )
    assert isinstance(notice, m.HookStatusNotice)
    return notice
