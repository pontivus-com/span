"""Host hooks: lifecycle notices without semantic authorship."""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.core.schema import record_wire as rw
from span.shell import hooks
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.install.constants import INSTALL_VERSION
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.functional_pyramid import (
    ensure_functional_pyramid_installation_store,
)
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
    installation = ensure_functional_pyramid_installation_store(
        data, retention=DEFAULT_LIFECYCLE_RETENTION
    )
    installation.close()
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
    def test_session_start_reports_unconfigured_when_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            output = _capture(hooks.cmd_session_start, data, str(root))
            self.assertIn("Functional Pyramid UNCONFIGURED", output)
            self.assertIn("span-functional-pyramid", output)

    def test_session_entry_composes_four_participation_health_branches_once(self):
        active_member = m.FunctionalPyramidMemberView(
            repository_id=REPO,
            declaration_refs=(
                m.EvidenceRef(
                    evidence_id=m.EvidenceId("fp-declaration"),
                    repository_id=REPO,
                    source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                    locator="docs/functional-pyramid.json",
                ),
            ),
            functional_scope=m.FunctionalScope(
                (
                    m.FunctionalScopeSelector(
                        m.FunctionalScopeSelectorKind.PREFIX,
                        path="src",
                    ),
                )
            ),
            coverage=m.FunctionalPyramidCoverage.PARTIAL,
        )
        degraded_finding = m.FunctionalPyramidFinding(
            reason=m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            repository_id=REPO,
            detail="repository unavailable",
            recovery="restore repository availability",
        )
        cases = (
            (
                "unconfigured",
                m.FunctionalPyramidStatus(
                    state=m.FunctionalPyramidParticipationState.UNCONFIGURED
                ),
                (
                    "UNCONFIGURED",
                    "span-functional-pyramid",
                    "Descriptive-only work remains available",
                ),
            ),
            (
                "excluded",
                m.FunctionalPyramidStatus(
                    state=m.FunctionalPyramidParticipationState.EXCLUDED
                ),
                ("EXCLUDED", "no initialization obligation", "descriptive-only"),
            ),
            (
                "active-valid",
                m.FunctionalPyramidStatus(
                    state=m.FunctionalPyramidParticipationState.ACTIVE,
                    health=m.FunctionalPyramidHealth.VALID,
                    pyramid_id=m.FunctionalPyramidId("fp-hooks"),
                    version=m.FunctionalPyramidVersion(1),
                    members=(active_member,),
                ),
                ("ACTIVE/VALID", "no separate Pyramid action", "governed semantic"),
            ),
            (
                "active-degraded",
                m.FunctionalPyramidStatus(
                    state=m.FunctionalPyramidParticipationState.ACTIVE,
                    health=m.FunctionalPyramidHealth.DEGRADED,
                    pyramid_id=m.FunctionalPyramidId("fp-hooks"),
                    version=m.FunctionalPyramidVersion(1),
                    members=(active_member,),
                    findings=(degraded_finding,),
                ),
                (
                    "ACTIVE/DEGRADED",
                    "governance needs attention",
                    "semantic orientation",
                ),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            for name, status, expected in cases:
                with (
                    self.subTest(name=name),
                    mock.patch.object(
                        hooks, "_functional_pyramid_status", return_value=status
                    ),
                ):
                    output = _capture(hooks.cmd_session_start, data, str(root))
                    self.assertEqual(len(output.splitlines()), 1)
                    for value in expected:
                        self.assertIn(value, output)
                    self.assertIn("ask the relevant surface", output)

    def test_adoption_primer_when_understanding_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = _recorded(tmp)
            output = _capture(hooks.cmd_adoption_primer, data, str(root))
            self.assertEqual(output, hooks.ADOPTION_PRIMER)
            self.assertIn("lifecycle is active", output)
            self.assertIn("_ask", output)
            self.assertIn("FunctionalPyramidSelector", output)
            self.assertIn("span-functional-pyramid", output)
            self.assertIn("ACTIVE/VALID", output)
            self.assertIn("EXCLUDED", output)
            self.assertNotIn("_record", output)
            self.assertNotIn("_reconsider", output)

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
            self.assertIn("FunctionalPyramidSelector", output)

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

    def test_changed_scope_projection_receives_complete_input_before_render_bound(self):
        class FakeReconsider:
            def __init__(self):
                self.requests = []

            def preview_changed_scope(self, request):
                self.requests.append(request)
                return object()

        class FakeContext:
            def __init__(self, reconsider):
                self.reconsider = reconsider

        class FakeInstallation:
            def __init__(self, reconsider):
                self.reconsider = reconsider

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def context_for_locator(self, root):
                return FakeContext(self.reconsider)

        reconsider = FakeReconsider()
        paths = tuple(
            f"src/file-{index}.py" for index in range(hooks.HOOK_DIAGNOSTIC_LIMIT + 3)
        )
        with (
            mock.patch.object(hooks, "repo_map", return_value={"/repo": "/repo"}),
            mock.patch(
                "span.shell.installation_runtime.open_installation_runtime",
                return_value=FakeInstallation(reconsider),
            ),
        ):
            repository_id, projection = hooks._affected_for_root(
                "/data", "/repo", paths
            )

        self.assertEqual(repository_id, "repo")
        self.assertIsNotNone(projection)
        self.assertEqual(reconsider.requests[0].changed_paths, paths)

    def test_stdin_path_parser_does_not_silently_cap_changed_scope(self):
        payload = [
            {"file_path": f"/repo/src/file-{index}.py"}
            for index in range(hooks.HOOK_DIAGNOSTIC_LIMIT * 5)
        ]
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            paths = hooks._stdin_paths()
        self.assertEqual(len(paths), len(payload))
        self.assertEqual(paths[-1], payload[-1]["file_path"])

    def test_codex_apply_patch_parser_uses_only_documented_patch_markers(self):
        command = """*** Begin Patch
*** Update File: src/a.py
*** Move to: src/moved.py
*** Add File: src/new.py
*** Delete File: src/old.py
*** End Patch
"""
        self.assertEqual(
            hooks._codex_apply_patch_paths(command),
            ("src/a.py", "src/moved.py", "src/new.py", "src/old.py"),
        )
        self.assertIsNone(
            hooks._codex_apply_patch_paths("*** Begin Patch\n*** End Patch")
        )

    def test_codex_post_tool_emits_structured_context_for_complete_native_scope(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {
                "command": (
                    "*** Begin Patch\n"
                    "*** Update File: src/a.py\n"
                    "*** Add File: src/b.py\n"
                    "*** End Patch\n"
                )
            },
        }
        observed = []

        def project(_data_dir, paths):
            observed.append(tuple(paths))
            return ("span: repo needs attention; call reconsider after editing.",)

        with (
            mock.patch("sys.stdin", io.StringIO(json.dumps(payload))),
            mock.patch.object(hooks, "_source_change_notices", side_effect=project),
        ):
            output = _capture(hooks.cmd_codex_post_tool, "/data", "/repo")

        result = json.loads(output)
        self.assertEqual(observed, [("/repo/src/a.py", "/repo/src/b.py")])
        self.assertEqual(
            result["hookSpecificOutput"]["hookEventName"],
            "PostToolUse",
        )
        self.assertIn(
            "call reconsider after editing",
            result["hookSpecificOutput"]["additionalContext"],
        )

    def test_codex_post_tool_reports_incomplete_native_scope_without_guessing(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": "not an apply_patch document"},
        }
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            output = _capture(hooks.cmd_codex_post_tool, "/data", "/repo")

        result = json.loads(output)
        self.assertIn(
            "could not normalize the complete changed scope",
            result["hookSpecificOutput"]["additionalContext"],
        )

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

    def test_functional_pyramid_unconfigured_notice_routes_to_skill(self):
        status = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.UNCONFIGURED
        )
        with mock.patch.object(
            hooks, "_functional_pyramid_status", return_value=status
        ):
            notice = hooks._functional_pyramid_notice(
                "/tmp/data",
                {"/tmp/hooks-repo": "/tmp/hooks-repo"},
                "/tmp/hooks-repo",
            )
        self.assertIsNotNone(notice)
        assert notice is not None
        self.assertIn("UNCONFIGURED", notice)
        self.assertIn("span-functional-pyramid", notice)

    def test_functional_pyramid_excluded_notice_is_silent(self):
        status = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.EXCLUDED
        )
        with mock.patch.object(
            hooks, "_functional_pyramid_status", return_value=status
        ):
            notice = hooks._functional_pyramid_notice(
                "/tmp/data",
                {"/tmp/hooks-repo": "/tmp/hooks-repo"},
                "/tmp/hooks-repo",
            )
        self.assertIsNone(notice)

    def test_functional_pyramid_active_valid_notice_is_silent(self):
        status = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=m.FunctionalPyramidHealth.VALID,
            pyramid_id=m.FunctionalPyramidId("fp-hooks"),
            version=m.FunctionalPyramidVersion(1),
            members=(
                m.FunctionalPyramidMemberView(
                    repository_id=REPO,
                    declaration_refs=(
                        m.EvidenceRef(
                            evidence_id=m.EvidenceId("fp-declaration"),
                            repository_id=REPO,
                            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                            locator="docs/functional-pyramid.json",
                        ),
                    ),
                    functional_scope=m.FunctionalScope(
                        (
                            m.FunctionalScopeSelector(
                                m.FunctionalScopeSelectorKind.PREFIX,
                                path="src",
                            ),
                        )
                    ),
                    coverage=m.FunctionalPyramidCoverage.PARTIAL,
                ),
            ),
        )
        with mock.patch.object(
            hooks, "_functional_pyramid_status", return_value=status
        ):
            notice = hooks._functional_pyramid_notice(
                "/tmp/data",
                {"/tmp/hooks-repo": "/tmp/hooks-repo"},
                "/tmp/hooks-repo",
            )
        self.assertIsNone(notice)

    def test_functional_pyramid_active_degraded_notice_routes_to_lifecycle(self):
        finding = m.FunctionalPyramidFinding(
            reason=m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            repository_id=REPO,
            detail="repository unavailable",
            recovery="restore repository availability",
        )
        status = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=m.FunctionalPyramidHealth.DEGRADED,
            pyramid_id=m.FunctionalPyramidId("fp-hooks"),
            version=m.FunctionalPyramidVersion(1),
            members=(
                m.FunctionalPyramidMemberView(
                    repository_id=REPO,
                    declaration_refs=(
                        m.EvidenceRef(
                            evidence_id=m.EvidenceId("fp-declaration"),
                            repository_id=REPO,
                            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                            locator="docs/functional-pyramid.json",
                        ),
                    ),
                    functional_scope=m.FunctionalScope(
                        (
                            m.FunctionalScopeSelector(
                                m.FunctionalScopeSelectorKind.PREFIX,
                                path="src",
                            ),
                        )
                    ),
                    coverage=m.FunctionalPyramidCoverage.PARTIAL,
                ),
            ),
            findings=(finding,),
        )
        with mock.patch.object(
            hooks, "_functional_pyramid_status", return_value=status
        ):
            notice = hooks._functional_pyramid_notice(
                "/tmp/data",
                {"/tmp/hooks-repo": "/tmp/hooks-repo"},
                "/tmp/hooks-repo",
            )
        self.assertIsNotNone(notice)
        assert notice is not None
        self.assertIn("ACTIVE/DEGRADED", notice)
        self.assertIn("FunctionalPyramidSelector", notice)
        self.assertIn("span-functional-pyramid", notice)

    def test_hook_source_uses_canonical_changed_scope_projection(self):
        source = pathlib.Path(hooks.__file__).read_text(encoding="utf-8")
        self.assertIn("preview_changed_scope", source)
        self.assertNotIn("source_observation_ids_for_locator", source)
        self.assertNotIn('support_dependents("SOURCE"', source)

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
