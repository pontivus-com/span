"""Typed reverse-index reads for ordinary and installation-scoped effects."""

from __future__ import annotations

import sqlite3 as _sqlite3

from span.core import model as _m
from span.core import support_rules as _support_rules

__all__ = ["premise_dependents", "support_dependents"]


def support_dependents(
    connection: _sqlite3.Connection, dependency_kind: str, dependency_ref: str
) -> tuple[_m.ConclusionRevisionRef, ...]:
    """Read exact indexed edges; never classify their semantic currency."""
    rows = connection.execute(
        "SELECT understanding_id, conclusion_id, revision"
        " FROM support_dependencies"
        " WHERE dependency_kind=? AND dependency_ref=?"
        " ORDER BY understanding_id, conclusion_id, revision",
        (dependency_kind, dependency_ref),
    ).fetchall()
    return tuple(
        _m.ConclusionRevisionRef(
            understanding_id=_m.UnderstandingId(row["understanding_id"]),
            conclusion_id=_m.ConclusionId(row["conclusion_id"]),
            revision=_m.ConclusionRevisionNumber(row["revision"]),
        )
        for row in rows
    )


def premise_dependents(
    connection: _sqlite3.Connection,
    invalidated: set[_m.ConclusionRevisionRef],
) -> tuple[_m.ConclusionRevisionRef, ...]:
    """Supply retained edges in the existing transaction, including historical ones."""
    traversal = _support_rules.premise_closure(invalidated, set())
    position = next(traversal)
    while isinstance(position, _m.ConclusionRevisionRef):
        position = traversal.send(
            support_dependents(connection, "PREMISE", position.label)
        )
    indirect, _ = position
    return tuple(sorted(indirect, key=lambda ref: ref.sort_key))
