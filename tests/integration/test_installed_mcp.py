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
}

_SOURCE_SET = ("src", "pyproject.toml", "README.md")

_EXPECTED_TOOLS = {
    "initialize_repository",
    "start_context",
    "understand_question",
    "understand_retrieve",
    "reassess",
    "verification_support",
    "evidence_start",
    "evidence_extend",
    "record_create",
    "record_add",
    "record_confirm",
    "record_correct",
    "record_replace",
    "record_withdraw",
    "record_challenge",
    "record_update",
    "record_verification",
    "locate",
    "neighbors",
}

_RETIRED_TOOLS = {
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
            "from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION\n"
            f"store = LifecycleStore({str(data_dir / (repo.name + '.db'))!r},"
            " retention=DEFAULT_LIFECYCLE_RETENTION)\n"
            f"store.register_repository({repo.name!r}, {str(repo.resolve())!r})\n"
            "store.close()\n"
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
        self.assertFalse(_RETIRED_TOOLS & set(observed["tools"]))
        self.assertTrue(observed["removed_error"])
        self.assertEqual(observed["removed"]["kind"], "removed")
        self.assertIn("understand_question", observed["removed"]["replacement"])
        for key in (
            "admitted_error",
            "created_error",
            "found_error",
            "retrieved_error",
        ):
            self.assertFalse(observed[key], key)
        self.assertTrue(observed["observation"])
        self.assertTrue(observed["context_id"])
        self.assertTrue(observed["understanding_id"])
        self.assertIn(
            observed["found_kind"],
            {"InvestigationNeeded", "UnderstandingCandidateAnswer"},
        )
        self.assertEqual(observed["statement"], "Alpha declares VALUE = 1.")
        self.assertEqual(observed["version"], 1)

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
