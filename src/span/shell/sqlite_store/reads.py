"""Semantic reads: subjects, claims, relationships, evidence, and freshness.

One read method per fact group; all decode through the canonical JSON row."""

from __future__ import annotations

import sqlite3 as _sqlite3

import datetime as _datetime

from span.core import model as m
from span.core import paging as _paging
from span.core.refs import ref_value
from span.ports.structural import StructuralDirection

from span.shell.sqlite_store.mapping import (
    _decode_claim,
    _decode_conflict,
    _decode_dependency,
    _decode_relationship,
    _decode_subject,
    _scope_filter,
    _scope_range_queries,
)


class ReadMixin:
    _db: _sqlite3.Connection

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
        """Exact canonical-locator lookup ([design note I](docs/design-references.md#i) S1 §5.1).

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
                    _paging.next_page_token(offset + len(items)) if truncated else None
                ),
            ),
        )

    def count_repository_subjects(self, repository_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM subjects WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def load_subjects_in_scope(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        bounds: m.QueryBounds,
        after: tuple[str, str] | None = None,
    ) -> m.SubjectPage:
        """Bounded keyset page of subjects inside an exact evidence scope."""
        limit = bounds.max_subjects
        rows: list[tuple[str, str, str]] = []
        for where, params in _scope_range_queries(scope):
            sql = (
                "SELECT locator, kind, canonical_json FROM subjects "
                "WHERE repository_id=? AND " + where
            )
            args: list[object] = [repository_id, *params]
            if after is not None:
                sql += " AND (locator > ? OR (locator = ? AND kind > ?))"
                args.extend((after[0], after[0], after[1]))
            sql += " ORDER BY locator, kind LIMIT ?"
            args.append(limit + 1)
            rows.extend(self._db.execute(sql, tuple(args)).fetchall())

        rows.sort(key=lambda row: (row[0], row[1]))
        seen: set[tuple[str, str]] = set()
        unique: list[tuple[str, str, str]] = []
        for row in rows:
            key = (row[0], row[1])
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)

        kept = unique[:limit]
        items = tuple(_decode_subject(payload) for (_locator, _kind, payload) in kept)
        truncated = len(unique) > limit
        return m.SubjectPage(
            items=items,
            bound_info=m.BoundInfo(
                requested_max_results=limit,
                requested_max_depth=0,
                returned_results=len(items),
                truncated=truncated,
                truncated_category="semantic_subjects" if truncated else None,
                continuation_token=None,
            ),
        )

    def count_subjects_in_scope(
        self, repository_id: str, scope: m.EvidenceScope
    ) -> int:
        clause, params = _scope_filter(scope)
        row = self._db.execute(
            "SELECT COUNT(*) FROM subjects " "WHERE repository_id=? AND " + clause,
            (repository_id, *params),
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
                    raise ValueError(f"unknown claim ref: {ref.id.value}")
                found.append(_decode_claim(row[0]))
            else:
                row = self._db.execute(
                    "SELECT canonical_json FROM relationships "
                    "WHERE relationship_id=? AND repository_id=?",
                    (ref.id.value, repository_id),
                ).fetchone()
                if row is None:
                    raise ValueError(f"unknown relationship ref: {ref.id.value}")
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
        wanted = {ref_value(i) for i in claim_or_relationship_ids}
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

    def load_premise_dependents(
        self,
        repository_id: str,
        premise_refs: tuple[m.ClaimRef | m.RelationshipRef, ...],
    ) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
        wanted = {r.id.value for r in premise_refs}
        if not wanted:
            return ()
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

    def load_verification_record(
        self,
        repository_id: str,
        subject: m.SubjectId,
        scope_fingerprint: str,
    ) -> m.VerificationRecord | None:
        """The single current record for one (subject, verified scope)."""
        row = self._db.execute(
            "SELECT subject_locator, subject_kind, scope_fingerprint, command, "
            "exit_status, observed_revision, observed_at, observer "
            "FROM verification_records WHERE repository_id=? "
            "AND subject_locator=? AND subject_kind=? AND scope_fingerprint=?",
            (
                repository_id,
                subject.canonical_locator,
                subject.subject_kind.value,
                scope_fingerprint,
            ),
        ).fetchone()
        if row is None:
            return None
        return m.VerificationRecord(
            repository_id=repository_id,
            subject=m.SubjectId(
                repository_id=repository_id,
                subject_kind=m.SubjectKind(row[1]),
                canonical_locator=row[0],
            ),
            scope_fingerprint=row[2],
            command=row[3],
            exit_status=row[4],
            observed_revision=row[5],
            observed_at=_datetime.datetime.fromisoformat(row[6]),
            observer=row[7],
        )
