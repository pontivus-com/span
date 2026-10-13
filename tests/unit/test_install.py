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
        source = (
            pathlib.Path(install.__file__).read_text()
        )
        tree = ast.parse(source)
        allowed_roots = {
            "__future__",
            "argparse", "datetime", "hashlib", "importlib", "json", "os",
            "shutil", "sqlite3", "subprocess", "sys", "pathlib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    self.assertIn(root, allowed_roots, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    self.assertIn(
                        node.module.split(".")[0], allowed_roots,
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


class OpencodeMergeTest(unittest.TestCase):
    def test_merge_updates_span_entry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({
                "mcp": {
                    "span": {
                        "type": "local",
                        "command": ["old-binary"],
                        "enabled": True,
                    },
                    "graft": {"type": "local", "command": ["graft"]},
                },
            }))
            result = install.merge_opencode_config(
                str(config_path),
                ["span-mcp", "--data-dir", "/d"],
                dry_run=False,
            )
            config = json.loads(config_path.read_text())
            self.assertEqual(
                config["mcp"]["span"]["command"],
                ["span-mcp", "--data-dir", "/d"],
            )
            # Addendum F F-4: the standalone graft MCP is deregistered;
            # its entries are removed, not preserved.
            self.assertNotIn("graft", config["mcp"])
            self.assertEqual(result["removed_graft_entries"], ["graft"])

    def test_merge_removes_graft_server_entries(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({
                "mcp": {
                    "servers": {
                        "span": {"command": ["old"]},
                        "graft": {"command": ["graft"]},
                    },
                },
            }))
            result = install.merge_opencode_config(
                str(config_path), ["span-mcp"], dry_run=False
            )
            config = json.loads(config_path.read_text())
            self.assertNotIn("graft", config["mcp"]["servers"])
            self.assertEqual(
                config["mcp"]["servers"]["span"]["command"], ["span-mcp"]
            )
            self.assertEqual(
                result["removed_graft_entries"], ["servers.graft"])

    def test_merge_reports_no_removal_when_absent(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({"mcp": {}}))
            result = install.merge_opencode_config(
                str(config_path), ["span-mcp"], dry_run=False
            )
            self.assertEqual(result["removed_graft_entries"], [])

    def test_merge_creates_missing_entry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({"mcp": {}}))
            install.merge_opencode_config(
                str(config_path), ["span-mcp"], dry_run=False
            )
            config = json.loads(config_path.read_text())
            self.assertTrue(config["mcp"]["span"]["enabled"])

    def test_dry_run_writes_nothing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "opencode.json"
            config_path.write_text(json.dumps({"mcp": {}}))
            install.merge_opencode_config(
                str(config_path), ["span-mcp"], dry_run=True
            )
            self.assertEqual(
                json.loads(config_path.read_text()), {"mcp": {}}
            )


class CodexGraftDeregistrationTest(unittest.TestCase):
    """Addendum F F-4: legacy graft MCP removal from codex."""

    def test_removed_on_success(self):
        from unittest.mock import patch

        with patch.object(install.shutil, "which", return_value="/codex"), \
                patch.object(install, "_run", return_value="") as run:
            result = install.deregister_codex_graft(dry_run=False)
        run.assert_called_once_with(
            ["codex", "mcp", "remove", "graft"], dry_run=False
        )
        self.assertEqual(result["status"], "removed")

    def test_failure_reports_manual_not_fatal(self):
        from unittest.mock import patch

        with patch.object(install.shutil, "which", return_value="/codex"), \
                patch.object(
                    install, "_run",
                    side_effect=SystemExit("no such entry"),
                ):
            result = install.deregister_codex_graft(dry_run=False)
        self.assertEqual(result["status"], "manual")

    def test_absent_cli_skips(self):
        from unittest.mock import patch

        with patch.object(install.shutil, "which", return_value=None):
            result = install.deregister_codex_graft(dry_run=False)
        self.assertEqual(result["status"], "skipped")

    def test_dry_run_runs_nothing(self):
        from unittest.mock import patch

        with patch.object(install.shutil, "which", return_value="/codex"), \
                patch.object(install, "_run") as run:
            result = install.deregister_codex_graft(dry_run=True)
        run.assert_not_called()
        self.assertEqual(result["status"], "skipped")


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
            stored = json.loads(
                (pathlib.Path(data_dir) / "install.json").read_text()
            )
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
        from unittest.mock import patch

        with patch.object(install, "_has_venv_pip", return_value=False), \
                patch.object(install.shutil, "which", return_value="/uv"), \
                patch.object(install, "_run") as run:
            install.pip_install("/venv/bin/python", "/span")
        run.assert_called_once_with(
            [
                "/uv", "pip", "install", "--reinstall", "--no-cache",
                "--python", "/venv/bin/python", "/span",
            ],
            dry_run=False,
        )

    def test_main_returns_success_for_console_entrypoint(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(install, "check_prereqs"):
                result = install.main([
                    "--dry-run",
                    "--span-repo", tmp,
                    "--data-dir", str(pathlib.Path(tmp) / "data"),
                    "--venv-dir", str(pathlib.Path(tmp) / "venv"),
                    "--bin-dir", str(pathlib.Path(tmp) / "bin"),
                    "--no-codex",
                    "--no-hooks",
                    "--no-skills",
                ])
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
        self.assertEqual(install.STRUCTURAL_INDEXER_VERSION, "0.21.1")

    def test_ensure_structural_indexer_skips_when_present(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            venv = pathlib.Path(tmp) / "venv"
            tools = install.default_tools_dir(venv)
            binary = install.indexer_binary_path(tools)
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n")
            self.assertEqual(
                install.ensure_structural_indexer(venv, dry_run=False),
                str(binary),
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
                binary = install.indexer_binary_path(
                    install.default_tools_dir(venv))
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_text("#!/bin/sh\n")

                class _Proc:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return _Proc()

            with patch.object(subprocess, "run", side_effect=fake_run):
                binary = install.ensure_structural_indexer(
                    venv, dry_run=False)
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
                subprocess, "run",
                side_effect=AssertionError("dry run must not invoke npm"),
            ):
                binary = install.ensure_structural_indexer(
                    venv, dry_run=True)
            self.assertFalse(pathlib.Path(binary).exists())

    def test_check_prereqs_names_node_and_npm_not_indexer(self):
        from unittest.mock import patch

        def fake_which(tool):
            return {"node": "/node", "npm": "/npm"}.get(tool)

        with patch.object(install.shutil, "which", side_effect=fake_which):
            install.check_prereqs()  # must not raise

        def fake_which_missing_npm(tool):
            return {"node": "/node"}.get(tool)

        with patch.object(
            install.shutil, "which", side_effect=fake_which_missing_npm
        ):
            with self.assertRaises(SystemExit) as ctx:
                install.check_prereqs()
            self.assertIn("npm", str(ctx.exception))
            self.assertNotIn("graft", str(ctx.exception))

    def test_graft_check_missing_index_is_diagnostic_not_gate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            # Provisioning builds the provider cache when needed; a
            # missing in-target index is diagnostic only.
            self.assertIsNone(install.check_graft_index(tmp))

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

    def test_scan_deletion_no_process_or_registry_probes(self):        # Addendum F F-5: the E-14 process/registry scan is deleted. The
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
            in_sync, count, extra = install.source_venv_in_sync(
                repo, python)
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
            self.assertIsNone(
                install.backup_data_dir(data / "absent", dry_run=False))
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
            self.assertEqual(
                install.compare_census(snap, snap), [])
            (root / "graft" / "a.md").write_text("# a\n")
            after = tmp + "/after.json"
            install.snapshot_census([tmp], after, dry_run=False)
            self.assertEqual(
                install.compare_census(snap, after), [tmp])

    def test_load_seeds_round_trip_and_failure(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "seeds.json")
            self.assertEqual(install.load_seeds(None, dry_run=False), [])
            pathlib.Path(path).write_text(json.dumps([]))
            self.assertEqual(
                install.load_seeds(path, dry_run=False), [])
            pathlib.Path(path).write_text(json.dumps(
                [{
                    "$type": "EvidenceRef",
                    "evidence_id": {
                        "$type": "EvidenceId", "value": "ev-a",
                    },
                    "repository_id": "r",
                    "source_kind": "SOURCE_CODE",
                    "locator": "a.py",
                }]))
            self.assertEqual(
                len(install.load_seeds(path, dry_run=False)), 1)
            with self.assertRaises(SystemExit):
                install.load_seeds(
                    str(pathlib.Path(tmp) / "absent.json"),
                    dry_run=False)
            pathlib.Path(path).write_text("not json")
            with self.assertRaises(SystemExit):
                install.load_seeds(path, dry_run=False)

    def test_load_seeds_shape_failure_names_item_index(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "seeds.json")
            pathlib.Path(path).write_text(json.dumps(
                [{"evidence_id": "ev-a"}]))
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

            with patch.object(
                install.importlib, "import_module", side_effect=_missing
            ):
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
                str(pathlib.Path(tmp)) + p[1:]
                if p.startswith("~") else p
            )
            try:
                install.wire_codex_hooks("/bin/span-hooks", dry_run=False)
            finally:
                os.path.expanduser = real_expanduser

    def test_opencode_plugin_deploy_refused_target_write(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            src = (repo / "integrations" / "hosts" / "opencode")
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
            (span_repo / "skills" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span" / "SKILL.md").write_text(
                "# Span\n"
            )
            (span_repo / "skills" / "empty").mkdir(parents=True)
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                (home / ".config" / "opencode" / "skills").mkdir(
                    parents=True
                )
                (home / ".codex" / "skills").mkdir(parents=True)
                deployed = install.deploy_skills(
                    span_repo, dry_run=False
                )
                # Both skill dirs land on both hosts (whole-dir copy).
                self.assertEqual(len(deployed), 4)
                opencode_span = (
                    home / ".config" / "opencode" / "skills" / "span"
                )
                self.assertEqual(
                    (opencode_span / "SKILL.md").read_text(), "# Span\n"
                )
                origin = json.loads(
                    (opencode_span / ".span-origin.json").read_text()
                )
                self.assertEqual(origin["skill"], "span")
            finally:
                os.path.expanduser = real_expanduser

    def test_skills_dry_run_writes_nothing(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            span_repo = pathlib.Path(tmp) / "span"
            (span_repo / "skills" / "span").mkdir(parents=True)
            (span_repo / "skills" / "span" / "SKILL.md").write_text("x")
            real_expanduser = os.path.expanduser
            os.path.expanduser = lambda p: (
                str(home) + p[1:] if p.startswith("~") else p
            )
            try:
                (home / ".config" / "opencode" / "skills").mkdir(
                    parents=True
                )
                install.deploy_skills(span_repo, dry_run=True)
                self.assertFalse(
                    (home / ".config" / "opencode" / "skills" / "span")
                    .exists()
                )
            finally:
                os.path.expanduser = real_expanduser

    def test_detect_hosts(self):
        hosts = install.detect_hosts()
        self.assertTrue(hosts["opencode"])
        self.assertIn("codex", hosts)


if __name__ == "__main__":
    unittest.main()
