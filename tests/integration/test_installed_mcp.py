"""Installed MCP-process acceptance lane for the current lifecycle surface.

Builds an isolated virtualenv with a non-editable install of the current
source tree (plus a generated packaging-time ``BUILD_IDENTITY``) and drives
the installed ``span-mcp`` console entrypoint over MCP stdio. The client path
uses no ``span.*`` imports; assertions read wire JSON.

Requires ``uv`` for the isolated environment; skips only when it is absent,
never silently passes.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import os as _os
import pathlib as _pathlib
import shutil as _shutil
import subprocess as _subprocess
import tempfile as _tempfile
import unittest as _unittest

_REPO_FILES = {
    "README.md": "# synth\n\nSynthetic repository.\n",
    "src/alpha.py": "VALUE = 1\n",
    "src/beta.py": "OTHER = 2\n",
    "docs/foundation.md": "# Foundation\n",
    "docs/functional-pyramid.json": _json.dumps(
        {
            "version": 3,
            "source_id": "__REPOSITORY_ID__:repository",
            "kind": "repository",
            "scope": ".",
            "documents": [
                {
                    "repository_id": "__REPOSITORY_ID__",
                    "document_ref": "docs/foundation.md",
                }
            ],
            "placements": [
                {
                    "document": {
                        "repository_id": "__REPOSITORY_ID__",
                        "document_ref": "docs/foundation.md",
                        "layer": "P0",
                    },
                    "scope": ".",
                    "governing_placements": ["ROOT"],
                }
            ],
        },
        sort_keys=True,
    )
    + "\n",
}


def _classification_file(declaring, area):
    def identity(locator):
        return {
            "declaring_repository_id": declaring,
            "repository_id": "repo-b",
            "document_ref": locator,
        }

    rows = []
    for layer, locator, scope, parent in (
        ("P0", "rules/p0-v1.md", ".", None),
        ("P1", "rules/p1.md", ".", "rules/p0-v1.md"),
        ("P2S", "rules/p2s.md", area, "rules/p1.md"),
        ("P2W", "rules/p2w.md", area, "rules/p2s.md"),
    ):
        rows.append(
            {
                **identity(locator),
                "disposition": "place",
                "layer": layer,
                "scope": scope,
                "governing_documents": (
                    ["ROOT"] if parent is None else [identity(parent)]
                ),
                "authority_kind": (
                    "CONTRACT_SPECIFICATION" if layer == "P2S" else "REPOSITORY_RULE"
                ),
                "authority_status": "ACCEPTED",
            }
        )
    rows.append(
        {
            **identity("rules/p0-v2.md"),
            "disposition": "exclude",
            "exclusion_reason": "not yet adopted",
        }
    )
    return _json.dumps({"version": 1, "rows": rows}, sort_keys=True) + "\n"


_GOVERNED_A_FILES = {
    "README.md": "# governed A\n",
    "src/alpha.py": "VALUE = 1\n",
    "docs/classification.json": _classification_file("repo-a", "src"),
    "docs/invalid-functional-pyramid.json": "{not-json\n",
}

_GOVERNED_B_FILES = {
    "README.md": "# governed B\n",
    "rules/p0-v1.md": "P0 authority version one.\n",
    "rules/p0-v2.md": "P0 authority version two.\n",
    "rules/p1.md": "P1 authority.\n",
    "rules/p2s.md": "Shared P2 contract authority.\n",
    "rules/p2w.md": "Workflow P2 contract authority.\n",
    "docs/classification.json": _classification_file("repo-b", "rules"),
}


_SOURCE_SET = ("src", "pyproject.toml", "README.md")

_EXPECTED_TOOLS = {"ask", "record", "reconsider"}

_NON_CURRENT_TOOLS = {
    "explain",
    "trace",
    "impact",
    "authority",
    "status",
    "refresh",
    "initialize_target",
    "submit_interpretation",
}


def _tree_digest(root):
    files = []
    for entry in _SOURCE_SET:
        path = root / entry
        if path.is_dir():
            for dirpath, dirnames, filenames in _os.walk(path):
                dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
                for name in sorted(filenames):
                    if name.endswith((".pyc", ".pyo")):
                        continue
                    files.append(_pathlib.Path(dirpath) / name)
        elif path.is_file():
            files.append(path)
    digest = _hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _tree_revision(root):
    try:
        head = _subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        dirty = _subprocess.run(("git", "-C", str(root), "diff", "--quiet"), timeout=30)
        if head.returncode != 0:
            return "unknown"
        return head.stdout.strip() + ("" if dirty.returncode == 0 else "-dirty")
    except (OSError, _subprocess.SubprocessError):
        return "unknown"


def _ensure_isolated_exe(work):
    if _shutil.which("uv") is None:
        raise _unittest.SkipTest(
            "installed lane needs uv for the isolated non-editable install"
        )
    repo_root = _pathlib.Path(__file__).resolve().parents[2]
    srctree = work / "srctree"
    _shutil.copytree(
        repo_root / "src",
        srctree / "src",
        ignore=_shutil.ignore_patterns("__pycache__"),
    )
    for name in ("pyproject.toml", "README.md", "setup.py"):
        _shutil.copy(repo_root / name, srctree / name)
    _shutil.copytree(
        repo_root / "scripts",
        srctree / "scripts",
        ignore=_shutil.ignore_patterns("__pycache__"),
    )
    _shutil.copytree(repo_root / "skills", srctree / "skills")
    (srctree / "docs").mkdir()
    _shutil.copy(
        repo_root / "docs" / "agents-snippet.md",
        srctree / "docs" / "agents-snippet.md",
    )
    plugin_dir = srctree / "integrations" / "hosts" / "opencode"
    plugin_dir.mkdir(parents=True)
    _shutil.copy(
        repo_root / "integrations" / "hosts" / "opencode" / "span-hooks.js",
        plugin_dir / "span-hooks.js",
    )
    identity = {
        "source_revision": _tree_revision(repo_root),
        "source_digest": _tree_digest(repo_root),
    }
    (srctree / "src" / "span" / "BUILD_IDENTITY").write_text(
        _json.dumps(identity, sort_keys=True), encoding="utf-8"
    )
    venv = work / "iso-venv"
    _subprocess.run(
        ("uv", "venv", str(venv)), check=True, timeout=300, capture_output=True
    )
    isolated_python = str(venv / "bin" / "python")
    _subprocess.run(
        ("uv", "pip", "install", "--python", isolated_python, str(srctree)),
        check=True,
        timeout=900,
        capture_output=True,
    )
    return str(venv / "bin" / "span-mcp"), isolated_python, identity


def _write_repo(work):
    for rel, content in _REPO_FILES.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            content.replace("__REPOSITORY_ID__", work.name),
            encoding="utf-8",
        )


def _write_files(root, files):
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class InstalledMcpDriverTest(_unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = _pathlib.Path(_tempfile.mkdtemp(prefix="span-installed-mcp-"))
        cls.addClassCleanup(_shutil.rmtree, cls.tmp, True)
        cls.exe, cls.isolated_python, cls.identity = _ensure_isolated_exe(
            cls.tmp / "gate"
        )

    def _env(self):
        return {k: v for k, v in _os.environ.items() if k != "PYTHONPATH"}

    def test_installed_entrypoint_resolved(self):
        outside = _subprocess.run(
            [
                self.isolated_python,
                "-c",
                "import span; print(span.__file__)",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=self._env(),
        )
        self.assertEqual(outside.returncode, 0, outside.stderr[-2000:])
        self.assertIn("site-packages", outside.stdout)
        help_result = _subprocess.run(
            [self.exe, "--help"],
            capture_output=True,
            text=True,
            timeout=120,
            env=self._env(),
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr[-2000:])

    def _create_store(self, repo: _pathlib.Path, data_dir: _pathlib.Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        code = (
            "import hashlib\n"
            "from pathlib import Path\n"
            "from span.core import model as m\n"
            "from span.shell.sqlite_store.lifecycle import LifecycleStore\n"
            "from span.shell.sqlite_store.functional_pyramid import "
            "ensure_functional_pyramid_installation_store\n"
            "from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION\n"
            f"root = Path({str(repo.resolve())!r})\n"
            f"repository_id = {repo.name!r}\n"
            "bindings = ()\n"
            "foundation = root / 'docs/foundation.md'\n"
            "if foundation.is_file():\n"
            "    digest = hashlib.sha256(foundation.read_bytes()).hexdigest()\n"
            "    bindings = (m.AuthorityBinding(\n"
            "        evidence_ref=m.EvidenceRef(\n"
            "            evidence_id=m.EvidenceId('authority-foundation'),\n"
            "            repository_id=repository_id,\n"
            "            source_kind=m.EvidenceSourceKind.DOCUMENTATION,\n"
            "            locator='docs/foundation.md',\n"
            "            revision_or_fingerprint=f'sha256:{digest}',\n"
            "        ),\n"
            "        authority_kind=m.AuthorityKind.REPOSITORY_RULE,\n"
            "        status=m.AuthorityStatus.ACCEPTED,\n"
            "    ),)\n"
            f"store = LifecycleStore({str(data_dir / (repo.name + '.db'))!r},"
            " retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            "store.register_repository(\n"
            "    repository_id, str(root), authority_bindings=bindings\n"
            ")\n"
            "store.close()\n"
            f"fp = ensure_functional_pyramid_installation_store({str(data_dir)!r}, "
            "retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            "fp.close()\n"
        )
        created = _subprocess.run(
            [self.isolated_python, "-c", code],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=300,
            env=self._env(),
        )
        self.assertEqual(created.returncode, 0, created.stderr[-2000:])

    def test_packaged_opencode_plugin_reaches_real_installed_hook_store(self):
        """Exercise deployed OpenCode plugin -> installed span-hooks -> real store."""
        if _shutil.which("node") is None:
            raise _unittest.SkipTest(
                "packaged OpenCode hook lane needs Node for the managed plugin"
            )
        root = self.tmp / "opencode-real-hook"
        repo = root / "hook-repo"
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "README.md").write_text("# hook repo\n", encoding="utf-8")
        data_dir = root / "data"
        self._create_store(repo, data_dir)

        receipt_code = (
            "import json\n"
            "from pathlib import Path\n"
            "from span.shell.install.constants import INSTALL_VERSION\n"
            f"path = Path({str(data_dir / 'install.json')!r})\n"
            f"repos = [{str(repo.resolve())!r}]\n"
            "path.write_text(json.dumps({'install_version': INSTALL_VERSION, "
            "'repos': repos, 'host_registration': {}}), encoding='utf-8')\n"
        )
        receipt = _subprocess.run(
            [self.isolated_python, "-c", receipt_code],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            env=self._env(),
        )
        self.assertEqual(receipt.returncode, 0, receipt.stderr[-2000:])

        real_hook = _pathlib.Path(self.exe).with_name("span-hooks")
        self.assertTrue(real_hook.is_file())
        plugin_dir = root / "opencode-plugin"
        config_path = root / "config/opencode.json"
        not_a_checkout = root / "distribution-mode"
        not_a_checkout.mkdir()
        deploy_code = (
            "from span.shell.install.hosts import deploy_opencode_plugin\n"
            "from span.shell.install.paths import opencode_plugin_path\n"
            f"source = opencode_plugin_path({str(not_a_checkout)!r})\n"
            f"deploy_opencode_plugin(str(source), {str(plugin_dir)!r}, "
            f"{str(config_path)!r}, {str(real_hook)!r}, {str(data_dir)!r}, "
            f"dry_run=False, span_root={str(root)!r})\n"
        )
        deployed = _subprocess.run(
            [self.isolated_python, "-c", deploy_code],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            env=self._env(),
        )
        self.assertEqual(deployed.returncode, 0, deployed.stderr[-4000:])
        self.assertTrue((plugin_dir / "index.js").is_file())
        self.assertTrue((plugin_dir / "span-hooks").is_file())

        driver = root / "drive-opencode-hook.mjs"
        driver.write_text(
            """
import { pathToFileURL } from "node:url";
const pluginPath = process.argv[2];
const repoRoot = process.argv[3];
const registered = {};
const ctx = {
  location: { directory: repoRoot },
  event: { subscribe: async function* () {} },
  tool: {
    list: async () => [{ id: "span_ask" }],
    hook: async (name, handler) => { registered["tool:" + name] = handler; },
  },
  session: {
    hook: async (name, handler) => {
      registered["session:" + name] = handler;
      return { dispose() {} };
    },
  },
};
const plugin = (await import(pathToFileURL(pluginPath).href + "?real=1")).default;
const dispose = await plugin.setup(ctx);
const event = { sessionID: "real-session", system: [] };
registered["session:context"](event);
console.log(JSON.stringify(event.system));
dispose();
""".strip() + "\n",
            encoding="utf-8",
        )
        proc = _subprocess.run(
            ["node", str(driver), str(plugin_dir / "index.js"), str(repo)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            env=self._env(),
        )
        self.assertEqual(proc.returncode, 0, (proc.stderr or proc.stdout)[-4000:])
        observed = _json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["type"], "text")
        self.assertIn("Functional Pyramid UNCONFIGURED", observed[0]["text"])
        self.assertIn("ask the relevant surface", observed[0]["text"])

    def _install_governed_runtime(
        self,
        repo_a: _pathlib.Path,
        repo_b: _pathlib.Path,
        data_dir: _pathlib.Path,
        *,
        governed: bool = True,
    ) -> tuple[str, list[str], dict[str, str]]:
        """Use the same sole installer entry for ordinary and governed setup."""
        self.assertFalse(data_dir.exists())
        runtime_root = data_dir.parent / (data_dir.name + "-runtime")
        runtime_root.mkdir(parents=True, exist_ok=True)
        install_exe = _pathlib.Path(self.exe).with_name("span-install")
        repo_root = _pathlib.Path(__file__).resolve().parents[2]
        venv_dir = runtime_root / "venv"
        bin_dir = runtime_root / "bin"
        isolated_home = runtime_root / "home"
        isolated_home.mkdir()
        env = self._env()
        env["HOME"] = str(isolated_home)
        env["XDG_CONFIG_HOME"] = str(runtime_root / "config")
        ordinary = [
            str(install_exe),
            "--repo",
            str(repo_a),
            "--repo",
            str(repo_b),
            "--data-dir",
            str(data_dir),
            "--venv-dir",
            str(venv_dir),
            "--bin-dir",
            str(bin_dir),
            "--span-repo",
            str(repo_root),
            "--no-codex",
            "--no-claude",
            "--no-hooks",
            "--no-skills",
        ]
        command = ordinary + [
            "--functional-pyramid-classification-file",
            repo_a.name,
            str(repo_a / "docs/classification.json"),
            "--functional-pyramid-classification-file",
            repo_b.name,
            str(repo_b / "docs/classification.json"),
        ]
        self._execute_installer(command if governed else ordinary, env)
        runtime_exe = venv_dir / "bin" / "span-mcp"
        self.assertTrue(runtime_exe.is_file())
        self.assertTrue((data_dir / f"{repo_a.name}.db").is_file())
        self.assertTrue((data_dir / f"{repo_b.name}.db").is_file())
        for root in (repo_a, repo_b):
            self.assertEqual(
                (root / ".span" / "functional-pyramid.json").is_file(), governed
            )
        return str(runtime_exe), command, env

    def _execute_installer(self, command, env):
        installed = _subprocess.run(
            command,
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=900,
            env=env,
        )
        self.assertEqual(
            installed.returncode,
            0,
            (installed.stderr or installed.stdout)[-12000:],
        )
        return installed

    def test_installed_document_only_governed_initialization(self):
        root = self.tmp / "document-only"
        repo_a, repo_b = root / "repo-a", root / "repo-b"
        for repo, files in ((repo_a, _GOVERNED_A_FILES), (repo_b, _GOVERNED_B_FILES)):
            repo.mkdir(parents=True)
            _write_files(repo, files)
            self.assertFalse((repo / ".span").exists())
        data_dir = root / "data"
        runtime_exe, command, env = self._install_governed_runtime(
            repo_a, repo_b, data_dir
        )
        receipt = _json.loads((data_dir / "install.json").read_text())
        self.assertNotIn("pending_governed_initialization", receipt)
        entries = receipt["governed_initialization"]
        self.assertEqual(set(entries), {"repo-a", "repo-b"})
        self.assertEqual(entries["repo-a"]["version"], 1)
        self.assertEqual(entries["repo-b"]["version"], 1)
        self.assertEqual(
            entries["repo-a"]["pyramid_id"], entries["repo-b"]["pyramid_id"]
        )
        self.assertEqual(entries["repo-a"]["bindings"], [])
        self.assertEqual(len(entries["repo-b"]["bindings"]), 4)
        self.assertEqual(len(entries["repo-a"]["artifacts"]), 3)
        self.assertTrue(receipt["verify"]["acceptance_ok"])
        for repo in receipt["verify"]["repos"]:
            self.assertEqual(
                repo["functional_pyramid"]["participation"]["state"], "ACTIVE"
            )
            self.assertEqual(
                repo["functional_pyramid"]["provenance"]["state"], "PROVENANCE_MATCH"
            )
        before = entries["repo-a"]["participation_results"]
        # The sole input may be reformatted without creating another version.
        path = repo_a / "docs/classification.json"
        path.write_text(_json.dumps(_json.loads(path.read_text()), indent=2))
        self._execute_installer(command, env)
        repeated = _json.loads((data_dir / "install.json").read_text())
        entry = repeated["governed_initialization"]["repo-a"]
        self.assertEqual(entry["version"], 1)
        self.assertEqual(entry["participation_results"], before)
        self.assertTrue(repeated["verify"]["acceptance_ok"])
        self.assertTrue(_pathlib.Path(runtime_exe).is_file())

        # Invalid input must fail before changing accepted installation metadata.
        receipt_path = data_dir / "install.json"
        accepted_bytes = receipt_path.read_bytes()
        original = path.read_text()
        path.write_text("{invalid")
        rejected = _subprocess.run(command, cwd=str(self.tmp), capture_output=True, text=True, timeout=900, env=env)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(receipt_path.read_bytes(), accepted_bytes)
        path.write_text(original)

        # Exercise interruption after the participation write but before final receipt promotion.
        for repo in (repo_a, repo_b):
            classification = repo / "docs/classification.json"
            content = _json.loads(classification.read_text())
            for row in content["rows"]:
                if row["document_ref"] == "rules/p2s.md":
                    row["authority_kind"] = "DECISION_RECORD"
            classification.write_text(_json.dumps(content))
        injected = (
            "from span.shell.install import cli, governed; "
            "from unittest.mock import patch; import sys; "
            "patch.object(governed, 'finalize', side_effect=RuntimeError('injected interruption')).start(); "
            "cli.main(sys.argv[1:])"
        )
        interrupted = _subprocess.run(
            [str(_pathlib.Path(runtime_exe).with_name("python")), "-c", injected, *command[1:]],
            cwd=str(self.tmp), capture_output=True, text=True, timeout=900, env=env,
        )
        self.assertNotEqual(interrupted.returncode, 0)
        self.assertIn("injected interruption", interrupted.stderr)
        pending = _json.loads(receipt_path.read_text())["pending_governed_initialization"]
        self.assertEqual(pending["accepted_version"], 2)
        self._execute_installer(command, env)
        recovered = _json.loads(receipt_path.read_text())
        self.assertNotIn("pending_governed_initialization", recovered)
        self.assertEqual(recovered["governed_initialization"]["repo-a"]["version"], 2)
        self.assertTrue(recovered["verify"]["acceptance_ok"])

    def test_installed_cross_repository_governance_journey(self):
        root = self.tmp / "governed"
        repo_a = root / "repo-a"
        repo_b = root / "repo-b"
        repo_a.mkdir(parents=True, exist_ok=True)
        repo_b.mkdir(parents=True, exist_ok=True)
        _write_files(repo_a, _GOVERNED_A_FILES)
        _write_files(repo_b, _GOVERNED_B_FILES)
        data_dir = self.tmp / "governed-data"
        runtime_exe, command, env = self._install_governed_runtime(
            repo_a, repo_b, data_dir, governed=False
        )

        probe = _pathlib.Path(__file__).with_name(
            "functional_pyramid_governed_probe.py"
        )
        proc = _subprocess.run(
            [
                self.isolated_python,
                str(probe),
                runtime_exe,
                str(repo_a),
                str(repo_b),
                str(data_dir),
                repo_a.name,
                repo_b.name,
                _json.dumps(command),
            ],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=900,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, (proc.stderr or proc.stdout)[-8000:])
        observed = _json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertEqual(observed["unknown_repository_kind"], "Rejected")
        self.assertEqual(observed["unknown_pyramid_kind"], "Rejected")
        self.assertFalse(observed["mixed_candidate_error"])
        self.assertIn("UNREGISTERED_MEMBER", observed["mixed_validation_reasons"])
        self.assertIn(
            "DECLARATION_INVALID", observed["mixed_validation_reasons"]
        )
        self.assertEqual(observed["mixed_graph_reasons"], [])

        self.assertFalse(observed["pre_status_error"])
        self.assertEqual(observed["pre_status_state"], "UNCONFIGURED")
        self.assertEqual(observed["manual_activation_kind"], "Rejected")
        self.assertFalse(observed["candidate_error"])
        self.assertTrue(observed["candidate_ready"])
        self.assertFalse(observed["activated_error"])
        self.assertEqual(observed["activated_kind"], "FunctionalPyramidRecorded")
        self.assertFalse(observed["pre_created_error"])
        self.assertEqual(observed["pre_created_qualification"], "CURRENT")
        self.assertIn("repo-a", observed["activation_effect_repositories"])
        self.assertFalse(observed["activation_receipt_before_error"])
        self.assertEqual(len(observed["activation_receipt_before_refs"]), 1)
        self.assertFalse(observed["activation_replay_before_error"])
        self.assertIn(
            "repo-a", observed["activation_replay_before_effect_repositories"]
        )
        self.assertFalse(observed["pre_reestablished_error"])
        self.assertEqual(observed["pre_reestablished_qualification"], "CURRENT")
        self.assertFalse(observed["activation_receipt_after_error"])
        self.assertEqual(
            observed["activation_receipt_after_refs"],
            observed["activation_receipt_before_refs"],
        )
        self.assertFalse(observed["activation_replay_after_error"])
        self.assertEqual(observed["activation_replay_after_effect_count"], 0)
        self.assertEqual(observed["activation_replay_after_context_count"], 0)

        self.assertFalse(observed["ask_a_error"])
        self.assertEqual(observed["ask_a_route_status"], "RESOLVED")
        self.assertEqual(
            observed["ask_a_documents"],
            [
                "rules/p0-v1.md",
                "rules/p1.md",
                "rules/p2s.md",
                "rules/p2w.md",
            ],
        )
        self.assertEqual(observed["directory_src_route_status"], "RESOLVED")
        self.assertEqual(
            observed["directory_src_documents"],
            observed["ask_a_documents"],
        )
        self.assertEqual(
            observed["directory_root_documents"],
            ["rules/p0-v1.md", "rules/p1.md"],
        )
        self.assertFalse(observed["owner_ask_error"])
        self.assertEqual(observed["owner_route_status"], "RESOLVED")
        self.assertEqual(
            observed["read_exposes_internal"],
            {"routes": False, "provenance": False, "health": False},
        )

        self.assertFalse(observed["created_error"])
        self.assertEqual(observed["created_qualification"], "CURRENT")
        self.assertFalse(observed["captured_ask_error"])
        self.assertEqual(observed["captured_ask_kind"], "Gap")
        self.assertEqual(observed["captured_gap_reason"], "pending_curation")
        self.assertFalse(observed["pending_error"])
        self.assertEqual(observed["pending_kind"], "PendingCuration")
        self.assertTrue(observed["pending_contains_created"])
        self.assertFalse(observed["curated_error"])
        self.assertEqual(observed["curated_kind"], "UnderstandingRecorded")
        self.assertFalse(observed["fresh_reuse_error"])
        self.assertEqual(observed["fresh_reuse_kind"], "Answer")
        self.assertFalse(observed["snapshot_before_error"])
        self.assertTrue(observed["snapshot_before_has_route"])
        self.assertIn("rules/p0-v1.md", observed["snapshot_before_authority_locators"])

        self.assertFalse(observed["changed_error"])
        self.assertIn("repo-a", observed["changed_surface_repositories"])
        self.assertEqual(observed["changed_context_repository"], "repo-a")

        self.assertFalse(observed["reestablished_error"])
        self.assertEqual(observed["reestablished_qualification"], "CURRENT")
        self.assertFalse(observed["snapshot_after_error"])
        self.assertTrue(observed["snapshot_after_has_route"])
        self.assertIn("rules/p0-v2.md", observed["snapshot_after_authority_locators"])
        self.assertFalse(observed["ask_after_error"])
        self.assertEqual(observed["ask_after_kind"], "Answer")
        self.assertFalse(observed["corrected_error"])
        self.assertEqual(observed["corrected_kind"], "UnderstandingRecorded")
        self.assertFalse(observed["corrected_ask_error"])
        self.assertEqual(observed["corrected_ask_kind"], "Gap")
        self.assertEqual(observed["corrected_gap_reason"], "pending_curation")
        self.assertFalse(observed["corrected_pending_error"])
        self.assertTrue(observed["corrected_pending_contains_target"])
        self.assertFalse(observed["recurated_error"])
        self.assertEqual(observed["recurated_kind"], "UnderstandingRecorded")
        self.assertFalse(observed["final_ask_error"])
        self.assertEqual(observed["final_ask_kind"], "Answer")

    def test_installed_lifecycle_over_stdio(self):
        work = self.tmp / "synth"
        work.mkdir(parents=True, exist_ok=True)
        _write_repo(work)
        data_dir = self.tmp / "data"
        self._create_store(work, data_dir)
        probe = _pathlib.Path(__file__).with_name("lifecycle_probe.py")
        proc = _subprocess.run(
            [
                self.isolated_python,
                str(probe),
                str(self.exe),
                str(work),
                str(data_dir),
                work.name,
            ],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=300,
            env=self._env(),
        )
        self.assertEqual(proc.returncode, 0, (proc.stderr or proc.stdout)[-4000:])
        observed = _json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertEqual(set(observed["tools"]), _EXPECTED_TOOLS)
        self.assertFalse(_NON_CURRENT_TOOLS & set(observed["tools"]))
        self.assertTrue(observed["unknown_error"])
        self.assertEqual(observed["unknown"]["kind"], "unknown_tool")
        self.assertIsNone(observed["unknown"]["replacement"])
        for key in (
            "cold_error",
            "created_error",
            "curated_error",
            "warm_error",
            "retrieved_error",
        ):
            self.assertFalse(observed[key], key)
        self.assertTrue(observed["understanding_id"])
        self.assertEqual(observed["cold_kind"], "Gap")
        self.assertEqual(observed["found_kind"], "Answer")
        self.assertEqual(observed["statement"], "Alpha declares VALUE = 1.")
        self.assertEqual(observed["version"], 2)
        self.assertFalse(observed["fp_status_before_error"])
        self.assertEqual(observed["fp_status_before_kind"], "FunctionalPyramidStatus")
        self.assertEqual(observed["fp_status_before_state"], "UNCONFIGURED")
        self.assertFalse(observed["fp_candidate_error"])
        self.assertEqual(observed["fp_candidate_kind"], "FunctionalPyramidCandidate")
        self.assertTrue(observed["fp_activation_ready"])
        self.assertFalse(observed["fp_activate_error"])
        self.assertEqual(observed["fp_activate_kind"], "Rejected")
        self.assertFalse(observed["fp_status_after_error"])
        self.assertEqual(observed["fp_status_after_state"], "UNCONFIGURED")
        self.assertIsNone(observed["fp_status_after_health"])
        self.assertFalse(observed["fp_receipt_error"])
        self.assertEqual(observed["fp_receipt_kind"], "Rejected")
        self.assertIsNone(observed["fp_receipt_action"])

    def test_fresh_process_reuses_without_state(self):
        work = self.tmp / "reuse"
        work.mkdir(parents=True, exist_ok=True)
        _write_repo(work)
        data_dir = self.tmp / "reuse-data"
        self._create_store(work, data_dir)
        probe = _pathlib.Path(__file__).with_name("lifecycle_probe.py")
        first = _subprocess.run(
            [
                self.isolated_python,
                str(probe),
                str(self.exe),
                str(work),
                str(data_dir),
                work.name,
            ],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=300,
            env=self._env(),
        )
        self.assertEqual(first.returncode, 0, (first.stderr or first.stdout)[-4000:])
        second = _subprocess.run(
            [
                self.isolated_python,
                str(probe),
                str(self.exe),
                str(work),
                str(data_dir),
                work.name,
            ],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=300,
            env=self._env(),
        )
        self.assertEqual(second.returncode, 0, (second.stderr or second.stdout)[-4000:])
        observed = _json.loads(second.stdout.strip().splitlines()[-1])
        self.assertFalse(observed["created_error"])
        self.assertEqual(observed["statement"], "Alpha declares VALUE = 1.")


if __name__ == "__main__":
    _unittest.main()
