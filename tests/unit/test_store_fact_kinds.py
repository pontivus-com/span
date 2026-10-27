"""Store fact-kind declarations and schema 8 (Step 16, D17/D18).

Every table declares whether it holds an Observation, a State, or a Handle.
The declaration is checked against ``sqlite_master`` in both directions, so a
carrier cannot be added without answering what kind of fact it is. Schema 8
adds ``verification_records``, removes the write-only retirement archives, and
migrates only on explicit request.
"""

import datetime
import json
import pathlib
import sqlite3
import tempfile
import unittest

from span.core import model as m
from span.ports.store import (
    STORE_FACT_DECLARATIONS,
    FactKind,
    SemanticStore,
)
from span.shell.sqlite_store import SCHEMA_VERSION, SqliteSemanticStore, migrate_store

REPO = "fact-svc"


def _subject(locator="src/a.py"):
    return m.Subject(m.SubjectId(REPO, m.SubjectKind.COMPONENT, locator), locator, None)


def _physical_tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _primary_keys(connection):
    keys = {}
    for table in _physical_tables(connection):
        keys[table] = tuple(
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            if row[5]
        )
    return keys


def _undeclared_tables(physical, declarations):
    return sorted(physical - {declaration.table for declaration in declarations})


def _declared_but_missing(physical, declarations):
    return sorted({declaration.table for declaration in declarations} - physical)


def _key_mismatches(primary_keys, declarations):
    bad = {}
    for declaration in declarations:
        if declaration.kind is not FactKind.STATE:
            continue
        actual = primary_keys.get(declaration.table, ())
        if declaration.key_columns != actual:
            bad[declaration.table] = {
                "declared": declaration.key_columns,
                "physical": actual,
            }
    return bad


def _unresolved_writers(declarations):
    return sorted(
        declaration.writer
        for declaration in declarations
        if not callable(getattr(SemanticStore, declaration.writer, None))
    )


class FactKindDeclarationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name) / "store.db"
        self.store = SqliteSemanticStore(str(self.path))
        self.physical = _physical_tables(self.store._db)
        self.keys = _primary_keys(self.store._db)

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_every_table_is_declared_and_every_declaration_exists(self):
        self.assertEqual(_undeclared_tables(self.physical, STORE_FACT_DECLARATIONS), [])
        self.assertEqual(
            _declared_but_missing(self.physical, STORE_FACT_DECLARATIONS), []
        )

    def test_declarations_are_unique_per_table(self):
        tables = [d.table for d in STORE_FACT_DECLARATIONS]
        self.assertEqual(len(tables), len(set(tables)))

    def test_every_state_key_is_the_physical_primary_key(self):
        self.assertEqual(_key_mismatches(self.keys, STORE_FACT_DECLARATIONS), {})

    def test_observations_declare_no_natural_key(self):
        for declaration in STORE_FACT_DECLARATIONS:
            if declaration.kind is FactKind.OBSERVATION:
                with self.subTest(table=declaration.table):
                    self.assertEqual(declaration.key_columns, ())

    def test_every_writer_resolves_on_the_port(self):
        self.assertEqual(_unresolved_writers(STORE_FACT_DECLARATIONS), [])

    def test_gate_detects_an_unclassified_table(self):
        reduced = tuple(d for d in STORE_FACT_DECLARATIONS if d.table != "meta")
        self.assertEqual(_undeclared_tables(self.physical, reduced), ["meta"])

    def test_gate_detects_a_state_key_that_is_not_the_primary_key(self):
        wrong = tuple(d for d in STORE_FACT_DECLARATIONS if d.table != "subjects") + (
            type(STORE_FACT_DECLARATIONS[0])(
                "subjects", FactKind.STATE, ("repository_id",), "write_index_batch"
            ),
        )
        self.assertIn("subjects", _key_mismatches(self.keys, wrong))

    def test_gate_detects_an_unresolvable_writer(self):
        wrong = tuple(d for d in STORE_FACT_DECLARATIONS if d.table != "claims") + (
            type(STORE_FACT_DECLARATIONS[0])(
                "claims", FactKind.OBSERVATION, (), "no_such_writer"
            ),
        )
        self.assertEqual(_unresolved_writers(wrong), ["no_such_writer"])

    def test_retirement_archives_are_gone(self):
        self.assertNotIn("retired_claims", self.physical)
        self.assertNotIn("retired_relationships", self.physical)

    def test_verification_records_are_a_state_with_a_natural_key(self):
        self.assertIn("verification_records", self.physical)
        self.assertEqual(
            self.keys["verification_records"],
            (
                "repository_id",
                "subject_locator",
                "subject_kind",
                "scope_fingerprint",
            ),
        )


def _record(exit_status=0, observed_at=None):
    return m.VerificationRecord(
        repository_id=REPO,
        subject=_subject().subject_id,
        scope_fingerprint="scope-1",
        command="pytest tests/unit",
        exit_status=exit_status,
        observed_revision="rev-1",
        observed_at=observed_at or datetime.datetime.now(datetime.timezone.utc),
        observer="ci",
    )


class VerificationRecordStoreTest(unittest.TestCase):
    def test_repeated_writes_leave_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "store.db"))
            try:
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(_subject(),),
                        verification_records=(_record(exit_status=0),),
                    )
                )
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(_subject(),),
                        verification_records=(_record(exit_status=1),),
                    )
                )
                rows = store._db.execute(
                    "SELECT COUNT(*) FROM verification_records"
                ).fetchone()
                self.assertEqual(rows[0], 1)
                loaded = store.load_verification_record(
                    REPO, _subject().subject_id, "scope-1"
                )
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.exit_status, 1)
            finally:
                store.close()

    def test_absent_record_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(str(pathlib.Path(tmp) / "store.db"))
            try:
                self.assertIsNone(
                    store.load_verification_record(REPO, _subject().subject_id, "never")
                )
            finally:
                store.close()


def _downgrade_to_seven(path):
    """Turn a current store into the schema-7 shape it superseded."""
    connection = sqlite3.connect(str(path))
    try:
        with connection:
            connection.execute("DROP TABLE verification_records")
            connection.execute(
                "CREATE TABLE retired_claims("
                "claim_id TEXT PRIMARY KEY, repository_id TEXT NOT NULL, "
                "retired_at TEXT NOT NULL, canonical_json TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE retired_relationships("
                "relationship_id TEXT PRIMARY KEY, repository_id TEXT NOT NULL, "
                "retired_at TEXT NOT NULL, canonical_json TEXT NOT NULL)"
            )
            connection.execute("UPDATE meta SET value='7' WHERE key='schema_version'")
    finally:
        connection.close()


def _rewrite_target_accounts_to_legacy(path):
    """Inject mapping-era target-account fields without changing the version."""
    connection = sqlite3.connect(str(path))
    try:
        with connection:
            rows = connection.execute(
                "SELECT target_id, canonical_json FROM target_associations"
            ).fetchall()
            for target_id, payload in rows:
                data = json.loads(payload)
                accounts = data.get("inventory_accounting") or []
                legacy = []
                for index, account in enumerate(accounts):
                    adapted = dict(account)
                    if index == 0:
                        adapted["exclusion_basis"] = {
                            "$type": "SemanticBasis",
                            "derivation": "EXPLICIT_EVIDENCE",
                            "summary": "legacy exclusion",
                            "input_refs": [],
                        }
                        legacy.append(adapted)
                    else:
                        legacy.append(
                            {
                                "$type": "TargetInventoryAccount",
                                "evidence_ref": account["evidence_ref"],
                                "assigned_area_subjects": [],
                                "resolution_requirements": [],
                            }
                        )
                data["inventory_accounting"] = legacy
                connection.execute(
                    "UPDATE target_associations SET canonical_json=? "
                    "WHERE target_id=?",
                    (json.dumps(data), target_id),
                )
    finally:
        connection.close()


def _downgrade_to_eight(path):
    """Turn a current store into the schema-8 shape (mapping-era accounts)."""
    _rewrite_target_accounts_to_legacy(path)
    connection = sqlite3.connect(str(path))
    try:
        with connection:
            connection.execute("UPDATE meta SET value='8' WHERE key='schema_version'")
    finally:
        connection.close()


class MigrationTest(unittest.TestCase):
    def test_version_seven_fails_closed_then_migrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            store = SqliteSemanticStore(str(path))
            try:
                store.write_index_batch(m.CanonicalIndexBatch(subjects=(_subject(),)))
            finally:
                store.close()
            _downgrade_to_seven(path)

            with self.assertRaisesRegex(ValueError, "schema version 7"):
                SqliteSemanticStore(str(path))

            report = migrate_store(path)
            self.assertTrue(report["migrated"])
            self.assertEqual((report["from"], report["to"]), (7, SCHEMA_VERSION))

            reopened = SqliteSemanticStore(str(path))
            try:
                self.assertEqual(
                    reopened.schema_version(), m.SchemaVersion(SCHEMA_VERSION)
                )
                loaded = reopened.load_subjects(REPO, (_subject().subject_id,))
                self.assertEqual(
                    [s.subject_id.canonical_locator for s in loaded], ["src/a.py"]
                )
                tables = _physical_tables(reopened._db)
                self.assertIn("verification_records", tables)
                self.assertNotIn("retired_claims", tables)
            finally:
                reopened.close()

    def test_version_eight_rewrites_target_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            store = SqliteSemanticStore(str(path))
            try:
                subject = _subject()
                refs = tuple(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId(f"ev-{index}"),
                        repository_id=REPO,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator=f"src/f{index}.py",
                        revision_or_fingerprint="fp",
                    )
                    for index in range(2)
                )
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(subject,),
                        target_associations=(
                            m.TargetAssociation(
                                target_id=m.TargetId("target-8"),
                                repository_id=REPO,
                                target_scope=m.EvidenceScope(paths=("src",)),
                                objective="migrate",
                                area_subjects=(subject.subject_id,),
                                inventory_accounting=tuple(
                                    m.TargetInventoryAccount(
                                        evidence_ref=ref,
                                        assigned_area_subjects=(subject.subject_id,),
                                    )
                                    for ref in refs
                                ),
                            ),
                        ),
                    )
                )
            finally:
                store.close()
            _downgrade_to_eight(path)
            report = migrate_store(path)
            self.assertTrue(report["migrated"])
            self.assertEqual((report["from"], report["to"]), (8, SCHEMA_VERSION))
            self.assertEqual(report["rewritten_target_accounts"], 1)
            self.assertEqual(report["dropped_target_accounts"], 1)
            reopened = SqliteSemanticStore(str(path))
            try:
                self.assertEqual(
                    reopened.schema_version(), m.SchemaVersion(SCHEMA_VERSION)
                )
                association = reopened.load_target_association(
                    REPO, m.TargetId("target-8")
                )
                assert association is not None
                self.assertEqual(len(association.inventory_accounting), 1)
                self.assertEqual(
                    association.inventory_accounting[0].assigned_area_subjects,
                    (subject.subject_id,),
                )
            finally:
                reopened.close()

    def test_version_nine_normalizes_legacy_target_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            subject = _subject()
            ref = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-9"),
                repository_id=REPO,
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/f9.py",
                revision_or_fingerprint="fp",
            )
            store = SqliteSemanticStore(str(path))
            try:
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(subject,),
                        target_associations=(
                            m.TargetAssociation(
                                target_id=m.TargetId("target-9"),
                                repository_id=REPO,
                                target_scope=m.EvidenceScope(paths=("src",)),
                                objective="migrate",
                                area_subjects=(subject.subject_id,),
                                inventory_accounting=(
                                    m.TargetInventoryAccount(
                                        evidence_ref=ref,
                                        assigned_area_subjects=(subject.subject_id,),
                                    ),
                                ),
                            ),
                        ),
                    )
                )
            finally:
                store.close()
            _rewrite_target_accounts_to_legacy(path)
            report = migrate_store(path)
            self.assertTrue(report["migrated"])
            self.assertEqual(
                (report["from"], report["to"]),
                (SCHEMA_VERSION, SCHEMA_VERSION),
            )
            self.assertEqual(report["rewritten_target_accounts"], 1)
            self.assertEqual(report["dropped_target_accounts"], 0)
            reopened = SqliteSemanticStore(str(path))
            try:
                association = reopened.load_target_association(
                    REPO, m.TargetId("target-9")
                )
                assert association is not None
                self.assertEqual(len(association.inventory_accounting), 1)
            finally:
                reopened.close()

    def test_second_migration_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            SqliteSemanticStore(str(path)).close()
            _downgrade_to_seven(path)
            first = migrate_store(path)
            second = migrate_store(path)
            self.assertTrue(first["migrated"])
            self.assertFalse(second["migrated"])
            self.assertEqual(second["rewritten_verifications"], 0)

    def test_unknown_version_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            store = SqliteSemanticStore(str(path))
            store.close()
            connection = sqlite3.connect(str(path))
            try:
                with connection:
                    connection.execute(
                        "UPDATE meta SET value='6' WHERE key='schema_version'"
                    )
            finally:
                connection.close()
            with self.assertRaisesRegex(ValueError, "only schema 7"):
                migrate_store(path)

    def test_missing_store_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "no Span store"):
                migrate_store(pathlib.Path(tmp) / "absent.db")

    def test_current_version_needs_no_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            SqliteSemanticStore(str(path)).close()
            report = migrate_store(path)
            self.assertFalse(report["migrated"])
            self.assertEqual(report["to"], SCHEMA_VERSION)


class SchemaNineMigrationTest(unittest.TestCase):
    def test_rewrites_080_question_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "store.db"
            subject = _subject()
            question = m.SemanticQuestionScope(
                scope_root=subject.subject_id,
                subject=subject.subject_id,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="purpose",
                materiality_basis="migration test",
            )
            coverage = m.InterpretationCoverage(
                subjects=(subject.subject_id,),
                question_slice="purpose",
                question=question,
                disposition=m.SemanticQuestionDisposition.PENDING,
            )
            store = SqliteSemanticStore(str(path))
            try:
                store.write_index_batch(
                    m.CanonicalIndexBatch(
                        subjects=(subject,),
                        coverage=(coverage,),
                    )
                )
                (payload,) = store._db.execute(
                    "SELECT canonical_json FROM question_coverages"
                ).fetchone()
                data = json.loads(payload)
                data["declared_complete"] = False
                with store._db:
                    store._db.execute(
                        "UPDATE question_coverages SET canonical_json=?",
                        (json.dumps(data, sort_keys=True),),
                    )
            finally:
                store.close()

            preview = migrate_store(path, dry_run=True)
            self.assertFalse(preview["migrated"])
            self.assertEqual(preview["rewritten_question_coverages"], 1)

            report = migrate_store(path)
            self.assertTrue(report["migrated"])
            self.assertEqual(report["rewritten_question_coverages"], 1)

            reopened = SqliteSemanticStore(str(path))
            try:
                loaded = reopened.load_all_question_coverages(REPO, None, ())
                self.assertEqual(loaded, (coverage,))
            finally:
                reopened.close()

            second = migrate_store(path)
            self.assertFalse(second["migrated"])
            self.assertEqual(second["rewritten_question_coverages"], 0)


if __name__ == "__main__":
    unittest.main()
