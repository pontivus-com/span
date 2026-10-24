"""Unit tests for the cross-platform installer (Linux behaviors).

The installer module must import without Span installed (checked by
AST: no span.* imports at top level), so these tests exercise pure
platform logic, config merge, and dry-run planning only.
"""

import ast
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell import install


class NoSpanImportTest(unittest.TestCase):
    def test_top_level_imports_are_stdlib_only(self):
        source = pathlib.Path(install.__file__).read_text()
        tree = ast.parse(source)
        allowed_roots = {
            "__future__",
            "argparse",
            "datetime",
            "hashlib",
            "importlib",
            "json",
            "os",
            "shutil",
            "sqlite3",
            "subprocess",
            "sys",
            "pathlib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    self.assertIn(root, allowed_roots, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    self.assertIn(
                        node.module.split(".")[0],
                        allowed_roots,
                        node.module,
                    )


class PlatformTableTest(unittest.TestCase):
    def test_linux_resolves(self):
        paths = install.platform_paths("linux")
        self.assertIn("venv_dir", paths)
        self.assertIn("data_dir", paths)
        self.assertIn("bin_dir", paths)

    def test_unverified_platforms_refuse(self):
        for key in ("darwin", "win32"):
            with self.assertRaises(SystemExit, msg=key):
                install.platform_paths(key)
        with self.assertRaises(SystemExit):
            install.platform_paths("plan9")

    def test_table_covers_future_platforms_structurally(self):
        for key, entry in install.PLATFORM_PATHS.items():
            self.assertIn("supported", entry, key)
            for name in ("venv_dir", "data_dir", "bin_dir"):
                self.assertIn(name, entry, f"{key}.{name}")


class OpencodeInstallGuidanceTest(unittest.TestCase):
    """Install docs must document only the supported nested OpenCode V2 form."""

    def test_install_docs_document_nested_v2_registration_only(self):
        readme = (
            pathlib.Path(__file__).resolve().parents[2] / "docs" / "install.md"
        ).read_text(encoding="utf-8")
        start = readme.index("### OpenCode")
        end = readme.index("## Verify the installation", start)
        block = readme[start:end]
        self.assertIn('"servers"', block)
        self.assertIn('"codemode": false', block)
        self.assertNotIn('"enabled"', block)
        self.assertIn("Do not use the legacy", block)
        json_start = block.index("```json") + len("```json")
        json_end = block.index("```", json_start)
        example = json.loads(block[json_start:json_end])
        self.assertIn("servers", example["mcp"])
        self.assertNotIn("span", example["mcp"])
        nested = example["mcp"]["servers"]["span"]
        self.assertEqual(nested["type"], "local")
        self.assertIs(nested["codemode"], False)
        self.assertNotIn("enabled", nested)
        self.assertNotIn("disabled", nested)


class OpencodeMergeTest(unittest.TestCase):
    def test_merge_rejects_flat_span_entry(self):
        import tempfile

        original = {
            "mcp": {
                "span": {
                    "type": "local",
                    "command": ["old-binary"],
                    "enabled": True,
                    "cwd": "/work",
                    "environment": {"A": "1"},
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps(original))
            with self.assertRaises(SystemExit) as ctx:
                install.merge_opencode_config(
                    str(config_path),
                    ["span-mcp", "--data-dir", "/d"],
                    dry_run=False,
                )
            self.assertIn("unsupported flat mcp.span", str(ctx.exception))
            # Rejected, never migrated: the config is left untouched.
            self.assertEqual(json.loads(config_path.read_text()), original)

    def test_merge_preserves_unrelated_entries(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "servers": {"other": {"command": ["other"]}},
                            "other": {"command": ["top-level"]},
                        },
                    }
                )
            )
            result = install.merge_opencode_config(
                str(config_path), ["span-mcp"], dry_run=False
            )
            config = json.loads(config_path.read_text())
            self.assertEqual(
                config["mcp"]["servers"]["other"],
                {"command": ["other"]},
            )
            self.assertEqual(config["mcp"]["other"], {"command": ["top-level"]})
            self.assertEqual(
                config["mcp"]["servers"]["span"]["command"],
                ["span-mcp"],
            )
            self.assertNotIn("removed_obsolete_entries", result)

    def test_merge_creates_missing_nested_entry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({"mcp": {}}))
            install.merge_opencode_config(str(config_path), ["span-mcp"], dry_run=False)
            config = json.loads(config_path.read_text())
            self.assertNotIn("span", config["mcp"])
            nested = config["mcp"]["servers"]["span"]
            self.assertEqual(nested["type"], "local")
            self.assertEqual(nested["command"], ["span-mcp"])
            self.assertIs(nested["codemode"], False)
            self.assertNotIn("enabled", nested)
            self.assertNotIn("disabled", nested)

    def test_merge_keeps_correct_nested_entry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "servers": {
                                "span": {
                                    "type": "local",
                                    "command": ["span-mcp"],
                                    "codemode": False,
                                }
                            }
                        },
                    }
                )
            )
            install.merge_opencode_config(str(config_path), ["span-mcp"], dry_run=False)
            nested = json.loads(config_path.read_text())["mcp"]["servers"]["span"]
            self.assertEqual(nested["command"], ["span-mcp"])
            self.assertNotIn("enabled", nested)

    def test_merge_reenables_disabled_nested_entry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "servers": {
                                "span": {
                                    "type": "local",
                                    "command": ["span-mcp"],
                                    "codemode": False,
                                    "disabled": True,
                                }
                            }
                        },
                    }
                )
            )
            install.merge_opencode_config(str(config_path), ["span-mcp"], dry_run=False)
            nested = json.loads(config_path.read_text())["mcp"]["servers"]["span"]
            self.assertNotIn("disabled", nested)

    def test_merge_rejects_flat_and_nested_duplicate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "span": {
                                "type": "local",
                                "command": ["old"],
                                "enabled": True,
                            },
                            "servers": {
                                "span": {
                                    "type": "local",
                                    "command": ["nested"],
                                    "codemode": False,
                                }
                            },
                        },
                    }
                )
            )
            with self.assertRaises(SystemExit):
                install.merge_opencode_config(
                    str(config_path), ["span-mcp"], dry_run=False
                )

    def test_dry_run_writes_nothing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({"mcp": {}}))
            install.merge_opencode_config(str(config_path), ["span-mcp"], dry_run=True)
            self.assertEqual(json.loads(config_path.read_text()), {"mcp": {}})


class AgentsRuleIsolationTest(unittest.TestCase):
    def test_deploy_changes_only_the_managed_agents_block(self):
        import tempfile

        root = pathlib.Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            (target / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
            (target / "keep.txt").write_text("unchanged\n", encoding="utf-8")
            before = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            result = install.deploy_agents_rules(root, [target])
            after = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            self.assertEqual(set(after), set(before))
            self.assertEqual(
                after[pathlib.Path("keep.txt")],
                before[pathlib.Path("keep.txt")],
            )
            self.assertIn(b"## Span lifecycle", after[pathlib.Path("AGENTS.md")])
            self.assertFalse((target / "AGENTS.md.bak-span").exists())
            self.assertEqual(result[str(target)]["status"], "wired")


class ReceiptScopeTest(unittest.TestCase):
    def test_write_receipt_persists_scope_list(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = str(pathlib.Path(tmp) / "data")
            payload = {
                "install_version": 1,
                "repos": ["/r/alpha", "/r/beta"],
                "verify": {"repos": []},
            }
            install.write_receipt(data_dir, payload, dry_run=False)
            stored = json.loads((pathlib.Path(data_dir) / "install.json").read_text())
            # The receipt scope list is what hook commands resolve
            # coverage against; it must persist verbatim.
            self.assertEqual(stored["repos"], ["/r/alpha", "/r/beta"])

    def test_write_receipt_dry_run_writes_nothing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = str(pathlib.Path(tmp) / "data")
            install.write_receipt(data_dir, {"repos": []}, dry_run=True)
            self.assertFalse(pathlib.Path(data_dir).exists())


class PlanningTest(unittest.TestCase):
    def test_pip_install_reinstalls_same_version_checkout(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            (repo / "src" / "span").mkdir(parents=True)
            with (
                patch.object(install, "_has_venv_pip", return_value=False),
                patch.object(install.shutil, "which", return_value="/uv"),
                patch.object(install, "_run") as run,
            ):
                install.pip_install("/venv/bin/python", repo)
            run.assert_called_once_with(
                [
                    "/uv",
                    "pip",
                    "install",
                    "--reinstall",
                    "--no-cache",
                    "--python",
                    "/venv/bin/python",
                    str(repo),
                ],
                dry_run=False,
            )

    def test_pip_install_installs_distribution_when_not_a_checkout(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(install, "_has_venv_pip", return_value=False),
                patch.object(install.shutil, "which", return_value="/uv"),
                patch.object(install, "distribution_version", return_value="0.6.0"),
                patch.object(install, "_run") as run,
            ):
                install.pip_install("/venv/bin/python", tmp)
            run.assert_called_once_with(
                [
                    "/uv",
                    "pip",
                    "install",
                    "--reinstall",
                    "--no-cache",
                    "--python",
                    "/venv/bin/python",
                    "span-mcp==0.6.0",
                ],
                dry_run=False,
            )

    def test_install_mode_resolves_assets_by_mode(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            (repo / "src" / "span").mkdir(parents=True)
            (repo / "skills" / "span").mkdir(parents=True)
            (repo / "docs").mkdir()
            (repo / "docs" / "agents-snippet.md").write_text("snippet\n")
            self.assertEqual(install.install_mode(repo), "checkout")
            self.assertEqual(install.canonical_skills_dir(repo), repo / "skills")
            self.assertEqual(
                install.agents_snippet_path(repo),
                repo / "docs" / "agents-snippet.md",
            )
            bundled = install.bundled_assets_root()
            self.assertEqual(install.canonical_skills_dir(tmp), bundled / "skills")
            self.assertEqual(
                install.agents_snippet_path(tmp),
                bundled / "agents-snippet.md",
            )

    def test_bundled_assets_match_canonical_sources(self):
        # The wheel carries copies of the canonical skills and lifecycle
        # snippet because an installed package has no repository root.
        # Copies drift silently, so equality is asserted here.
        repo_root = pathlib.Path(__file__).resolve().parents[2]
        bundled = repo_root / "src" / "span" / "_assets"
        canonical_skills = repo_root / "skills"
        for skill in sorted(p.name for p in canonical_skills.iterdir() if p.is_dir()):
            source = canonical_skills / skill / "SKILL.md"
            if not source.is_file():
                continue
            copy = bundled / "skills" / skill / "SKILL.md"
            self.assertTrue(copy.is_file(), f"missing bundled skill: {skill}")
            self.assertEqual(source.read_bytes(), copy.read_bytes(), skill)
        snippet = repo_root / "docs" / "agents-snippet.md"
        self.assertEqual(
            snippet.read_bytes(), (bundled / "agents-snippet.md").read_bytes()
        )

    def test_main_returns_success_for_console_entrypoint(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(install, "check_prereqs"):
                result = install.main(
                    [
                        "--dry-run",
                        "--span-repo",
                        tmp,
                        "--data-dir",
                        str(pathlib.Path(tmp) / "data"),
                        "--venv-dir",
                        str(pathlib.Path(tmp) / "venv"),
                        "--bin-dir",
                        str(pathlib.Path(tmp) / "bin"),
                        "--no-codex",
                        "--no-hooks",
                        "--no-skills",
                    ]
                )
            self.assertIsNone(result)

    def test_data_dir_inside_target_refused(self):
        args = install.parse_args(
            ["--repo", "/r", "--data-dir", "/r/data", "--dry-run"]
        )
        self.assertEqual(args.data_dir, "/r/data")

    def test_expose_binary_dry_run(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            dst = install.expose_binary(
                str(pathlib.Path(tmp) / "venv"),
                str(pathlib.Path(tmp) / "bin"),
                dry_run=True,
            )
            self.assertFalse(dst.exists())

    def test_structural_indexer_constants_pinned(self):
        from span.shell.structural import graft as g

        self.assertEqual(
            install.STRUCTURAL_INDEXER_PACKAGE, g.STRUCTURAL_INDEXER_PACKAGE
        )
        self.assertEqual(
            install.STRUCTURAL_INDEXER_VERSION, g.STRUCTURAL_INDEXER_VERSION
        )
        # Pinned to the latest published release; bumps update the
        # installer constant, the provider constant, and the ledger row
        # in the same change.
        self.assertEqual(install.STRUCTURAL_INDEXER_VERSION, "0.25.0")

    def test_ensure_structural_indexer_skips_when_present(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            venv = pathlib.Path(tmp) / "venv"
            tools = install.default_tools_dir(venv)
            binary = install.indexer_binary_path(tools)
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")
            package_json = (
                tools
                / "node_modules"
                / install.STRUCTURAL_INDEXER_PACKAGE
                / "package.json"
            )
            package_json.parent.mkdir(parents=True)
            package_json.write_text(
                json.dumps(
                    {
                        "name": install.STRUCTURAL_INDEXER_PACKAGE,
                        "version": install.STRUCTURAL_INDEXER_VERSION,
                    }
                )
            )
            self.assertEqual(
                install.ensure_structural_indexer(venv, dry_run=False),
                str(binary),
            )

    def test_ensure_structural_indexer_replaces_stale_version(self):
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            venv = pathlib.Path(tmp) / "venv"
            tools = install.default_tools_dir(venv)
            binary = install.indexer_binary_path(tools)
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")
            package_json = (
                tools
                / "node_modules"
                / install.STRUCTURAL_INDEXER_PACKAGE
                / "package.json"
            )
            package_json.parent.mkdir(parents=True)
            package_json.write_text(
                json.dumps(
                    {
                        "name": install.STRUCTURAL_INDEXER_PACKAGE,
                        "version": "0.21.1",
                    }
                )
            )
            recorded = {}

            def fake_run(cmd, **kwargs):
                recorded["cmd"] = cmd

                class _Proc:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return _Proc()

            with patch.object(subprocess, "run", side_effect=fake_run):
                install.ensure_structural_indexer(venv, dry_run=False)
            self.assertIn(
                f"{install.STRUCTURAL_INDEXER_PACKAGE}@"
                f"{install.STRUCTURAL_INDEXER_VERSION}",
                recorded["cmd"],
            )

    def test_ensure_structural_indexer_installs_pinned_version(self):
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            venv = pathlib.Path(tmp) / "venv"
            recorded = {}

            def fake_run(cmd, **kwargs):
                recorded["cmd"] = cmd
                binary = install.indexer_binary_path(install.default_tools_dir(venv))
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_text("#!/bin/sh\n")

                class _Proc:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return _Proc()

            with patch.object(subprocess, "run", side_effect=fake_run):
                binary = install.ensure_structural_indexer(venv, dry_run=False)
            self.assertIn(
                f"{install.STRUCTURAL_INDEXER_PACKAGE}@"
                f"{install.STRUCTURAL_INDEXER_VERSION}",
                recorded["cmd"],
            )
            self.assertTrue(pathlib.Path(binary).is_file())

    def test_ensure_structural_indexer_dry_run_installs_nothing(self):
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            venv = pathlib.Path(tmp) / "venv"
            with patch.object(
                subprocess,
                "run",
                side_effect=AssertionError("dry run must not invoke npm"),
            ):
                binary = install.ensure_structural_indexer(venv, dry_run=True)
            self.assertFalse(pathlib.Path(binary).exists())

    def test_check_prereqs_names_node_and_npm_not_indexer(self):
        from unittest.mock import patch

        def fake_which(tool):
            return {"node": "/node", "npm": "/npm"}.get(tool)

        with patch.object(install.shutil, "which", side_effect=fake_which):
            install.check_prereqs()  # must not raise

        def fake_which_missing_npm(tool):
            return {"node": "/node"}.get(tool)

        with patch.object(install.shutil, "which", side_effect=fake_which_missing_npm):
            with self.assertRaises(SystemExit) as ctx:
                install.check_prereqs()
            self.assertIn("npm", str(ctx.exception))
            self.assertNotIn("graft", str(ctx.exception))

    def test_target_census_is_read_only(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            graph = root / "graft" / ".graph"
            graph.mkdir(parents=True)
            (graph / "wiring.json").write_text('{"nodes": []}')
            (root / "graft" / "a.md").write_text("# a\n")
            before = sorted(p.name for p in root.rglob("*"))
            snap = install.target_artifact_snapshot(tmp)
            after = sorted(p.name for p in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertTrue(snap["wiring"]["present"])
            self.assertEqual(snap["markdown_cards"], 1)

    def test_scan_deletion_no_process_or_registry_probes(
        self,
    ):  # Addendum F F-5: the E-14 process/registry scan is deleted. The
        # install path must not reference process inspection, MCP
        # registries, attestation, or coexistence handling. (Bare
        # "codex"/"mcp" still occur legitimately in span host wiring.)
        import pathlib

        source = pathlib.Path(install.__file__).read_text()
        for forbidden in (
            "check_graft_isolation",
            "_active_graft_processes",
            "_enabled_graft_mcp_entries",
            "_registered_graft_mcp_servers",
            "allow_first_party_graft",
            "graft_isolation",
            "attested_readonly",
            "coexistence_accepted",
            "verified_isolated",
            "mcp list",
            "deregister_obsolete_codex_mcp",
            "codex_obsolete_mcp_removal",
            "removed_obsolete_entries",
            '"ps"',
            "'ps'",
        ):
            self.assertNotIn(forbidden, source, forbidden)


class Tier1MechanismTest(unittest.TestCase):
    def _tree(self, tmp, files):
        repo = pathlib.Path(tmp) / "span"
        src = repo / "src" / "span"
        src.mkdir(parents=True)
        for rel, content in files.items():
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        venv = pathlib.Path(tmp) / "venv"
        site = venv / "lib" / "python3.12" / "site-packages" / "span"
        return repo, venv / "bin" / "python", site

    def test_sync_check_passes_on_identical_tree(self):
        import tempfile

        files = {"core/model.py": "X = 1\n", "shell/mcp.py": "Y = 2\n"}
        with tempfile.TemporaryDirectory() as tmp:
            repo, python, site = self._tree(tmp, files)
            site.mkdir(parents=True)
            for rel, content in files.items():
                dst = site / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content)
            in_sync, count, extra = install.source_venv_in_sync(repo, python)
            self.assertTrue(in_sync)
            self.assertEqual(count, 2)
            self.assertEqual(extra, ())

    def test_sync_check_fails_on_drift_and_missing_tree(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo, python, site = self._tree(tmp, {"a.py": "1\n"})
            in_sync, _, extra = install.source_venv_in_sync(repo, python)
            self.assertFalse(in_sync)
            self.assertEqual(extra, ())
            site.mkdir(parents=True)
            (site / "a.py").write_text("2\n")
            in_sync, _, _ = install.source_venv_in_sync(repo, python)
            self.assertFalse(in_sync)
            (site / "a.py").write_text("1\n")
            (site / "stale.py").write_text("old\n")
            in_sync, _, extra = install.source_venv_in_sync(repo, python)
            self.assertTrue(in_sync)
            self.assertEqual(extra, ("stale.py",))

    def test_verify_installed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo, python, site = self._tree(tmp, {"a.py": "1\n"})
            ok, _ = install.verify_installed(repo, python)
            self.assertFalse(ok)
            site.mkdir(parents=True)
            (site / "a.py").write_text("2\n")
            ok, _ = install.verify_installed(repo, python)
            self.assertFalse(ok)
            (site / "a.py").write_text("1\n")
            ok, detail = install.verify_installed(repo, python)
            self.assertTrue(ok)
            self.assertIn("1 files match", detail)
            (site / "stale.py").write_text("old\n")
            ok, detail = install.verify_installed(repo, python)
            self.assertFalse(ok)
            self.assertIn("stale.py", detail)

    def test_verify_installed_distribution_mode_checks_version(self):
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(install, "distribution_version", return_value="0.6.0"):
                match = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="0.6.0\n"
                )
                with patch.object(install.subprocess, "run", return_value=match):
                    ok, detail = install.verify_installed(tmp, "/venv/bin/python")
                self.assertTrue(ok)
                self.assertIn("0.6.0", detail)
                drift = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="0.5.0\n"
                )
                with patch.object(install.subprocess, "run", return_value=drift):
                    ok, detail = install.verify_installed(tmp, "/venv/bin/python")
                self.assertFalse(ok)
                self.assertIn("0.5.0", detail)

    def test_distribution_fast_path_compares_version(self):
        import subprocess
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(install, "distribution_version", return_value="0.6.0"):
                match = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="0.6.0\n"
                )
                with patch.object(install.subprocess, "run", return_value=match):
                    in_sync, _, extra = install.distribution_venv_in_sync(
                        pathlib.Path(tmp) / "python"
                    )
                self.assertTrue(in_sync)
                self.assertEqual(extra, ())
                drift = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="0.5.0\n"
                )
                with patch.object(install.subprocess, "run", return_value=drift):
                    in_sync, _, _ = install.distribution_venv_in_sync(
                        pathlib.Path(tmp) / "python"
                    )
                self.assertFalse(in_sync)

    def test_clean_build_staging(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            build_lib = repo / "build" / "lib" / "span"
            build_lib.mkdir(parents=True)
            (build_lib / "stale.py").write_text("old\n")
            egg = repo / "src" / "span.egg-info"
            egg.mkdir(parents=True)
            (egg / "SOURCES.txt").write_text("old\n")
            keep = repo / "src" / "span" / "model.py"
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("X = 1\n")
            removed = install._clean_build_staging(repo, dry_run=False)
            self.assertEqual(len(removed), 2)
            self.assertFalse((repo / "build").exists())
            self.assertFalse(egg.exists())
            self.assertTrue(keep.is_file())
            # Dry run removes nothing.
            build_lib.mkdir(parents=True)
            removed = install._clean_build_staging(repo, dry_run=True)
            self.assertTrue((repo / "build").exists())

    def test_backup_copies_consistent_snapshot(self):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            db = data / "repo.db"
            conn = sqlite3.connect(str(db))
            conn.execute("CREATE TABLE t(x TEXT)")
            conn.execute("INSERT INTO t VALUES('v')")
            conn.commit()
            conn.close()
            dest = install.backup_data_dir(data, dry_run=False)
            assert dest is not None
            copied = pathlib.Path(dest) / "repo.db"
            self.assertTrue(copied.is_file())
            check = sqlite3.connect(str(copied))
            try:
                rows = check.execute("SELECT * FROM t").fetchall()
            finally:
                check.close()
            self.assertEqual(rows, [("v",)])
            self.assertIsNone(install.backup_data_dir(data / "absent", dry_run=False))
            self.assertFalse((data / "repo.db.bak").exists())

    def test_snapshot_and_compare_round_trip(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            graph = root / "graft" / ".graph"
            graph.mkdir(parents=True)
            (graph / "wiring.json").write_text('{"nodes": []}')
            snap = tmp + "/before.json"
            install.snapshot_census([tmp], snap, dry_run=False)
            stored = json.loads(pathlib.Path(snap).read_text())
            self.assertIn(tmp, stored)
            self.assertEqual(install.compare_census(snap, snap), [])
            (root / "graft" / "a.md").write_text("# a\n")
            after = tmp + "/after.json"
            install.snapshot_census([tmp], after, dry_run=False)
            self.assertEqual(install.compare_census(snap, after), [tmp])

    def test_load_seeds_round_trip_and_failure(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "seeds.json")
            self.assertEqual(install.load_seeds(None, dry_run=False), [])
            pathlib.Path(path).write_text(json.dumps([]))
            self.assertEqual(install.load_seeds(path, dry_run=False), [])
            pathlib.Path(path).write_text(
                json.dumps(
                    [
                        {
                            "$type": "EvidenceRef",
                            "evidence_id": {
                                "$type": "EvidenceId",
                                "value": "ev-a",
                            },
                            "repository_id": "r",
                            "source_kind": "SOURCE_CODE",
                            "locator": "a.py",
                        }
                    ]
                )
            )
            self.assertEqual(len(install.load_seeds(path, dry_run=False)), 1)
            with self.assertRaises(SystemExit):
                install.load_seeds(
                    str(pathlib.Path(tmp) / "absent.json"), dry_run=False
                )
            pathlib.Path(path).write_text("not json")
            with self.assertRaises(SystemExit):
                install.load_seeds(path, dry_run=False)

    def test_load_seeds_shape_failure_names_item_index(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "seeds.json")
            pathlib.Path(path).write_text(json.dumps([{"evidence_id": "ev-a"}]))
            try:
                install.load_seeds(path, dry_run=False)
            except SystemExit as exc:
                self.assertIn("seeds[0]", str(exc))
            else:
                self.fail("expected SystemExit")

    def test_load_seeds_decoder_unavailable_fails_closed(self):
        import json
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "seeds.json")
            pathlib.Path(path).write_text(json.dumps([]))
            real_import = install.importlib.import_module

            def _missing(name, *args, **kwargs):
                if name == "span.core.model":
                    raise ImportError("no span.core.model in test")
                return real_import(name, *args, **kwargs)

            with patch.object(install.importlib, "import_module", side_effect=_missing):
                try:
                    install.load_seeds(path, dry_run=False)
                except SystemExit as exc:
                    self.assertIn("canonical decoder unavailable", str(exc))
                else:
                    self.fail("expected SystemExit")


class HookWiringTest(unittest.TestCase):
    def test_codex_merge_adds_entries_and_dedupes(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            hooks_path = home / ".codex" / "hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(json.dumps({"hooks": {}}))
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                install.wire_codex_hooks("/bin/span-hooks", dry_run=False)
                first = json.loads(hooks_path.read_text())
                self.assertIn("SessionStart", first["hooks"])
                install.wire_codex_hooks("/bin/span-hooks", dry_run=False)
                second = json.loads(hooks_path.read_text())
                self.assertEqual(first, second)
            finally:
                os.path.expanduser = real_expanduser

    def test_codex_merge_missing_file_skips(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(pathlib.Path(tmp)) + p[1:] if p.startswith("~") else p
            )
            try:
                install.wire_codex_hooks("/bin/span-hooks", dry_run=False)
            finally:
                os.path.expanduser = real_expanduser

    def test_opencode_plugin_deploy_refused_target_write(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            src = repo / "integrations" / "hosts" / "opencode"
            src.mkdir(parents=True)
            (src / "span-hooks.js").write_text("// plugin")
            project = pathlib.Path(tmp) / "proj"
            # Addendum E §3/E-02: per-target plugin deployment is removed.
            with self.assertRaises(SystemExit):
                install.wire_opencode_plugin(repo, project, dry_run=False)
            self.assertFalse(
                (project / ".opencode" / "plugins" / "span-hooks.js").exists()
            )

    def test_opencode_plugin_dry_run_skipped(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            project = pathlib.Path(tmp) / "proj"
            result = install.wire_opencode_plugin(repo, project, dry_run=True)
            self.assertEqual(result["status"], "skipped")
            self.assertFalse(
                (project / ".opencode" / "plugins" / "span-hooks.js").exists()
            )


class SkillDeployTest(unittest.TestCase):
    def test_skills_deploy_verbatim_with_origin(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            span_repo = pathlib.Path(tmp) / "span"
            (span_repo / "src" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span" / "SKILL.md").write_text("# Span\n")
            (span_repo / "skills" / "empty").mkdir(parents=True)
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                (home / ".config" / "opencode" / "skills").mkdir(parents=True)
                (home / ".codex" / "skills").mkdir(parents=True)
                deployed = install.deploy_skills(span_repo, dry_run=False)
                # Both skill dirs land on both hosts (whole-dir copy).
                self.assertEqual(len(deployed), 4)
                opencode_span = home / ".config" / "opencode" / "skills" / "span"
                self.assertEqual((opencode_span / "SKILL.md").read_text(), "# Span\n")
                origin = json.loads((opencode_span / ".span-origin.json").read_text())
                self.assertEqual(origin["skill"], "span")
            finally:
                os.path.expanduser = real_expanduser

    def test_skills_dry_run_writes_nothing(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            span_repo = pathlib.Path(tmp) / "span"
            (span_repo / "src" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span" / "SKILL.md").write_text("x")
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                (home / ".config" / "opencode" / "skills").mkdir(parents=True)
                install.deploy_skills(span_repo, dry_run=True)
                self.assertFalse(
                    (home / ".config" / "opencode" / "skills" / "span").exists()
                )
            finally:
                os.path.expanduser = real_expanduser

    def test_skills_deploy_into_fresh_claude_host(self):
        # A freshly installed Claude Code has ~/.claude but no skills
        # directory. Deployment must create it, otherwise the host is
        # detected and then silently gets no skills.
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            span_repo = pathlib.Path(tmp) / "span"
            (span_repo / "src" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span" / "SKILL.md").write_text("# Span\n")
            (home / ".claude").mkdir(parents=True)
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                deployed = install.deploy_skills(span_repo, dry_run=False)
                self.assertEqual(len(deployed), 1)
                installed = home / ".claude" / "skills" / "span" / "SKILL.md"
                self.assertEqual(installed.read_text(), "# Span\n")
                # Hosts with no directory are never fabricated.
                self.assertFalse((home / ".codex").exists())
                self.assertFalse((home / ".config" / "opencode").exists())
            finally:
                os.path.expanduser = real_expanduser

    def test_skills_deploy_from_bundled_assets_in_distribution_mode(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            not_a_checkout = pathlib.Path(tmp) / "cwd"
            not_a_checkout.mkdir()
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                (home / ".config" / "opencode" / "skills").mkdir(parents=True)
                deployed = install.deploy_skills(not_a_checkout, dry_run=False)
                self.assertTrue(deployed)
                bundled = install.bundled_assets_root() / "skills" / "span" / "SKILL.md"
                installed = (
                    home / ".config" / "opencode" / "skills" / "span" / "SKILL.md"
                )
                self.assertEqual(bundled.read_bytes(), installed.read_bytes())
                origin = json.loads(
                    (
                        home
                        / ".config"
                        / "opencode"
                        / "skills"
                        / "span"
                        / ".span-origin.json"
                    ).read_text()
                )
                self.assertIsNone(origin["span_repo"])
                self.assertEqual(origin["install_mode"], "distribution")
                self.assertEqual(
                    origin["distribution_version"], install.distribution_version()
                )
            finally:
                os.path.expanduser = real_expanduser

    def test_detect_hosts(self):
        hosts = install.detect_hosts()
        self.assertTrue(hosts["opencode"])
        self.assertIn("codex", hosts)
        self.assertIn("claude", hosts)


class ClaudeHostTest(unittest.TestCase):
    """Claude Code is a managed host: register, wire, inspect."""

    def _home(self, tmp):
        import os

        real_expanduser = os.path.expanduser
        os.path.expanduser = lambda p: (
            str(pathlib.Path(tmp)) + p[1:] if p.startswith("~") else p
        )
        return real_expanduser

    def test_claude_hooks_added_and_deduped(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            settings = pathlib.Path(tmp) / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"permissions": {"allow": ["Bash"]}}))
            real_expanduser = self._home(tmp)
            try:
                install.wire_claude_hooks("/bin/span-hooks", "/data", dry_run=False)
                first = json.loads(settings.read_text())
                for event in ("SessionStart", "PostToolUse", "Stop"):
                    self.assertIn(event, first["hooks"])
                # Every command names the installed data directory; the
                # runner must never fall back to the platform default.
                commands = [
                    hook["command"]
                    for groups in first["hooks"].values()
                    for group in groups
                    for hook in group["hooks"]
                ]
                self.assertEqual(
                    sorted(commands),
                    [
                        "/bin/span-hooks session-start --data-dir /data",
                        "/bin/span-hooks session-stop --data-dir /data",
                        "/bin/span-hooks source-changed --data-dir /data",
                    ],
                )
                # Foreign settings survive untouched.
                self.assertEqual(first["permissions"], {"allow": ["Bash"]})
                install.wire_claude_hooks("/bin/span-hooks", "/data", dry_run=False)
                self.assertEqual(first, json.loads(settings.read_text()))
            finally:
                os.path.expanduser = real_expanduser

    def test_claude_hooks_replace_older_span_entries(self):
        # Upgrading must converge: a prior Span command with different
        # arguments is replaced, while a foreign command in the same
        # event group survives.
        import json
        import os
        import tempfile

        seeded = {
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup|resume|compact",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "/bin/span-hooks session-start",
                            },
                            {"type": "command", "command": "/opt/other setup"},
                        ],
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            settings = pathlib.Path(tmp) / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps(seeded))
            real_expanduser = self._home(tmp)
            try:
                install.wire_claude_hooks("/bin/span-hooks", "/data", dry_run=False)
                after = json.loads(settings.read_text())
                commands = [
                    hook["command"]
                    for group in after["hooks"]["SessionStart"]
                    for hook in group["hooks"]
                ]
                self.assertEqual(
                    sorted(commands),
                    [
                        "/bin/span-hooks session-start --data-dir /data",
                        "/opt/other setup",
                    ],
                )
            finally:
                os.path.expanduser = real_expanduser

    def test_claude_hooks_preserve_foreign_hooks_and_back_up(self):
        import json
        import os
        import tempfile

        foreign = {
            "hooks": {
                "SessionStart": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "x"}]}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            settings = pathlib.Path(tmp) / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps(foreign))
            real_expanduser = self._home(tmp)
            try:
                install.wire_claude_hooks("/bin/span-hooks", "/data", dry_run=False)
                after = json.loads(settings.read_text())
                self.assertEqual(
                    after["hooks"]["SessionStart"][0],
                    foreign["hooks"]["SessionStart"][0],
                )
                backup = settings.with_suffix(".json.bak-span")
                self.assertEqual(json.loads(backup.read_text()), foreign)
            finally:
                os.path.expanduser = real_expanduser

    def test_claude_hooks_missing_settings_skips(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            real_expanduser = self._home(tmp)
            try:
                result = install.wire_claude_hooks(
                    "/bin/span-hooks", "/data", dry_run=False
                )
            finally:
                os.path.expanduser = real_expanduser
            self.assertEqual(result["status"], "skipped")
            self.assertFalse((pathlib.Path(tmp) / ".claude").exists())

    def test_register_claude_uses_user_scope_stdio(self):
        from unittest.mock import patch

        with (
            patch.object(install.shutil, "which", return_value="/claude"),
            patch.object(install.subprocess, "run") as remove,
            patch.object(install, "_run") as run,
        ):
            install.register_claude(["/bin/span-mcp", "--data-dir", "/d"])
        self.assertEqual(
            remove.call_args_list[0].args[0],
            ["claude", "mcp", "remove", "span", "--scope", "user"],
        )
        run.assert_called_once_with(
            [
                "claude",
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "stdio",
                "span",
                "--",
                "/bin/span-mcp",
                "--data-dir",
                "/d",
            ],
            dry_run=False,
        )

    def test_register_claude_absent_skips(self):
        from unittest.mock import patch

        with patch.object(install.shutil, "which", return_value=None):
            result = install.register_claude(["/bin/span-mcp"])
        self.assertEqual(result["status"], "skipped")

    def test_register_claude_dry_run_writes_nothing(self):
        from unittest.mock import patch

        with (
            patch.object(install.shutil, "which", return_value="/claude"),
            patch.object(install.subprocess, "run") as remove,
            patch.object(install, "_run") as run,
        ):
            result = install.register_claude(["/bin/span-mcp"], dry_run=True)
        remove.assert_not_called()
        run.assert_not_called()
        self.assertEqual(result["status"], "skipped")

    def test_inspect_claude_registration_states(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            real_expanduser = self._home(tmp)
            try:
                expected = ["/bin/span-mcp", "--data-dir", "/d"]
                self.assertEqual(
                    install.inspect_claude_registration(expected)["status"],
                    "missing",
                )
                config_path = pathlib.Path(tmp) / ".claude.json"
                config_path.write_text(
                    json.dumps(
                        {
                            "mcpServers": {
                                "span": {
                                    "command": "/bin/span-mcp",
                                    "args": ["--data-dir", "/d"],
                                }
                            }
                        }
                    )
                )
                self.assertEqual(
                    install.inspect_claude_registration(expected)["status"],
                    "matched",
                )
                config_path.write_text(
                    json.dumps(
                        {
                            "mcpServers": {
                                "span": {
                                    "command": "/bin/span-mcp",
                                    "args": ["--data-dir", "/other"],
                                }
                            }
                        }
                    )
                )
                self.assertEqual(
                    install.inspect_claude_registration(expected)["status"],
                    "mismatched",
                )
                config_path.write_text("{not json")
                self.assertEqual(
                    install.inspect_claude_registration(expected)["status"],
                    "unreadable",
                )
            finally:
                os.path.expanduser = real_expanduser


class HostRegistrationInspectionTest(unittest.TestCase):
    """SPMCP-01: read-only, truthful host-registration discovery."""

    def _config(self, tmp, command, enabled=True, codemode=False):
        entry = {
            "type": "local",
            "command": command,
            "codemode": codemode,
        }
        if not enabled:
            entry["disabled"] = True
        path = pathlib.Path(tmp) / "opencode.json"
        path.write_text(
            json.dumps(
                {
                    "mcp": {"servers": {"span": entry}},
                }
            )
        )
        return path

    def test_matching_command_is_matched(self):
        import tempfile

        expected = ["/bin/span-mcp", "--data-dir", "/d", "--repo", "/r"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._config(tmp, expected)
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "matched")

    def test_wrong_data_dir_is_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp", "--data-dir", "/d", "--repo", "/r"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._config(
                tmp,
                [
                    "/bin/span-mcp",
                    "--data-dir",
                    "/other",
                    "--repo",
                    "/r",
                ],
            )
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "mismatched")

    def test_codemode_entry_is_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp", "--data-dir", "/d"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._config(tmp, expected, codemode=True)
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "mismatched")
        self.assertIn("Code Mode", result["reason"])

    def test_wrong_or_missing_repo_is_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp", "--data-dir", "/d", "--repo", "/r"]
        with tempfile.TemporaryDirectory() as tmp:
            wrong = self._config(
                tmp,
                [
                    "/bin/span-mcp",
                    "--data-dir",
                    "/d",
                    "--repo",
                    "/other",
                ],
            )
            result = install.inspect_opencode_registration(str(wrong), expected)
            self.assertEqual(result["status"], "mismatched")
            missing = self._config(
                tmp,
                [
                    "/bin/span-mcp",
                    "--data-dir",
                    "/d",
                ],
            )
            result = install.inspect_opencode_registration(str(missing), expected)
            self.assertEqual(result["status"], "mismatched")

    def test_disabled_entry_is_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp", "--data-dir", "/d"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._config(tmp, expected, enabled=False)
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "mismatched")
        self.assertIn("disabled", result["reason"])

    def test_missing_span_entry_is_missing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "opencode.json"
            path.write_text(json.dumps({"mcp": {}}))
            result = install.inspect_opencode_registration(str(path), ["/bin/span-mcp"])
        self.assertEqual(result["status"], "missing")

    def test_flat_entry_is_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp"]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "opencode.json"
            path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "span": {
                                "type": "local",
                                "command": expected,
                                "enabled": True,
                            }
                        },
                    }
                )
            )
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "mismatched")
        self.assertIn("unsupported flat mcp.span", result["reason"])

    def test_duplicate_registrations_are_mismatched(self):
        import tempfile

        expected = ["/bin/span-mcp"]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "opencode.json"
            path.write_text(
                json.dumps(
                    {
                        "mcp": {
                            "span": {
                                "type": "local",
                                "command": expected,
                                "enabled": True,
                            },
                            "servers": {
                                "span": {
                                    "type": "local",
                                    "command": expected,
                                    "codemode": False,
                                }
                            },
                        },
                    }
                )
            )
            result = install.inspect_opencode_registration(str(path), expected)
        self.assertEqual(result["status"], "mismatched")
        self.assertIn("duplicate", result["reason"])

    def test_no_config_available_is_missing(self):
        result = install.inspect_opencode_registration(None, ["/bin/span-mcp"])
        self.assertEqual(result["status"], "missing")

    def test_invalid_json_is_unreadable(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "opencode.json"
            path.write_text("{not json")
            result = install.inspect_opencode_registration(str(path), ["/bin/span-mcp"])
        self.assertEqual(result["status"], "unreadable")

    def test_doctor_inspection_leaves_config_bytes_unchanged(self):
        import tempfile
        from unittest.mock import patch

        expected = ["/bin/span-mcp", "--data-dir", "/d"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._config(tmp, expected)
            before = path.read_bytes()
            with (
                patch.object(install.shutil, "which", return_value="/bin/span-mcp"),
                patch.object(
                    install, "verify_installation", return_value={"repos": []}
                ),
                patch.object(install, "check_skills"),
            ):
                report = install.doctor(
                    "/venv/bin/python",
                    "/d",
                    [],
                    str(path),
                )
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report["opencode_registration"]["status"], "matched")

    def test_codex_present_reports_manual_without_registry_query(self):
        from unittest.mock import patch

        with (
            patch.object(install.shutil, "which", return_value="/bin/span-mcp"),
            patch.object(install, "verify_installation", return_value={"repos": []}),
            patch.object(install, "check_skills"),
            patch.object(
                install, "detect_hosts", return_value={"opencode": True, "codex": True}
            ),
            patch.object(
                install.subprocess,
                "run",
                side_effect=AssertionError("doctor must not query a registry"),
            ),
        ):
            report = install.doctor(
                "/venv/bin/python",
                "/d",
                [],
                None,
            )
        self.assertEqual(report["codex_registration"]["status"], "manual")
        self.assertIn(
            "not deterministically inspectable",
            report["codex_registration"]["reason"],
        )

    def test_codex_absent_reports_skipped(self):
        from unittest.mock import patch

        with (
            patch.object(install.shutil, "which", return_value="/bin/span-mcp"),
            patch.object(install, "verify_installation", return_value={"repos": []}),
            patch.object(install, "check_skills"),
            patch.object(
                install, "detect_hosts", return_value={"opencode": True, "codex": False}
            ),
        ):
            report = install.doctor(
                "/venv/bin/python",
                "/d",
                [],
                None,
            )
        self.assertEqual(report["codex_registration"]["status"], "skipped")

    def test_verify_only_is_the_only_verification_flag(self):
        args = install.parse_args(["--verify-only"])
        self.assertTrue(args.verify_only)
        self.assertFalse(hasattr(args, "verify"))
        verification_keys = {key for key in vars(args).keys() if "verify" in key}
        self.assertEqual(verification_keys, {"verify_only"})
        source = pathlib.Path(install.__file__).read_text()
        self.assertNotIn('"--verify"', source)
        self.assertIn('"--verify-only"', source)


if __name__ == "__main__":
    unittest.main()
