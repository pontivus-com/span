"""HOOK_FAST: bounded work, hook bounds, no continuations.

A lifecycle hook runs on every source change, so its cost must be a function of
the page it reports on, not of the scope the editor happens to be in. The hook
resolves one frontier page under ``hook_fast_bounds`` and classifies only that
page; it never allocates a continuation, so the remainder is deliberately
unseen (I-32 silence).
"""

import unittest
from unittest import mock

from span import service as ops
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.core import model as m
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
)

REPO = "hook-fixture"
COUNT = 20
DEFAULT_HOOK_SUBJECTS = DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds.max_subjects


def _files() -> dict[str, str]:
    return {f"big/f{index}.py": f"v{index} = {index}\n" for index in range(COUNT)}


def _harness():
    files = _files()
    subjects = tuple(
        InMemorySubject(locator, m.SubjectKind.COMPONENT, locator) for locator in files
    )
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(path, text) for path, text in files.items()),
        subjects,
        (InMemoryEdge("big/f0.py", m.StructuralEdgeKind.REFERENCES, "big/f1.py"),),
    )
    evidence = FixtureEvidenceSource(REPO, dict(files))
    store = SqliteSemanticStore(":memory:")
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


class HookBoundednessTest(unittest.TestCase):
    def test_scope_wide_hook_classifies_only_one_page(self):
        structural, evidence, store = _harness()
        try:
            calls = []
            from span.service.operations import status as status_module

            original = status_module._load_subject_state

            def _counting(*args, **kwargs):
                calls.append(args[1] if len(args) > 1 else kwargs.get("subject_id"))
                return original(*args, **kwargs)

            with mock.patch.object(
                status_module, "_load_subject_state", side_effect=_counting
            ):
                notice = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.EvidenceScope(paths=("big",), evidence_refs=()),
                        mode=m.StatusMode.HOOK_FAST,
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertLessEqual(
                len(set(calls)),
                DEFAULT_HOOK_SUBJECTS,
                "the hook classified more subjects than its page holds",
            )
            self.assertGreater(len(set(calls)), 0)
        finally:
            store.close()

    def test_hook_bounds_are_not_the_normal_bounds(self):
        """A caller-supplied large bound cannot widen a hook."""
        structural, evidence, store = _harness()
        try:
            calls = []
            from span.service.operations import status as status_module

            original = status_module._load_subject_state

            def _counting(*args, **kwargs):
                calls.append(1)
                return original(*args, **kwargs)

            with mock.patch.object(
                status_module, "_load_subject_state", side_effect=_counting
            ):
                ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.EvidenceScope(paths=("big",), evidence_refs=()),
                        mode=m.StatusMode.HOOK_FAST,
                        bounds=m.QueryBounds(
                            max_results=250,
                            max_depth=6,
                            max_subjects=32,
                            max_evidence_units=96,
                            max_evidence_bytes=384_000,
                            max_candidate_claims=256,
                            max_candidate_relationships=256,
                        ),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
            self.assertLessEqual(len(calls), DEFAULT_HOOK_SUBJECTS)
        finally:
            store.close()

    def test_hook_never_allocates_a_continuation(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            with mock.patch.object(
                continuations, "pend", side_effect=AssertionError("hook suspended")
            ):
                notice = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.EvidenceScope(paths=("big",), evidence_refs=()),
                        mode=m.StatusMode.HOOK_FAST,
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            self.assertIsInstance(notice, m.HookStatusNotice)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
