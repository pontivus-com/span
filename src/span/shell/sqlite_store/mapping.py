"""Row mapping and query filters for the SQLite store (plan §10.2).

Canonical JSON plus query columns; no second semantic model is introduced.
"""

from __future__ import annotations

import json as _json

from span.core import model as m

_PREFIX_CEILING = chr(0x10FFFF)


def _encode(canonical: object) -> str:
    return _json.dumps(canonical, sort_keys=True)


def _decode_claim(payload: str) -> m.SemanticClaim:
    value = m.from_canonical(m.SemanticClaim, _json.loads(payload))
    assert isinstance(value, m.SemanticClaim)
    return value


def _decode_relationship(payload: str) -> m.SemanticRelationship:
    value = m.from_canonical(m.SemanticRelationship, _json.loads(payload))
    assert isinstance(value, m.SemanticRelationship)
    return value


def _decode_subject(payload: str) -> m.Subject:
    value = m.from_canonical(m.Subject, _json.loads(payload))
    assert isinstance(value, m.Subject)
    return value


def _path_filter(stem: str) -> tuple[str, tuple[object, ...]]:
    """Exact segment-boundary membership for one path (``evidence_scope_allows``).

    ``substr`` and equality are used rather than ``GLOB``/``LIKE`` so the
    predicate is case-sensitive and has no wildcard to escape. The surrounding
    range bound keeps the scan on the primary-key index.
    """
    return (
        "(locator = ? OR substr(locator, 1, ?) IN (?, ?, ?))",
        (stem, len(stem) + 1, stem + "/", stem + "#", stem + ":"),
    )


def _scope_filter(scope: m.EvidenceScope) -> tuple[str, tuple[object, ...]]:
    """Whole-scope membership clause, the SQL form of ``evidence_scope_allows``."""
    clauses: list[str] = []
    params: list[object] = []
    for ref in scope.evidence_refs:
        clauses.append("locator = ?")
        params.append(ref.locator)
    for prefix in scope.paths:
        clause, values = _path_filter(prefix.rstrip("/"))
        clauses.append(clause)
        params.extend(values)
    if not clauses:
        raise ValueError("scope must not be empty")
    return "(" + " OR ".join(clauses) + ")", tuple(params)


def _scope_range_queries(
    scope: m.EvidenceScope,
) -> tuple[tuple[str, tuple[object, ...]], ...]:
    """One contiguous index range per scope component.

    A page is fetched by index search on ``(repository_id, locator, kind)``
    rather than by scanning the repository partition. Components can overlap
    when one path is a prefix of another; the caller dedupes.
    """
    components: list[tuple[str, tuple[object, ...]]] = []
    for ref in scope.evidence_refs:
        components.append(("locator = ?", (ref.locator,)))
    for prefix in scope.paths:
        stem = prefix.rstrip("/")
        clause, values = _path_filter(stem)
        components.append(
            (
                "locator >= ? AND locator < ? AND " + clause,
                (stem, stem + _PREFIX_CEILING, *values),
            )
        )
    if not components:
        raise ValueError("scope must not be empty")
    return tuple(components)


def _decode_dependency(payload: str) -> m.EvidenceDependency:
    value = m.from_canonical(m.EvidenceDependency, _json.loads(payload))
    assert isinstance(value, m.EvidenceDependency)
    return value


def _decode_coverage(payload: str) -> m.CoverageDependency:
    value = m.from_canonical(m.CoverageDependency, _json.loads(payload))
    assert isinstance(value, m.CoverageDependency)
    return value


def _decode_question_coverage(payload: str) -> m.InterpretationCoverage:
    value = m.from_canonical(m.InterpretationCoverage, _json.loads(payload))
    assert isinstance(value, m.InterpretationCoverage)
    return value


def _decode_conflict(payload: str) -> m.RecordedConflict:
    value = m.from_canonical(m.RecordedConflict, _json.loads(payload))
    assert isinstance(value, m.RecordedConflict)
    return value
