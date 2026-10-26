"""Phase 3 operation tests (plan §11.5/§11.6/§11.8, §11.5.1, §11.9,
F-13/F-14/F-15).

Deterministic throughout; the FixtureAgent stands in for the invoking
agent. Covers trace frontier/direction/filter/boundary/suspend,
status NORMAL/HOOK_FAST/read-only proof, impact brief completeness and
the ChangeCondition derivation table, and truncation tokens.
"""

import unittest
from unittest import mock

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span import service as ops
from span.service.answers import _select_answer_items
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.evidence import FixtureEvidenceSource
from span.core import paging as _paging
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

from tests.support.agent_exchange import (
    FILES,
    REPO,
    _bounds,
    _exchange,
    _harness,
    _ref,
    _seeds,
    _sid,
)

from tests.support.factories import query_bounds, semantic_harness

from tests.support.factories import subject_id

from tests.support.factories import evidence_ref


def _trace_request(**overrides):
    base = dict(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/flow.py", (), None),
        direction=StructuralDirection.BOTH,
        relationship_filter=None,
        boundary_only=False,
        bounds=_bounds(),
    )
    base.update(overrides)
    return ops.SemanticTraceRequest(**base)


def _impact_request(kind=ops.ChangeKind.BEHAVIOR, description=None, affected=()):
    return ops.SemanticImpactRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/flow.py", (), None),
        change_kind=kind,
        change_description=description,
        bounds=_bounds(),
        affected_assertions=tuple(affected),
    )


class TraceTest(unittest.TestCase):
    def test_truncated_trace_returns_no_dead_token(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _trace_request(bounds=_bounds(max_results=1, max_subjects=1)),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            self.assertTrue(answer.bound_info.truncated)
            # A truncated trace is signposted, never handed a token its
            # own operation cannot redeem (Addendum M §M-06).
            self.assertIsNone(answer.bound_info.continuation_token)
        finally:
            store.close()

    def test_frontier_rels_edges_context(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _trace_request(),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            content = answer.content
            self.assertIsInstance(content, m.TraceContent)
            kinds = {r.kind for r in content.relationships}
            self.assertIn(m.RelationshipKind.CROSSES_BOUNDARY, kinds)
            self.assertIn(m.RelationshipKind.VERIFIED_BY, kinds)
            self.assertTrue(content.structural_edges)
            # F-14 lifecycle representation in lifecycle context.
            self.assertTrue(content.lifecycle_context)
        finally:
            store.close()

    def test_direction_filters_traversal(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _trace_request(direction=StructuralDirection.UPSTREAM),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            # UPSTREAM from flow.py: only relationships pointing at flow
            # (direction-true traversal); structural routes stay possible.
            self.assertIsInstance(answer.content, m.TraceContent)
            self.assertEqual(
                {r.kind for r in answer.content.relationships},
                {m.RelationshipKind.VERIFIED_BY},
            )
            self.assertTrue(answer.content.structural_edges)
        finally:
            store.close()

    def test_relationship_filter_and_boundary_only(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _trace_request(relationship_filter=(m.RelationshipKind.VERIFIED_BY,)),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            kinds = {r.kind for r in answer.content.relationships}
            self.assertEqual(kinds, {m.RelationshipKind.VERIFIED_BY})
            bounded = _exchange(
                _trace_request(boundary_only=True),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            bkinds = {r.kind for r in bounded.content.relationships}
            self.assertEqual(bkinds, {m.RelationshipKind.CROSSES_BOUNDARY})
        finally:
            store.close()

    def test_trace_suspends_for_missing_frontier(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.trace(
                _trace_request(),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=_seeds(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()


def _status_request(**overrides):
    base = dict(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/flow.py", (), None),
        bounds=_bounds(),
    )
    base.update(overrides)
    return ops.SemanticStatusRequest(**base)


class StatusTest(unittest.TestCase):

    def test_page_token_rejects_changed_listing_arguments(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "contract/api", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            first = ops.status(
                _status_request(target=None, bounds=_bounds(max_subjects=1)),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            token = first.bound_info.continuation_token
            self.assertIsNotNone(token)
            with self.assertRaises(ValueError):
                ops.status(
                    _status_request(
                        target=None,
                        bounds=_bounds(max_subjects=2),
                        page_token=token,
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_normal_full_answer(self):
        structural, evidence, store, agent = _harness()
        try:
            # S2 observational: establish via explain first, then status
            # reads back without suspending.
            from span import service as _ops

            _explain_req = _ops.SemanticExplainRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/flow.py", (), None),
                bounds=_bounds(),
            )
            _exchange(
                _explain_req,
                _ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            answer = _exchange(
                _status_request(),
                ops.status,
                structural,
                evidence,
                store,
                agent,
            )
            content = answer.content
            self.assertIsInstance(content, m.StatusContent)
            self.assertTrue(content.freshness_items)
            # F-15: candidate and current-pass verification distinguished.
            currencies = {v.currency for v in content.verification_status}
            # F7: without an execution record, an attested link never
            # becomes a published pass.
            self.assertEqual(currencies, {m.DerivedCurrency.UNKNOWN})
            self.assertEqual(content.refresh_scope.paths, ())
        finally:
            store.close()

    def test_status_projects_first_time_live_question_without_token(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=_seeds(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.status(
                _status_request(),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertTrue(
                any(
                    "CQ_01" in requirement.description
                    and "live explain" in requirement.description
                    and "continuation returned" in requirement.description
                    for requirement in answer.resolution_requirements
                )
            )
            self.assertNotIn(
                pending.continuation,
                " ".join(
                    requirement.description
                    for requirement in answer.resolution_requirements
                ),
            )
            report = answer.content.coverage_report
            self.assertIsNotNone(report)
            entry = next(
                entry
                for entry in report.page.entries
                if entry.subject.canonical_locator == "src/flow.py"
            )
            self.assertIs(
                entry.disposition,
                m.SemanticCoverageDisposition.UNASSESSED,
            )
            entry_descriptions = " ".join(
                requirement.description
                for requirement in answer.resolution_requirements
                if requirement.subject_or_claim == entry.subject
            )
            self.assertIn("live explain", entry_descriptions)
            self.assertNotIn("run question-local explain", entry_descriptions)
        finally:
            store.close()

    def test_ambiguous_selector_returns_canonical_candidates(self):
        structural = InMemoryStructuralSource(
            REPO,
            (InMemoryFile("a.py", "x\n"), InMemoryFile("b.py", "y\n")),
            (
                InMemorySubject("a.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
                InMemorySubject("b.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
            ),
        )
        evidence = FixtureEvidenceSource(REPO, {"a.py": "x\n", "b.py": "y\n"})
        store = SqliteSemanticStore(":memory:")
        try:
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
            answer = ops.status(
                _status_request(target=m.SubjectSelector(None, "dup", (), None)),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsNotNone(answer.subject_resolution)
            self.assertIs(
                answer.subject_resolution.ambiguity,
                m.ResolutionAmbiguity.AMBIGUOUS,
            )
            self.assertEqual(
                {
                    candidate.subject.subject_id.canonical_locator
                    for candidate in answer.subject_resolution.candidates
                },
                {"a.py#dup", "b.py#dup"},
            )
            requirement = next(
                requirement
                for requirement in answer.resolution_requirements
                if requirement.kind is m.ResolutionKind.AMBIGUOUS_IDENTITY
            )
            self.assertIn("2 subjects match", requirement.description)
        finally:
            store.close()

    def test_ready_qualifier_is_separate_from_semantic_coverage(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(answer.content.store_readiness, m.StoreReadiness.READY)
            self.assertTrue(
                answer.state_explanation[0].startswith(
                    "repository store_readiness: READY means the Span semantic store"
                )
            )
            self.assertIn("reported separately", answer.state_explanation[0])
            coverage_line = next(
                line
                for line in answer.state_explanation
                if line.startswith("semantic coverage (")
            )
            for token in (
                "current",
                "incomplete",
                "stale",
                "unverifiable",
                "unassessed subjects",
                "persisted pending",
                "persisted open",
            ):
                self.assertIn(token, coverage_line)
        finally:
            store.close()

    def test_status_explanation_names_target_and_missing_authority(self):
        from span.service.operations.status import _status_state_explanation

        content = m.StatusContent(
            store_readiness=m.StoreReadiness.READY,
            target_disposition=m.SemanticCoverageDisposition.INCOMPLETE,
        )
        requirements = (
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=None,
                description="governing authority not recorded",
                supporting_context=(),
            ),
        )
        lines = _status_state_explanation((), content, requirements)
        self.assertTrue(
            any(line.startswith("target disposition: INCOMPLETE") for line in lines)
        )
        self.assertTrue(
            any("governing authority remains unresolved" in line for line in lines)
        )

    def test_absent_source_reads_unverifiable(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            evidence._files.pop("src/flow.py", None)
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            entry = next(
                entry
                for entry in answer.content.coverage_report.page.entries
                if entry.subject.canonical_locator == "src/flow.py"
            )
            self.assertIs(
                entry.disposition,
                m.SemanticCoverageDisposition.UNVERIFIABLE,
            )
            self.assertTrue(
                any(
                    "absent from the evidence inventory" in requirement.description
                    for requirement in answer.resolution_requirements
                    if requirement.subject_or_claim == entry.subject
                )
            )
        finally:
            store.close()

    def test_store_failure_reading_coverage_is_an_error(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )

            def boom(*args, **kwargs):
                raise RuntimeError("store read failed")

            store.load_coverage_dependencies = boom
            with self.assertRaises(RuntimeError):
                ops.status(
                    _status_request(target=None),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_provider_failure_capturing_snapshot_is_an_error(self):

        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            from span.service.operations.status import coverage as status_coverage

            with mock.patch.object(
                status_coverage,
                "_coverage_scope_snapshots",
                side_effect=RuntimeError("provider down"),
            ):
                with self.assertRaises(RuntimeError):
                    ops.status(
                        _status_request(target=None),
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=ContinuationStore(),
                    )
        finally:
            store.close()

    def test_inventory_failure_is_not_reported_as_absent_source(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )

            def boom(*args, **kwargs):
                raise RuntimeError("evidence provider down")

            evidence.inventory_evidence = boom
            with self.assertRaises(RuntimeError):
                ops.status(
                    _status_request(target=None),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_store_failure_reading_target_association_is_an_error(self):
        structural, evidence, store, agent = _harness()
        try:

            def boom(*args, **kwargs):
                raise RuntimeError("store read failed")

            store.load_target_association = boom
            with self.assertRaises(RuntimeError):
                ops.status(
                    _status_request(target=m.TargetId("tgt-missing")),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_none_target_reports_empty_persisted_frontier(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsInstance(answer.content, m.StatusContent)
            self.assertEqual(answer.content.freshness_items, ())
            report = answer.content.coverage_report
            self.assertIsNotNone(report)
            self.assertEqual(report.repository.persisted_subject_count, 0)
            self.assertEqual(report.page.entries, ())
        finally:
            store.close()

    def test_none_target_projects_first_time_live_question(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=_seeds(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertTrue(
                any(
                    "live explain" in requirement.description
                    for requirement in answer.resolution_requirements
                )
            )
            self.assertNotIn(
                pending.continuation,
                " ".join(
                    requirement.description
                    for requirement in answer.resolution_requirements
                ),
            )
        finally:
            store.close()

    def test_none_target_reports_persisted_frontier_states(self):
        structural, evidence, store, agent = _harness()
        try:
            from span import service as _ops

            _exchange(
                _ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                _ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            unassessed = _sid("persisted/unassessed")
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(unassessed, "Unassessed", None),)
                )
            )
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            report = answer.content.coverage_report
            self.assertIsNotNone(report)
            self.assertGreater(report.repository.persisted_subject_count, 0)
            self.assertGreater(report.page.returned_subject_count, 0)
            flow = next(
                entry
                for entry in report.page.entries
                if entry.subject.canonical_locator == "src/flow.py"
            )
            self.assertGreater(flow.semantic_item_count, 0)
            self.assertGreater(flow.question_count, 0)
            self.assertIn(
                flow.disposition,
                {
                    m.SemanticCoverageDisposition.CURRENT,
                    m.SemanticCoverageDisposition.INCOMPLETE,
                    m.SemanticCoverageDisposition.STALE,
                    m.SemanticCoverageDisposition.UNVERIFIABLE,
                },
            )
            self.assertTrue(
                any(
                    entry.disposition is m.SemanticCoverageDisposition.UNASSESSED
                    for entry in report.page.entries
                )
            )
        finally:
            store.close()

    def test_non_current_entries_carry_actionable_requirements(self):
        from span.service.operations.status import (
            _repository_coverage_entry,
        )

        structural, evidence, store, agent = _harness()
        try:
            from span import service as _ops

            _exchange(
                _ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                _ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            unassessed = _sid("persisted/unassessed")
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(unassessed, "Unassessed", None),)
                )
            )
            subjects = store.load_subjects(
                REPO,
                (unassessed,),
            )
            entry, requirements = _repository_coverage_entry(
                REPO,
                subjects[0],
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                entry.disposition,
                m.SemanticCoverageDisposition.UNASSESSED,
            )
            self.assertTrue(requirements)
        finally:
            store.close()

    def test_repository_entries_order_within_page(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                _status_request(),
                ops.status,
                structural,
                evidence,
                store,
                agent,
            )
            answer = ops.status(
                _status_request(target=None),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            entries = answer.content.coverage_report.page.entries
            rank = {
                m.SemanticCoverageDisposition.STALE: 0,
                m.SemanticCoverageDisposition.UNVERIFIABLE: 1,
                m.SemanticCoverageDisposition.INCOMPLETE: 2,
                m.SemanticCoverageDisposition.UNASSESSED: 3,
                m.SemanticCoverageDisposition.CURRENT: 4,
            }
            keys = [
                (
                    rank[e.disposition],
                    -e.open_question_count,
                    -e.pending_question_count,
                    e.subject.canonical_locator,
                    e.subject.subject_kind.value,
                )
                for e in entries
            ]
            self.assertEqual(keys, sorted(keys))
        finally:
            store.close()

    def test_none_target_report_paginates_persisted_subjects(self):
        structural, evidence, store, agent = _harness()
        try:
            # S2 observational: establish via explain first; status only
            # reads back persisted subjects.
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "contract/api", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            bounds = _bounds(max_subjects=1)
            first = ops.status(
                _status_request(target=None, bounds=bounds),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertTrue(first.bound_info.truncated)
            token = first.bound_info.continuation_token
            self.assertIsNotNone(token)
            _digest, _c, _r, _q = _paging.parse_question_token(token)
            self.assertNotEqual(_digest, "default")
            self.assertEqual((_c, _r, _q), (1, 0, 0))
            second = ops.status(
                _status_request(
                    target=None,
                    bounds=bounds,
                    page_token=token,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertNotEqual(
                first.content.coverage_report.page.entries,
                second.content.coverage_report.page.entries,
            )
        finally:
            store.close()

    def test_uninitialized_never_bootstraps(self):
        from span.shell.sqlite_store import SqliteSemanticStore as _Store

        structural, evidence, _, _ = _harness()
        store = _Store(":memory:")
        try:
            # No initialize call: every query path reports setup state
            # without starting initialization implicitly.
            answer = ops.status(
                _status_request(),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(
                answer.content.store_readiness,
                m.StoreReadiness.UNINITIALIZED,
            )
            self.assertTrue(
                any(
                    "initialize_repository" in r.description
                    for r in answer.resolution_requirements
                )
            )
            notice = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                    mode=m.StatusMode.HOOK_FAST,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(notice.store_readiness, m.StoreReadiness.UNINITIALIZED)
            self.assertIn("initialize_repository", notice.recommended_action)
            # Still uninitialized: nothing was bootstrapped.
            self.assertIsNone(store.load_repository_state(REPO))
            explained = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(explained, m.SemanticAnswer)
            self.assertEqual(explained.content.claims, ())
        finally:
            store.close()

    def test_unknown_claim_ref_target_rejected(self):
        structural, evidence, store, agent = _harness()
        try:
            with self.assertRaises(ops.StatusTargetError):
                ops.status(
                    _status_request(target=m.ClaimRef(id=m.ClaimId("c-1"))),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_known_claim_ref_target_served(self):
        structural, evidence, store, agent = _harness()
        try:
            # S2 observational: establish via explain first, then status
            # reads back without suspending.
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            indexed = _exchange(
                _status_request(),
                ops.status,
                structural,
                evidence,
                store,
                agent,
            )
            self.assertTrue(indexed.content.claims)
            target = m.ClaimRef(id=indexed.content.claims[0].claim_id)
            answer = ops.status(
                _status_request(target=target),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsInstance(answer.content, m.StatusContent)
            carried = {c.claim_id.value for c in answer.content.claims}
            self.assertIn(target.id.value, carried)
        finally:
            store.close()

    def test_status_declares_which_mode_answered(self):
        structural, evidence, store, agent = _harness()
        try:
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            cases = (
                (None, m.StatusResolvedMode.REPOSITORY),
                (
                    m.SubjectSelector(None, "src/flow.py", (), None),
                    m.StatusResolvedMode.SCOPED,
                ),
                (
                    m.EvidenceScope(paths=("src",), evidence_refs=()),
                    m.StatusResolvedMode.SCOPED,
                ),
            )
            for target, expected in cases:
                answer = ops.status(
                    _status_request(target=target),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(answer, m.SemanticAnswer)
                self.assertIs(answer.content.resolved_mode, expected, target)
        finally:
            store.close()

    def test_expired_campaign_handle_names_the_recovery(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = ops.status(
                _status_request(target=m.TargetId("tgt-never-existed")),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIs(answer.content.resolved_mode, m.StatusResolvedMode.CAMPAIGN)
            self.assertIs(
                answer.content.target_disposition,
                m.SemanticCoverageDisposition.UNASSESSED,
            )
            self.assertTrue(answer.resolution_requirements)
            description = " ".join(
                requirement.description
                for requirement in answer.resolution_requirements
            )
            self.assertIn("unknown or expired", description)
            self.assertIn("initialize_target", description)
        finally:
            store.close()

    def test_hook_fast_read_only_proof(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            # S2 observational: establish via explain first so later
            # readback observes persisted coverage, not synthesis.
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            _exchange(
                _status_request(),
                ops.status,
                structural,
                evidence,
                store,
                agent,
                continuations=continuations,
            )
            changed = dict(FILES)
            changed["src/flow.py"] = "class Pipe:\n    pass\n    # touched\n"
            evidence_v2 = FixtureEvidenceSource(REPO, changed)
            notice = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                    mode=m.StatusMode.HOOK_FAST,
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(notice.store_readiness, m.StoreReadiness.READY)
            self.assertGreater(notice.stale_count, 0)
            self.assertTrue(notice.recommended_action)
            self.assertIn("exact SubjectSelector", notice.recommended_action)
            self.assertIn("src/flow.py", notice.recommended_action)
            self.assertNotIn("cont-", notice.recommended_action)
            # Read-only proof: the store still shows CURRENT (no mark).
            page = store.load_claims(REPO, (_sid("src/flow.py"),), (), _bounds())
            current = [c for c in page.items if c.kind is m.ClaimKind.PURPOSE]
            self.assertTrue(current)
            self.assertTrue(
                all(c.freshness.state is m.FreshnessState.CURRENT for c in current)
            )
        finally:
            store.close()

    def test_hook_fast_none_is_baseline_only(self):
        structural, evidence, store, agent = _harness()
        try:
            notice = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=None,
                    bounds=_bounds(),
                    mode=m.StatusMode.HOOK_FAST,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertEqual(notice.affected_count, 0)
        finally:
            store.close()


class SelectionAtomicityTest(unittest.TestCase):
    def _claim(self, cid, owner):
        return m.SemanticClaim(
            claim_id=m.ClaimId(cid),
            subject=_sid("src/flow.py"),
            kind=m.ClaimKind.OWNERSHIP_CUSTODY,
            assertion_nature=m.AssertionNature.NORMATIVE,
            value=m.OwnershipCustodyValue(
                _sid(owner),
                m.OwnershipRole.OWNER,
                m.OwnershipExclusivity.EXCLUSIVE,
            ),
            evidence=(_ref("OWNERSHIP.md"),),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )

    def test_conflict_pairs_never_split(self):
        a = self._claim("c-a", "team/a")
        b = self._claim("c-b", "team/b")
        filler = tuple(
            m.SemanticClaim(
                claim_id=m.ClaimId(f"c-{n}"),
                subject=_sid("src/flow.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue(f"s{n}", ()),
                evidence=(_ref("README.md"),),
                trust=m.TrustState.UNRESOLVED,
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            for n in range(4)
        )
        claims = (a, b) + filler
        conflicts = (
            m.SemanticConflict(
                left=m.ClaimRef(id=a.claim_id),
                right=m.ClaimRef(id=b.claim_id),
            ),
        )
        for budget in range(1, 8):
            with self.subTest(budget=budget):
                kept_c, kept_r, kept_conf, truncated, _ = _select_answer_items(
                    claims, (), conflicts, budget
                )
                kept_ids = {c.claim_id.value for c in kept_c}
                for pair in kept_conf:
                    self.assertIn(pair.left.id.value, kept_ids)
                    self.assertIn(pair.right.id.value, kept_ids)


class ImpactTest(unittest.TestCase):
    def _indexed(self):
        structural, evidence, store, agent = _harness()
        answer = _exchange(
            _impact_request(),
            ops.impact,
            structural,
            evidence,
            store,
            agent,
        )
        return structural, evidence, store, agent, answer

    def _refs_for(self, answer, kinds):
        refs = []
        for claim in answer.content.claims:
            if claim.kind in kinds:
                refs.append(m.ClaimRef(id=claim.claim_id))
        for rel in answer.content.relationships:
            if rel.kind in kinds:
                refs.append(m.RelationshipRef(id=rel.relationship_id))
        return refs

    def test_brief_completeness(self):
        structural, evidence, store, agent, first = self._indexed()
        try:
            content = first.content
            self.assertIsInstance(content, m.ImpactContent)
            # Identity/purpose context present (carried canonical items).
            self.assertTrue(content.target_context)
            self.assertTrue(content.claims)
            # Proposal-sensitive rows need typed affected assertions:
            # name the invariant, an accepted authority claim, and the
            # boundary relationship explicitly (plan I-38).
            affected = (
                self._refs_for(first, {m.ClaimKind.INVARIANT_CONSTRAINT})
                + [
                    ref
                    for ref in self._refs_for(
                        first,
                        {
                            m.ClaimKind.PURPOSE,
                            m.ClaimKind.OWNERSHIP_CUSTODY,
                        },
                    )[:1]
                ]
                + self._refs_for(first, {m.RelationshipKind.CROSSES_BOUNDARY})
            )
            self.assertTrue(affected)
            answer = _exchange(
                _impact_request(affected=affected),
                ops.impact,
                structural,
                evidence,
                store,
                agent,
            )
            conds = set(answer.content.change_conditions)
            self.assertIn(m.ChangeCondition.AUTHORITY_CHANGE, conds)
            self.assertIn(m.ChangeCondition.BOUNDARY_CHANGE, conds)
            self.assertIn(m.ChangeCondition.INVARIANT_CHANGE, conds)
            # Both establishment classes present.
            establishments = {i.establishment for i in answer.content.impacts}
            self.assertIn(
                m.ImpactEstablishment.SEMANTICALLY_ESTABLISHED, establishments
            )
            self.assertIn(m.ImpactEstablishment.STRUCTURAL_POSSIBILITY, establishments)
            # Verification + requirements present; refs resolve in-answer.
            self.assertTrue(answer.content.verification)
            carried = {c.claim_id.value for c in answer.content.claims} | {
                r.relationship_id.value for r in answer.content.relationships
            }
            for ref in list(answer.content.target_context) + list(
                answer.content.verification
            ):
                self.assertIn(ref.id.value, carried)
            self.assertTrue(
                any(
                    r.kind is m.ResolutionKind.MISSING_AUTHORITY
                    for r in answer.resolution_requirements
                )
            )
        finally:
            store.close()

    def test_proposal_rows_need_typed_assertions(self):
        structural, evidence, store, agent, first = self._indexed()
        try:
            bare = set(first.content.change_conditions)
            self.assertNotIn(m.ChangeCondition.INVARIANT_CHANGE, bare)
            self.assertNotIn(m.ChangeCondition.AUTHORITY_CHANGE, bare)
            self.assertNotIn(m.ChangeCondition.BOUNDARY_CHANGE, bare)
            invariant = self._refs_for(first, {m.ClaimKind.INVARIANT_CONSTRAINT})
            self.assertTrue(invariant)
            named = _exchange(
                _impact_request(affected=invariant),
                ops.impact,
                structural,
                evidence,
                store,
                agent,
            )
            self.assertIn(
                m.ChangeCondition.INVARIANT_CHANGE,
                set(named.content.change_conditions),
            )
        finally:
            store.close()

    def test_change_kind_gates(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            by_kind = {}
            for kind in (
                ops.ChangeKind.OWNERSHIP,
                ops.ChangeKind.REPRESENTATION,
                ops.ChangeKind.CONFIGURATION,
                ops.ChangeKind.LIFECYCLE,
            ):
                answer = _exchange(
                    _impact_request(kind),
                    ops.impact,
                    structural,
                    evidence,
                    store,
                    agent,
                    continuations=continuations,
                )
                by_kind[kind] = set(answer.content.change_conditions)
            self.assertIn(
                m.ChangeCondition.OWNERSHIP_CHANGE,
                by_kind[ops.ChangeKind.OWNERSHIP],
            )
            self.assertIn(
                m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE,
                by_kind[ops.ChangeKind.REPRESENTATION],
            )
            self.assertIn(
                m.ChangeCondition.CONFIGURATION_CHANGE,
                by_kind[ops.ChangeKind.CONFIGURATION],
            )
            self.assertIn(
                m.ChangeCondition.LIFECYCLE_CHANGE,
                by_kind[ops.ChangeKind.LIFECYCLE],
            )
            other = _exchange(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    change_kind=ops.ChangeKind.OTHER,
                    change_description="swap helper",
                    bounds=_bounds(),
                ),
                ops.impact,
                structural,
                evidence,
                store,
                agent,
                continuations=continuations,
            )
            other_conds = set(other.content.change_conditions)
            # Pure kind-gated rows are suppressed under OTHER ...
            self.assertNotIn(m.ChangeCondition.OWNERSHIP_CHANGE, other_conds)
            self.assertNotIn(
                m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE,
                other_conds,
            )
            # ... proposal-sensitive rows need typed assertions ...
            self.assertNotIn(m.ChangeCondition.AUTHORITY_CHANGE, other_conds)
            self.assertNotIn(m.ChangeCondition.INVARIANT_CHANGE, other_conds)
            # ... but independently established presence dimensions apply.
            self.assertIn(m.ChangeCondition.CONFIGURATION_CHANGE, other_conds)
        finally:
            store.close()

    def test_public_contract_change(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "contract/api", (), None),
                    change_kind=ops.ChangeKind.BEHAVIOR,
                    change_description=None,
                    bounds=_bounds(),
                ),
                ops.impact,
                structural,
                evidence,
                store,
                agent,
            )
            self.assertIn(
                m.ChangeCondition.PUBLIC_CONTRACT_CHANGE,
                set(answer.content.change_conditions),
            )
        finally:
            store.close()

    def test_other_requires_description(self):
        structural, evidence, store, agent = _harness()
        try:
            with self.assertRaises(ValueError):
                ops.impact(
                    ops.SemanticImpactRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/flow.py", (), None),
                        change_kind=ops.ChangeKind.OTHER,
                        change_description=None,
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                    authority_seeds=_seeds(),
                )
        finally:
            store.close()

    def test_second_page_retrieval(self):
        """Pagination is explicit and redeemable (plan I-39).

        A bounded status over many claims returns a `pgv:` cursor;
        resubmitting it yields the remaining items with no repeats and
        no dangling references.
        """
        structural, evidence, store, agent = _harness()
        try:
            # S2 observational: establish via explain first so the
            # bounded status pages persisted claims.
            _exchange(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(),
                ),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            first = _exchange(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(max_results=4, max_subjects=4),
                ),
                ops.status,
                structural,
                evidence,
                store,
                agent,
            )
            token = first.bound_info.continuation_token
            self.assertTrue(first.bound_info.truncated)
            self.assertTrue(token.startswith("pgv:"))
            first_ids = {item.item.id.value for item in first.content.freshness_items}
            second = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(max_results=4, max_subjects=4),
                    page_token=token,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            second_ids = {item.item.id.value for item in second.content.freshness_items}
            self.assertFalse(first_ids & second_ids)
            self.assertTrue(second_ids)
            carried = {c.claim_id.value for c in second.content.claims} | {
                r.relationship_id.value for r in second.content.relationships
            }
            for item in second.content.freshness_items:
                self.assertIn(item.item.id.value, carried)
        finally:
            store.close()


class ContextualTraceTest(unittest.TestCase):
    """trace(path) reuses established CQ_04 execution context."""

    CTX = "ctx-trace"

    _bounds = staticmethod(query_bounds)

    def _establish_execution(self, store, files, canon, root, term):
        eref = evidence_ref(
            "canonical_assembly/candidate_packager.py",
            repository_id=self.CTX,
            files=files,
        )
        fp = fingerprint_content(files["canonical_assembly/candidate_packager.py"])
        claim = m.SemanticClaim(
            claim_id=m.ClaimId("c-purpose"),
            subject=canon,
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("packs", ()),
            evidence=(eref,),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )
        mem = m.SemanticRelationship(
            relationship_id=m.RelationshipId("r-mem"),
            source=canon,
            kind=m.RelationshipKind.MEMBER_OF,
            target=root,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(eref,),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )
        exec_rel = m.SemanticRelationship(
            relationship_id=m.RelationshipId("r-exec"),
            source=root,
            kind=m.RelationshipKind.PRODUCES,
            target=term,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(eref,),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )
        from span.service.questions import effective_trace_slice

        qslice = effective_trace_slice(
            root.canonical_locator,
            StructuralDirection.BOTH,
            None,
            False,
        )

        def _cov(subj, ref):
            q = m.SemanticQuestionScope(
                scope_root=root,
                subject=subj,
                question_class=m.SemanticQuestionClass.CQ_04,
                question_slice=qslice,
                materiality_basis="TRACE question-local",
            )
            return m.InterpretationCoverage(
                subjects=(subj,),
                question_slice=qslice,
                question=q,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(ref,),
                disposition_basis="b",
            )

        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=(
                    m.Subject(canon, "Canonical Assembly", None),
                    m.Subject(root, "Review Workflow", None),
                    m.Subject(term, "Terminal", None),
                ),
                claims=(claim,),
                relationships=(mem, exec_rel),
                evidence_dependencies=(
                    m.EvidenceDependency(m.ClaimRef(id=claim.claim_id), eref, fp),
                    m.EvidenceDependency(
                        m.RelationshipRef(id=mem.relationship_id), eref, fp
                    ),
                    m.EvidenceDependency(
                        m.RelationshipRef(id=exec_rel.relationship_id),
                        eref,
                        fp,
                    ),
                ),
                coverage=(
                    _cov(
                        root,
                        m.RelationshipRef(id=exec_rel.relationship_id),
                    ),
                    _cov(
                        term,
                        m.RelationshipRef(id=exec_rel.relationship_id),
                    ),
                    _cov(
                        canon,
                        m.RelationshipRef(id=mem.relationship_id),
                    ),
                ),
            )
        )
        return qslice

    def test_trace_path_starts_from_established_root(self):
        from span.service.requests import SemanticTraceRequest

        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT,
                "candidate_packager",
            ),
        )
        structural, evidence, store = semantic_harness(
            self.CTX, files, subjects=tuple(subjects)
        )
        try:
            canon = subject_id("canonical_assembly", repository_id=self.CTX)
            root = subject_id(
                "review_workflow", m.SubjectKind.SUBSYSTEM, repository_id=self.CTX
            )
            term = subject_id("terminal", repository_id=self.CTX)
            self._establish_execution(store, files, canon, root, term)
            answer = ops.trace(
                SemanticTraceRequest(
                    repository_id=self.CTX,
                    target=m.SubjectSelector(
                        None,
                        "canonical_assembly/candidate_packager.py",
                        (),
                        None,
                    ),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=self._bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(
                answer.subject_resolution.ambiguity,
                m.ResolutionAmbiguity.RESOLVED,
            )
            self.assertEqual(
                answer.subject_resolution.candidates[0].subject.subject_id,
                root,
            )
            kinds = {(r.source, r.kind) for r in answer.content.relationships}
            self.assertTrue(
                any(
                    src == root and kind is m.RelationshipKind.PRODUCES
                    for src, kind in kinds
                )
            )
            self.assertEqual(
                answer.subject_resolution.candidates[0].subject.subject_id,
                root,
            )
        finally:
            store.close()

    def test_leaf_coverage_never_becomes_root_coverage(self):
        from span.service.requests import SemanticTraceRequest

        files = {"canonical_assembly/candidate_packager.py": "x=1\n"}
        subjects = (
            InMemorySubject(
                "canonical_assembly/candidate_packager.py",
                m.SubjectKind.COMPONENT,
                "candidate_packager",
            ),
        )
        structural, evidence, store = semantic_harness(
            self.CTX, files, subjects=tuple(subjects)
        )
        try:
            canon = subject_id("canonical_assembly", repository_id=self.CTX)
            root = subject_id(
                "review_workflow", m.SubjectKind.SUBSYSTEM, repository_id=self.CTX
            )
            eref = evidence_ref(
                "canonical_assembly/candidate_packager.py",
                repository_id=self.CTX,
                files=files,
            )
            fp = fingerprint_content(files["canonical_assembly/candidate_packager.py"])
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("c-purpose"),
                subject=canon,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("packs", ()),
                evidence=(eref,),
                trust=m.TrustState.ESTABLISHED,
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            mem = m.SemanticRelationship(
                relationship_id=m.RelationshipId("r-mem"),
                source=canon,
                kind=m.RelationshipKind.MEMBER_OF,
                target=root,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                evidence=(eref,),
                trust=m.TrustState.ESTABLISHED,
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            from span.service.questions import effective_trace_slice

            leaf_slice = effective_trace_slice(
                canon.canonical_locator,
                StructuralDirection.BOTH,
                None,
                False,
            )
            leaf_q = m.SemanticQuestionScope(
                scope_root=canon,
                subject=canon,
                question_class=m.SemanticQuestionClass.CQ_04,
                question_slice=leaf_slice,
                materiality_basis="TRACE question-local",
            )
            leaf_cov = m.InterpretationCoverage(
                subjects=(canon,),
                question_slice=leaf_slice,
                question=leaf_q,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(m.RelationshipRef(id=mem.relationship_id),),
                disposition_basis="b",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(
                        m.Subject(canon, "Canonical Assembly", None),
                        m.Subject(root, "Review Workflow", None),
                    ),
                    claims=(claim,),
                    relationships=(mem,),
                    evidence_dependencies=(
                        m.EvidenceDependency(m.ClaimRef(id=claim.claim_id), eref, fp),
                        m.EvidenceDependency(
                            m.RelationshipRef(id=mem.relationship_id),
                            eref,
                            fp,
                        ),
                    ),
                    coverage=(leaf_cov,),
                )
            )
            pending = ops.trace(
                SemanticTraceRequest(
                    repository_id=self.CTX,
                    target=m.SubjectSelector(
                        None,
                        "canonical_assembly/candidate_packager.py",
                        (),
                        None,
                    ),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=self._bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertEqual(pending.request.question.scope_root, root)
            self.assertIs(
                pending.request.question.question_class,
                m.SemanticQuestionClass.CQ_04,
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
