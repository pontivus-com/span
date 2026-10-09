"""Unit tests for the host hook runner (read-only notices).

Builds a real store through the canonical write path, then drives
the stdlib-only hook module against it. Hooks must never write,
never break the session, and report staleness without classifying
beyond observed-vs-current bytes.
"""

import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from span.shell import hooks


def _receipt(data_dir, repos):
    (pathlib.Path(data_dir) / "install.json").write_text(json.dumps({
        "repos": repos,
        "verify": {"repos": []},
    }))


class HookNoticeTest(unittest.TestCase):
    def _seeded(self, tmp, freshness_state="CURRENT"):
        from span.core import model as m
        from span.shell.sqlite_store import SqliteSemanticStore

        root = str(pathlib.Path(tmp) / "repo")
        target = pathlib.Path(root) / "src" / "a.py"
        target.parent.mkdir(parents=True)
        target.write_text("VALUE = 1\n")
        data_dir = str(pathlib.Path(tmp) / "data")
        pathlib.Path(data_dir).mkdir()
        _receipt(data_dir, [root])
        db = str(pathlib.Path(data_dir) / "repo.db")
        store = SqliteSemanticStore(db)
        sid = m.SubjectId(
            repository_id="repo", subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/a.py",
        )
        import hashlib

        fp = hashlib.sha256(b"VALUE = 1\n").hexdigest()
        ref = m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-src/a.py"),
            repository_id="repo",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/a.py",
            revision_or_fingerprint=fp,
        )
        claim = m.SemanticClaim(
            claim_id=m.ClaimId("clm-1"), subject=sid,
            kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue("does things", ()),
            evidence=(ref,),
            trust=m.TrustState.PARTIAL,
            freshness=m.Freshness(
                m.FreshnessState(freshness_state), reason="t"
            ),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "t"
            ),
        )
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=(m.Subject(sid, "a", None),),
                claims=(claim,),
                evidence_dependencies=(
                    m.EvidenceDependency(
                        semantic_id=m.ClaimRef(id=m.ClaimId("clm-1")),
                        evidence_ref=ref,
                        observed_fingerprint=fp,
                    ),
                ),
            )
        )
        store.close()
        return root, data_dir, str(target)

    def _seed_coverage(self, data_dir, disposition="ANSWERED"):
        from span.core import model as m
        from span.shell.sqlite_store import SqliteSemanticStore

        db = str(pathlib.Path(data_dir) / "repo.db")
        store = SqliteSemanticStore(db)
        sid = m.SubjectId(
            repository_id="repo", subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/a.py",
        )
        scope = m.SemanticQuestionScope(
            scope_root=sid, subject=sid,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="hook coverage",
            materiality_basis="hook test",
        )
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=(m.Subject(sid, "a", None),),
                coverage=(
                    m.InterpretationCoverage(
                        subjects=(sid,),
                        question_slice="hook coverage",
                        evidence_scope=m.EvidenceScope(
                            paths=(), evidence_refs=()
                        ),
                        declared_complete=(
                            disposition == "ANSWERED"
                        ),
                        question=scope,
                        disposition=m.SemanticQuestionDisposition(
                            disposition
                        ),
                        result_refs=(
                            (
                                m.ClaimRef(id=m.ClaimId("clm-1")),
                            )
                            if disposition == "ANSWERED"
                            else ()
                        ),
                        resolution_requirements=(),
                        disposition_basis="hook test",
                        question_evidence=(),
                    ),
                ),
            )
        )
        store.close()

    def test_session_start_prompts_orientation_without_coverage(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_session_start(data_dir, root)
            text = out.getvalue()
            self.assertIn("repo", text)
            self.assertIn("no established coverage", text)
            self.assertIn("orient", text)

    def test_session_start_silent_when_established_current(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(tmp)
            self._seed_coverage(data_dir)
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_session_start(data_dir, root)
            self.assertEqual(out.getvalue(), "")

    def test_session_start_reports_noncurrent_scope(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(
                tmp, freshness_state="STALE"
            )
            self._seed_coverage(
                data_dir, disposition="PENDING"
            )
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_session_start(data_dir, root)
            text = out.getvalue()
            self.assertIn("repo", text)
            self.assertIn("needs attention", text)
            self.assertIn("1 stale", text)
            self.assertIn("1 pending", text)

    def test_source_changed_silent_when_unchanged(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, target = self._seeded(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_source_changed(data_dir, [target])
            self.assertEqual(out.getvalue(), "")

    def test_source_changed_reports_moved(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, target = self._seeded(tmp)
            # Move the bytes: dependents now need status/refresh.
            pathlib.Path(target).write_text("VALUE = 2\n")
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_source_changed(data_dir, [target])
            text = out.getvalue()
            self.assertIn("moved", text)
            self.assertIn("clm-1", text)

    def test_source_changed_ignores_untracked_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_source_changed(
                    data_dir, [str(pathlib.Path(root) / "other.py")]
                )
            self.assertEqual(out.getvalue(), "")

    def test_session_stop_silent_on_clean_close(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(tmp)
            self._seed_coverage(data_dir)
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_session_stop(data_dir, root)
            self.assertEqual(out.getvalue(), "")

    def test_session_stop_reports_actionable_scope(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(
                tmp, freshness_state="STALE"
            )
            self._seed_coverage(data_dir, disposition="PENDING")
            out = io.StringIO()
            with redirect_stdout(out):
                hooks.cmd_session_stop(data_dir, root)
            text = out.getvalue()
            self.assertIn("close:", text)
            self.assertIn("1 stale", text)
            self.assertIn("1 pending", text)

    def test_session_hooks_scope_to_active_repository(self):
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, data_dir, _ = self._seeded(
                tmp, freshness_state="STALE"
            )
            self._seed_coverage(data_dir, disposition="PENDING")
            other_root = pathlib.Path(tmp) / "other"
            other_root.mkdir()
            shutil.copyfile(
                pathlib.Path(data_dir) / "repo.db",
                pathlib.Path(data_dir) / "other.db",
            )
            _receipt(data_dir, [root, str(other_root)])

            start_out = io.StringIO()
            with redirect_stdout(start_out):
                with patch.object(
                    hooks, "default_data_dir", return_value=data_dir
                ):
                    hooks.main([
                        "--repo-root", str(other_root), "session-start"
                    ])
            self.assertIn("other", start_out.getvalue())
            self.assertNotIn("repo", start_out.getvalue())

            stop_out = io.StringIO()
            with redirect_stdout(stop_out):
                with patch.object(
                    hooks, "default_data_dir", return_value=data_dir
                ), patch.object(
                    hooks.os, "getcwd", return_value=str(other_root)
                ):
                    hooks.main(["session-stop"])
            self.assertIn("other close:", stop_out.getvalue())
            self.assertNotIn("repo close:", stop_out.getvalue())

    def test_missing_receipt_is_silent_success(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                with self.assertRaises(SystemExit) as ctx:
                    hooks.cmd_session_start(
                        str(pathlib.Path(tmp) / "nodir")
                    )
            self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
