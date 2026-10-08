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
            "argparse", "datetime", "json", "os", "shutil",
            "subprocess", "sys", "pathlib",
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
            install.merge_opencode_config(
                str(config_path),
                ["span-mcp", "--data-dir", "/d"],
                dry_run=False,
            )
            config = json.loads(config_path.read_text())
            self.assertEqual(
                config["mcp"]["span"]["command"],
                ["span-mcp", "--data-dir", "/d"],
            )
            self.assertEqual(
                config["mcp"]["graft"]["command"], ["graft"]
            )

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


class PlanningTest(unittest.TestCase):
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

    def test_graft_check_missing_index_fails_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                install.check_graft_index(tmp, build=False, dry_run=True)


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

    def test_opencode_plugin_deploys(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "span"
            src = (repo / "integrations" / "hosts" / "opencode")
            src.mkdir(parents=True)
            (src / "span-hooks.js").write_text("// plugin")
            project = pathlib.Path(tmp) / "proj"
            install.wire_opencode_plugin(repo, project, dry_run=False)
            deployed = project / ".opencode" / "plugins" / "span-hooks.js"
            self.assertTrue(deployed.exists())
            self.assertEqual(deployed.read_text(), "// plugin")


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
