"""Pure Claude Code event mapping onto Span's hook contract."""

from __future__ import annotations

from integrations.hooks.contract import HookIntent, MappedEvent, map_to_intent

__all__ = ["EDIT_TOOLS", "adapt_event"]

EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def adapt_event(event: dict) -> MappedEvent | None:
    """Map one Claude event; the canonical ``span-hooks`` runtime owns execution."""
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
    if hook == "PostToolUse" and event.get("tool") in EDIT_TOOLS:
        paths = event.get("paths", ())
        if not isinstance(paths, (list, tuple)):
            return None
        return map_to_intent(HookIntent.SOURCE_CHANGED, tuple(str(p) for p in paths))
    return None
