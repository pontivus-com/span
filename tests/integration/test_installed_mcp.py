"""Installed MCP-process acceptance lane (0.9.0 lifecycle surface).

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
    "docs/functional-pyramid.json": (
        '{"version":1,"contexts":[{"context_id":"ctx-runtime",'
        '"coverage":[{"kind":"PREFIX","path":"src"}],"inherits":[],"rules":[]}],'
        '"rules":[]}\n'
    ),
}

_GOVERNED_A_FILES = {
    "README.md": "# governed A\n",
    "src/alpha.py": "VALUE = 1\n",
    "docs/functional-pyramid.json": (
        '{"version":1,"contexts":[{"context_id":"ctx-a",'
        '"coverage":[{"kind":"PREFIX","path":"src"}],"inherits":[],'
        '"rules":[{"repository_id":"repo-b","identity":"rule-p0"}]}],"rules":[]}\n'
    ),
    "docs/invalid-functional-pyramid.json": "{not-json\n",
}

_GOVERNED_B_FILES = {
    "README.md": "# governed B\n",
    "rules/p0-v1.md": "P0 authority version one.\n",
    "rules/p0-v2.md": "P0 authority version two.\n",
    "docs/functional-pyramid.json": (
        '{"version":1,"contexts":[],"rules":[{"rule_id":"rule-p0","layer":"P0",'
        '"owner":{"repository_id":"repo-b","authority_ref":"authority-p0-v1"},'
        '"governing_rule_ids":["ROOT"]}]}\n'
    ),
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
    for name in ("pyproject.toml", "README.md"):
        _shutil.copy(repo_root / name, srctree / name)
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
        path.write_text(content, encoding="utf-8")


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
            "from span.shell.sqlite_store.lifecycle import LifecycleStore\n"
            "from span.shell.sqlite_store.functional_pyramid import "
            "ensure_functional_pyramid_installation_store\n"
            "from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION\n"
            f"store = LifecycleStore({str(data_dir / (repo.name + '.db'))!r},"
            " retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            f"store.register_repository({repo.name!r}, {str(repo.resolve())!r})\n"
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

    def _create_governed_stores(
        self,
        repo_a: _pathlib.Path,
        repo_b: _pathlib.Path,
        data_dir: _pathlib.Path,
    ) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        code = (
            "import hashlib\n"
            "from pathlib import Path\n"
            "from span.core import model as m\n"
            "from span.shell.sqlite_store.lifecycle import LifecycleStore\n"
            "from span.shell.sqlite_store.functional_pyramid import "
            "ensure_functional_pyramid_installation_store\n"
            "from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION\n"
            f"repo_a = Path({str(repo_a.resolve())!r})\n"
            f"repo_b = Path({str(repo_b.resolve())!r})\n"
            f"data_dir = Path({str(data_dir)!r})\n"
            "def authority(evidence_id, locator):\n"
            "    digest = hashlib.sha256((repo_b / locator).read_bytes()).hexdigest()\n"
            "    return m.AuthorityBinding(\n"
            "        evidence_ref=m.EvidenceRef(\n"
            "            evidence_id=m.EvidenceId(evidence_id),\n"
            "            repository_id=repo_b.name,\n"
            "            source_kind=m.EvidenceSourceKind.DOCUMENTATION,\n"
            "            locator=locator,\n"
            "            revision_or_fingerprint=f'sha256:{digest}',\n"
            "        ),\n"
            "        authority_kind=m.AuthorityKind.REPOSITORY_RULE,\n"
            "        status=m.AuthorityStatus.ACCEPTED,\n"
            "    )\n"
            "store_a = LifecycleStore(data_dir / f'{repo_a.name}.db', "
            "retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            "store_a.register_repository(repo_a.name, str(repo_a))\n"
            "store_a.close()\n"
            "store_b = LifecycleStore(data_dir / f'{repo_b.name}.db', "
            "retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            "store_b.register_repository(\n"
            "    repo_b.name, str(repo_b),\n"
            "    authority_bindings=(\n"
            "        authority('authority-p0-v1', 'rules/p0-v1.md'),\n"
            "        authority('authority-p0-v2', 'rules/p0-v2.md'),\n"
            "    ),\n"
            ")\n"
            "store_b.close()\n"
            "fp = ensure_functional_pyramid_installation_store(\n"
            "    data_dir, retention=DEFAULT_LIFECYCLE_RETENTION\n"
            ")\n"
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
        self.assertEqual(created.returncode, 0, created.stderr[-4000:])

    def test_installed_cross_repository_governance_journey(self):
        root = self.tmp / "governed"
        repo_a = root / "repo-a"
        repo_b = root / "repo-b"
        repo_a.mkdir(parents=True, exist_ok=True)
        repo_b.mkdir(parents=True, exist_ok=True)
        _write_files(repo_a, _GOVERNED_A_FILES)
        _write_files(repo_b, _GOVERNED_B_FILES)
        data_dir = self.tmp / "governed-data"
        self._create_governed_stores(repo_a, repo_b, data_dir)

        probe = _pathlib.Path(__file__).with_name(
            "functional_pyramid_governed_probe.py"
        )
        proc = _subprocess.run(
            [
                self.isolated_python,
                str(probe),
                str(self.exe),
                str(repo_a),
                str(repo_b),
                str(data_dir),
                repo_a.name,
                repo_b.name,
            ],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=300,
            env=self._env(),
        )
        self.assertEqual(proc.returncode, 0, (proc.stderr or proc.stdout)[-8000:])
        observed = _json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertEqual(observed["unknown_repository_kind"], "Rejected")
        self.assertEqual(observed["unknown_pyramid_kind"], "Rejected")
        self.assertFalse(observed["mixed_candidate_error"])
        self.assertIn(
            "UNREGISTERED_MEMBER", observed["mixed_validation_reasons"]
        )
        self.assertIn(
            "INVALID_DECLARATION_SOURCE", observed["mixed_validation_reasons"]
        )
        self.assertIn("INVALID_DECLARATION", observed["mixed_graph_reasons"])

        self.assertFalse(observed["candidate_error"])
        self.assertTrue(observed["candidate_ready"])
        self.assertFalse(observed["activated_error"])
        self.assertEqual(observed["activated_kind"], "FunctionalPyramidRecorded")

        self.assertFalse(observed["ask_a_error"])
        self.assertEqual(observed["ask_a_route_status"], "RESOLVED")
        self.assertIn("authority-p0-v1", observed["ask_a_rule_authority_ids"])

        self.assertFalse(observed["owner_ask_error"])
        self.assertEqual(observed["owner_scope_relation"], "UNCOVERED")
        self.assertEqual(observed["owner_route_status"], "UNRESOLVED")
        self.assertIn("ctx-a", observed["owner_downstream_contexts"])

        self.assertFalse(observed["created_error"])
        self.assertEqual(observed["created_qualification"], "CURRENT")
        self.assertFalse(observed["snapshot_before_error"])
        self.assertTrue(observed["snapshot_before_has_route"])
        self.assertIn(
            "authority-p0-v1", observed["snapshot_before_authority_ids"]
        )

        self.assertFalse(observed["changed_error"])
        self.assertIn("repo-a", observed["changed_surface_repositories"])
        self.assertEqual(observed["changed_context_repository"], "repo-a")

        self.assertFalse(observed["reestablished_error"])
        self.assertEqual(observed["reestablished_qualification"], "CURRENT")
        self.assertFalse(observed["snapshot_after_error"])
        self.assertTrue(observed["snapshot_after_has_route"])
        self.assertIn(
            "authority-p0-v2", observed["snapshot_after_authority_ids"]
        )
        self.assertFalse(observed["ask_after_error"])
        self.assertEqual(observed["ask_after_kind"], "Answer")

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
            "warm_error",
            "retrieved_error",
        ):
            self.assertFalse(observed[key], key)
        self.assertTrue(observed["understanding_id"])
        self.assertEqual(observed["cold_kind"], "Gap")
        self.assertEqual(observed["found_kind"], "Answer")
        self.assertEqual(observed["statement"], "Alpha declares VALUE = 1.")
        self.assertEqual(observed["version"], 1)
        self.assertFalse(observed["fp_status_before_error"])
        self.assertEqual(observed["fp_status_before_kind"], "FunctionalPyramidStatus")
        self.assertEqual(observed["fp_status_before_state"], "UNCONFIGURED")
        self.assertFalse(observed["fp_candidate_error"])
        self.assertEqual(observed["fp_candidate_kind"], "FunctionalPyramidCandidate")
        self.assertTrue(observed["fp_activation_ready"])
        self.assertFalse(observed["fp_activate_error"])
        self.assertEqual(observed["fp_activate_kind"], "FunctionalPyramidRecorded")
        self.assertFalse(observed["fp_status_after_error"])
        self.assertEqual(observed["fp_status_after_state"], "ACTIVE")
        self.assertEqual(observed["fp_status_after_health"], "VALID")
        self.assertFalse(observed["fp_receipt_error"])
        self.assertEqual(
            observed["fp_receipt_kind"], "RetrievedFunctionalPyramidReceipt"
        )
        self.assertEqual(observed["fp_receipt_action"], "activate")

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
