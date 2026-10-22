"""Hook integration tests (plan Phase 4.9–4.10).

Pins the host-neutral contract, the Claude-style reference mapping,
hook-safe behavior (HOOK_FAST only; silence on irrelevance;
setup notice without implicit bootstrap), and read-only proof (hooks
never mark freshness or write semantic state).
"""

import pathlib
import unittest

from span.core import model as m
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

from integrations.hooks.contract import (
    HookIntent,
    hook_status_request,
    map_to_intent,
)
from integrations.hooks.hosts.claude.adapter import (
    EDIT_TOOLS,
    adapt_event,
    run_automatic_hook,
)

REPO = "hook-svc"

FILES = {
    "README.md": "# hook-svc\n\nHooks.\n",
    "src/main.py": "VALUE = 1\n",
}


def _bounds():
    return DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds


def _harness(initialized=True):
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        (InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    if initialized:
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                authority_seeds=(),
            ),
            repository_id=REPO,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    return structural, evidence, store


class ContractTest(unittest.TestCase):
    def test_intents(self):
        self.assertEqual(
            {i.value for i in HookIntent},
            {"SESSION_START", "SOURCE_CHANGED", "SESSION_STOP"},
        )

    def test_session_start_has_no_target(self):
        mapped = map_to_intent(HookIntent.SESSION_START)
        self.assertIsNone(mapped.target)

    def test_change_carries_scope(self):
        mapped = map_to_intent(
            HookIntent.SOURCE_CHANGED, ("src/main.py",)
        )
        self.assertIsInstance(mapped.target, m.EvidenceScope)
        self.assertEqual(mapped.target.paths, ("src/main.py",))

    def test_request_is_hook_fast_only(self):
        request = hook_status_request(
            REPO,
            map_to_intent(HookIntent.SESSION_START),
            _bounds(),
        )
        self.assertIs(request.mode, m.StatusMode.HOOK_FAST)


class ClaudeMappingTest(unittest.TestCase):
    def test_session_start(self):
        mapped = adapt_event({"hook": "SessionStart"})
        self.assertIs(mapped.intent, HookIntent.SESSION_START)
        self.assertIsNone(mapped.target)

    def test_post_edit_tools_map(self):
        for tool in sorted(EDIT_TOOLS):
            with self.subTest(tool=tool):
                mapped = adapt_event(
                    {
                        "hook": "PostToolUse",
                        "tool": tool,
                        "paths": ["src/main.py"],
                    }
                )
                self.assertIs(
                    mapped.intent, HookIntent.SOURCE_CHANGED
                )
                self.assertEqual(
                    mapped.target.paths, ("src/main.py",)
                )

    def test_non_edit_tool_is_silent(self):
        self.assertIsNone(
            adapt_event(
                {
                    "hook": "PostToolUse",
                    "tool": "Read",
                    "paths": ["src/main.py"],
                }
            )
        )

    def test_stop_maps(self):
        mapped = adapt_event(
            {"hook": "Stop", "paths": ["src/main.py"]}
        )
        self.assertIs(mapped.intent, HookIntent.SESSION_STOP)

    def test_unknown_hook_is_silent(self):
        self.assertIsNone(adapt_event({"hook": "Eclipse"}))
        self.assertIsNone(adapt_event({}))
        self.assertIsNone(adapt_event("nope"))


class HookSafetyTest(unittest.TestCase):
    def test_uninitialized_session_start_setup_notice(self):
        structural, evidence, store = _harness(initialized=False)
        try:
            notice = run_automatic_hook(
                {"hook": "SessionStart"},
                repository_id=REPO,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(
                notice.readiness, m.RepositoryReadiness.UNINITIALIZED
            )
            self.assertIn("initialize_repository",
                          notice.recommended_action)
            # No implicit bootstrap happened.
            self.assertIsNone(store.load_repository_state(REPO))
        finally:
            store.close()

    def test_irrelevant_change_is_silent(self):
        structural, evidence, store = _harness()
        try:
            notice = run_automatic_hook(
                {
                    "hook": "PostToolUse",
                    "tool": "Edit",
                    "paths": ["docs/notes.md"],
                },
                repository_id=REPO,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertEqual(notice.affected_count, 0)
            self.assertIsNone(notice.recommended_action)
        finally:
            store.close()

    def test_session_stop_closure_classification(self):
        structural, evidence, store = _harness()
        try:
            notice = run_automatic_hook(
                {"hook": "Stop", "paths": []},
                repository_id=REPO,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(
                notice.readiness, m.RepositoryReadiness.READY
            )
        finally:
            store.close()

    def test_adapter_calls_only_hook_fast_status(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        source = (
            root / "integrations" / "hooks" / "hosts" / "claude"
            / "adapter.py"
        ).read_text(encoding="utf-8")
        self.assertIn("HOOK_FAST", source)
        self.assertIn("ops.status(", source)
        for forbidden in (
            "initialize_repository",
            "explain",
            "impact",
            "trace",
            "authority",
            "refresh",
            "submit_interpretation",
            "prepare_interpretation_task",
            "reissue_interpretation",
        ):
            self.assertNotIn(f"ops.{forbidden}(", source)


if __name__ == "__main__":
    unittest.main()
