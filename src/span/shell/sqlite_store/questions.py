"""Question coverage and discovery-dependency reads."""

from __future__ import annotations

import sqlite3 as _sqlite3

import json as _json

from span.core import model as m

from span.shell.sqlite_store.mapping import (
    _decode_coverage,
    _decode_question_coverage,
)


class QuestionReadMixin:
    _db: _sqlite3.Connection

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
            self._filter_question_coverages(repository_id, scope_root, subject_ids)
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

    def count_question_dispositions(self, repository_id: str) -> dict[str, int]:
        rows = self._db.execute(
            "SELECT disposition, COUNT(*) FROM question_coverages "
            "WHERE repository_id=? GROUP BY disposition",
            (repository_id,),
        ).fetchall()
        return {str(d): int(n) for d, n in rows}
