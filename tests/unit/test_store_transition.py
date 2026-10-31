"""Offline transition gate (G-6): lossless archive/export and recovery.

Every fixture is created inside a temporary directory. No live Span store is
opened, migrated or reaped by this module.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.shell import store_transition as st

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)

LEGACY_DDL = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE repositories(
  repository_id TEXT PRIMARY KEY,
  revision_id TEXT,
  dirty INTEGER NOT NULL,
  state_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  authority_seeds_json TEXT NOT NULL
);
CREATE TABLE subjects(
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, locator, kind)
);
CREATE TABLE claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE question_coverages(
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
    repository_id, scope_root_locator, scope_root_kind, subject_locator,
    subject_kind, question_class, question_slice
  )
);
CREATE TABLE target_associations(
  repository_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  last_touched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, target_id)
);
CREATE TABLE experimental_notes(
  note_id INTEGER PRIMARY KEY,
  body TEXT,
  payload BLOB,
  score REAL,
  missing TEXT
);
"""


def _seed() -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId("ev-rule"),
        repository_id="demo",
        source_kind=m.EvidenceSourceKind.DOCUMENTATION,
        locator="docs/rule.md",
        revision_or_fingerprint="sha256:rule",
    )


def _legacy_store(
    path: pathlib.Path,
    *,
    version: int = 9,
    seeds: tuple[m.EvidenceRef, ...] = (),
    with_seed_column: bool = True,
) -> pathlib.Path:
    connection = sqlite3.connect(path)
    try:
        if with_seed_column:
            connection.executescript(LEGACY_DDL)
        else:
            connection.executescript(
                LEGACY_DDL.replace(",\n  authority_seeds_json TEXT NOT NULL", "")
            )
        connection.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
            (str(version),),
        )
        if with_seed_column:
            connection.execute(
                "INSERT INTO repositories VALUES(?,?,?,?,?,?)",
                (
                    "demo",
                    "rev-1",
                    0,
                    "fp-1",
                    "2026-10-30T00:00:00+00:00",
                    json.dumps(
                        [m.to_canonical(item) for item in seeds], sort_keys=True
                    ),
                ),
            )
        else:
            connection.execute(
                "INSERT INTO repositories VALUES(?,?,?,?,?)",
                (
                    "demo",
                    "rev-1",
                    0,
                    "fp-1",
                    "2026-10-30T00:00:00+00:00",
                ),
            )
        connection.execute(
            "INSERT INTO subjects VALUES(?,?,?,?)",
            ("demo", "src/app.py", "COMPONENT", '{"subject":"src/app.py"}'),
        )
        connection.execute(
            "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
            (
                "claim-1",
                "demo",
                "src/app.py",
                "COMPONENT",
                "PURPOSE",
                "ACCEPTED",
                "CURRENT",
                '{"statement":"The app has an entry point."}',
            ),
        )
        connection.execute(
            "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
            (
                "claim-orphan",
                "demo",
                "",
                "",
                "RESPONSIBILITY",
                "ACCEPTED",
                "CURRENT",
                '{"statement":"Unassociated legacy fact."}',
            ),
        )
        connection.execute(
            "INSERT INTO question_coverages VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "demo",
                "src",
                "COMPONENT",
                "src/app.py",
                "COMPONENT",
                "PURPOSE",
                "slice",
                "ANSWERED",
                "2026-10-30T00:00:00+00:00",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO target_associations VALUES(?,?,?,?,?)",
            (
                "demo",
                "tgt-1",
                "2026-10-30T00:00:00+00:00",
                "2027-01-01T00:00:00+00:00",
                '{"progress":"partial"}',
            ),
        )
        connection.execute(
            "INSERT INTO experimental_notes VALUES(?,?,?,?,?)",
            (1, "text", b"\x00\x01\xfe\xff", float("inf"), None),
        )
        connection.execute(
            "INSERT INTO experimental_notes VALUES(?,?,?,?,?)",
            (2, None, None, 1.5, "present"),
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _config(
    root: pathlib.Path,
    data: pathlib.Path,
    *,
    free_bytes=None,
) -> st.TransitionConfig:
    kwargs = {"clock": lambda: NOW}
    if free_bytes is not None:
        kwargs["free_bytes"] = free_bytes
    return st.TransitionConfig(
        data_dir=data,
        repository_id="demo",
        root=str(root),
        **kwargs,
    )


def _export_tables(path: pathlib.Path) -> dict[str, list[dict[str, object]]]:
    tables: dict[str, list[dict[str, object]]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if "table" in payload and "columns" in payload:
            current = payload["table"]
            tables[current] = []
        elif "rows" in payload:
            assert payload["table"] == current
        elif current is not None:
            tables[current].append(payload)
    return tables


class InspectTest(unittest.TestCase):
    def test_inspect_is_read_only_and_reports_unknown_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            inspection = st.inspect_store(_config(root, data))
            self.assertEqual(inspection.schema_version, 9)
            self.assertEqual(inspection.integrity, "ok")
            self.assertEqual(inspection.unknown_tables, ("experimental_notes",))
            self.assertIn(
                "unknown tables preserved and exported: experimental_notes",
                inspection.limitations,
            )
            self.assertFalse((data / "transitions").exists())
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(before, after)

    def test_inspect_missing_store_reports_setup_not_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            inspection = st.inspect_store(_config(root, data))
            self.assertFalse(inspection.exists)
            self.assertEqual(inspection.required_free_bytes, 0)
            self.assertIn("explicit initialize_repository", inspection.limitations[0])


class ApplyTest(unittest.TestCase):
    def _apply(
        self, tmp: str
    ) -> tuple[pathlib.Path, pathlib.Path, st.TransitionReport]:
        root = pathlib.Path(tmp) / "demo"
        root.mkdir()
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        _legacy_store(data / "demo.db", seeds=(_seed(),))
        report = st.apply(_config(root, data))
        return root, data, report

    def test_apply_archives_stages_and_activates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data, report = self._apply(tmp)
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            self.assertTrue(report.changed)
            active = data / "demo.db"
            connection = sqlite3.connect(active)
            try:
                version = connection.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()[0]
                self.assertEqual(version, "10")
                root_row = connection.execute(
                    "SELECT root FROM repositories WHERE repository_id='demo'"
                ).fetchone()[0]
                self.assertEqual(root_row, str(root.resolve()))
                seeds = json.loads(
                    connection.execute(
                        "SELECT authority_seeds_json FROM repositories"
                        " WHERE repository_id='demo'"
                    ).fetchone()[0]
                )
                self.assertEqual(seeds, [m.to_canonical(_seed())])
                for table in (
                    "understandings",
                    "conclusions",
                    "challenges",
                    "verification_runs",
                    "record_receipts",
                ):
                    self.assertEqual(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                            0
                        ],
                        0,
                    )
            finally:
                connection.close()
            paths = st.TransitionPaths(data, "demo")
            self.assertTrue(paths.archive.is_file())
            self.assertTrue(paths.export.is_file())
            self.assertTrue(paths.export_report.is_file())
            report_text = paths.report.read_text(encoding="utf-8")
            self.assertIn("raw historical export", report_text)
            self.assertIn("does not create an", report_text)
            self.assertIn("claim-orphan", report_text)
            self.assertIn("tgt-1", report_text)

    def test_export_preserves_cell_types_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, data, _ = self._apply(tmp)
            paths = st.TransitionPaths(data, "demo")
            tables = _export_tables(paths.export)
            notes = tables["experimental_notes"]
            self.assertEqual(
                notes[0],
                [
                    1,
                    "text",
                    {"$span.blob": base64.b64encode(b"\x00\x01\xfe\xff").decode()},
                    {"$span.real": "inf"},
                    None,
                ],
            )
            self.assertEqual(notes[1], [2, None, None, 1.5, "present"])
            self.assertIn("claim-orphan", json.dumps(tables["claims"]))

    def test_schema_seven_and_eight_are_lossless_without_seed_column(self):
        for version in (7, 8):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as tmp:
                    root = pathlib.Path(tmp) / "demo"
                    root.mkdir()
                    data = pathlib.Path(tmp) / "data"
                    data.mkdir()
                    _legacy_store(
                        data / "demo.db",
                        version=version,
                        with_seed_column=False,
                    )
                    report = st.apply(_config(root, data))
                    self.assertEqual(report.state, st.TransitionState.VERIFIED)
                    self.assertTrue(
                        any(
                            "no authority_seeds_json" in item
                            for item in report.limitations
                        )
                    )
                    paths = st.TransitionPaths(data, "demo")
                    self.assertEqual(st._reconcile_export(paths)[0].name, "claims")

    def test_export_has_no_legacy_decoder_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            code = f"""
import pathlib, sys
from span.shell import store_transition as st
config = st.TransitionConfig(
    data_dir=pathlib.Path({str(data)!r}),
    repository_id='demo',
    root={str(root)!r},
)
st.inspect_store(config)
paths = st.TransitionPaths(config.data_dir, 'demo')
paths.transition_dir.mkdir(parents=True, exist_ok=True)
with st._exclusive_source(paths.active) as source:
    st._archive(paths, config, source)
st._export(paths)
forbidden = [
    name for name in sys.modules
    if name in {{
        'span.shell.sqlite_store.mapping',
        'span.shell.sqlite_store.schema',
        'span.shell.sqlite_store.store',
        'span.shell.sqlite_store.migrations',
    }}
]
print(','.join(sorted(forbidden)))
"""
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                env={
                    "PYTHONPATH": str(
                        pathlib.Path(__file__).resolve().parents[2] / "src"
                    ),
                    "PATH": "/usr/bin:/bin",
                },
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "")


class RefusalTest(unittest.TestCase):
    def test_unsupported_source_schema_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _legacy_store(data / "demo.db", version=6)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(
                st.TransitionError, "unsupported source schema 6"
            ):
                st.apply(_config(root, data))
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_occupied_store_refuses_without_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            holder = sqlite3.connect(data / "demo.db")
            try:
                holder.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(
                    st.TransitionError, "held by a live process"
                ):
                    st.apply(_config(root, data))
            finally:
                holder.rollback()
                holder.close()
            manifest = st._read_manifest(st.TransitionPaths(data, "demo"))
            self.assertIsNone(manifest)
            self.assertEqual(st._read_schema_version_ro(data / "demo.db"), 9)

    def test_wrong_root_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "different-name"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            with self.assertRaisesRegex(st.TransitionError, "derives repository id"):
                st.apply(_config(root, data))

    def test_missing_root_refuses_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            config = st.TransitionConfig(
                data_dir=data, repository_id="demo", clock=lambda: NOW
            )
            with self.assertRaisesRegex(st.TransitionError, "transition-root"):
                st.apply(config)

    def test_low_space_refuses_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            with self.assertRaisesRegex(st.TransitionError, "insufficient free space"):
                st.apply(_config(root, data, free_bytes=lambda _path: 0))
            self.assertFalse((data / "transitions" / "demo" / "archive.db").exists())

    def test_already_current_apply_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            st.apply(_config(root, data))
            with self.assertRaisesRegex(st.TransitionError, "already schema 10"):
                st.apply(_config(root, data))
            inspection, _, state = st.inspect_store_report(_config(root, data))
            self.assertEqual(state, st.TransitionState.ALREADY_CURRENT)


class RecoveryTest(unittest.TestCase):
    def _fixture(self, tmp: str) -> tuple[pathlib.Path, pathlib.Path]:
        root = pathlib.Path(tmp) / "demo"
        root.mkdir()
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        _legacy_store(data / "demo.db", seeds=(_seed(),))
        return root, data

    def test_interruption_after_archive_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_export", stop):
                with self.assertRaisesRegex(
                    st.TransitionError, "simulated interruption"
                ):
                    st.apply(_config(root, data))
            manifest = st._read_manifest(st.TransitionPaths(data, "demo"))
            self.assertEqual(manifest.state, st.TransitionState.ARCHIVED)
            self.assertTrue((data / "transitions" / "demo" / "archive.db").is_file())
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)

    def test_interruption_after_export_resumes_without_rearchiving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_stage", stop):
                with self.assertRaises(st.TransitionError):
                    st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            manifest = st._read_manifest(paths)
            self.assertEqual(manifest.state, st.TransitionState.STAGED)
            archive_hash = hashlib.sha256(paths.archive.read_bytes()).hexdigest()
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            self.assertEqual(
                archive_hash, hashlib.sha256(paths.archive.read_bytes()).hexdigest()
            )

    def test_rollback_before_activation_discards_owned_staging_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_stage", stop):
                with self.assertRaises(st.TransitionError):
                    st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            paths.staging.write_bytes(b"owned staging")
            report = st.rollback(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.ROLLED_BACK)
            self.assertFalse(paths.staging.exists())
            self.assertTrue(paths.archive.is_file())
            self.assertTrue(paths.export.is_file())
            self.assertEqual(st._read_schema_version_ro(paths.active), 9)

    def test_rollback_after_activation_preserves_new_format_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            connection = sqlite3.connect(paths.active)
            try:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('new-write', 'kept')"
                )
                connection.commit()
            finally:
                connection.close()
            report = st.rollback(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.ROLLED_BACK)
            self.assertEqual(st._read_schema_version_ro(paths.active), 9)
            preserved = list(paths.transition_dir.glob("new-format-*.db"))
            self.assertEqual(len(preserved), 1)
            connection = sqlite3.connect(preserved[0])
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='new-write'"
                    ).fetchone()[0],
                    "kept",
                )
            finally:
                connection.close()

    def test_corrupt_archive_fails_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            paths.archive.write_bytes(b"not a database")
            with self.assertRaises(st.TransitionError):
                st.verify(_config(root, data))

    def test_verify_is_observational(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            active = data / "demo.db"
            before = hashlib.sha256(active.read_bytes()).hexdigest()
            report = st.verify(_config(root, data))
            self.assertFalse(report.changed)
            self.assertEqual(before, hashlib.sha256(active.read_bytes()).hexdigest())


class DispatchTest(unittest.TestCase):
    def test_parse_phase_rejects_unknown(self):
        with self.assertRaisesRegex(st.TransitionError, "unknown transition phase"):
            st.parse_phase("migrate")

    def test_report_payload_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            report = st.dispatch(_config(root, data), st.TransitionPhase.INSPECT)
            payload = st.report_payload(report)
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(payload["inspection"]["schema_version"], 9)
            json.dumps(payload)


class InstallerCommandTest(unittest.TestCase):
    def test_migrate_store_rejects_with_replacement_guidance(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--migrate-store", "demo", "--data-dir", str(data)])
            message = str(raised.exception)
            self.assertIn("--migrate-store was removed", message)
            self.assertIn("--transition-phase inspect", message)
            self.assertEqual(list(data.iterdir()), [])

    def test_transition_phase_requires_store(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--transition-phase", "inspect", "--data-dir", str(data)])
            self.assertIn("require --transition-store", str(raised.exception))

    def test_transition_store_requires_phase(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--transition-store", "demo", "--data-dir", str(data)])
            self.assertIn("requires --transition-phase", str(raised.exception))

    def test_apply_dry_run_changes_nothing(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            import contextlib
            import io

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install.main(
                    [
                        "--transition-store",
                        "demo",
                        "--transition-phase",
                        "apply",
                        "--transition-root",
                        str(root),
                        "--data-dir",
                        str(data),
                        "--dry-run",
                    ]
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(
                before, hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            )
            self.assertFalse((data / "transitions").exists())

    def test_inspect_command_prints_report_and_changes_nothing(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            import contextlib
            import io

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install.main(
                    [
                        "--transition-store",
                        "demo",
                        "--transition-phase",
                        "inspect",
                        "--data-dir",
                        str(data),
                    ]
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(payload["inspection"]["schema_version"], 9)
            self.assertEqual(
                before, hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            )
            self.assertFalse((data / "transitions").exists())


if __name__ == "__main__":
    unittest.main()
