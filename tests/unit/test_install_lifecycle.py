"""Install lifecycle: uninstall, purge, and orphan reporting (Step 15).

Install has create and use; these tests pin the terminal. Uninstall reverses
only host-side writes and never touches repository data; purge removes exactly
one explicit ID; list-orphans reports without deleting.
"""

import hashlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.shell import install
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
)
from span.service import initialize_repository
from span.service.requests import SemanticInitializeRepositoryRequest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _snapshot(root):
    """Relative path → content hash for every file under one root."""
    root = pathlib.Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        elif path.is_dir() and not any(path.iterdir()):
            result[str(path.relative_to(root)) + "/"] = "empty-dir"
    return result


def _write(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


class _HostFixture:
    """A temporary HOME plus one target repository."""

    def __init__(self, root):
        self.home = pathlib.Path(root) / "home"
        self.target = pathlib.Path(root) / "repo"
        self.data = pathlib.Path(root) / "data"
        self.opencode = self.home / ".config" / "opencode" / "opencode.json"
        self.codex_hooks = self.home / ".codex" / "hooks.json"
        self.claude = self.home / ".claude" / "settings.json"
        self.target.mkdir(parents=True)
        (self.home / ".config" / "opencode").mkdir(parents=True)
        (self.home / ".codex").mkdir(parents=True)
        (self.home / ".claude").mkdir(parents=True)
        self.data.mkdir(parents=True)
        _write(
            self.opencode,
            {
                "theme": "dark",
                "mcp": {"servers": {"foreign": {"type": "local", "command": ["x"]}}},
            },
        )
        _write(
            self.codex_hooks,
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [{"type": "command", "command": "other"}],
                        }
                    ]
                }
            },
        )
        _write(
            self.claude,
            {
                "model": "opus",
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [{"type": "command", "command": "other"}],
                        }
                    ]
                },
            },
        )
        (self.target / "AGENTS.md").write_text(
            "# Project notes\n\nKeep this line.\n", encoding="utf-8"
        )

    def install(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            install.merge_opencode_config(
                self.opencode, ["/venv/bin/span-mcp", "--data-dir", str(self.data)]
            )
            install.wire_codex_hooks("/venv/bin/span-hooks")
            install.wire_claude_hooks("/venv/bin/span-hooks", self.data)
            install.ensure_agents_rule(REPO_ROOT, self.target)
            install.deploy_skills(REPO_ROOT)
        install.write_receipt(
            self.data,
            {
                "repos": [str(self.target)],
                "host_registration": {"opencode": {"config": str(self.opencode)}},
            },
        )


def _run_uninstall(fixture):
    with mock.patch.dict(os.environ, {"HOME": str(fixture.home)}):
        with mock.patch.object(install.shutil, "which", return_value=None):
            return install.uninstall(fixture.data, [], None)


class UninstallTest(unittest.TestCase):
    def test_install_then_uninstall_restores_the_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _HostFixture(tmp)
            before = {
                "home": _snapshot(fixture.home),
                "target": _snapshot(fixture.target),
            }
            fixture.install()
            self.assertNotEqual(
                _snapshot(fixture.home), before["home"], "install wrote nothing"
            )
            _run_uninstall(fixture)
            self.assertEqual(_snapshot(fixture.home), before["home"])
            self.assertEqual(_snapshot(fixture.target), before["target"])
            self.assertFalse((fixture.data / "install.json").exists())

    def test_uninstall_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _HostFixture(tmp)
            fixture.install()
            _run_uninstall(fixture)
            report = _run_uninstall(fixture)
            self.assertEqual(report["receipt"], {"status": "absent"})
            self.assertEqual(report["opencode"]["status"], "absent")

    def test_uninstall_never_touches_repository_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _HostFixture(tmp)
            fixture.install()
            store = fixture.data / "repo.db"
            store.write_bytes(b"store")
            index_file = fixture.data / "structural" / "repo" / "wiring.json"
            _write(index_file, {"nodes": []})
            _run_uninstall(fixture)
            self.assertTrue(store.exists())
            self.assertTrue(index_file.exists())

    def test_malformed_agents_markers_are_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _HostFixture(tmp)
            (fixture.target / "AGENTS.md").write_text(
                "<!-- span:start -->\nno end marker\n", encoding="utf-8"
            )
            result = install.remove_agents_block(fixture.target)
            self.assertEqual(result["status"], "absent")
            self.assertIn(
                "no end marker",
                (fixture.target / "AGENTS.md").read_text(encoding="utf-8"),
            )

    def test_foreign_skill_without_the_marker_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _HostFixture(tmp)
            foreign = fixture.home / ".codex" / "skills" / "span"
            foreign.mkdir(parents=True)
            (foreign / "SKILL.md").write_text("mine\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"HOME": str(fixture.home)}):
                install.remove_deployed_skills()
            self.assertTrue((foreign / "SKILL.md").exists())


class PurgeTest(unittest.TestCase):
    def test_purge_removes_only_the_named_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            named = data / "kept-name.db"
            named.write_bytes(b"named")
            named_wal = data / "kept-name.db-wal"
            named_wal.write_bytes(b"wal")
            other = data / "other.db"
            other.write_bytes(b"other")
            named_index = data / "structural" / "kept-name" / "wiring.json"
            _write(named_index, {"nodes": []})
            other_index = data / "structural" / "other" / "wiring.json"
            _write(other_index, {"nodes": []})

            report = install.purge_repository(data, "kept-name")

            self.assertIn(str(named), report["removed"])
            self.assertFalse(named.exists())
            self.assertFalse(named_wal.exists())
            self.assertFalse((data / "structural" / "kept-name").exists())
            self.assertTrue(other.exists())
            self.assertTrue(other_index.exists())

    def test_purge_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            self.assertEqual(install.purge_repository(data, "gone")["removed"], [])
            self.assertEqual(install.purge_repository(data, "gone")["removed"], [])

    def test_purge_rejects_traversal_and_separators(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("..", ".", "a/b", "a\\\\b", ""):
                with self.subTest(value=bad):
                    with self.assertRaises(SystemExit):
                        install.purge_repository(tmp, bad)

    def test_purged_store_can_be_reinitialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            store_path = data / "repo.db"
            store = SqliteSemanticStore(str(store_path))
            try:
                initialize_repository(
                    SemanticInitializeRepositoryRequest(
                        repository_locator="fixture", authority_seeds=()
                    ),
                    repository_id="repo",
                    structural=InMemoryStructuralSource(
                        "repo", (InMemoryFile("README.md", "# x\n"),), (), ()
                    ),
                    evidence=FixtureEvidenceSource("repo", {"README.md": "# x\n"}),
                    store=store,
                    canonical_root="/roots/x/repo",
                )
            finally:
                store.close()

            install.purge_repository(data, "repo")
            self.assertFalse(store_path.exists())

            reopened = SqliteSemanticStore(str(store_path))
            try:
                result = initialize_repository(
                    SemanticInitializeRepositoryRequest(
                        repository_locator="fixture", authority_seeds=()
                    ),
                    repository_id="repo",
                    structural=InMemoryStructuralSource(
                        "repo", (InMemoryFile("README.md", "# x\n"),), (), ()
                    ),
                    evidence=FixtureEvidenceSource("repo", {"README.md": "# x\n"}),
                    store=reopened,
                    canonical_root="/roots/x/repo",
                )
                self.assertEqual(result.canonical_root, "/roots/x/repo")
            finally:
                reopened.close()


class OrphanTest(unittest.TestCase):
    def test_orphans_are_reported_and_nothing_is_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            (data / "known.db").write_bytes(b"k")
            (data / "orphan.db").write_bytes(b"o")
            _write(data / "structural" / "orphan-two" / "wiring.json", {"nodes": []})
            _write(data / "install.json", {"repos": ["/roots/known"]})

            report = install.list_orphans(data)

            self.assertEqual(report["present"], ["known", "orphan", "orphan-two"])
            self.assertEqual(report["registered"], ["known"])
            self.assertEqual(report["orphans"], ["orphan", "orphan-two"])
            self.assertTrue(report["receipt_present"])
            self.assertTrue((data / "orphan.db").exists())

    def test_no_receipt_reports_every_id_without_claiming_orphaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            (data / "a.db").write_bytes(b"a")
            report = install.list_orphans(data)
            self.assertEqual(report["orphans"], ["a"])
            self.assertFalse(report["receipt_present"])


if __name__ == "__main__":
    unittest.main()
