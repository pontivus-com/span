"""SQLite curation read/query mechanics for lifecycle schema 15."""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3

from span.core import model as m


def decode_curation_row(row: _sqlite3.Row) -> m.CurationDisposition:
    """Decode one persisted curation row and verify its structural projection."""
    disposition = m.from_canonical(
        m.CurationDisposition,
        _json.loads(row["canonical_json"]),
    )
    inherited_revision = (
        None
        if disposition.inherited_from is None
        else disposition.inherited_from.revision.value
    )
    observed = (
        row["understanding_id"],
        row["conclusion_id"],
        int(row["revision"]),
        int(row["accepted_in_version"]),
        row["origin"],
        row["inherited_from_revision"],
    )
    canonical = (
        disposition.ref.understanding_id.value,
        disposition.ref.conclusion_id.value,
        disposition.ref.revision.value,
        disposition.accepted_in_version.value,
        disposition.origin.value,
        inherited_revision,
    )
    if observed != canonical:
        raise ValueError("curation structural columns disagree with canonical payload")
    return disposition


def find_curation(
    connection: _sqlite3.Connection,
    ref: m.ConclusionRevisionRef,
    *,
    as_of_version: m.UnderstandingVersionNumber | None = None,
) -> m.CurationDisposition | None:
    statement = (
        "SELECT understanding_id, conclusion_id, revision,"
        " accepted_in_version, origin, inherited_from_revision, canonical_json"
        " FROM conclusion_curations"
        " WHERE understanding_id=? AND conclusion_id=? AND revision=?"
    )
    parameters: list[object] = [
        ref.understanding_id.value,
        ref.conclusion_id.value,
        ref.revision.value,
    ]
    if as_of_version is not None:
        statement += " AND accepted_in_version<=?"
        parameters.append(as_of_version.value)
    row = connection.execute(statement, tuple(parameters)).fetchone()
    return None if row is None else decode_curation_row(row)


def get_curations(
    connection: _sqlite3.Connection,
    understanding_id: str,
    *,
    as_of_version: m.UnderstandingVersionNumber | None = None,
) -> tuple[m.CurationDisposition, ...]:
    statement = (
        "SELECT understanding_id, conclusion_id, revision,"
        " accepted_in_version, origin, inherited_from_revision, canonical_json"
        " FROM conclusion_curations WHERE understanding_id=?"
    )
    parameters: list[object] = [understanding_id]
    if as_of_version is not None:
        statement += " AND accepted_in_version<=?"
        parameters.append(as_of_version.value)
    statement += " ORDER BY conclusion_id, revision"
    rows = connection.execute(statement, tuple(parameters)).fetchall()
    return tuple(decode_curation_row(row) for row in rows)


def pending_curation_candidates(
    connection: _sqlite3.Connection,
    repository_id: str,
    *,
    after: m.ConclusionRevisionRef | None = None,
) -> tuple[m.PendingCurationItem, ...]:
    """Return current-membership uncurated candidates in exact key order."""
    statement = (
        "SELECT u.understanding_id, u.current_version, u.surface_kind,"
        " u.surface_locator, u.question, m.conclusion_id, m.revision"
        " FROM understandings u"
        " JOIN understanding_membership m"
        " ON m.understanding_id=u.understanding_id"
        " AND m.version=u.current_version"
        " LEFT JOIN conclusion_curations cc"
        " ON cc.understanding_id=m.understanding_id"
        " AND cc.conclusion_id=m.conclusion_id"
        " AND cc.revision=m.revision"
        " WHERE u.repository_id=? AND cc.understanding_id IS NULL"
    )
    parameters: list[object] = [repository_id]
    if after is not None:
        statement += (
            " AND (m.understanding_id>?"
            " OR (m.understanding_id=? AND m.conclusion_id>?)"
            " OR (m.understanding_id=? AND m.conclusion_id=?"
            " AND m.revision>?))"
        )
        parameters.extend(
            (
                after.understanding_id.value,
                after.understanding_id.value,
                after.conclusion_id.value,
                after.understanding_id.value,
                after.conclusion_id.value,
                after.revision.value,
            )
        )
    statement += " ORDER BY m.understanding_id, m.conclusion_id, m.revision"
    rows = connection.execute(statement, tuple(parameters)).fetchall()
    return tuple(
        m.PendingCurationItem(
            ref=m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId(row["understanding_id"]),
                conclusion_id=m.ConclusionId(row["conclusion_id"]),
                revision=m.ConclusionRevisionNumber(row["revision"]),
            ),
            understanding_version=m.UnderstandingVersionNumber(row["current_version"]),
            surface=m.SurfaceKey(
                repository_id=repository_id,
                kind=m.SurfaceKind(row["surface_kind"]),
                locator=row["surface_locator"],
            ),
            question=row["question"],
        )
        for row in rows
    )
