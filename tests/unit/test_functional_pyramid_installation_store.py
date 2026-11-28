"""Installation-scoped Functional Pyramid persistence tests (T07)."""

import datetime
import json
import pathlib
import tempfile
import threading
import unittest

from span.core import model as m
from span.shell.install.recovery import create_backup, restore_backup, verify_backup
from span.shell.install.repository_backup import create_repository_backup
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.readiness import probe_functional_pyramid_installation_store
from span.shell.sqlite_store.functional_pyramid import (
    INSTALLATION_SCHEMA_VERSION,
    FunctionalPyramidInstallationSchemaError,
    FunctionalPyramidInstallationStore,
    FunctionalPyramidInstallationStoreError,
    _decode_member,
    ensure_functional_pyramid_installation_store,
    functional_pyramid_installation_path,
)
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 11, 21, 12, 0, tzinfo=datetime.timezone.utc)


class FunctionalPyramidInstallationStoreTest(unittest.TestCase):
    def test_legacy_member_row_projects_only_version2_membership_identity(self) -> None:
        payload = json.dumps(
            {
                "$type": "FunctionalPyramidMemberView",
                "repository_id": "repo",
                "declaration_refs": [
                    {
                        "$type": "EvidenceRef",
                        "evidence_id": {
                            "$type": "EvidenceId",
                            "value": "decl-legacy",
                        },
                        "repository_id": "repo",
                        "source_kind": "CONFIGURATION",
                        "locator": ".span/functional-pyramid.json",
                        "revision_or_fingerprint": "legacy-digest",
                        "section_or_span": None,
                    }
                ],
                "functional_scope": {
                    "$type": "FunctionalScope",
                    "selectors": [
                        {
                            "$type": "FunctionalScopeSelector",
                            "kind": "REPOSITORY",
                            "path": None,
                            "locator": None,
                        }
                    ],
                },
                "coverage": "PARTIAL",
            }
        )

        member = _decode_member(payload)

        self.assertEqual(member.repository_id, "repo")
        self.assertEqual(
            tuple(ref.locator for ref in member.declaration_refs),
            (".span/functional-pyramid.json",),
        )
        self.assertFalse(hasattr(member, "functional_scope"))
        self.assertFalse(hasattr(member, "coverage"))

    def test_runtime_open_does_not_create_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = functional_pyramid_installation_path(tmp)
            with self.assertRaises(FunctionalPyramidInstallationSchemaError):
                FunctionalPyramidInstallationStore(
                    path,
                    retention=DEFAULT_LIFECYCLE_RETENTION,
                )
            self.assertFalse(path.exists())

    def test_explicit_setup_creates_only_installation_owned_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ensure_functional_pyramid_installation_store(
                tmp,
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            self.addCleanup(store.close)
            self.assertEqual(store.schema_version(), INSTALLATION_SCHEMA_VERSION)
            tables = {
                row["name"]
                for row in store._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                    " AND name NOT LIKE 'sqlite_%'"
                )
            }
            self.assertEqual(
                tables,
                {
                    "meta",
                    "functional_pyramid_versions",
                    "functional_pyramids",
                    "functional_pyramid_active_members",
                    "functional_pyramid_exclusions",
                    "functional_pyramid_receipts",
                    "delivery_selections",
                    "delivery_cursors",
                    "addressed_requests",
                },
            )
            readiness = probe_functional_pyramid_installation_store(tmp)
            self.assertTrue(readiness["ready"])
            self.assertEqual(readiness["schema_version"], 2)

    def test_bound_delivery_cursor_survives_reopen_and_reuses_position(self) -> None:
        selection = m.DeliverySelection(
            selection_id="selection",
            created_at=NOW,
            expires_at=NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime,
            state_fingerprint=m.ContentDigest("digest"),
            binding=m.DirectoryReadBinding(
                selector=m.FunctionalPyramidDirectorySelector("repo", "."),
                owner_repository_id="repo",
                placements=(),
                unresolved_count=3,
            ),
        )
        position = m.DeliveryPosition(
            m.DeliveryCollection.UNRESOLVED, 1, selection.state_fingerprint
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = functional_pyramid_installation_path(tmp)
            store = FunctionalPyramidInstallationStore.create(
                path, retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                with store.transaction() as transaction:
                    transaction.write_delivery_selection(selection)
                    self.assertEqual(
                        transaction.issue_delivery_cursor(
                            "selection", position, "cur-1"
                        ),
                        "cur-1",
                    )
            finally:
                store.close()
            store = FunctionalPyramidInstallationStore(
                path, retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                self.assertEqual(
                    store.load_delivery_cursor("cur-1"), (selection, position)
                )
                self.assertIsNone(store.load_delivery_cursor("cur-unknown"))
                with store.transaction() as transaction:
                    self.assertEqual(
                        transaction.issue_delivery_cursor(
                            "selection", position, "cur-2"
                        ),
                        "cur-1",
                    )
            finally:
                store.close()

    def test_installation_receipt_retention_is_not_repository_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(tmp),
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(store.close)
            expired = NOW - datetime.timedelta(seconds=1)
            store._connection.execute(
                "INSERT INTO functional_pyramid_receipts("
                "request_id, content_digest, committed_at, replay_expires_at,"
                " action, pyramid_id, version, members_json,"
                " participation_effects_json, dependent_effect_refs_json"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "req-1",
                    "digest",
                    NOW.isoformat(),
                    expired.isoformat(),
                    "exclude",
                    None,
                    None,
                    "[]",
                    "[]",
                    "[]",
                ),
            )
            store._connection.commit()
            self.assertEqual(store.reap_expired(NOW), 1)
            self.assertEqual(
                store._connection.execute(
                    "SELECT COUNT(*) FROM functional_pyramid_receipts"
                ).fetchone()[0],
                0,
            )

    def test_full_backup_and_restore_carry_installation_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            source = base / "source"
            source.mkdir()
            installation = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(source),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            installation.close()

            backup_root = base / "backups"
            artifact = pathlib.Path(
                create_backup(source, backup_root=backup_root, label="fp-state")
            )
            self.assertTrue(
                (artifact / "installation" / "functional-pyramid.db").is_file()
            )
            manifest = json.loads((artifact / "manifest.json").read_text())
            paths = {item["path"] for item in manifest["artifacts"]}
            self.assertIn("installation/functional-pyramid.db", paths)
            report = verify_backup(artifact)
            self.assertTrue(report.ok, report.failures)

            target = base / "target"
            target.mkdir()
            restored = restore_backup(
                artifact,
                target,
                confirm=artifact.name,
                backup_root=base / "pre-restore",
            )
            self.assertIn(
                str(target / "installation" / "functional-pyramid.db"),
                restored.restored,
            )
            reopened = FunctionalPyramidInstallationStore(
                functional_pyramid_installation_path(target),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            reopened.close()

    def test_attached_transaction_rolls_back_state_context_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            root.mkdir()
            repository_path = base / "repo.db"
            repository = LifecycleStore(
                repository_path,
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(repository.close)
            repository.register_repository("repo", str(root))

            installation = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(base),
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(installation.close)

            pyramid_id = m.FunctionalPyramidId("fp-rollback")
            version = m.FunctionalPyramidVersion(1)
            member = m.FunctionalPyramidMemberView(
                repository_id="repo",
                declaration_refs=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("decl-fp-rollback"),
                        repository_id="repo",
                        source_kind=m.EvidenceSourceKind.CONFIGURATION,
                        locator=".span/functional-pyramid.json",
                        revision_or_fingerprint="sha256:decl-fp-rollback",
                    ),
                ),
            )
            context = m.InvestigationContext(
                context_id=m.InvestigationContextId("ctx-fp-rollback"),
                repository_id="repo",
                request_id=m.RequestId("effects:ctx-fp-rollback"),
                binding_digest=m.ContentDigest("digest-context"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(paths=("src/a.py",)),
                created_at=NOW,
                expires_at=NOW + datetime.timedelta(hours=1),
            )
            receipt = m.FunctionalPyramidReceipt(
                request_id=m.RequestId("fp-write"),
                content_digest=m.ContentDigest("digest-write"),
                committed_at=NOW,
                action=m.FunctionalPyramidAction.ACTIVATE,
                pyramid_id=pyramid_id,
                version=version,
                members=(member,),
                participation_effects=(
                    m.FunctionalPyramidParticipationEffect(
                        repository_id="repo",
                        state=m.FunctionalPyramidParticipationState.ACTIVE,
                    ),
                ),
                dependency_effects=m.AcceptedDependencyEffects(()),
            )

            with self.assertRaisesRegex(RuntimeError, "force rollback"):
                with installation.transaction(
                    (("repo", str(repository_path)),)
                ) as transaction:
                    transaction.write_pyramid_version(
                        pyramid_id=pyramid_id,
                        version=version,
                        content_digest=m.ContentDigest("digest-write"),
                        committed_at=NOW,
                        members=(member,),
                    )
                    transaction.set_current_pyramid(
                        pyramid_id=pyramid_id,
                        version=version,
                        members=(member,),
                    )
                    transaction.write_reestablishment_context(context)
                    transaction.write_receipt(
                        receipt,
                        replay_expires_at=NOW + datetime.timedelta(hours=2),
                    )
                    raise RuntimeError("force rollback")

            self.assertIsNone(installation.active_pyramid_id("repo"))
            self.assertIsNone(installation.pyramid_version(pyramid_id))
            self.assertIsNone(installation.receipt(m.RequestId("fp-write")))
            self.assertIsNone(repository.find_context_by_id("ctx-fp-rollback"))

    def test_concurrent_overlapping_activation_serializes_to_one_active_instance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = functional_pyramid_installation_path(tmp)
            created = FunctionalPyramidInstallationStore.create(
                path,
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            created.close()
            stores = (
                FunctionalPyramidInstallationStore(
                    path,
                    retention=DEFAULT_LIFECYCLE_RETENTION,
                    clock=lambda: NOW,
                ),
                FunctionalPyramidInstallationStore(
                    path,
                    retention=DEFAULT_LIFECYCLE_RETENTION,
                    clock=lambda: NOW,
                ),
            )
            self.addCleanup(stores[0].close)
            self.addCleanup(stores[1].close)
            member = m.FunctionalPyramidMemberView(
                repository_id="repo",
                declaration_refs=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("decl-concurrent"),
                        repository_id="repo",
                        source_kind=m.EvidenceSourceKind.CONFIGURATION,
                        locator="docs/functional-pyramid.json",
                        revision_or_fingerprint="sha256:decl-concurrent",
                    ),
                ),
            )
            barrier = threading.Barrier(3)
            successes: list[str] = []
            failures: list[BaseException] = []

            def activate(
                store: FunctionalPyramidInstallationStore, pyramid_value: str
            ) -> None:
                try:
                    barrier.wait()
                    pyramid_id = m.FunctionalPyramidId(pyramid_value)
                    version = m.FunctionalPyramidVersion(1)
                    with store.transaction() as transaction:
                        transaction.write_pyramid_version(
                            pyramid_id=pyramid_id,
                            version=version,
                            content_digest=m.ContentDigest(f"digest-{pyramid_value}"),
                            committed_at=NOW,
                            members=(member,),
                        )
                        transaction.set_current_pyramid(
                            pyramid_id=pyramid_id,
                            version=version,
                            members=(member,),
                        )
                    successes.append(pyramid_value)
                except BaseException as exc:
                    failures.append(exc)

            threads = (
                threading.Thread(target=activate, args=(stores[0], "fp-a")),
                threading.Thread(target=activate, args=(stores[1], "fp-b")),
            )
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())

            self.assertEqual(len(successes), 1)
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0], FunctionalPyramidInstallationStoreError)
            active = stores[0].active_pyramid_id("repo")
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.value, successes[0])
            self.assertEqual(
                stores[0]
                ._connection.execute("SELECT COUNT(*) FROM functional_pyramids")
                .fetchone()[0],
                1,
            )

    def test_repository_portable_backup_excludes_installation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "repo"
            root.mkdir()
            data = base / "data"
            data.mkdir()

            repository = LifecycleStore(
                data / "repo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            repository.register_repository("repo", str(root))
            repository.close()

            installation = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(data),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            installation.close()

            artifact = pathlib.Path(create_repository_backup(root, data))
            self.assertTrue((artifact / "repo.db").is_file())
            self.assertFalse((artifact / "installation").exists())
            manifest = json.loads((artifact / "manifest.json").read_text())
            self.assertEqual(manifest["artifact"]["path"], "repo.db")


if __name__ == "__main__":
    unittest.main()
