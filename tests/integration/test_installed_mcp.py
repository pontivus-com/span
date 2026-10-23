"""Installed MCP-process acceptance lane (Addendum I S9.3/S9.5/S9.8).

Builds an isolated virtualenv with a non-editable install of the
current source tree (plus a generated packaging-time ``BUILD_IDENTITY``)
and drives the S9.3 behavior matrix through the installed ``span-mcp``
console entrypoint over MCP stdio: tool/schema parity, observational
status, exact-path retrieval, schema-built submission, fresh-session
reuse, question-specific trace, authority separation, discriminated
impact, freshness mutation, refresh correction, and correction
isolation. A second server process over the same data directory proves
reuse without conversational memory.

The client path uses no ``span.*`` imports: request shapes come from
the server's own ``tools/list`` schemas and pending payloads, and all
assertions read wire JSON. A service-unit pass cannot substitute for
this gate. Requires ``uv`` and network access to build the isolated
environment; skips otherwise.
"""

import asyncio as _asyncio
import contextlib as _contextlib
import hashlib as _hashlib
import json as _json
import os as _os
import pathlib as _pathlib
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import unittest as _unittest


_REPO_FILES = {
    "README.md": "# synth\n\nSynthetic repository.\n",
    "src/alpha.py": "VALUE = 1\n",
    "src/beta.py": "OTHER = 2\n",
}

# Source set hashed into the packaging-time content digest. Mirrors
# the files the distribution is built from.
_SOURCE_SET = (
    "src",
    "pyproject.toml",
    "README.md",
)


def _tree_digest(root):
    """Content digest over the exact source bytes (sorted, deterministic).

    Dirty-tree-inclusive: two different working trees never share an
    identity even at one HEAD revision.
    """
    files = []
    for entry in _SOURCE_SET:
        path = root / entry
        if path.is_dir():
            for dirpath, dirnames, filenames in _os.walk(path):
                dirnames[:] = sorted(
                    d for d in dirnames if d != "__pycache__"
                )
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
            capture_output=True, text=True, timeout=30,
        )
        dirty = _subprocess.run(
            ("git", "-C", str(root), "diff", "--quiet"),
            timeout=30,
        )
        if head.returncode != 0:
            return "unknown"
        return head.stdout.strip() + (
            "" if dirty.returncode == 0 else "-dirty"
        )
    except (OSError, _subprocess.SubprocessError):
        return "unknown"


def _ensure_isolated_exe(work):
    """Install the current tree non-editably into a fresh venv.

    Returns (exe path, identity dict). The install carries a generated
    packaging-time BUILD_IDENTITY; the source tree is never on the
    isolated interpreter's path.
    """
    if _shutil.which("uv") is None:
        raise AssertionError(
            "S9.8 BLOCKED: uv is unavailable, so the isolated "
            "install cannot be established; refusing to pass the "
            "installed gate without it"
        )
    repo_root = _pathlib.Path(__file__).resolve().parents[2]
    srctree = work / "srctree"
    _shutil.copytree(
        repo_root / "src", srctree / "src",
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
        ("uv", "venv", str(venv)), check=True, timeout=300,
        capture_output=True,
    )
    isolated_python = str(venv / "bin" / "python")
    _subprocess.run(
        ("uv", "pip", "install", "--python", isolated_python,
         str(srctree)),
        check=True, timeout=900, capture_output=True,
    )
    return str(venv / "bin" / "span-mcp"), isolated_python, identity


def _write_repo(work):
    for rel, content in _REPO_FILES.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # git identity for structural currency (mirrors the provision
    # path test).
    for args in (
        ("init", "-q"),
        ("add", "-A"),
        (
            "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "held-out",
        ),
    ):
        _subprocess.run(
            ("git", "-C", str(work), *args),
            check=True, timeout=60,
        )
    # No target structural artifacts: the installed provider must build
    # the index into Span's data directory during provisioning.


class InstalledMcpDriverTest(_unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = _pathlib.Path(
            _tempfile.mkdtemp(prefix="span-installed-mcp-")
        )
        cls.addClassCleanup(_shutil.rmtree, cls.tmp, True)
        cls.exe, cls.isolated_python, cls.identity = (
            _ensure_isolated_exe(cls.tmp / "gate")
        )
        proc = _subprocess.run(
            [cls.isolated_python, "-c",
             "import span, json, sys;"
             "print(span.__file__);"
             "print(sys.version.split()[0]);"
             "print(open(__import__('pathlib').Path(span.__file__)"
             ".resolve().parent / 'BUILD_IDENTITY').read())"],
            capture_output=True, text=True, timeout=120,
            cwd=str(cls.tmp),
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        if proc.returncode != 0:
            raise AssertionError(
                "S9.8 BLOCKED: isolated package identity unreadable: "
                + proc.stderr[-2000:]
            )
        location, interpreter, identity_json = (
            proc.stdout.strip().splitlines()
        )
        if "site-packages" not in location:
            raise AssertionError(
                "S9.8 BLOCKED: isolated install resolves inside the "
                f"source tree: {location}"
            )
        identity = _json.loads(identity_json)
        if identity.get("source_digest") != cls.identity["source_digest"]:
            raise AssertionError(
                "S9.8 BLOCKED: installed BUILD_IDENTITY digest mismatch"
            )
        cls.pkg_location = location
        cls.pkg_identity = identity
        cls.pkg_interpreter = interpreter
        cls.pkg_interpreter_path = cls.isolated_python
        cls._ec31_result = None

    def test_installed_entrypoint_resolved(self):
        proc = _subprocess.run(
            [self.exe, "--help"],
            capture_output=True, text=True, timeout=120,
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        # Resolved in setUpClass: installed package outside any source
        # tree with matching packaging-time identity.
        self.assertIn("site-packages", self.pkg_location)
        self.assertEqual(
            self.pkg_identity["source_digest"],
            self.identity["source_digest"],
        )
        self.assertEqual(
            self.pkg_identity["source_revision"],
            self.identity["source_revision"],
        )

    def test_cold_start_handshake_before_setup(self):
        """CS-07/CS-08: MCP handshake precedes every setup side effect.

        A fresh installed process, fresh repository, and fresh data
        directory expose the registered repository ID through
        ``tools/list`` with no structural artifact and no semantic
        database. The explicit ``initialize_repository`` call in that
        same process then builds the provider index into Span's data
        directory and writes nothing to the target.
        """
        work = self.tmp / "cold"
        work.mkdir(parents=True, exist_ok=True)
        _write_repo(work)
        data_dir = self.tmp / "cold-data"
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = _pathlib.Path(__file__).with_name("cold_start_probe.py")
        proc = _subprocess.run(
            [
                self.isolated_python, str(probe),
                str(self.exe), str(work), str(data_dir),
            ],
            cwd=str(self.tmp),
            capture_output=True, text=True, timeout=300,
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        self.assertEqual(
            proc.returncode, 0,
            (proc.stderr or proc.stdout)[-4000:],
        )
        observed = _json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertEqual(len(observed["tools"]), 11)
        self.assertEqual(observed["registered"], ["cold"])
        self.assertFalse(
            observed["before_initialize"]["wiring"],
            "structural build ran before the MCP handshake",
        )
        self.assertFalse(
            observed["before_initialize"]["database"],
            "semantic initialization ran merely by process startup",
        )
        self.assertFalse(observed["initialize_error"])
        self.assertEqual(observed["initialize"]["readiness"], "READY")
        self.assertEqual(
            observed["initialize"]["repository_id"], "cold"
        )
        self.assertTrue(
            observed["after_initialize"]["wiring"],
            "explicit initialize_repository did not build the index",
        )
        self.assertTrue(observed["after_initialize"]["database"])

        # The target repository stays free of provider artifacts.
        self.assertFalse((work / "graft").exists())
        self.assertFalse((work / ".graph").exists())
        self.assertFalse(
            any(
                path.name == "wiring.json"
                for path in work.rglob("wiring.json")
            )
        )
        self.assertTrue(
            (
                data_dir / "structural" / "cold" / ".graph"
                / "wiring.json"
            ).is_file()
        )

    def _run_authority_restart(self):
        """Run the EC-31 black-box probe once per installed lane."""
        if type(self)._ec31_result is None:
            work = self.tmp / "restart"
            work.mkdir(parents=True, exist_ok=True)
            _write_repo(work)
            data_dir = self.tmp / "restart-data"
            data_dir.mkdir(parents=True, exist_ok=True)
            probe = _pathlib.Path(__file__).with_name(
                "authority_restart_probe.py"
            )
            proc = _subprocess.run(
                [
                    self.isolated_python, str(probe),
                    str(self.exe), str(work), str(data_dir),
                ],
                cwd=str(self.tmp),
                capture_output=True, text=True, timeout=300,
                env={k: v for k, v in _os.environ.items()
                     if k != "PYTHONPATH"},
            )
            self.assertEqual(
                proc.returncode, 0,
                (proc.stderr or proc.stdout)[-4000:],
            )
            type(self)._ec31_result = _json.loads(
                proc.stdout.strip().splitlines()[-1]
            )
        return type(self)._ec31_result

    def test_installed_authority_restart(self):
        """EC-31: fresh process, no re-init, new question keeps seeds.

        Process A initializes once with an explicit authority seed.
        Process B starts fresh over the same data directory, performs no
        ``initialize_repository``, asks a previously unestablished
        question, and receives ``PendingInterpretation`` whose brief
        carries the restored seed.
        """
        observed = self._run_authority_restart()
        self.assertEqual(observed["phase"], "EC-31")
        self.assertTrue(observed["ok"])
        self.assertEqual(observed["first_ready"], "READY")
        self.assertFalse(observed["restart_called_initialize"])
        self.assertTrue(observed["pending"])
        self.assertEqual(
            observed["authority_seed_locator"], "README.md"
        )
        self.assertTrue(
            any(
                "README.md" in line
                for line in observed["brief_evidence_authority"]
            ),
            observed["brief_evidence_authority"],
        )

    def test_installed_mcp_acceptance(self):
        work = self.tmp / "synth"
        work.mkdir(parents=True, exist_ok=True)
        _write_repo(work)
        data_dir = self.tmp / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        transcript = []
        from span.shell import install

        config_path = self.tmp / "opencode.json"
        config_path.write_text(
            _json.dumps({"mcp": {}}), encoding="utf-8"
        )
        install.merge_opencode_config(
            str(config_path),
            [self.exe, "--data-dir", str(data_dir), "--repo", str(work)],
            dry_run=False,
        )
        guidance = self.tmp / "guidance"
        guidance.mkdir(parents=True, exist_ok=True)
        install.ensure_agents_rule(
            _pathlib.Path(__file__).resolve().parents[2],
            guidance,
            dry_run=False,
        )
        runner = _pathlib.Path(__file__).with_name(
            "external_client_runner.py"
        )
        proc = _subprocess.run(
            [
                self.isolated_python, str(runner),
                str(self.exe), str(work), str(data_dir),
                str(config_path), str(guidance / "AGENTS.md"),
            ],
            cwd=str(self.tmp),
            capture_output=True, text=True, timeout=300,
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        self.assertEqual(
            proc.returncode, 0,
            (proc.stderr or proc.stdout)[-4000:],
        )
        external = _json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(external["span_imports"], [])
        self.assertEqual(external["forbidden_reads"], [])
        ec31 = self._run_authority_restart()
        ec_results = dict(external["ec_results"])
        ec_results["EC-31"] = bool(ec31.get("ok"))
        expected_ec = {f"EC-{index:02d}" for index in range(1, 32)}
        self.assertEqual(set(ec_results), expected_ec)
        self.assertTrue(all(ec_results.values()))
        transcript = list(external["transcript"])
        transcript.append(ec31)
        alpha_claim, beta_claim = external["claims"]
        self.assertTrue(alpha_claim)
        self.assertTrue(beta_claim)
        self.assertNotEqual(alpha_claim, beta_claim)
        for entry in transcript:
            print(f"stdio: {_json.dumps(entry, sort_keys=True)}")
        print(f"installed MCP claims: {alpha_claim} {beta_claim}")
        record = {
            "program": "span-mcp-agent-usability (Addendum M friction closure)",
            "runner": (
                "separate black-box client process with no Span imports; "
                "local isolated virtualenv with a non-editable install; "
                "installed span-mcp driven over MCP stdio"
            ),
            "command": [
                self.exe, "--data-dir", "<tmp>/data",
                "--repo", "<tmp>/synth",
            ],
            "executable": self.exe,
            "package_location": type(self).pkg_location,
            "interpreter": self.pkg_interpreter,
            "interpreter_path": self.pkg_interpreter_path,
            "package_version": next(
                entry["server_version"] for entry in transcript
                if "server_version" in entry
            ),
            "source_revision": self.identity["source_revision"],
            "source_digest": self.identity["source_digest"],
            "schema_digest": next(
                entry["schema_digest"] for entry in transcript
                if "schema_digest" in entry
            ),
            "exit_code": 0,
            "span_imports": external["span_imports"],
            "forbidden_reads": external["forbidden_reads"],
            "ec_results": ec_results,
            "transcript_path": (
                "span/.context/verification/stdio-transcript.jsonl"
            ),
            "transcript": transcript,
        }
        record_path = (
            _pathlib.Path(__file__).resolve().parents[2]
            / ".context" / "verification" / "record.json"
        )
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            _json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (record_path.parent / "stdio-transcript.jsonl").write_text(
            "\n".join(
                _json.dumps(entry, sort_keys=True)
                for entry in transcript
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    _unittest.main()
