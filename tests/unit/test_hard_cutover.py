"""Zero-legacy hard-cutover gates (HC-01..HC-10, AP-01..AP-10).

These gates pin the current runtime contract only: schema 7 is the sole
supported store schema, no runtime migration or legacy decode path
exists, current task coverage always carries a non-empty discovery
scope, and configured authority seeds persist and rehydrate after a
process restart.
"""

import datetime
import json
import pathlib
import sqlite3
import tempfile
import unittest

from span import service as ops
from span.core import model as m
from span.service.discovery import _coverage_for_task
from span.shell import install
from span.shell.context import open_repository_context
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp_server import ServerConfig, provision_repository
from span.shell.sqlite_store import SCHEMA_VERSION, SqliteSemanticStore
from span.shell.structural import structural_source_from_config
from span.shell.structural.graft import GraftStructuralSource
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

_REPO = "hard-cutover-repo"
_FILES = {"src/a.py": "VALUE = 1\n", "README.md": "# hard cutover\n"}


def _bounds() -> m.QueryBounds:
    return m.QueryBounds(
        max_results=50,
        max_depth=5,
        max_subjects=8,
        max_evidence_units=24,
        max_evidence_bytes=96_000,
        max_candidate_claims=64,
        max_candidate_relationships=64,
    )


def _sid(locator: str = "src/a.py") -> m.SubjectId:
    return m.SubjectId(
        repository_id=_REPO,
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator=locator,
    )


def _seed(locator: str = "README.md") -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{locator}"),
        repository_id=_REPO,
        source_kind=m.EvidenceSourceKind.DOCUMENTATION,
        locator=locator,
        revision_or_fingerprint=fingerprint_content(_FILES[locator]),
    )


def _state(repository_id: str = _REPO) -> m.RepositoryState:
    return m.RepositoryState(
        repository_id=repository_id,
        revision_id="rev-1",
        dirty=False,
        state_fingerprint="fp-1",
        observed_at=datetime.datetime(
            2026, 10, 23, tzinfo=datetime.timezone.utc
        ),
    )


def _sources() -> tuple[InMemoryStructuralSource, FixtureEvidenceSource]:
    structural = InMemoryStructuralSource(
        _REPO,
        tuple(InMemoryFile(path, body) for path, body in _FILES.items()),
        (InMemorySubject("src/a.py", m.SubjectKind.COMPONENT, "a"),),
        (),
    )
    return structural, FixtureEvidenceSource(_REPO, dict(_FILES))


def _initialize(
    store: SqliteSemanticStore,
    seeds: tuple[m.EvidenceRef, ...] | None,
) -> ops.SemanticInitializeRepositoryResult:
    structural, evidence = _sources()
    return ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            authority_seeds=seeds,
        ),
        repository_id=_REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )


class HC01SchemaVersionTest(unittest.TestCase):
    def test_only_schema_seven_is_supported(self):
        self.assertEqual(SCHEMA_VERSION, 7)


class HC02FreshStoreTest(unittest.TestCase):
    def test_fresh_store_creates_schema_seven(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSemanticStore(
                str(pathlib.Path(tmp) / "fresh.db")
            )
            try:
                self.assertEqual(store.schema_version(), m.SchemaVersion(7))
                columns = {
                    row[1]
                    for row in store._db.execute(
                        "PRAGMA table_info(repositories)"
                    ).fetchall()
                }
                self.assertIn("authority_seeds_json", columns)
            finally:
                store.close()


class HC03CurrentStoreTest(unittest.TestCase):
    def test_existing_schema_seven_opens_normally(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "current.db")
            first = SqliteSemanticStore(path)
            try:
                first.record_repository_initialization(
                    _state(), (_seed(),)
                )
            finally:
                first.close()
            second = SqliteSemanticStore(path)
            try:
                self.assertEqual(
                    second.schema_version(), m.SchemaVersion(7)
                )
                self.assertEqual(
                    second.load_repository_authority_seeds(_REPO),
                    (_seed(),),
                )
            finally:
                second.close()


class HC04VersionedStoreRejectedTest(unittest.TestCase):
    def test_older_versioned_store_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "old.db"
            con = sqlite3.connect(path)
            try:
                con.executescript(
                    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"
                    "INSERT INTO meta VALUES('schema_version', '6');"
                    "CREATE TABLE claims(claim_id TEXT PRIMARY KEY);"
                )
                con.commit()
            finally:
                con.close()
            with self.assertRaisesRegex(
                ValueError,
                "unsupported Span store schema version 6; migrate this "
                "store to schema 7 before using this Span build",
            ):
                SqliteSemanticStore(str(path))
            # Rejection never mutates the store.
            con = sqlite3.connect(path)
            try:
                row = con.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
                self.assertEqual(row[0], "6")
            finally:
                con.close()


class HC05UnversionedStoreRejectedTest(unittest.TestCase):
    def test_non_empty_unversioned_store_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "unversioned.db"
            con = sqlite3.connect(path)
            try:
                con.execute("CREATE TABLE claims(claim_id TEXT PRIMARY KEY)")
                con.commit()
            finally:
                con.close()
            with self.assertRaisesRegex(
                ValueError,
                "unsupported Span store schema version 0",
            ):
                SqliteSemanticStore(str(path))


class HC06AssertionNatureTest(unittest.TestCase):
    def test_nature_vocabulary_is_exact(self):
        self.assertEqual(
            {nature.value for nature in m.AssertionNature},
            {"DESCRIPTIVE", "NORMATIVE"},
        )

    def test_removed_nature_cannot_enter_ingress(self):
        payload = {
            "$type": "CandidateSemanticClaim",
            "candidate_key": "k",
            "subject": m.to_canonical(_sid()),
            "kind": "PURPOSE",
            "value": {
                "$type": "PurposeValue",
                "summary": "s",
                "capability_refs": [],
            },
            "assertion_nature": "LEGACY_UNCLASSIFIED",
            "evidence": [],
            "candidate_authority": None,
            "basis": {
                "$type": "SemanticBasis",
                "derivation": "SEMANTIC_INTERPRETATION",
            },
        }
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.CandidateSemanticClaim, payload)


class HC07UncoveredAssertionsInvariantTest(unittest.TestCase):
    def test_stored_assertions_without_coverage_fail_explain(self):
        structural, evidence = _sources()
        store = SqliteSemanticStore(":memory:")
        try:
            sid = _sid()
            store.record_repository_initialization(_state(), ())
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("claim-uncovered"),
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("does a thing", ()),
                basis=m.SemanticBasis(
                    m.DerivationKind.EXPLICIT_EVIDENCE, "b"
                ),
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "a", None),),
                    claims=(claim,),
                )
            )
            self.assertEqual(
                store.load_question_coverages(
                    _REPO, sid, (sid,), _bounds()
                ),
                (),
            )
            with self.assertRaisesRegex(
                RuntimeError, "semantic store invariant violation"
            ):
                from span.service.operations.explain import (
                    _compose_explain_answer,
                )

                _compose_explain_answer(
                    _REPO,
                    m.Subject(sid, "a", None),
                    None,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    bounds=_bounds(),
                    state=_state(),
                )
        finally:
            store.close()


class HC08EmptyDiscoveryScopeTest(unittest.TestCase):
    def test_task_coverage_rejects_empty_scope(self):
        _, evidence = _sources()
        with self.assertRaisesRegex(
            ValueError, "task discovery scope must be non-empty"
        ):
            _coverage_for_task(
                _REPO,
                (_sid(),),
                evidence=evidence,
                seeds=(),
                discovery_scope=m.EvidenceScope(),
            )


class HC09StructuralConstructionTest(unittest.TestCase):
    def test_file_backed_source_requires_artifact_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                ValueError, "requires artifact_dir"
            ):
                GraftStructuralSource(_REPO, tmp)

    def test_factory_requires_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError):
                structural_source_from_config(tmp)  # type: ignore[call-arg]


class HC10InstallerCutoverTest(unittest.TestCase):
    def test_flat_registration_is_rejected_not_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            original = {
                "mcp": {
                    "span": {
                        "type": "local",
                        "command": ["old"],
                    }
                }
            }
            config_path.write_text(json.dumps(original))
            with self.assertRaises(SystemExit):
                install.merge_opencode_config(
                    str(config_path), ["span-mcp"], dry_run=False
                )
            self.assertEqual(
                json.loads(config_path.read_text()), original
            )
            inspected = install.inspect_opencode_registration(
                str(config_path), ["span-mcp"]
            )
            self.assertEqual(inspected["status"], "mismatched")
            self.assertIn("unsupported flat mcp.span", inspected["reason"])

    def test_no_agents_flag_is_removed(self):
        with self.assertRaises(SystemExit):
            install.parse_args(["--no-agents"])


class AP01SeedPersistenceTest(unittest.TestCase):
    def test_initialization_persists_seeds(self):
        store = SqliteSemanticStore(":memory:")
        try:
            seeds = (_seed(),)
            _initialize(store, seeds)
            self.assertEqual(
                store.load_repository_authority_seeds(_REPO), seeds
            )
        finally:
            store.close()


class AP02RestartRehydrationTest(unittest.TestCase):
    def test_context_rehydrates_seeds_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / _REPO
            repo.mkdir()
            data_dir = root / "data"
            data_dir.mkdir()
            seeds = (_seed(),)
            store = SqliteSemanticStore(
                str(data_dir / f"{_REPO}.db")
            )
            try:
                store.record_repository_initialization(_state(), seeds)
            finally:
                store.close()
            # A new process opens the existing store through the shared
            # context opener; no setup call is made.
            repository_id, context = open_repository_context(
                data_dir, str(repo)
            )
            try:
                self.assertEqual(repository_id, _REPO)
                self.assertEqual(context.authority_seeds, seeds)
            finally:
                context.store.close()


class AP03OmittedSeedsPreserveTest(unittest.TestCase):
    def test_omitted_seeds_preserve_configured_seeds(self):
        store = SqliteSemanticStore(":memory:")
        try:
            seeds = (_seed(),)
            _initialize(store, seeds)
            _initialize(store, None)
            self.assertEqual(
                store.load_repository_authority_seeds(_REPO), seeds
            )
        finally:
            store.close()


class AP04ExplicitEmptyClearsTest(unittest.TestCase):
    def test_explicit_empty_tuple_clears_seeds(self):
        store = SqliteSemanticStore(":memory:")
        try:
            _initialize(store, (_seed(),))
            _initialize(store, ())
            self.assertEqual(
                store.load_repository_authority_seeds(_REPO), ()
            )
        finally:
            store.close()


class AP05NonEmptyReplacesTest(unittest.TestCase):
    def test_non_empty_tuple_replaces_seeds(self):
        store = SqliteSemanticStore(":memory:")
        try:
            _initialize(store, (_seed("README.md"),))
            replacement = (
                _seed("README.md"),
                _seed("src/a.py"),
            )
            _initialize(store, replacement)
            self.assertEqual(
                store.load_repository_authority_seeds(_REPO), replacement
            )
        finally:
            store.close()


class AP06AbsentRowTest(unittest.TestCase):
    def test_uninitialized_repository_has_no_seeds(self):
        store = SqliteSemanticStore(":memory:")
        try:
            self.assertEqual(
                store.load_repository_authority_seeds("never-seen"), ()
            )
        finally:
            store.close()


class AP07MalformedSeedsFailClosedTest(unittest.TestCase):
    def test_malformed_configured_seeds_never_fall_back_to_empty(self):
        store = SqliteSemanticStore(":memory:")
        try:
            store.record_repository_initialization(_state(), ())
            store._db.execute(
                "UPDATE repositories SET authority_seeds_json=? "
                "WHERE repository_id=?",
                ("{not json", _REPO),
            )
            store._db.commit()
            with self.assertRaisesRegex(
                ValueError, "authority seeds are not canonical"
            ):
                store.load_repository_authority_seeds(_REPO)
        finally:
            store.close()

    def test_non_evidence_items_fail_closed(self):
        store = SqliteSemanticStore(":memory:")
        try:
            store.record_repository_initialization(_state(), ())
            store._db.execute(
                "UPDATE repositories SET authority_seeds_json=? "
                "WHERE repository_id=?",
                (json.dumps([{"not": "an evidence ref"}]), _REPO),
            )
            store._db.commit()
            with self.assertRaises(ValueError):
                store.load_repository_authority_seeds(_REPO)
        finally:
            store.close()

    def test_foreign_repository_seed_fails_closed(self):
        store = SqliteSemanticStore(":memory:")
        try:
            foreign = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-foreign"),
                repository_id="another-repository",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="README.md",
            )
            store.record_repository_initialization(_state(), ())
            store._db.execute(
                "UPDATE repositories SET authority_seeds_json=? "
                "WHERE repository_id=?",
                (
                    json.dumps(m.to_canonical((foreign,)), sort_keys=True),
                    _REPO,
                ),
            )
            store._db.commit()
            with self.assertRaisesRegex(
                ValueError, "seed for repository 'another-repository'"
            ):
                store.load_repository_authority_seeds(_REPO)
        finally:
            store.close()


class AP08ProvisioningResolutionTest(unittest.TestCase):
    def test_locators_resolve_only_for_explicit_non_empty_tuple(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / _REPO
            repo.mkdir()
            for path, body in _FILES.items():
                target = repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
            data_dir = root / "data"
            wiring = data_dir / "structural" / _REPO / ".graph"
            wiring.mkdir(parents=True)
            (wiring / "wiring.json").write_text(
                json.dumps({"nodes": [], "edges": []}),
                encoding="utf-8",
            )
            requested = (
                m.EvidenceRef(
                    evidence_id=m.EvidenceId("ev-README.md"),
                    repository_id=_REPO,
                    source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                    locator="README.md",
                ),
            )
            context, _ = provision_repository(
                ServerConfig(data_dir=data_dir),
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator=str(repo),
                    authority_seeds=requested,
                ),
            )
            try:
                persisted = context.authority_seeds
                self.assertEqual(
                    tuple(seed.locator for seed in persisted),
                    ("README.md",),
                )
                self.assertTrue(
                    persisted[0].revision_or_fingerprint
                )
                self.assertEqual(
                    persisted,
                    context.store.load_repository_authority_seeds(
                        _REPO
                    ),
                )
            finally:
                context.store.close()


class AP09NoPersistentStoreTest(unittest.TestCase):
    def test_no_store_yields_in_memory_uninitialized_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / _REPO
            repo.mkdir()
            data_dir = root / "data"
            repository_id, context = open_repository_context(
                data_dir, str(repo)
            )
            try:
                self.assertEqual(repository_id, _REPO)
                self.assertEqual(context.authority_seeds, ())
                self.assertIsNone(
                    context.store.load_repository_state(_REPO)
                )
                self.assertFalse(
                    (data_dir / f"{_REPO}.db").exists()
                )
            finally:
                context.store.close()


class AP10SingleAtomicWriteTest(unittest.TestCase):
    def test_initialization_writes_one_repository_row_once(self):
        store = SqliteSemanticStore(":memory:")
        try:
            calls = []
            original = store.record_repository_initialization

            def counting(state, seeds):
                calls.append((state, seeds))
                return original(state, seeds)

            store.record_repository_initialization = counting
            _initialize(store, (_seed(),))
            self.assertEqual(len(calls), 1)
            rows = store._db.execute(
                "SELECT COUNT(*) FROM repositories"
            ).fetchone()
            self.assertEqual(rows[0], 1)
        finally:
            store.close()
