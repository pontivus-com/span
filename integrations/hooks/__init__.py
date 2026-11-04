"""Host-neutral lifecycle hook adapters."""

from .contract import HookIntent, MappedEvent, map_to_intent

__all__ = ["HookIntent", "MappedEvent", "map_to_intent"]
