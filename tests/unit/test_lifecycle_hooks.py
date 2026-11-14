"""Host hooks: lifecycle notices without semantic authorship."""

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
from span.shell.install.constants import INSTALL_VERSION
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import LifecycleStore
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService

REPO = "hooks-repo"
FILES = {"src/app.py": "line1\nline2\n", "README.md": "# hooks\n"}


def _write_receipt(data: pathlib.Path, root: pathlib.Path) -> None:
    (data / "install.json").write_text(
        json.dumps(
            {
                "install_version": INSTALL_VERSION,
                "repos": [str(root)],
                "host_registration": {},
            }
        ),
        encoding="utf-8",
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
    lifecycle = LifecycleService(
        store=store,
        authority=store,
        support=support,
        evidence=evidence_service,
    )
    admitted = evidence_service.start(
        m.EvidenceStartRequest(
            repository_id=REPO,
            request_id=m.RequestId("hook-evidence"),
            scope=m.EvidenceScope(paths=("src/app.py",)),
            requests=(m.EvidenceRequest("src/app.py"),),
        )
    )
    wire = rw.RecordRequestWire(
        request_id="hook-create",
        context=m.InvestigationContextRef(
            repository_id=REPO,
            context_id=admitted.context.context_id,
        ),
        kind=m.RecordKind.UNDERSTANDING,
        surface=rw.SurfaceWire(kind=m.SurfaceKind.FILE, locator="src/app.py"),
        question="What does the app do?",
        scope_paths=("src/app.py",),
        conclusion="The app emits line1.",
        support=(rw.SourceSupportWire(locator="src/app.py"),),
    )
    lifecycle.record(wire)
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

    def test_adoption_primer_when_understanding_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            output = _capture(hooks.cmd_adoption_primer, data, str(root))
            self.assertEqual(output, hooks.ADOPTION_PRIMER)
            self.assertIn("governs semantic understanding", output)
            self.assertIn("_ask", output)
            self.assertIn("direct tools", output)
            self.assertNotIn("current", output)
            self.assertNotIn("stale", output)

    def test_adoption_primer_reaches_a_cold_registered_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / REPO
            root.mkdir()
            data = base / "data"
            data.mkdir()
            _write_receipt(data, root)
            store = LifecycleStore(
                data / f"{REPO}.db", retention=DEFAULT_LIFECYCLE_RETENTION
            )
            store.register_repository(REPO, str(root.resolve()))
            store.close()
            output = _capture(hooks.cmd_adoption_primer, data, str(root))
            self.assertEqual(output, hooks.ADOPTION_PRIMER)
            self.assertIn("Record supported conclusions", output)

    def test_adoption_primer_is_silent_without_a_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / REPO
            root.mkdir()
            data = base / "data"
            data.mkdir()
            _write_receipt(data, root)
            self.assertEqual(_capture(hooks.cmd_adoption_primer, data, str(root)), "")

    def test_adoption_primer_is_silent_for_unregistered_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            (base / "elsewhere").mkdir()
            data = base / "data"
            data.mkdir()
            (data / "install.json").write_text(
                json.dumps(
                    {
                        "install_version": INSTALL_VERSION,
                        "repos": [],
                        "host_registration": {},
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                _capture(hooks.cmd_adoption_primer, data, str(base / "elsewhere")),
                "",
            )

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
            self.assertIn("installer", output)
            self.assertEqual(sorted(p.name for p in data.iterdir()), ["install.json"])

    def test_unversioned_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / REPO
            root.mkdir()
            data = base / "data"
            data.mkdir()
            (data / "install.json").write_text(
                json.dumps({"repos": [str(root)]}), encoding="utf-8"
            )
            with self.assertRaises(SystemExit):
                hooks.cmd_session_start(data, str(root))

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
            self.assertIn("reconsider", output)

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
                        request_id=m.RequestId("unused"),
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
