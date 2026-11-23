"""Beta-2 regressions for the released repository-initialization contract defect.

These tests are intentionally written against the Beta-2 target behavior before
the runtime fix. T01 requires them to fail on the pre-fix runtime so B2-D01 is
encoded before installer implementation changes.
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


class Beta2InitializationRegressionTest(unittest.TestCase):
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
                mock.patch.object(cli, "load_seeds", return_value=[]),
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
                    "source_venv_in_sync",
                    return_value=(True, 1, ()),
                ),
                mock.patch.object(cli, "expose_binary"),
                mock.patch.object(cli, "read_receipt", return_value=None),
                mock.patch.object(cli, "_register_hosts", return_value={}),
                mock.patch.object(
                    cli, "verify_installation", return_value={"repos": []}
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
