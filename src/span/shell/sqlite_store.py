"""Minimum SQLite SemanticStore (plan Phase 1.7, §10, v0.6 §4.11/§5.5).

Persists canonical domain types directly — rows map to canonical JSON
plus query columns; no second semantic model is introduced (§10.2/§10.3,
I-15). Table decomposition is physical only and carries no semantic
authority. Stdlib ``sqlite3``; no third-party binding (ledger).

Schema version is 2 (``SCHEMA_VERSION``): coverage dependencies and
retired-assertion history tables added for v0.6 reconciliation (I-37).
v1 dependency rows (bare-id ``semantic_id``) do not decode under the
tagged v0.6 carriers; development stores rebuild per §10.4.
Rebuild/migration rules are plan §10.4 and belong to release
engineering, not this module.
"""

from __future__ import annotations

import datetime as _datetime
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging

__all__ = ["SCHEMA_VERSION", "SqliteSemanticStore"]

SCHEMA_VERSION = 2

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
CREATE TABLE IF NOT EXISTS coverage_dependencies(
  repository_id TEXT NOT NULL,
  scope_locators TEXT NOT NULL,
  inventory_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS retired_claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  retired_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS retired_relationships(
  relationship_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  retired_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conflict_records(
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, subject_locator, left_id, right_id)
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


def _decode_coverage(payload: str) -> m.CoverageDependency:
    value = m.from_canonical(m.CoverageDependency, _json.loads(payload))
    assert isinstance(value, m.CoverageDependency)
    return value


def _decode_conflict(payload: str) -> m.RecordedConflict:
    value = m.from_canonical(m.RecordedConflict, _json.loads(payload))
    assert isinstance(value, m.RecordedConflict)
    return value


def _ref_id(ref: m.ClaimRef | m.RelationshipRef) -> str:
    return ref.id.value


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

    def load_by_refs(
        self,
        repository_id: str,
        refs: tuple[m.ClaimRef | m.RelationshipRef, ...],
    ) -> tuple[m.SemanticClaim | m.SemanticRelationship, ...]:
        """Resolve tagged refs (plan §5.5 `load_by_refs`).

        Unknown ids fail closed with ValueError; the service maps this
        to its typed target errors.
        """
        found: list[m.SemanticClaim | m.SemanticRelationship] = []
        for ref in refs:
            if isinstance(ref, m.ClaimRef):
                row = self._db.execute(
                    "SELECT canonical_json FROM claims "
                    "WHERE claim_id=? AND repository_id=?",
                    (ref.id.value, repository_id),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        f"unknown claim ref: {ref.id.value}"
                    )
                found.append(_decode_claim(row[0]))
            else:
                row = self._db.execute(
                    "SELECT canonical_json FROM relationships "
                    "WHERE relationship_id=? AND repository_id=?",
                    (ref.id.value, repository_id),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        f"unknown relationship ref: {ref.id.value}"
                    )
                found.append(_decode_relationship(row[0]))
        return tuple(found)

    def load_claims(
        self,
        repository_id: str,
        subject_ids: tuple[m.SubjectId, ...],
        claim_kinds: tuple[m.ClaimKind, ...],
        bounds: m.QueryBounds,
        page_token: str | None = None,
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
        kept, bound_info = _paging.paginate(
            tuple(items), bounds.max_results, "claims", page_token
        )
        return m.ClaimPage(
            items=tuple(kept),  # type: ignore[arg-type]
            bound_info=bound_info,
        )

    def load_relationships(
        self,
        repository_id: str,
        subject_ids: tuple[m.SubjectId, ...],
        relationship_kinds: tuple[m.RelationshipKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
        page_token: str | None = None,
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
        kept, bound_info = _paging.paginate(
            tuple(items), bounds.max_results, "relationships", page_token
        )
        return m.RelationshipPage(
            items=tuple(kept),  # type: ignore[arg-type]
            bound_info=bound_info,
        )

    def load_evidence_dependencies(
        self,
        repository_id: str,
        claim_or_relationship_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    ) -> tuple[m.EvidenceDependency, ...]:
        wanted = {_ref_id(i) for i in claim_or_relationship_ids}
        rows = self._db.execute(
            "SELECT canonical_json, semantic_id FROM evidence_dependencies "
            "WHERE repository_id=? ORDER BY semantic_id, evidence_id",
            (repository_id,),
        ).fetchall()
        return tuple(
            _decode_dependency(payload)
            for payload, semantic_id in rows
            if semantic_id in wanted
        )

    def load_conflicts(
        self,
        repository_id: str,
        subject_ids: tuple[m.SubjectId, ...],
    ) -> tuple[m.RecordedConflict, ...]:
        wanted = {s.canonical_locator for s in subject_ids}
        rows = self._db.execute(
            "SELECT canonical_json, subject_locator FROM conflict_records "
            "WHERE repository_id=? ORDER BY subject_locator, left_id, right_id",
            (repository_id,),
        ).fetchall()
        return tuple(
            _decode_conflict(payload)
            for payload, locator in rows
            if not wanted or locator in wanted
        )

    def load_coverage_dependencies(
        self,
        repository_id: str,
        scope_subjects: tuple[m.SubjectId, ...],
    ) -> tuple[m.CoverageDependency, ...]:
        """Coverage records overlapping the requested scope (plan §5.5)."""
        wanted = {s.canonical_locator for s in scope_subjects}
        rows = self._db.execute(
            "SELECT canonical_json, scope_locators FROM coverage_dependencies "
            "WHERE repository_id=? ORDER BY observed_at",
            (repository_id,),
        ).fetchall()
        found: list[m.CoverageDependency] = []
        for payload, scope_json in rows:
            try:
                scope = set(_json.loads(scope_json))
            except ValueError:
                continue
            if not wanted or scope & wanted:
                found.append(_decode_coverage(payload))
        return tuple(found)

    # -- writes ---------------------------------------------------------

    def write_index_batch(self, batch: m.CanonicalIndexBatch) -> m.StoreWriteResult:
        written = 0
        if not batch.subjects and (
            batch.claims
            or batch.relationships
            or batch.coverage_dependencies
            or batch.retires_claims
            or batch.retires_relationships
            or batch.conflicts
        ):
            raise ValueError("index batch with content requires subjects")
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
                        _ref_id(semantic_id),
                        "CLAIM"
                        if isinstance(semantic_id, m.ClaimRef)
                        else "RELATIONSHIP",
                        dep.evidence_ref.evidence_id.value,
                        dep.evidence_ref.repository_id,
                        dep.evidence_ref.locator,
                        dep.observed_fingerprint,
                        _encode(m.to_canonical(dep)),
                    ),
                )
                written += 1
            for coverage in batch.coverage_dependencies:
                scope = sorted(
                    {s.canonical_locator for s in coverage.scope_subjects}
                )
                self._db.execute(
                    "INSERT INTO coverage_dependencies"
                    "(repository_id, scope_locators, inventory_fingerprint, "
                    "observed_at, canonical_json) VALUES(?, ?, ?, ?, ?)",
                    (
                        batch.subjects[0].subject_id.repository_id
                        if batch.subjects
                        else "",
                        _json.dumps(scope, sort_keys=True),
                        coverage.inventory_fingerprint,
                        coverage.observed_at.isoformat(),
                        _encode(m.to_canonical(coverage)),
                    ),
                )
                written += 1
            retired_at = _datetime.datetime.now(
                _datetime.timezone.utc
            ).isoformat()
            for ref in batch.retires_claims:
                row = self._db.execute(
                    "SELECT canonical_json, repository_id FROM claims "
                    "WHERE claim_id=?",
                    (ref.id.value,),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        f"retire names unknown claim: {ref.id.value}"
                    )
                self._db.execute(
                    "INSERT OR REPLACE INTO retired_claims"
                    "(claim_id, repository_id, retired_at, canonical_json) "
                    "VALUES(?, ?, ?, ?)",
                    (ref.id.value, row[1], retired_at, row[0]),
                )
                self._db.execute(
                    "DELETE FROM claims WHERE claim_id=?", (ref.id.value,)
                )
                self._db.execute(
                    "DELETE FROM evidence_dependencies WHERE semantic_id=?",
                    (ref.id.value,),
                )
                written += 1
            for ref in batch.retires_relationships:
                row = self._db.execute(
                    "SELECT canonical_json, repository_id FROM relationships "
                    "WHERE relationship_id=?",
                    (ref.id.value,),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        "retire names unknown relationship: "
                        + ref.id.value
                    )
                self._db.execute(
                    "INSERT OR REPLACE INTO retired_relationships"
                    "(relationship_id, repository_id, retired_at, "
                    "canonical_json) VALUES(?, ?, ?, ?)",
                    (ref.id.value, row[1], retired_at, row[0]),
                )
                self._db.execute(
                    "DELETE FROM relationships WHERE relationship_id=?",
                    (ref.id.value,),
                )
                self._db.execute(
                    "DELETE FROM evidence_dependencies WHERE semantic_id=?",
                    (ref.id.value,),
                )
                written += 1
            for conflict in batch.conflicts:
                left = conflict.left.id.value
                right = conflict.right.id.value
                self._db.execute(
                    "INSERT OR REPLACE INTO conflict_records"
                    "(repository_id, subject_locator, left_id, right_id, "
                    "canonical_json) VALUES(?, ?, ?, ?, ?)",
                    (
                        conflict.subject.repository_id,
                        conflict.subject.canonical_locator,
                        left,
                        right,
                        _encode(m.to_canonical(conflict)),
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
                sid = _ref_id(update.semantic_id)
                if isinstance(update.semantic_id, m.ClaimRef):
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

    def record_repository_state(self, state: m.RepositoryState) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO repositories"
                "(repository_id, revision_id, dirty, state_fingerprint, "
                "observed_at) VALUES(?, ?, ?, ?, ?)",
                (
                    state.repository_id,
                    state.revision_id,
                    int(state.dirty),
                    state.state_fingerprint,
                    state.observed_at.isoformat(),
                ),
            )

    def load_repository_state(
        self, repository_id: str
    ) -> m.RepositoryState | None:
        row = self._db.execute(
            "SELECT revision_id, dirty, state_fingerprint, observed_at "
            "FROM repositories WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return None
        return m.RepositoryState(
            repository_id=repository_id,
            revision_id=row[0],
            dirty=bool(row[1]),
            state_fingerprint=row[2],
            observed_at=_datetime.datetime.fromisoformat(row[3]),
        )
