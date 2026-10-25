"""Unit tests for the host hook runner (canonical HOOK_FAST notices).

The runner is a transport over one canonical policy: every automatic
hook maps to exactly one ``status(..., mode=HOOK_FAST)`` call through
the shared shell context opener, and prints only what that notice
reports. These tests pin that boundary — no second status policy, no
SQL, no store bootstrap — and the exception-oriented output rules.

Fixture providers replace the context opener so the canonical call can
run without a built structural index.
"""

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from span import service as ops
from span.core import model as m
from span.shell import hooks
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import ServiceContext
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO_ID = "repo"
SUBJECT = m.SubjectId(
    repository_id=REPO_ID,
    subject_kind=m.SubjectKind.COMPONENT,
    canonical_locator="src/a.py",
)
CONTENT_V1 = "VALUE = 1\n"
CONTENT_V2 = "VALUE = 2\n"


def _receipt(data_dir, repos):
    (pathlib.Path(data_dir) / "install.json").write_text(
        json.dumps({"repos": repos}),
        encoding="utf-8",
    )


def _context(content):
    """Fixture-backed canonical context over one file version."""
    structural = InMemoryStructuralSource(
        REPO_ID,
        (InMemoryFile("src/a.py", content),),
        (InMemorySubject("src/a.py", m.SubjectKind.COMPONENT, "a"),),
    )
    evidence = FixtureEvidenceSource(REPO_ID, {"src/a.py": content})
    store = SqliteSemanticStore(":memory:")
    return structural, evidence, store


def _seed(data_dir, content):
    """Provision the store through the canonical write path."""
    structural, evidence, _ = _context(content)
    store = SqliteSemanticStore(str(pathlib.Path(data_dir) / f"{REPO_ID}.db"))
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            authority_seeds=(),
        ),
        repository_id=REPO_ID,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    fingerprint = fingerprint_content(content)
    ref = m.EvidenceRef(
        evidence_id=m.EvidenceId("ev-src/a.py"),
        repository_id=REPO_ID,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/a.py",
        revision_or_fingerprint=fingerprint,
    )
    claim = m.SemanticClaim(
        claim_id=m.ClaimId("clm-1"),
        subject=SUBJECT,
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("does things", ()),
        evidence=(ref,),
        trust=m.TrustState.PARTIAL,
        freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
        basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "t"),
    )
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(m.Subject(SUBJECT, "a", None),),
            claims=(claim,),
            evidence_dependencies=(
                m.EvidenceDependency(
                    semantic_id=m.ClaimRef(id=m.ClaimId("clm-1")),
                    evidence_ref=ref,
                    observed_fingerprint=fingerprint,
                ),
            ),
        )
    )
    store.close()


class HookRunnerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.root = base / "repo"
        (self.root / "src").mkdir(parents=True)
        (self.root / "src" / "a.py").write_text(CONTENT_V1, encoding="utf-8")
        self.data_dir = base / "data"
        self.data_dir.mkdir()
        _receipt(self.data_dir, [str(self.root)])

    def _with_context(self, content):
        """Patch the opener with fixture providers over ``content``."""
        db = self.data_dir / f"{REPO_ID}.db"

        def factory(data_dir, repo_root):
            structural, evidence, _ = _context(content)
            store = SqliteSemanticStore(str(db))
            return REPO_ID, ServiceContext(
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )

        return patch.object(hooks, "_context_for", side_effect=factory)

    def _run(self, function, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            function(*args)
        return out.getvalue()

    def test_ready_session_start_is_silent(self):
        _seed(self.data_dir, CONTENT_V1)
        with self._with_context(CONTENT_V1):
            self.assertEqual(
                self._run(hooks.cmd_session_start, self.data_dir, str(self.root)),
                "",
            )

    def test_uninitialized_notice_creates_no_store(self):
        # The real opener, not a fixture: an ordinary hook on a
        # repository explicit initialization never provisioned must not
        # create `<data-dir>/<id>.db` or its schema.
        out = self._run(hooks.cmd_session_start, self.data_dir, str(self.root))
        self.assertIn("UNINITIALIZED", out)
        self.assertIn("initialize_repository", out)
        self.assertFalse((self.data_dir / f"{self.root.name}.db").exists())
        self.assertEqual(
            sorted(p.name for p in self.data_dir.iterdir()),
            ["install.json"],
        )

    def test_stale_change_reports_canonical_notice(self):
        _seed(self.data_dir, CONTENT_V1)
        target = str(self.root / "src" / "a.py")
        with self._with_context(CONTENT_V2):
            out = self._run(hooks.cmd_source_changed, self.data_dir, [target])
        self.assertIn(f"span: {REPO_ID} needs attention (1 stale)", out)
        self.assertIn("run refresh with an exact SubjectSelector", out)
        self.assertIn("src/a.py", out)

    def test_unchanged_change_is_silent(self):
        _seed(self.data_dir, CONTENT_V1)
        target = str(self.root / "src" / "a.py")
        with self._with_context(CONTENT_V1):
            self.assertEqual(
                self._run(hooks.cmd_source_changed, self.data_dir, [target]),
                "",
            )

    def test_change_outside_registered_repository_is_silent(self):
        _seed(self.data_dir, CONTENT_V1)
        with self._with_context(CONTENT_V2):
            self.assertEqual(
                self._run(
                    hooks.cmd_source_changed,
                    self.data_dir,
                    [str(self.data_dir / "elsewhere.py")],
                ),
                "",
            )

    def test_session_stop_reports_host_supplied_scope(self):
        _seed(self.data_dir, CONTENT_V1)
        target = str(self.root / "src" / "a.py")
        stream = io.StringIO(json.dumps({"tool_input": {"file_path": target}}))
        with self._with_context(CONTENT_V2), patch.object(sys, "stdin", stream):
            out = self._run(hooks.cmd_session_stop, self.data_dir, str(self.root))
        self.assertIn(f"span: {REPO_ID} close: 1 stale", out)

    def test_session_stop_without_paths_is_silent(self):
        _seed(self.data_dir, CONTENT_V1)
        with (
            self._with_context(CONTENT_V1),
            patch.object(sys, "stdin", io.StringIO("")),
        ):
            self.assertEqual(
                self._run(hooks.cmd_session_stop, self.data_dir, str(self.root)),
                "",
            )

    def test_session_start_only_reports_the_active_repository(self):
        nested = self.root / "nested"
        nested.mkdir()
        _receipt(self.data_dir, [str(self.root), str(nested)])
        seen = []

        def factory(data_dir, repo_root):
            seen.append(repo_root)
            structural, evidence, _ = _context(CONTENT_V1)
            return REPO_ID, ServiceContext(
                structural=structural,
                evidence=evidence,
                store=SqliteSemanticStore(":memory:"),
                continuations=ContinuationStore(),
            )

        with patch.object(hooks, "_context_for", side_effect=factory):
            self._run(hooks.cmd_session_start, self.data_dir, str(nested))
        self.assertEqual(seen, [str(nested)])

    def test_missing_receipt_exits_zero(self):
        empty = pathlib.Path(self._tmp.name) / "empty"
        empty.mkdir()
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            hooks.main(["--data-dir", str(empty), "session-start"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("install receipt", err.getvalue())

    def test_every_command_uses_the_canonical_hook_fast_call(self):
        notice = m.HookStatusNotice(store_readiness=m.StoreReadiness.READY)
        seen = []

        def fake_status(request, **kwargs):
            seen.append(request)
            return notice

        with (
            patch.object(hooks.ops, "status", side_effect=fake_status),
            self._with_context(CONTENT_V1),
        ):
            self._run(hooks.cmd_session_start, self.data_dir, str(self.root))
        self.assertEqual(len(seen), 1)
        request = seen[0]
        self.assertIsInstance(request, ops.SemanticStatusRequest)
        self.assertIs(request.mode, m.StatusMode.HOOK_FAST)
        self.assertIsNone(request.target)

    def test_runner_carries_no_second_status_policy(self):
        source = pathlib.Path(hooks.__file__).read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("SELECT", source)
        self.assertNotIn("load_evidence_dependencies", source)
        self.assertIs(hooks.ops.status, ops.status)


if __name__ == "__main__":
    unittest.main()
