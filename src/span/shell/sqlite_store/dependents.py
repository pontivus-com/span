"""Premise-dependent projection for one committed transition (FD-37).

The transition itself lives in the core; this module only reads the reverse
dependency index the store already maintains and names the exact revisions a
superseded or withdrawn premise leaves unsupported.
"""

from __future__ import annotations

import sqlite3 as _sqlite3

from span.core import model as _m

__all__ = ["premise_dependents"]


def premise_dependents(
    connection: _sqlite3.Connection,
    invalidated: set[tuple[str, str, int]],
) -> tuple[_m.ConclusionRevisionRef, ...]:
    """Exact revisions whose premise this transition invalidates."""
    if not invalidated:
        return ()
    labels = sorted(
        f"{understanding}/{conclusion}@{revision}"
        for understanding, conclusion, revision in invalidated
    )
    placeholders = ",".join("?" for _ in labels)
    rows = connection.execute(
        "SELECT understanding_id, conclusion_id, revision"
        " FROM support_dependencies"
        " WHERE dependency_kind='PREMISE'"
        f" AND dependency_ref IN ({placeholders})",
        labels,
    ).fetchall()
    return tuple(
        sorted(
            {
                _m.ConclusionRevisionRef(
                    understanding_id=_m.UnderstandingId(row["understanding_id"]),
                    conclusion_id=_m.ConclusionId(row["conclusion_id"]),
                    revision=_m.ConclusionRevisionNumber(row["revision"]),
                )
                for row in rows
            },
            key=lambda ref: ref.sort_key,
        )
    )
