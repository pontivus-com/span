"""Beta-3 regressions for the inherited repository-initialization defects.

These tests encode the Beta-3 target behavior for B3-D01/B3-D02 after Beta-1
post-release use exposed the installer and acceptance composition defects.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from span.core import model as m
from span.shell import install
from span.shell.install import cli


class Beta3InitializationRegressionTest(unittest.TestCase):
    def _evidence(self, repository_id="repo-a"):
        return m.EvidenceRef(
            evidence_id=m.EvidenceId("authority-a"),
            repository_id=repository_id,
            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
            locator="docs/authority.md",
        )

    def _binding(self, repository_id="repo-a"):
        return m.AuthorityBinding(
            evidence_ref=self._evidence(repository_id),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )

    def _write_canonical_list(self, root, name, items):
        path = pathlib.Path(root) / name
        path.write_text(
            json.dumps([m.to_canonical(item) for item in items]),
            encoding="utf-8",
        )
        return path

    def test_authority_files_require_canonical_discriminators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            cases = (
                ("seeds", self._evidence(), "EvidenceRef"),
                ("bindings", self._binding(), "AuthorityBinding"),
            )
            for name, item, expected_type in cases:
                with self.subTest(name=name):
                    payload = m.to_canonical(item)
                    payload.pop("$type")
                    path = root / f"{name}.json"
                    path.write_text(json.dumps([payload]), encoding="utf-8")
                    seed_files = [["repo-a", str(path)]] if name == "seeds" else []
                    binding_files = (
                        [["repo-a", str(path)]] if name == "bindings" else []
                    )
                    with self.assertRaises(SystemExit) as caught:
                        install.load_authority_files(
                            [repo],
                            seed_files,
                            binding_files,
                            dry_run=False,
                        )
                    message = str(caught.exception)
                    self.assertIn(f"authority {name}[0]: invalid entry", message)
                    self.assertIn(str(path), message)
                    self.assertIn("retry", message)
                    self.assertNotIn(expected_type, message)
                    self.assertNotIn("$type", message)

    def test_authority_provider_failure_keeps_public_locator_not_diagnostics(self):
        from span.shell.install.preflight import validate_authority_files

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo-a"
            repo.mkdir()
            with (
                mock.patch(
                    "span.shell.filesystem_evidence.FilesystemEvidenceSource.read_exact",
                    side_effect=OSError("PRIVATE_DIAGNOSTIC_SENTINEL"),
                ),
                self.assertRaises(SystemExit) as caught,
            ):
                validate_authority_files(
                    (repo,), {}, {"repo-a": (self._binding(),)}
                )
            message = str(caught.exception)
            self.assertIn("repo-a/docs/authority.md", message)
            self.assertIn("restore access and retry", message)
            self.assertNotIn("PRIVATE_DIAGNOSTIC_SENTINEL", message)

    def test_repository_qualified_authority_file_grammar(self):
        args = install.parse_args(
            [
                "--repo",
                "/work/repo-b",
                "--authority-seeds-file",
                "repo-b",
                "/tmp/seeds.json",
                "--authority-bindings-file",
                "repo-b",
                "/tmp/bindings.json",
                "--dry-run",
            ]
        )
        self.assertEqual(
            tuple(tuple(item) for item in args.authority_seeds_file),
            (("repo-b", "/tmp/seeds.json"),),
        )
        self.assertEqual(
            tuple(tuple(item) for item in args.authority_bindings_file),
            (("repo-b", "/tmp/bindings.json"),),
        )

    def test_authority_file_tri_state_preserve_clear_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            empty_seeds = root / "empty-seeds.json"
            empty_seeds.write_text("[]", encoding="utf-8")
            bindings = self._write_canonical_list(
                root, "bindings.json", [self._binding()]
            )

            seeds, loaded_bindings = install.load_authority_files(
                [repo], [], [], dry_run=False
            )
            self.assertEqual(seeds, {})
            self.assertEqual(loaded_bindings, {})

            seeds, loaded_bindings = install.load_authority_files(
                [repo],
                [["repo-a", str(empty_seeds)]],
                [["repo-a", str(bindings)]],
                dry_run=False,
            )
            self.assertEqual(seeds["repo-a"], ())
            self.assertEqual(
                loaded_bindings["repo-a"],
                (self._binding(),),
            )

    def test_authority_file_nonempty_seed_decodes_canonical_carrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            seeds_path = self._write_canonical_list(
                root, "seeds.json", [self._evidence()]
            )
            seeds, bindings = install.load_authority_files(
                [repo],
                [["repo-a", str(seeds_path)]],
                [],
                dry_run=False,
            )
            self.assertEqual(seeds["repo-a"], (self._evidence(),))
            self.assertEqual(bindings, {})

    def test_authority_file_duplicate_and_unselected_mappings_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            payload = root / "empty.json"
            payload.write_text("[]", encoding="utf-8")
            with self.assertRaises(SystemExit):
                install.load_authority_files(
                    [repo],
                    [
                        ["repo-a", str(payload)],
                        ["repo-a", str(payload)],
                    ],
                    [],
                    dry_run=False,
                )
            with self.assertRaises(SystemExit):
                install.load_authority_files(
                    [repo],
                    [["repo-b", str(payload)]],
                    [],
                    dry_run=False,
                )

    def test_authority_file_repository_identity_mismatch_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            seeds_path = self._write_canonical_list(
                root,
                "seeds.json",
                [self._evidence("repo-b")],
            )
            bindings_path = self._write_canonical_list(
                root,
                "bindings.json",
                [self._binding("repo-b")],
            )
            with self.assertRaises(SystemExit):
                install.load_authority_files(
                    [repo],
                    [["repo-a", str(seeds_path)]],
                    [],
                    dry_run=False,
                )
            with self.assertRaises(SystemExit):
                install.load_authority_files(
                    [repo],
                    [],
                    [["repo-a", str(bindings_path)]],
                    dry_run=False,
                )

    def test_authority_file_malformed_content_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            not_list = root / "not-list.json"
            not_list.write_text("{}", encoding="utf-8")
            malformed = root / "malformed.json"
            malformed.write_text(
                json.dumps([{"repository_id": "repo-a"}]),
                encoding="utf-8",
            )
            for path in (not_list, malformed):
                with self.subTest(path=path.name):
                    with self.assertRaises(SystemExit):
                        install.load_authority_files(
                            [repo],
                            [["repo-a", str(path)]],
                            [],
                            dry_run=False,
                        )

    def test_full_install_dispatches_canonical_repository_provisioning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            data_dir = root / "data"
            venv_dir = root / "venv"
            bin_dir = root / "bin"

            def provision(_data_dir, request):
                repository_id = pathlib.Path(request.repository_locator).name
                runtime = SimpleNamespace(
                    repository_id=repository_id,
                    root=request.repository_locator,
                    structural=None,
                    evidence=None,
                    store=mock.Mock(),
                )
                result = m.InitializeRepositoryResult(
                    repository_id=repository_id,
                    canonical_root=str(
                        pathlib.Path(request.repository_locator).resolve()
                    ),
                    schema_version=14,
                    store_ready=True,
                    structural_status="index:CURRENT",
                )
                return runtime, result

            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "target_artifact_snapshot", return_value={}),
                mock.patch.object(cli, "load_authority_files", return_value=({}, {})),
                mock.patch.object(cli, "preflight_facts", return_value={}),
                mock.patch.object(
                    cli, "ensure_venv", return_value=venv_dir / "bin" / "python"
                ),
                mock.patch.object(
                    cli,
                    "ensure_structural_indexer",
                    return_value=str(root / "graft"),
                ),
                mock.patch.object(cli, "write_indexer_pointer", return_value={}),
                mock.patch.object(cli, "install_mode", return_value="checkout"),
                mock.patch.object(
                    cli,
                    "requested_build_identity",
                    return_value={
                        "source_revision": "a" * 40,
                        "source_digest": "b" * 64,
                    },
                ),
                mock.patch.object(
                    cli,
                    "source_venv_in_sync",
                    return_value=(True, 1, ()),
                ),
                mock.patch.object(cli, "expose_binary"),
                mock.patch.object(cli, "read_receipt", return_value=None),
                mock.patch.object(cli, "_register_hosts", return_value={}),
                mock.patch.object(
                    cli,
                    "verify_installation",
                    return_value={
                        "repos": [],
                        "build_identity": {
                            "source_revision": "a" * 40,
                            "source_digest": "b" * 64,
                        },
                    },
                ),
                mock.patch.object(cli, "write_receipt"),
                mock.patch.object(cli, "git_rev", return_value="test"),
                mock.patch(
                    "span.shell.context.provision_repository_runtime",
                    side_effect=provision,
                ) as provision_repository,
                mock.patch("span.shell.context.close_repository_runtime"),
            ):
                cli.main(
                    [
                        "--repo",
                        str(repo),
                        "--data-dir",
                        str(data_dir),
                        "--venv-dir",
                        str(venv_dir),
                        "--bin-dir",
                        str(bin_dir),
                        "--span-repo",
                        str(root),
                        "--no-codex",
                        "--no-hooks",
                        "--no-skills",
                    ]
                )

            self.assertEqual(provision_repository.call_count, 1)
            request = provision_repository.call_args.args[1]
            self.assertIsInstance(request, m.InitializeRepositoryRequest)
            self.assertEqual(
                pathlib.Path(request.repository_locator).resolve(), repo.resolve()
            )
            self.assertIsNone(request.authority_seeds)
            self.assertIsNone(request.authority_bindings)

    def test_authority_validation_precedes_installer_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            malformed = root / "seeds.json"
            malformed.write_text("{}", encoding="utf-8")
            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "target_artifact_snapshot", return_value={}),
                mock.patch.object(cli, "ensure_venv") as ensure_venv,
            ):
                with self.assertRaises(SystemExit):
                    cli.main(
                        [
                            "--repo",
                            str(repo),
                            "--authority-seeds-file",
                            "repo-a",
                            str(malformed),
                            "--data-dir",
                            str(root / "data"),
                            "--venv-dir",
                            str(root / "venv"),
                            "--bin-dir",
                            str(root / "bin"),
                            "--span-repo",
                            str(root),
                            "--no-codex",
                            "--no-hooks",
                            "--no-skills",
                        ]
                    )
            ensure_venv.assert_not_called()

    def test_exact_authority_validation_preserves_large_binding_set(self):
        from span.service.administration import validate_authority_configuration
        from tests.support.evidence import FixtureEvidenceSource

        files = {f"docs/rule-{index:04}.md": "# Rule" for index in range(1101)}
        refs = tuple(
            m.EvidenceRef(
                evidence_id=m.EvidenceId(f"declared-{locator}"),
                repository_id="repo-a",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator=locator,
            )
            for locator in files
        )
        bindings = tuple(
            m.AuthorityBinding(
                ref, m.AuthorityKind.REPOSITORY_RULE, m.AuthorityStatus.ACCEPTED
            )
            for ref in refs
        )
        source = FixtureEvidenceSource("repo-a", files)
        request = m.InitializeRepositoryRequest("repo-a", refs, bindings)
        with mock.patch.object(source, "read_exact", wraps=source.read_exact) as read:
            validated = validate_authority_configuration(
                request, repository_id="repo-a", evidence=source
            )
        self.assertEqual(read.call_count, len(files))
        self.assertEqual(validated.authority_bindings, bindings)
        self.assertEqual(
            tuple(ref.locator for ref in validated.authority_seeds or ()),
            tuple(files),
        )
        self.assertTrue(
            all(ref.revision_or_fingerprint for ref in validated.authority_seeds or ())
        )

    def test_late_invalid_authority_rejected_before_pending_or_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            docs = repo / "docs"
            docs.mkdir(parents=True)
            bindings = []
            for index in range(1101):
                locator = f"docs/rule-{index:04}.md"
                if index != 1100:
                    (repo / locator).write_text("# Rule")
                bindings.append(
                    m.AuthorityBinding(
                        m.EvidenceRef(
                            m.EvidenceId(f"rule-{index}"),
                            "repo-a",
                            m.EvidenceSourceKind.DOCUMENTATION,
                            locator,
                        ),
                        m.AuthorityKind.REPOSITORY_RULE,
                        m.AuthorityStatus.ACCEPTED,
                    )
                )
            payload = self._write_canonical_list(root, "bindings.json", bindings)
            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "ensure_venv") as ensure_venv,
                mock.patch.object(cli.governed, "retain_pending") as retain,
            ):
                with self.assertRaisesRegex(SystemExit, "missing locator.*rule-1100"):
                    cli.main(
                        [
                            "--repo",
                            str(repo),
                            "--authority-bindings-file",
                            "repo-a",
                            str(payload),
                            "--data-dir",
                            str(root / "data"),
                            "--span-repo",
                            str(root),
                            "--no-hooks",
                        ]
                    )
            ensure_venv.assert_not_called()
            retain.assert_not_called()
            self.assertFalse((root / "data/install.json").exists())
            self.assertFalse((root / "data/repo-a.db").exists())
            self.assertFalse((repo / ".span").exists())

    def test_multi_repository_provisioning_preserves_tri_state_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo_a = root / "repo-a"
            repo_b = root / "repo-b"
            repo_a.mkdir()
            repo_b.mkdir()
            (repo_b / "docs").mkdir()
            (repo_b / "docs/authority.md").write_text("# Authority\n")
            empty_seeds = root / "empty-seeds.json"
            empty_seeds.write_text("[]", encoding="utf-8")
            bindings = self._write_canonical_list(
                root,
                "bindings.json",
                [self._binding("repo-b")],
            )
            data_dir = root / "data"
            venv_dir = root / "venv"
            bin_dir = root / "bin"
            events = []

            def provision(_data_dir, request):
                repository_id = pathlib.Path(request.repository_locator).name
                events.append(f"provision:{repository_id}")
                runtime = SimpleNamespace(
                    repository_id=repository_id,
                    root=request.repository_locator,
                    structural=None,
                    evidence=None,
                    store=mock.Mock(),
                )
                result = m.InitializeRepositoryResult(
                    repository_id=repository_id,
                    canonical_root=str(
                        pathlib.Path(request.repository_locator).resolve()
                    ),
                    schema_version=14,
                    store_ready=True,
                    structural_status="index:CURRENT",
                    authority_seeds=request.authority_seeds or (),
                    authority_bindings=request.authority_bindings or (),
                )
                return runtime, result

            def close(runtime):
                events.append(f"close:{runtime.repository_id}")

            def backup(_data_dir, dry_run=False):
                self.assertFalse(dry_run)
                events.append("backup")
                return str(root / "backup")

            def hosts(*_args, **_kwargs):
                events.append("hosts")
                return {}

            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "target_artifact_snapshot", return_value={}),
                mock.patch.object(cli, "preflight_facts", return_value={}),
                mock.patch.object(
                    cli, "ensure_venv", return_value=venv_dir / "bin" / "python"
                ),
                mock.patch.object(
                    cli,
                    "ensure_structural_indexer",
                    return_value=str(root / "graft"),
                ),
                mock.patch.object(cli, "write_indexer_pointer", return_value={}),
                mock.patch.object(cli, "install_mode", return_value="checkout"),
                mock.patch.object(
                    cli,
                    "requested_build_identity",
                    return_value={
                        "source_revision": "a" * 40,
                        "source_digest": "b" * 64,
                    },
                ),
                mock.patch.object(
                    cli,
                    "source_venv_in_sync",
                    return_value=(True, 1, ()),
                ),
                mock.patch.object(cli, "expose_binary"),
                mock.patch.object(cli, "backup_data_dir", side_effect=backup),
                mock.patch.object(cli, "read_receipt", return_value=None),
                mock.patch.object(cli, "_register_hosts", side_effect=hosts),
                mock.patch.object(
                    cli,
                    "verify_installation",
                    return_value={
                        "repos": [],
                        "build_identity": {
                            "source_revision": "a" * 40,
                            "source_digest": "b" * 64,
                        },
                    },
                ),
                mock.patch.object(cli, "write_receipt") as write_receipt,
                mock.patch.object(cli, "git_rev", return_value="test"),
                mock.patch(
                    "span.shell.context.provision_repository_runtime",
                    side_effect=provision,
                ) as provision_repository,
                mock.patch(
                    "span.shell.context.close_repository_runtime",
                    side_effect=close,
                ),
            ):
                cli.main(
                    [
                        "--repo",
                        str(repo_a),
                        "--repo",
                        str(repo_b),
                        "--authority-seeds-file",
                        "repo-a",
                        str(empty_seeds),
                        "--authority-bindings-file",
                        "repo-b",
                        str(bindings),
                        "--data-dir",
                        str(data_dir),
                        "--venv-dir",
                        str(venv_dir),
                        "--bin-dir",
                        str(bin_dir),
                        "--span-repo",
                        str(root),
                        "--no-codex",
                        "--no-hooks",
                        "--no-skills",
                    ]
                )

            self.assertEqual(provision_repository.call_count, 2)
            first = provision_repository.call_args_list[0].args[1]
            second = provision_repository.call_args_list[1].args[1]
            self.assertEqual(pathlib.Path(first.repository_locator), repo_a)
            self.assertEqual(first.authority_seeds, ())
            self.assertIsNone(first.authority_bindings)
            self.assertEqual(pathlib.Path(second.repository_locator), repo_b)
            self.assertIsNone(second.authority_seeds)
            self.assertEqual(
                second.authority_bindings,
                (self._binding("repo-b"),),
            )
            self.assertEqual(
                events,
                [
                    "backup",
                    "provision:repo-a",
                    "close:repo-a",
                    "provision:repo-b",
                    "close:repo-b",
                    "hosts",
                ],
            )
            receipt = write_receipt.call_args.args[1]
            self.assertEqual(
                receipt["repository_initialization"],
                [
                    {
                        "repository_id": "repo-a",
                        "canonical_root": str(repo_a.resolve()),
                        "schema_version": 14,
                        "store_ready": True,
                        "structural_status": "index:CURRENT",
                        "authority_seed_count": 0,
                        "authority_binding_count": 0,
                        "warnings": [],
                    },
                    {
                        "repository_id": "repo-b",
                        "canonical_root": str(repo_b.resolve()),
                        "schema_version": 14,
                        "store_ready": True,
                        "structural_status": "index:CURRENT",
                        "authority_seed_count": 0,
                        "authority_binding_count": 1,
                        "warnings": [],
                    },
                ],
            )
            self.assertNotIn("seeds_resolved_and_active", receipt)

    def test_repository_initialization_failure_names_repository_and_stops_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            venv_dir = root / "venv"
            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "target_artifact_snapshot", return_value={}),
                mock.patch.object(cli, "load_authority_files", return_value=({}, {})),
                mock.patch.object(cli, "preflight_facts", return_value={}),
                mock.patch.object(
                    cli, "ensure_venv", return_value=venv_dir / "bin" / "python"
                ),
                mock.patch.object(
                    cli,
                    "ensure_structural_indexer",
                    return_value=str(root / "graft"),
                ),
                mock.patch.object(cli, "write_indexer_pointer", return_value={}),
                mock.patch.object(cli, "install_mode", return_value="checkout"),
                mock.patch.object(
                    cli,
                    "requested_build_identity",
                    return_value={
                        "source_revision": "a" * 40,
                        "source_digest": "b" * 64,
                    },
                ),
                mock.patch.object(
                    cli,
                    "source_venv_in_sync",
                    return_value=(True, 1, ()),
                ),
                mock.patch.object(cli, "expose_binary"),
                mock.patch.object(cli, "backup_data_dir", return_value="/backup"),
                mock.patch.object(cli, "read_receipt", return_value=None),
                mock.patch.object(cli, "_register_hosts") as register_hosts,
                mock.patch.object(cli, "write_receipt") as write_receipt,
                mock.patch(
                    "span.shell.context.provision_repository_runtime",
                    side_effect=ValueError("binding rejected"),
                ),
            ):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(
                        [
                            "--repo",
                            str(repo),
                            "--data-dir",
                            str(root / "data"),
                            "--venv-dir",
                            str(venv_dir),
                            "--bin-dir",
                            str(root / "bin"),
                            "--span-repo",
                            str(root),
                            "--no-codex",
                            "--no-hooks",
                            "--no-skills",
                        ]
                    )
            self.assertIn("repo-a", str(raised.exception))
            register_hosts.assert_not_called()
            write_receipt.assert_not_called()

    def test_dry_run_never_dispatches_repository_initialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            with (
                mock.patch.object(cli, "check_prereqs"),
                mock.patch.object(cli, "target_artifact_snapshot", return_value={}),
                mock.patch.object(cli, "load_authority_files", return_value=({}, {})),
                mock.patch.object(cli, "preflight_facts", return_value={}),
                mock.patch.object(
                    cli,
                    "ensure_venv",
                    return_value=root / "venv" / "bin" / "python",
                ),
                mock.patch.object(
                    cli,
                    "ensure_structural_indexer",
                    return_value=str(root / "graft"),
                ),
                mock.patch.object(cli, "write_indexer_pointer", return_value={}),
                mock.patch.object(cli, "install_mode", return_value="checkout"),
                mock.patch.object(
                    cli,
                    "requested_build_identity",
                    return_value={
                        "source_revision": "a" * 40,
                        "source_digest": "b" * 64,
                    },
                ),
                mock.patch.object(
                    cli,
                    "source_venv_in_sync",
                    return_value=(True, 1, ()),
                ),
                mock.patch.object(cli, "expose_binary"),
                mock.patch.object(cli, "read_receipt", return_value=None),
                mock.patch.object(cli, "_register_hosts", return_value={}),
                mock.patch.object(
                    cli,
                    "verify_installation",
                    return_value={
                        "repos": [],
                        "build_identity": {
                            "source_revision": "a" * 40,
                            "source_digest": "b" * 64,
                        },
                    },
                ),
                mock.patch.object(cli, "write_receipt"),
                mock.patch.object(cli, "git_rev", return_value="test"),
                mock.patch(
                    "span.shell.context.provision_repository_runtime"
                ) as provision_repository,
            ):
                cli.main(
                    [
                        "--dry-run",
                        "--repo",
                        str(repo),
                        "--data-dir",
                        str(root / "data"),
                        "--venv-dir",
                        str(root / "venv"),
                        "--bin-dir",
                        str(root / "bin"),
                        "--span-repo",
                        str(root),
                        "--no-codex",
                        "--no-hooks",
                        "--no-skills",
                    ]
                )
            provision_repository.assert_not_called()

    def test_verify_only_remains_observational(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo-a"
            repo.mkdir()
            with (
                mock.patch.object(cli, "doctor") as doctor,
                mock.patch(
                    "span.shell.context.provision_repository_runtime"
                ) as provision_repository,
            ):
                cli.main(
                    [
                        "--verify-only",
                        "--repo",
                        str(repo),
                        "--data-dir",
                        str(root / "data"),
                        "--venv-dir",
                        str(root / "venv"),
                        "--bin-dir",
                        str(root / "bin"),
                        "--span-repo",
                        str(root),
                        "--no-codex",
                        "--no-hooks",
                        "--no-skills",
                    ]
                )

            doctor.assert_called_once()
            provision_repository.assert_not_called()


if __name__ == "__main__":
    unittest.main()
