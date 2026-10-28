"""Migrate persisted data written by Span 0.8.0 to the 0.8.1 shape."""

from __future__ import annotations

import json as _json

from span.shell.sqlite_store.mapping import _encode


def _count_legacy_question_coverages(connection) -> int:
    """Count 0.8.0 coverage payloads carrying the retired completion flag."""
    rows = connection.execute(
        "SELECT canonical_json FROM question_coverages"
    ).fetchall()
    return sum(
        1
        for (payload,) in rows
        if isinstance((data := _json.loads(payload)), dict)
        and "declared_complete" in data
    )


def _rewrite_question_coverages(connection) -> int:
    """Remove the 0.8.0 completion flag from persisted coverage records.

    Span 0.8.1 derives completion from the disposition and result refs. The
    legacy field is validated before removal, and the caller owns the
    transaction so a failed rewrite leaves the store untouched.
    """
    rewritten = 0
    rows = connection.execute(
        "SELECT rowid, canonical_json FROM question_coverages"
    ).fetchall()
    for row_id, payload in rows:
        data = _json.loads(payload)
        if not isinstance(data, dict) or "declared_complete" not in data:
            continue
        if data.get("$type") != "InterpretationCoverage":
            raise ValueError(
                "cannot migrate question coverage with an unexpected canonical "
                f"type: {data.get('$type')!r}"
            )
        if not isinstance(data["declared_complete"], bool):
            raise ValueError(
                "cannot migrate question coverage with a non-boolean "
                "declared_complete field"
            )
        del data["declared_complete"]
        connection.execute(
            "UPDATE question_coverages SET canonical_json=? WHERE rowid=?",
            (_encode(data), row_id),
        )
        rewritten += 1
    return rewritten
