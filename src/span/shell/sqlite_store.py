"""Minimum SQLite SemanticStore (plan Phase 1.7, §10).

Persists canonical domain types directly — rows map to canonical JSON
plus query columns; no second semantic model is introduced (§10.2/§10.3,
I-15). Table decomposition is physical only and carries no semantic
authority. Stdlib ``sqlite3``; no third-party binding (ledger).

Schema version is 1 (``SCHEMA_VERSION``). Rebuild/migration rules are
plan §10.4 and belong to release engineering, not this module.
"""

from __future__ import annotations

import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3

from span.core import model as m
from span.ports.structural import StructuralDirection

__all__ = ["SCHEMA_VERSION", "SqliteSemanticStore"]

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories(
  repository_id TEXT PRIMARY KEY,
  revision_id TEXT,
  dirty INTEGER NOT NULL,
  state_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subjects(
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, locator, kind)
);
CREATE TABLE IF NOT EXISTS claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships(
  relationship_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  source_locator TEXT NOT NULL,
  target_locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_dependencies(
  semantic_id TEXT NOT NULL,
  semantic_kind TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  observed_fingerprint TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(semantic_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


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


def _decode_dependency(payload: str) -> m.EvidenceDependency:
    value = m.from_canonical(m.EvidenceDependency, _json.loads(payload))
    assert isinstance(value, m.EvidenceDependency)
    return value


class SqliteSemanticStore:
    """SemanticStore over one SQLite database file (or ``:memory:``).

    One persistent connection per instance (required for ``:memory:``).
    Single-threaded use; transactions are per-method (atomic batch
    writes for index materialization).
    """

    def __init__(self, path: str | _pathlib.Path) -> None:
        self._db = _sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._db.commit()

    def close(self) -> None:
        """Release the database connection (shell lifecycle only)."""
        self._db.close()

    # -- reads ----------------------------------------------------------

    def load_subjects(
        self, repository_id: str, subject_ids: tuple[m.SubjectId, ...]
    ) -> tuple[m.Subject, ...]:
        found: list[m.Subject] = []
        for sid in subject_ids:
            row = self._db.execute(
                "SELECT canonical_json FROM subjects "
                "WHERE repository_id=? AND locator=? AND kind=?",
                (repository_id, sid.canonical_locator, sid.subject_kind.value),
            ).fetchone()
            if row is not None:
                found.append(_decode_subject(row[0]))
        return tuple(found)

    def load_claims(
        self,
        repository_id: str,
        subject_ids: tuple[m.SubjectId, ...],
        claim_kinds: tuple[m.ClaimKind, ...],
        bounds: m.QueryBounds,
    ) -> m.ClaimPage:
        locators = {s.canonical_locator for s in subject_ids}
        kinds = {k.value for k in claim_kinds} if claim_kinds else None
        rows = self._db.execute(
            "SELECT canonical_json, subject_locator, kind FROM claims "
            "WHERE repository_id=? ORDER BY subject_locator, kind, claim_id",
            (repository_id,),
        ).fetchall()
        items = [
            _decode_claim(payload)
            for payload, locator, kind in rows
            if locator in locators and (kinds is None or kind in kinds)
        ]
        kept = tuple(items[: bounds.max_results])
        return m.ClaimPage(
            items=kept,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(items),
                truncated_category="claims" if len(kept) < len(items) else None,
                continuation_token=None,
            ),
        )

    def load_relationships(
        self,
        repository_id: str,
        subject_ids: tuple[m.SubjectId, ...],
        relationship_kinds: tuple[m.RelationshipKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
    ) -> m.RelationshipPage:
        locators = {s.canonical_locator for s in subject_ids}
        kinds = {k.value for k in relationship_kinds} if relationship_kinds else None
        rows = self._db.execute(
            "SELECT canonical_json, source_locator, target_locator, kind "
            "FROM relationships WHERE repository_id=? "
            "ORDER BY source_locator, target_locator, kind, relationship_id",
            (repository_id,),
        ).fetchall()
        items: list[m.SemanticRelationship] = []
        for payload, source, target, kind in rows:
            if kinds is not None and kind not in kinds:
                continue
            upstream = target in locators
            downstream = source in locators
            if direction is StructuralDirection.BOTH and not (upstream or downstream):
                continue
            if direction is StructuralDirection.UPSTREAM and not upstream:
                continue
            if direction is StructuralDirection.DOWNSTREAM and not downstream:
                continue
            items.append(_decode_relationship(payload))
        kept = tuple(items[: bounds.max_results])
        return m.RelationshipPage(
            items=kept,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_results,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(items),
                truncated_category=(
                    "relationships" if len(kept) < len(items) else None
                ),
                continuation_token=None,
            ),
        )

    def load_evidence_dependencies(
        self,
        repository_id: str,
        claim_or_relationship_ids: tuple[m.ClaimId | m.RelationshipId, ...],
    ) -> tuple[m.EvidenceDependency, ...]:
        wanted = {i.value for i in claim_or_relationship_ids}
        rows = self._db.execute(
            "SELECT canonical_json, semantic_id FROM evidence_dependencies "
            "ORDER BY semantic_id, evidence_id"
        ).fetchall()
        return tuple(
            _decode_dependency(payload)
            for payload, semantic_id in rows
            if semantic_id in wanted
        )

    # -- writes ---------------------------------------------------------

    def write_index_batch(self, batch: m.CanonicalIndexBatch) -> m.StoreWriteResult:
        written = 0
        with self._db:
            for subject in batch.subjects:
                sid = subject.subject_id
                self._db.execute(
                    "INSERT OR REPLACE INTO subjects"
                    "(repository_id, locator, kind, canonical_json) "
                    "VALUES(?, ?, ?, ?)",
                    (
                        sid.repository_id,
                        sid.canonical_locator,
                        sid.subject_kind.value,
                        _encode(m.to_canonical(subject)),
                    ),
                )
                written += 1
            for claim in batch.claims:
                self._db.execute(
                    "INSERT OR REPLACE INTO claims"
                    "(claim_id, repository_id, subject_locator, subject_kind, "
                    "kind, trust, freshness_state, canonical_json) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        claim.claim_id.value,
                        claim.subject.repository_id,
                        claim.subject.canonical_locator,
                        claim.subject.subject_kind.value,
                        claim.kind.value,
                        claim.trust.value,
                        claim.freshness.state.value,
                        _encode(m.to_canonical(claim)),
                    ),
                )
                written += 1
            for rel in batch.relationships:
                self._db.execute(
                    "INSERT OR REPLACE INTO relationships"
                    "(relationship_id, repository_id, source_locator, "
                    "target_locator, kind, trust, freshness_state, "
                    "canonical_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rel.relationship_id.value,
                        rel.source.repository_id,
                        rel.source.canonical_locator,
                        rel.target.canonical_locator,
                        rel.kind.value,
                        rel.trust.value,
                        rel.freshness.state.value,
                        _encode(m.to_canonical(rel)),
                    ),
                )
                written += 1
            for dep in batch.evidence_dependencies:
                semantic_id = dep.semantic_id
                self._db.execute(
                    "INSERT OR REPLACE INTO evidence_dependencies"
                    "(semantic_id, semantic_kind, evidence_id, repository_id, "
                    "locator, observed_fingerprint, canonical_json) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (
                        semantic_id.value,
                        "CLAIM"
                        if isinstance(semantic_id, m.ClaimId)
                        else "RELATIONSHIP",
                        dep.evidence_ref.evidence_id.value,
                        dep.evidence_ref.repository_id,
                        dep.evidence_ref.locator,
                        dep.observed_fingerprint,
                        _encode(m.to_canonical(dep)),
                    ),
                )
                written += 1
        return m.StoreWriteResult(written_count=written)

    def mark_freshness(
        self, updates: tuple[m.FreshnessUpdate, ...]
    ) -> m.StoreWriteResult:
        applied = 0
        with self._db:
            for update in updates:
                sid = update.semantic_id.value
                if isinstance(update.semantic_id, m.ClaimId):
                    row = self._db.execute(
                        "SELECT canonical_json FROM claims WHERE claim_id=?",
                        (sid,),
                    ).fetchone()
                    if row is None:
                        continue
                    claim = _decode_claim(row[0])
                    refreshed = m.SemanticClaim(
                        claim_id=claim.claim_id,
                        subject=claim.subject,
                        kind=claim.kind,
                        value=claim.value,
                        evidence=claim.evidence,
                        authority=claim.authority,
                        trust=claim.trust,
                        freshness=update.freshness,
                        basis=claim.basis,
                    )
                    self._db.execute(
                        "UPDATE claims SET freshness_state=?, canonical_json=? "
                        "WHERE claim_id=?",
                        (
                            update.freshness.state.value,
                            _encode(m.to_canonical(refreshed)),
                            sid,
                        ),
                    )
                    applied += 1
                else:
                    row = self._db.execute(
                        "SELECT canonical_json FROM relationships "
                        "WHERE relationship_id=?",
                        (sid,),
                    ).fetchone()
                    if row is None:
                        continue
                    rel = _decode_relationship(row[0])
                    refreshed_rel = m.SemanticRelationship(
                        relationship_id=rel.relationship_id,
                        source=rel.source,
                        kind=rel.kind,
                        target=rel.target,
                        evidence=rel.evidence,
                        authority=rel.authority,
                        trust=rel.trust,
                        freshness=update.freshness,
                        basis=rel.basis,
                    )
                    self._db.execute(
                        "UPDATE relationships SET freshness_state=?, "
                        "canonical_json=? WHERE relationship_id=?",
                        (
                            update.freshness.state.value,
                            _encode(m.to_canonical(refreshed_rel)),
                            sid,
                        ),
                    )
                    applied += 1
        return m.StoreWriteResult(written_count=applied)

    def schema_version(self) -> m.SchemaVersion:
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        return m.SchemaVersion(value=int(row[0]) if row else 0)
