"""Host hooks: optional, event-local, and never a semantic writer."""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.core.schema import record_wire as rw
from span.shell import hooks
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import LifecycleStore
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService

REPO = "hooks-repo"
FILES = {"src/app.py": "line1\nline2\n", "README.md": "# hooks\n"}


def _write_receipt(data: pathlib.Path, root: pathlib.Path) -> None:
    (data / "install.json").write_text(
        json.dumps({"repos": [str(root)]}), encoding="utf-8"
    )


def _recorded(tmp: str) -> tuple[pathlib.Path, pathlib.Path]:
    base = pathlib.Path(tmp)
    root = base / REPO
    root.mkdir()
    for path, body in FILES.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    data = base / "data"
    data.mkdir()
    _write_receipt(data, root)
    store = LifecycleStore(data / f"{REPO}.db", retention=DEFAULT_LIFECYCLE_RETENTION)
    store.register_repository(REPO, str(root.resolve()))
    evidence = FilesystemEvidenceSource(REPO, root)
    evidence_service = EvidenceService(store=store, evidence=evidence)
    support = SupportService(store=store, evidence=evidence, authority=store)
    lifecycle = LifecycleService(store=store, authority=store, support=support)
    admitted = evidence_service.start(
        m.EvidenceStartRequest(
            repository_id=REPO,
            request_id=m.RequestId("hook-evidence"),
            scope=m.EvidenceScope(paths=("src/app.py",)),
            requests=(m.EvidenceRequest("src/app.py"),),
            bounds=m.QueryBounds(
                max_results=50,
                max_depth=5,
                max_subjects=8,
                max_evidence_units=24,
                max_evidence_bytes=96_000,
                max_candidate_claims=64,
                max_candidate_relationships=64,
            ),
        )
    )
    observation = admitted.outcomes[0].observation_id.value
    wire = rw.RecordCreateWire(
        identity=rw.IdentityWire(
            repository_id=REPO,
            context_id=admitted.context.context_id.value,
            submission_id="hook-create",
        ),
        target=rw.ExplicitTargetWire(
            question="What does the app do?",
            scope_paths=("src/app.py",),
            scope_evidence_refs=(),
        ),
        conclusions=(
            rw.ConclusionWire(
                conclusion_id="c-1",
                statement="The app emits line1.",
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                scope_paths=("src/app.py",),
                scope_evidence_refs=(),
                support=(rw.SourceSupportWire(observation_id=observation),),
                basis_derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                basis_summary="read the source",
                basis_input_refs=(),
            ),
        ),
    )
    lifecycle.create(wire)
    store.close()
    return root, data


def _capture(fn, *args) -> str:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        fn(*args)
    return stream.getvalue().strip()


class LifecycleHooksTest(unittest.TestCase):
    def test_session_start_is_silent_when_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            self.assertEqual(_capture(hooks.cmd_session_start, data, str(root)), "")

    def test_session_start_reports_absent_store_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / REPO
            root.mkdir()
            data = base / "data"
            data.mkdir()
            _write_receipt(data, root)
            output = _capture(hooks.cmd_session_start, data, str(root))
            self.assertIn("no store", output)
            self.assertIn("initialize_repository", output)
            self.assertEqual(sorted(p.name for p in data.iterdir()), ["install.json"])

    def test_source_change_reports_bounded_dependents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            (root / "src" / "app.py").write_text("changed\n", encoding="utf-8")
            output = _capture(
                hooks.cmd_source_changed,
                data,
                [str(root / "src" / "app.py")],
            )
            self.assertIn("needs attention", output)
            self.assertIn("1 recorded understanding", output)
            self.assertIn("reassess", output)

    def test_unrelated_source_change_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            output = _capture(
                hooks.cmd_source_changed,
                data,
                [str(root / "README.md")],
            )
            self.assertEqual(output, "")

    def test_source_change_does_not_write_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            store = LifecycleStore(
                data / f"{REPO}.db", retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                before = len(store.list_understandings(REPO))
                receipts = store.get_receipt(
                    m.RecordingIdentity(
                        repository_id=REPO,
                        context_id=m.InvestigationContextId("unused"),
                        submission_id=m.SubmissionId("unused"),
                    )
                )
            finally:
                store.close()
            _capture(
                hooks.cmd_source_changed,
                data,
                [str(root / "src" / "app.py")],
            )
            store = LifecycleStore(
                data / f"{REPO}.db", retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                self.assertEqual(len(store.list_understandings(REPO)), before)
                self.assertIsNone(receipts)
            finally:
                store.close()

    def test_session_stop_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            output = _capture(hooks.cmd_session_stop, data, str(root))
            self.assertEqual(output, "")

    def test_hook_source_has_no_semantic_writer_or_builder(self):
        source = pathlib.Path(hooks.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "ensure_current",
            "record_understanding",
            "record_verification",
            ".create(",
            ".update(",
            "reassess(",
        ):
            self.assertNotIn(forbidden, source, forbidden)


if __name__ == "__main__":
    unittest.main()
