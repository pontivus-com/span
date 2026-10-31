"""Claude-style host adapter (reference implementation).

Maps Claude-style lifecycle events onto the host-neutral hook contract:

- ``SessionStart`` -> ``SESSION_START`` (readiness only);
- post-edit ``Write``/``Edit``/``MultiEdit`` -> ``SOURCE_CHANGED`` with the
  changed-path scope;
- ``Stop`` -> ``SESSION_STOP`` with the session changed scope.

Adaptation is pure event mapping. The shell hook runner owns the bounded
readiness/dependent check; this adapter holds no store or service handle.
"""

from __future__ import annotations

from integrations.hooks.contract import (
    HookIntent,
    MappedEvent,
    map_to_intent,
)

__all__ = [
    "EDIT_TOOLS",
    "adapt_event",
]

#: Claude-style post-edit tool names that change source files.
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def adapt_event(event: dict) -> MappedEvent | None:
    """Map one native event dict onto the hook contract.

    Accepted shapes (all keys optional unless noted):
    - ``{"hook": "SessionStart"}`` -> session start;
    - ``{"hook": "PostToolUse", "tool": <name>, "paths": [...]}`` ->
      source-changed for edit tools, ``None`` otherwise;
    - ``{"hook": "Stop", "paths": [...]}`` -> session stop.
    Unknown hook names yield ``None`` (silent, never invented work).
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
        return map_to_intent(HookIntent.SESSION_STOP, tuple(str(p) for p in paths))
    if hook == "PostToolUse":
        if event.get("tool") not in EDIT_TOOLS:
            return None
        paths = event.get("paths", ())
        if not isinstance(paths, (list, tuple)):
            return None
        return map_to_intent(HookIntent.SOURCE_CHANGED, tuple(str(p) for p in paths))
    return None
