"""Span bounded evidence discovery (plan §6.2, §8.5)."""

from __future__ import annotations

from span.service.discovery.inventory import (  # noqa: F401
    check_inventory_identity,
    enumerate_target_inventory,
    _inventory_snapshot,
    _read_units_within_bytes,
)

from span.service.discovery.selection import (  # noqa: F401
    discover_evidence,
    _coverage_for_task,
    _coverage_scope_snapshots,
)

__all__ = [
    "check_inventory_identity",
    "enumerate_target_inventory",
    "_inventory_snapshot",
    "_read_units_within_bytes",
    "discover_evidence",
    "_coverage_for_task",
    "_coverage_scope_snapshots",
]
