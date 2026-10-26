"""Writes: one batch entry point over one writer per table group."""

from __future__ import annotations

from collections.abc import Callable as _Callable

import sqlite3 as _sqlite3

import dataclasses as _dataclasses
import datetime as _datetime
import json as _json

from span.core import model as m
from span.core.refs import ref_value
from span.shell.sqlite_store.mapping import (
    _decode_claim,
    _decode_relationship,
    _encode,
)


class WriteMixin:
    _db: _sqlite3.Connection
    _now: _Callable[[], _datetime.datetime]
    _target_retention_days: int

    def write_index_batch(self, batch: m.CanonicalIndexBatch) -> m.StoreWriteResult:
        """Persist one canonical batch, one writer per table group.

        The batch is one transaction; each writer owns exactly one table group and
        returns the rows it wrote. Validation that the batch as a whole is
        well-formed happens here, before any write.
        """
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
            or batch.verification_records
        ):
            raise ValueError("index batch with content requires subjects")
        with self._db:
            written = self._write_subjects(batch.subjects)
            written += self._write_claims(batch.claims)
            written += self._write_relationships(batch.relationships)
            written += self._write_evidence_dependencies(batch.evidence_dependencies)
            written += self._write_coverage_dependencies(
                batch.coverage_dependencies, batch.subjects
            )
            written += self._write_question_coverages(coverages)
            written += self._write_premise_dependents(batch.claims, batch.relationships)
            written += self._write_retirements(
                batch.retires_claims, batch.retires_relationships
            )
            written += self._write_conflicts(batch.conflicts)
            written += self._write_verification_records(batch.verification_records)
            written += self._write_target_associations(batch.target_associations)
        return m.StoreWriteResult(written_count=written)

    def _write_subjects(self, subjects: tuple[m.Subject, ...]) -> int:
        written = 0
        for subject in subjects:
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
        return written

    def _write_claims(self, claims: tuple[m.SemanticClaim, ...]) -> int:
        written = 0
        for claim in claims:
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
        return written

    def _write_relationships(
        self, relationships: tuple[m.SemanticRelationship, ...]
    ) -> int:
        written = 0
        for rel in relationships:
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
        return written

    def _write_evidence_dependencies(
        self, dependencies: tuple[m.EvidenceDependency, ...]
    ) -> int:
        written = 0
        for dep in dependencies:
            semantic_id = dep.semantic_id
            self._db.execute(
                "INSERT OR REPLACE INTO evidence_dependencies"
                "(semantic_id, semantic_kind, evidence_id, repository_id, "
                "locator, observed_fingerprint, canonical_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    ref_value(semantic_id),
                    "CLAIM" if isinstance(semantic_id, m.ClaimRef) else "RELATIONSHIP",
                    dep.evidence_ref.evidence_id.value,
                    dep.evidence_ref.repository_id,
                    dep.evidence_ref.locator,
                    dep.observed_fingerprint,
                    _encode(m.to_canonical(dep)),
                ),
            )
            written += 1
        return written

    def _write_coverage_dependencies(
        self,
        dependencies: tuple[m.CoverageDependency, ...],
        subjects: tuple[m.Subject, ...],
    ) -> int:
        written = 0
        for coverage in dependencies:
            scope = sorted({s.canonical_locator for s in coverage.scope_subjects})
            self._db.execute(
                "INSERT INTO coverage_dependencies"
                "(repository_id, scope_locators, inventory_fingerprint, "
                "observed_at, canonical_json) VALUES(?, ?, ?, ?, ?)",
                (
                    subjects[0].subject_id.repository_id if subjects else "",
                    _json.dumps(scope, sort_keys=True),
                    coverage.inventory_fingerprint,
                    coverage.observed_at.isoformat(),
                    _encode(m.to_canonical(coverage)),
                ),
            )
            written += 1
        return written

    def _write_question_coverages(
        self, coverages: tuple[m.InterpretationCoverage, ...]
    ) -> int:
        written = 0
        for qcov in coverages:
            question = qcov.question
            if question is None:
                continue
            # [design note C](docs/design-references.md#c) C-05: persistence boundary. An ANSWERED row with empty
            # result refs is false completion regardless of what validation
            # admitted; the service must derive refs before writing. Fail the
            # batch, never persist it.
            if (
                qcov.disposition is m.SemanticQuestionDisposition.ANSWERED
                and not qcov.result_refs
            ):
                raise ValueError(
                    "ANSWERED question coverage without result refs cannot persist"
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
                    _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
                    _encode(m.to_canonical(qcov)),
                ),
            )
            written += 1
            for ref in qcov.result_refs:
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
                        ref.id.value,
                        "CLAIM" if isinstance(ref, m.ClaimRef) else "RELATIONSHIP",
                    ),
                )
                written += 1
        return written

    def _write_premise_dependents(
        self,
        claims: tuple[m.SemanticClaim, ...],
        relationships: tuple[m.SemanticRelationship, ...],
    ) -> int:
        written = 0
        items: tuple[m.SemanticClaim | m.SemanticRelationship, ...] = (
            *claims,
            *relationships,
        )
        for item in items:
            dep_id = (
                item.claim_id.value
                if isinstance(item, m.SemanticClaim)
                else item.relationship_id.value
            )
            dep_kind = "CLAIM" if isinstance(item, m.SemanticClaim) else "RELATIONSHIP"
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
                        "CLAIM" if isinstance(pref, m.ClaimRef) else "RELATIONSHIP",
                        dep_id,
                        dep_kind,
                        _json.dumps(
                            {"premise": pref.id.value, "dependent": dep_id},
                            sort_keys=True,
                        ),
                    ),
                )
                written += 1
        return written

    def _write_retirements(
        self,
        claims: tuple[m.ClaimRef, ...],
        relationships: tuple[m.RelationshipRef, ...],
    ) -> int:
        written = 0
        for claim_ref in claims:
            row = self._db.execute(
                "SELECT canonical_json, repository_id FROM claims WHERE claim_id=?",
                (claim_ref.id.value,),
            ).fetchone()
            if row is None:
                raise ValueError(f"retire names unknown claim: {claim_ref.id.value}")
            for statement in (
                "DELETE FROM claims WHERE claim_id=?",
                "DELETE FROM evidence_dependencies WHERE semantic_id=?",
                "DELETE FROM premise_dependents WHERE premise_id=? OR dependent_id=?",
                "DELETE FROM question_result_refs WHERE result_id=?",
            ):
                params = (
                    (claim_ref.id.value, claim_ref.id.value)
                    if "premise_dependents" in statement
                    else (claim_ref.id.value,)
                )
                self._db.execute(statement, params)
            written += 1
        for relationship_ref in relationships:
            row = self._db.execute(
                "SELECT canonical_json, repository_id FROM relationships "
                "WHERE relationship_id=?",
                (relationship_ref.id.value,),
            ).fetchone()
            if row is None:
                raise ValueError(
                    "retire names unknown relationship: " + relationship_ref.id.value
                )
            for statement in (
                "DELETE FROM relationships WHERE relationship_id=?",
                "DELETE FROM evidence_dependencies WHERE semantic_id=?",
                "DELETE FROM premise_dependents WHERE premise_id=? OR dependent_id=?",
                "DELETE FROM question_result_refs WHERE result_id=?",
            ):
                params = (
                    (relationship_ref.id.value, relationship_ref.id.value)
                    if "premise_dependents" in statement
                    else (relationship_ref.id.value,)
                )
                self._db.execute(statement, params)
            written += 1
        return written

    def _write_conflicts(self, conflicts: tuple[m.RecordedConflict, ...]) -> int:
        written = 0
        for conflict in conflicts:
            self._db.execute(
                "INSERT OR REPLACE INTO conflict_records"
                "(repository_id, subject_locator, left_id, right_id, "
                "canonical_json) VALUES(?, ?, ?, ?, ?)",
                (
                    conflict.subject.repository_id,
                    conflict.subject.canonical_locator,
                    conflict.left.id.value,
                    conflict.right.id.value,
                    _encode(m.to_canonical(conflict)),
                ),
            )
            written += 1
        return written

    def _write_verification_records(
        self, records: tuple[m.VerificationRecord, ...]
    ) -> int:
        written = 0
        for record in records:
            # State upsert on the natural key: one row per (subject, verified
            # scope), never a history.
            self._db.execute(
                "INSERT OR REPLACE INTO verification_records"
                "(repository_id, subject_locator, subject_kind, "
                "scope_fingerprint, command, exit_status, "
                "observed_revision, observed_at, observer) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.repository_id,
                    record.subject.canonical_locator,
                    record.subject.subject_kind.value,
                    record.scope_fingerprint,
                    record.command,
                    record.exit_status,
                    record.observed_revision,
                    record.observed_at.isoformat(),
                    record.observer,
                ),
            )
            written += 1
        return written

    def _write_target_associations(
        self,
        target_assocs: tuple[m.TargetAssociation, ...] | m.TargetAssociation | None,
    ) -> int:
        if isinstance(target_assocs, m.TargetAssociation):
            target_assocs = (target_assocs,)
        if not target_assocs:
            return 0
        written = 0
        now = self._now()
        now_iso = now.isoformat()
        expires = (
            now + _datetime.timedelta(days=self._target_retention_days)
        ).isoformat()
        self._db.execute(
            "DELETE FROM target_associations WHERE expires_at <= ?",
            (now_iso,),
        )
        for assoc in target_assocs:
            # The carrier carries the deadline it is stored under, so a status
            # answer can state the handle's lifespan from the same value the
            # reaper uses.
            stored = (
                assoc
                if assoc.expires_at == expires
                else _dataclasses.replace(assoc, expires_at=expires)
            )
            self._db.execute(
                "INSERT OR REPLACE INTO target_associations"
                "(repository_id, target_id, last_touched_at, "
                "expires_at, canonical_json) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    stored.repository_id,
                    stored.target_id.value,
                    now_iso,
                    expires,
                    _encode(m.to_canonical(stored)),
                ),
            )
            written += 1
        return written

    def mark_freshness(
        self, updates: tuple[m.FreshnessUpdate, ...]
    ) -> m.StoreWriteResult:
        applied = 0
        with self._db:
            for update in updates:
                sid = ref_value(update.semantic_id)
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
