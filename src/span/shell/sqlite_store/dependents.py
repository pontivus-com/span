"""Transaction-local exact premise closure for committed transitions."""

from __future__ import annotations

import sqlite3 as _sqlite3

from span.core import model as m


def premise_dependents(
    connection: _sqlite3.Connection,
    invalidated: set[tuple[str, str, int]],
) -> m.AcceptedDependencyEffects:
    """Traverse historical dependencies, retain only current actionable coordinates."""
    pending = list(sorted(invalidated))
    visited = set(invalidated)
    reached: set[tuple[str, str, int]] = set()
    while pending:
        understanding, conclusion, revision = pending.pop()
        rows = connection.execute(
            "SELECT understanding_id, conclusion_id, revision"
            " FROM support_dependencies"
            " WHERE dependency_kind='PREMISE' AND dependency_ref=?",
            (f"{understanding}/{conclusion}@{revision}",),
        ).fetchall()
        for row in rows:
            key = (str(row[0]), str(row[1]), int(row[2]))
            reached.add(key)
            if key not in visited:
                visited.add(key)
                pending.append(key)
    effects: list[m.AcceptedDependencyEffect] = []
    for understanding, conclusion, revision in sorted(reached - invalidated):
        row = connection.execute(
            "SELECT u.repository_id, u.surface_kind, u.surface_locator"
            " FROM understandings u JOIN understanding_membership members"
            " ON members.understanding_id=u.understanding_id"
            " AND members.version=u.current_version"
            " WHERE u.understanding_id=? AND members.conclusion_id=?"
            " AND members.revision=?",
            (understanding, conclusion, revision),
        ).fetchone()
        if row is not None:
            effects.append(
                m.AcceptedDependencyEffect(
                    surface=m.SurfaceKey(
                        str(row[0]), m.SurfaceKind(row[1]), str(row[2])
                    ),
                    ref=m.ConclusionRevisionRef(
                        m.UnderstandingId(understanding),
                        m.ConclusionId(conclusion),
                        m.ConclusionRevisionNumber(revision),
                    ),
                    reasons=(m.ChangeReason.INDIRECT,),
                )
            )
    return m.AcceptedDependencyEffects(tuple(effects))
