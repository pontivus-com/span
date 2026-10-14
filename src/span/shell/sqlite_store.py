"""Minimum SQLite SemanticStore (plan Phase 1.7, §10, v0.6 §4.11/§5.5).

Persists canonical domain types directly — rows map to canonical JSON
plus query columns; no second semantic model is introduced (§10.2/§10.3,
I-15). Table decomposition is physical only and carries no semantic
authority. Stdlib ``sqlite3``; no third-party binding (ledger).

Schema version is 5 (``SCHEMA_VERSION``): assertion-nature modality
(Addendum I S6) plus target-association accounting (Addendum E E-13A)
plus question coverage (Addendum B). v2/v3/v4 stores migrate
non-destructively; legacy items remain unassessed without invented
question ownership and preserve history without inferred nature.
"""

from __future__ import annotations

import datetime as _datetime
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging

__all__ = ["SCHEMA_VERSION", "TARGET_RETENTION_DAYS", "SqliteSemanticStore"]

SCHEMA_VERSION = 5

TARGET_RETENTION_DAYS = 90

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
CREATE TABLE IF NOT EXISTS question_coverages(
  repository_id TEXT NOT NULL,
  scope_root_locator TEXT NOT NULL,
  scope_root_kind TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  question_class TEXT NOT NULL,
  question_slice TEXT NOT NULL,
  disposition TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(
    repository_id, scope_root_locator, scope_root_kind,
    subject_locator, subject_kind, question_class, question_slice
  )
);
CREATE TABLE IF NOT EXISTS premise_dependents(
  repository_id TEXT NOT NULL,
  premise_id TEXT NOT NULL,
  premise_kind TEXT NOT NULL,
  dependent_id TEXT NOT NULL,
  dependent_kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, premise_id, dependent_id)
);
CREATE TABLE IF NOT EXISTS question_result_refs(
  repository_id TEXT NOT NULL,
  scope_root_locator TEXT NOT NULL,
  scope_root_kind TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  question_class TEXT NOT NULL,
  question_slice TEXT NOT NULL,
  result_id TEXT NOT NULL,
  result_kind TEXT NOT NULL,
  PRIMARY KEY(
    repository_id, scope_root_locator, scope_root_kind,
    subject_locator, subject_kind, question_class, question_slice,
    result_id
  )
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
CREATE TABLE IF NOT EXISTS target_associations(
  repository_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  last_touched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, target_id)
);
CREATE INDEX IF NOT EXISTS idx_target_associations_repo
  ON target_associations(repository_id);
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


def _decode_question_coverage(payload: str) -> m.InterpretationCoverage:
    value = m.from_canonical(m.InterpretationCoverage, _json.loads(payload))
    assert isinstance(value, m.InterpretationCoverage)
    return value


def _decode_conflict(payload: str) -> m.RecordedConflict:
    value = m.from_canonical(m.RecordedConflict, _json.loads(payload))
    assert isinstance(value, m.RecordedConflict)
    return value


def _strip_retired_target_account_fields(data: object) -> object:
    """Persistence-boundary transition for one retired field (E-13A/D).

    Rows persisted before the membership-only correction contain
    `observed_content_fingerprint` inside `TargetInventoryAccount`
    entries. Remove exactly that field, only inside dicts tagged
    `$type == "TargetInventoryAccount"`, before strict canonical
    decoding. Every other unknown field still fails closed in the
    decoder, and writes never re-encode the retired field.
    """
    if isinstance(data, list):
        return [_strip_retired_target_account_fields(item) for item in data]
    if isinstance(data, dict):
        if data.get("$type") == "TargetInventoryAccount":
            data = {
                key: value
                for key, value in data.items()
                if key != "observed_content_fingerprint"
            }
        return {
            key: _strip_retired_target_account_fields(value)
            for key, value in data.items()
        }
    return data


def _ref_id(ref: m.ClaimRef | m.RelationshipRef) -> str:
    return ref.id.value


class SqliteSemanticStore:
    """SemanticStore over one SQLite database file (or ``:memory:``).

    One persistent connection per instance (required for ``:memory:``).
    Single-threaded use; transactions are per-method (atomic batch
    writes for index materialization).
    """

    def __init__(
        self,
        path: str | _pathlib.Path,
        target_retention_days: int = TARGET_RETENTION_DAYS,
        utc_now: object = None,
    ) -> None:
        self._db = _sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys=ON")
        self._target_retention_days = target_retention_days
        self._utc_now = utc_now or (
            lambda: _datetime.datetime.now(_datetime.timezone.utc)
        )
        # Inspect on-disk version before mutating; fresh DB has no meta row.
        try:
            row = self._db.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
        except _sqlite3.OperationalError:
            row = None
        on_disk = int(row[0]) if row is not None else 0
        if on_disk not in (0, 2, 3, 4, 5):
            raise ValueError(f"unsupported schema version: {on_disk}")
        if on_disk == 0:
            # Fresh database: create the full v5 schema at once.
            self._db.executescript(_SCHEMA)
            self._db.execute(
                "INSERT OR REPLACE INTO meta(key, value) "
                "VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._db.commit()
            self._reap_expired_target_associations()
            return
        if on_disk == 5:
            self._db.executescript(_SCHEMA)
            self._db.execute(
                "INSERT OR REPLACE INTO meta(key, value) "
                "VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._db.commit()
            self._reap_expired_target_associations()
            return
        if on_disk == 4:
            # v4→v5 atomic: rewrite active and retired payloads with
            # LEGACY_UNCLASSIFIED, preserve IDs/trust/evidence/history,
            # publish v5 only after success. No decoder fallback remains
            # after migration except this single-version step.
            try:
                with self._db:
                    self._db.executescript(_SCHEMA)
                    self._migrate_v4_payloads_to_v5()
                    self._db.execute(
                        "INSERT OR REPLACE INTO meta(key, value) "
                        "VALUES('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )
            except Exception:
                raise
            self._reap_expired_target_associations()
            return
        if on_disk == 3:
            # v3→v4 tables then v4→v5 payloads, atomically; publish v5.
            try:
                with self._db:
                    self._db.execute(
                        "CREATE TABLE IF NOT EXISTS target_associations("
                        "  repository_id TEXT NOT NULL,"
                        "  target_id TEXT NOT NULL,"
                        "  last_touched_at TEXT NOT NULL,"
                        "  expires_at TEXT NOT NULL,"
                        "  canonical_json TEXT NOT NULL,"
                        "  PRIMARY KEY(repository_id, target_id))"
                    )
                    self._db.execute(
                        "CREATE INDEX IF NOT EXISTS "
                        "idx_target_associations_repo "
                        "ON target_associations(repository_id)"
                    )
                    tables = {
                        r[0]
                        for r in self._db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                    if "target_associations" not in tables:
                        raise RuntimeError("v3→v4 migration incomplete")
                    self._migrate_v4_payloads_to_v5()
                    self._db.execute(
                        "INSERT OR REPLACE INTO meta(key, value) "
                        "VALUES('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )
            except Exception:
                raise
            self._reap_expired_target_associations()
            return
        # v2→v3: one explicit atomic migration transaction. New
        # question-coverage/indexing tables are created and the version
        # is published in the SAME transaction; an interruption rolls
        # back without partial semantic state, leaving a valid v2
        # database behind (Addendum B B.8). No invented question
        # ownership: absence of coverage means unassessed.
        try:
            with self._db:
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS question_coverages("
                    "  repository_id TEXT NOT NULL,"
                    "  scope_root_locator TEXT NOT NULL,"
                    "  scope_root_kind TEXT NOT NULL,"
                    "  subject_locator TEXT NOT NULL,"
                    "  subject_kind TEXT NOT NULL,"
                    "  question_class TEXT NOT NULL,"
                    "  question_slice TEXT NOT NULL,"
                    "  disposition TEXT NOT NULL,"
                    "  observed_at TEXT NOT NULL,"
                    "  canonical_json TEXT NOT NULL,"
                    "  PRIMARY KEY("
                    "    repository_id, scope_root_locator, scope_root_kind,"
                    "    subject_locator, subject_kind, question_class,"
                    "    question_slice"
                    "  ))"
                )
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS premise_dependents("
                    "  repository_id TEXT NOT NULL,"
                    "  premise_id TEXT NOT NULL,"
                    "  premise_kind TEXT NOT NULL,"
                    "  dependent_id TEXT NOT NULL,"
                    "  dependent_kind TEXT NOT NULL,"
                    "  canonical_json TEXT NOT NULL,"
                    "  PRIMARY KEY(repository_id, premise_id, dependent_id))"
                )
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS question_result_refs("
                    "  repository_id TEXT NOT NULL,"
                    "  scope_root_locator TEXT NOT NULL,"
                    "  scope_root_kind TEXT NOT NULL,"
                    "  subject_locator TEXT NOT NULL,"
                    "  subject_kind TEXT NOT NULL,"
                    "  question_class TEXT NOT NULL,"
                    "  question_slice TEXT NOT NULL,"
                    "  result_id TEXT NOT NULL,"
                    "  result_kind TEXT NOT NULL,"
                    "  PRIMARY KEY("
                    "    repository_id, scope_root_locator, scope_root_kind,"
                    "    subject_locator, subject_kind, question_class,"
                    "    question_slice, result_id"
                    "  ))"
                )
                # Verify the new tables exist before publishing v3.
                tables = {
                    r[0]
                    for r in self._db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                missing = {
                    "question_coverages",
                    "premise_dependents",
                    "question_result_refs",
                } - tables
                if missing:
                    raise RuntimeError(
                        f"v2→v3 migration incomplete, missing: {sorted(missing)}"
                    )
                # v3→v4 tables chained in the same atomic migration,
                # then v4→v5 payloads; publish v5 only after success.
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS target_associations("
                    "  repository_id TEXT NOT NULL,"
                    "  target_id TEXT NOT NULL,"
                    "  last_touched_at TEXT NOT NULL,"
                    "  expires_at TEXT NOT NULL,"
                    "  canonical_json TEXT NOT NULL,"
                    "  PRIMARY KEY(repository_id, target_id))"
                )
                self._db.execute(
                    "CREATE INDEX IF NOT EXISTS "
                    "idx_target_associations_repo "
                    "ON target_associations(repository_id)"
                )
                self._migrate_v4_payloads_to_v5()
                self._db.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
        except Exception:
            # Context manager rolled back: on-disk state is still v2.
            # Re-check nothing was published before surfacing.
            raise
        self._reap_expired_target_associations()

    def _migrate_v4_payloads_to_v5(self) -> None:
        """Rewrite v4 claim/relationship payloads with LEGACY nature (S6).

        In one transaction, adds assertion_nature=LEGACY_UNCLASSIFIED to
        existing active and retired payloads, preserving old universal-
        authority trust outcome without classifying prose. Preserves
        original IDs, references, trust, evidence, retirement history,
        and question dispositions. New IDs include nature; old IDs are
        not recomputed. Malformed payloads rollback the transaction.
        Idempotent: rows already carrying nature are left untouched.
        Caller holds the migration transaction; version is published
        only after this succeeds.
        """
        for table, id_col in (
            ("claims", "claim_id"),
            ("relationships", "relationship_id"),
            ("retired_claims", "claim_id"),
            ("retired_relationships", "relationship_id"),
        ):
            try:
                rows = self._db.execute(
                    f"SELECT {id_col}, canonical_json FROM {table}"
                ).fetchall()
            except _sqlite3.OperationalError:
                continue
            for row_id, payload in rows:
                try:
                    data = _json.loads(payload)
                except ValueError as exc:
                    raise RuntimeError(
                        f"v4→v5 migration malformed payload in {table}: "
                        f"{row_id}: {exc}"
                    ) from exc
                if not isinstance(data, dict):
                    raise RuntimeError(
                        f"v4→v5 migration malformed payload in {table}: "
                        f"{row_id}"
                    )
                if "assertion_nature" in data:
                    continue
                data["assertion_nature"] = "LEGACY_UNCLASSIFIED"
                # Validate the rewritten payload decodes under v5 before
                # writing: preserves trust/evidence/history, rejects
                # malformed without partial state (transaction rolls back).
                try:
                    if table in ("claims", "retired_claims"):
                        decoded = m.from_canonical(m.SemanticClaim, data)
                        assert isinstance(decoded, m.SemanticClaim)
                        assert (
                            decoded.assertion_nature
                            is m.AssertionNature.LEGACY_UNCLASSIFIED
                        )
                    else:
                        decoded = m.from_canonical(
                            m.SemanticRelationship, data
                        )
                        assert isinstance(
                            decoded, m.SemanticRelationship
                        )
                        assert (
                            decoded.assertion_nature
                            is m.AssertionNature.LEGACY_UNCLASSIFIED
                        )
                except Exception as exc:
                    raise RuntimeError(
                        f"v4→v5 migration validation failed in {table}: "
                        f"{row_id}: {exc}"
                    ) from exc
                self._db.execute(
                    f"UPDATE {table} SET canonical_json=? "
                    f"WHERE {id_col}=?",
                    (_encode(m.to_canonical(decoded)), row_id),
                )

    def _now(self) -> _datetime.datetime:
        result = self._utc_now()
        assert isinstance(result, _datetime.datetime)
        return result

    def _reap_expired_target_associations(self) -> int:
        now_iso = self._now().isoformat()
        try:
            cur = self._db.execute(
                "DELETE FROM target_associations WHERE expires_at <= ?",
                (now_iso,),
            )
            self._db.commit()
            return cur.rowcount or 0
        except _sqlite3.OperationalError:
            return 0

    def close(self) -> None:
        """Release the database connection (shell lifecycle only)."""
        self._db.close()

    def load_target_association(
        self, repository_id: str, target_id: m.TargetId
    ) -> m.TargetAssociation | None:
        try:
            row = self._db.execute(
                "SELECT canonical_json, expires_at FROM target_associations "
                "WHERE repository_id=? AND target_id=?",
                (repository_id, target_id.value),
            ).fetchone()
        except _sqlite3.OperationalError:
            return None
        if row is None:
            return None
        payload, expires_at = row
        # TTL-as-absent: expired rows read as absent without mutating.
        if expires_at <= self._now().isoformat():
            return None
        data = _json.loads(payload)
        # Persistence-boundary transition (Addendum E E-13A/D): rows
        # written before the membership-only correction carry the retired
        # `observed_content_fingerprint` inside TargetInventoryAccount
        # entries. Strip it here, at the explicitly governed store
        # boundary, before strict canonical decoding. The general decoder
        # stays strict: every other unknown field still fails closed, and
        # this retired field is never re-encoded on write.
        data = _strip_retired_target_account_fields(data)
        value = m.from_canonical(m.TargetAssociation, data)
        assert isinstance(value, m.TargetAssociation)
        return value

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

    def load_subjects_by_locator(
        self,
        repository_id: str,
        locator: str,
        expected_kinds: tuple[m.SubjectKind, ...],
        bounds: m.QueryBounds,
    ) -> m.SubjectPage:
        """Exact canonical-locator lookup (Addendum I S1 §5.1).

        Exact string equality only. Kinds filtered before limiting,
        ordered by kind, one extra row to detect truncation. Uses the
        existing (repository_id, locator, kind) subject key; no new
        identity table or name index.
        """
        if not locator:
            return m.SubjectPage(
                items=(),
                bound_info=m.BoundInfo(
                    requested_max_results=bounds.max_subjects,
                    requested_max_depth=0,
                    returned_results=0,
                    truncated=False,
                    truncated_category=None,
                    continuation_token=None,
                ),
            )
        if expected_kinds:
            kinds = [k.value for k in expected_kinds]
            placeholders = ",".join("?" for _ in kinds)
            rows = self._db.execute(
                "SELECT canonical_json, kind FROM subjects "
                f"WHERE repository_id=? AND locator=? AND kind IN ({placeholders}) "
                "ORDER BY kind LIMIT ?",
                (repository_id, locator, *kinds, bounds.max_subjects + 1),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT canonical_json, kind FROM subjects "
                "WHERE repository_id=? AND locator=? "
                "ORDER BY kind LIMIT ?",
                (repository_id, locator, bounds.max_subjects + 1),
            ).fetchall()
        truncated = len(rows) > bounds.max_subjects
        kept = rows[: bounds.max_subjects]
        items = tuple(_decode_subject(payload) for payload, _ in kept)
        return m.SubjectPage(
            items=items,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(items),
                truncated=truncated,
                truncated_category="candidates" if truncated else None,
                continuation_token=None,
            ),
        )

    def load_repository_subjects(
        self,
        repository_id: str,
        bounds: m.QueryBounds,
        offset: int = 0,
    ) -> m.SubjectPage:
        """Load a bounded page from persisted semantic subjects only."""
        if offset < 0:
            raise ValueError("subject offset must be non-negative")
        rows = self._db.execute(
            "SELECT canonical_json FROM subjects "
            "WHERE repository_id=? ORDER BY locator, kind "
            "LIMIT ? OFFSET ?",
            (repository_id, bounds.max_subjects, offset),
        ).fetchall()
        items = tuple(_decode_subject(payload) for (payload,) in rows)
        total = self.count_repository_subjects(repository_id)
        truncated = offset + len(items) < total
        return m.SubjectPage(
            items=items,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(items),
                truncated=truncated,
                truncated_category="semantic_subjects" if truncated else None,
                continuation_token=(
                    _paging.next_page_token(offset + len(items))
                    if truncated else None
                ),
            ),
        )

    def count_repository_subjects(self, repository_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM subjects WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

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

    def load_evidence_records(
        self,
        repository_id: str,
        evidence_ids: tuple[str, ...],
    ) -> tuple[m.EvidenceDependency, ...]:
        wanted = set(evidence_ids)
        rows = self._db.execute(
            "SELECT canonical_json, evidence_id FROM evidence_dependencies "
            "WHERE repository_id=? ORDER BY evidence_id, semantic_id",
            (repository_id,),
        ).fetchall()
        return tuple(
            _decode_dependency(payload)
            for payload, evidence_id in rows
            if evidence_id in wanted
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
            "WHERE repository_id=? ORDER BY observed_at, rowid",
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

    def load_question_coverages(
        self,
        repository_id: str,
        scope_root: m.SubjectId | None,
        subject_ids: tuple[m.SubjectId, ...],
        bounds: m.QueryBounds,
    ) -> tuple[m.InterpretationCoverage, ...]:
        wanted = {s.canonical_locator for s in subject_ids}
        rows = self._db.execute(
            "SELECT canonical_json, scope_root_locator, subject_locator, "
            "question_class, question_slice FROM question_coverages "
            "WHERE repository_id=? ORDER BY question_class, subject_locator, "
            "question_slice",
            (repository_id,),
        ).fetchall()
        found: list[m.InterpretationCoverage] = []
        for payload, root_loc, subj_loc, _qclass, _qslice in rows:
            if scope_root is not None and root_loc != scope_root.canonical_locator:
                continue
            if wanted and subj_loc not in wanted:
                continue
            found.append(_decode_question_coverage(payload))
        return tuple(found[: bounds.max_results])

    def _filter_question_coverages(
        self,
        repository_id: str,
        scope_root: m.SubjectId | None,
        subject_ids: tuple[m.SubjectId, ...],
    ) -> list[m.InterpretationCoverage]:
        wanted = {s.canonical_locator for s in subject_ids}
        rows = self._db.execute(
            "SELECT canonical_json, scope_root_locator, subject_locator "
            "FROM question_coverages "
            "WHERE repository_id=? ORDER BY question_class, subject_locator, "
            "question_slice",
            (repository_id,),
        ).fetchall()
        found: list[m.InterpretationCoverage] = []
        for payload, root_loc, subj_loc in rows:
            if scope_root is not None and root_loc != scope_root.canonical_locator:
                continue
            if wanted and subj_loc not in wanted:
                continue
            found.append(_decode_question_coverage(payload))
        return found

    def load_all_question_coverages(
        self,
        repository_id: str,
        scope_root: m.SubjectId | None,
        subject_ids: tuple[m.SubjectId, ...],
    ) -> tuple[m.InterpretationCoverage, ...]:
        """Unbounded reads for reconciliation decisions (B-03)."""
        return tuple(
            self._filter_question_coverages(
                repository_id, scope_root, subject_ids
            )
        )

    def count_question_coverages(
        self,
        repository_id: str,
        scope_root: m.SubjectId | None,
        subject_ids: tuple[m.SubjectId, ...],
    ) -> int:
        wanted = {s.canonical_locator for s in subject_ids}
        rows = self._db.execute(
            "SELECT scope_root_locator, subject_locator FROM question_coverages "
            "WHERE repository_id=?",
            (repository_id,),
        ).fetchall()
        count = 0
        for root_loc, subj_loc in rows:
            if scope_root is not None and root_loc != scope_root.canonical_locator:
                continue
            if wanted and subj_loc not in wanted:
                continue
            count += 1
        return count

    def load_premise_dependents(
        self,
        repository_id: str,
        premise_refs: tuple[m.ClaimRef | m.RelationshipRef, ...],
    ) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
        wanted = {r.id.value for r in premise_refs}
        if not wanted:
            return ()
        rows = self._db.execute(
            "SELECT dependent_id, dependent_kind FROM premise_dependents "
            "WHERE repository_id=? ORDER BY dependent_id",
            (repository_id,),
        ).fetchall()
        # Filter by premise membership via premise_id column.
        premise_rows = self._db.execute(
            "SELECT premise_id, dependent_id, dependent_kind "
            "FROM premise_dependents WHERE repository_id=?",
            (repository_id,),
        ).fetchall()
        out: list[m.ClaimRef | m.RelationshipRef] = []
        seen: set[str] = set()
        for premise_id, dep_id, dep_kind in premise_rows:
            if premise_id not in wanted or dep_id in seen:
                continue
            seen.add(dep_id)
            if dep_kind == "CLAIM":
                out.append(m.ClaimRef(id=m.ClaimId(dep_id)))
            else:
                out.append(m.RelationshipRef(id=m.RelationshipId(dep_id)))
        return tuple(out)

    # -- writes ---------------------------------------------------------

    def write_index_batch(self, batch: m.CanonicalIndexBatch) -> m.StoreWriteResult:
        written = 0
        coverages = batch.coverage
        if isinstance(coverages, m.InterpretationCoverage):
            coverages = (coverages,)
        if not batch.subjects and (
            batch.claims
            or batch.relationships
            or batch.coverage_dependencies
            or coverages
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
            for qcov in coverages:
                question = qcov.question
                if question is None:
                    continue
                # Addendum C C-05: persistence boundary. An ANSWERED row
                # with empty result refs is false completion regardless of
                # what validation admitted; the service must derive refs
                # before writing. Fail the batch, never persist it.
                if (
                    qcov.disposition
                    is m.SemanticQuestionDisposition.ANSWERED
                    and not qcov.result_refs
                ):
                    raise ValueError(
                        "ANSWERED question coverage without result refs "
                        "cannot persist"
                    )
                repo_id = question.scope_root.repository_id
                self._db.execute(
                    "DELETE FROM question_result_refs WHERE repository_id=? "
                    "AND scope_root_locator=? AND scope_root_kind=? "
                    "AND subject_locator=? AND subject_kind=? "
                    "AND question_class=? AND question_slice=?",
                    (
                        repo_id,
                        question.scope_root.canonical_locator,
                        question.scope_root.subject_kind.value,
                        question.subject.canonical_locator,
                        question.subject.subject_kind.value,
                        question.question_class.value,
                        question.question_slice,
                    ),
                )
                self._db.execute(
                    "INSERT OR REPLACE INTO question_coverages"
                    "(repository_id, scope_root_locator, scope_root_kind, "
                    "subject_locator, subject_kind, question_class, "
                    "question_slice, disposition, observed_at, canonical_json) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        repo_id,
                        question.scope_root.canonical_locator,
                        question.scope_root.subject_kind.value,
                        question.subject.canonical_locator,
                        question.subject.subject_kind.value,
                        question.question_class.value,
                        question.question_slice,
                        qcov.disposition.value,
                        _datetime.datetime.now(
                            _datetime.timezone.utc
                        ).isoformat(),
                        _encode(m.to_canonical(qcov)),
                    ),
                )
                written += 1
                for ref in qcov.result_refs:
                    rid = ref.id.value
                    rkind = "CLAIM" if isinstance(ref, m.ClaimRef) else "RELATIONSHIP"
                    self._db.execute(
                        "INSERT OR REPLACE INTO question_result_refs"
                        "(repository_id, scope_root_locator, scope_root_kind, "
                        "subject_locator, subject_kind, question_class, "
                        "question_slice, result_id, result_kind) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            repo_id,
                            question.scope_root.canonical_locator,
                            question.scope_root.subject_kind.value,
                            question.subject.canonical_locator,
                            question.subject.subject_kind.value,
                            question.question_class.value,
                            question.question_slice,
                            rid,
                            rkind,
                        ),
                    )
                    written += 1
            for item in (*batch.claims, *batch.relationships):
                dep_id = (
                    item.claim_id.value
                    if isinstance(item, m.SemanticClaim)
                    else item.relationship_id.value
                )
                dep_kind = (
                    "CLAIM"
                    if isinstance(item, m.SemanticClaim)
                    else "RELATIONSHIP"
                )
                repo_id = (
                    item.subject.repository_id
                    if isinstance(item, m.SemanticClaim)
                    else item.source.repository_id
                )
                for pref in item.basis.input_refs:
                    if not isinstance(pref, (m.ClaimRef, m.RelationshipRef)):
                        continue
                    self._db.execute(
                        "INSERT OR REPLACE INTO premise_dependents"
                        "(repository_id, premise_id, premise_kind, "
                        "dependent_id, dependent_kind, canonical_json) "
                        "VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            repo_id,
                            pref.id.value,
                            "CLAIM"
                            if isinstance(pref, m.ClaimRef)
                            else "RELATIONSHIP",
                            dep_id,
                            dep_kind,
                            _json.dumps(
                                {"premise": pref.id.value, "dependent": dep_id},
                                sort_keys=True,
                            ),
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
                self._db.execute(
                    "DELETE FROM premise_dependents WHERE premise_id=? "
                    "OR dependent_id=?",
                    (ref.id.value, ref.id.value),
                )
                self._db.execute(
                    "DELETE FROM question_result_refs WHERE result_id=?",
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
                self._db.execute(
                    "DELETE FROM premise_dependents WHERE premise_id=? "
                    "OR dependent_id=?",
                    (ref.id.value, ref.id.value),
                )
                self._db.execute(
                    "DELETE FROM question_result_refs WHERE result_id=?",
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
            target_assocs = batch.target_associations
            if isinstance(target_assocs, m.TargetAssociation):
                target_assocs = (target_assocs,)
            if target_assocs:
                now = self._now()
                now_iso = now.isoformat()
                expires = (
                    now
                    + _datetime.timedelta(days=self._target_retention_days)
                ).isoformat()
                self._db.execute(
                    "DELETE FROM target_associations WHERE expires_at <= ?",
                    (now_iso,),
                )
                for assoc in target_assocs:
                    self._db.execute(
                        "INSERT OR REPLACE INTO target_associations"
                        "(repository_id, target_id, last_touched_at, "
                        "expires_at, canonical_json) "
                        "VALUES(?, ?, ?, ?, ?)",
                        (
                            assoc.repository_id,
                            assoc.target_id.value,
                            now_iso,
                            expires,
                            _encode(m.to_canonical(assoc)),
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
                        assertion_nature=claim.assertion_nature,
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
                        assertion_nature=rel.assertion_nature,
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
