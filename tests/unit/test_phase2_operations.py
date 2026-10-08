"""Phase 2 operation tests (plan §7 exchange, §6 discovery, §8 reuse,
§9 refresh, §11.1 init, §11.12 submit).

All deterministic; the FixtureAgent stands in for the invoking agent.
"""

import datetime
import unittest

from span.core import model as m
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service_operations as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


FILES = {
    "README.md": "# svc\n\nDoes things.\n",
    "src/main.py": "VALUE = 1\n",
}

SUBJECTS = (
    InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),
)


def _sid():
    return m.SubjectId(
        repository_id="repo-1",
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator="src/main.py",
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose-main",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        value=m.PurposeValue("does things", ()),
        evidence=(_ref("README.md"), _ref("src/main.py")),
        candidate_authority=m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=_ref("README.md"),
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span="Does things",
                status_section="README.md",
                applicability_section=None,
            ),
        ),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the service purpose",
        ),
    )


def _agent():
    return FixtureAgent(
        {"src/main.py": FixtureCandidates((_candidate(),), ())}
    )


def _state():
    return m.RepositoryState(
        repository_id="repo-1", revision_id="r1", dirty=False,
        state_fingerprint="fp",
        observed_at=datetime.datetime(
            2026, 1, 1, tzinfo=datetime.timezone.utc
        ),
    )


def _bare_request():
    return m.SemanticInterpretationRequest(
        repository_id="repo-1",
        subjects=(m.Subject(_sid(), "main", None),),
        evidence_units=(),
        structural_observations=(),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(_sid(),),
        bounds=_bounds(),
    )


def _harness(files=None):
    files = FILES if files is None else files
    structural = InMemoryStructuralSource(
        "repo-1",
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        SUBJECTS,
    )
    evidence = FixtureEvidenceSource("repo-1", dict(files))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id="repo-1",
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id="repo-1",
        target=m.SubjectSelector(None, "src/main.py", (), None),
        bounds=_bounds(),
    )


def _run_exchange(explain_request, structural, evidence, store, agent,
                  seeds=(), continuations=None):
    """Drive one full suspend→perform→submit cycle; returns the answer."""
    continuations = continuations or ContinuationStore()
    pending = ops.explain(
        explain_request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    assert isinstance(pending, PendingInterpretation), type(pending)
    result = agent.perform(pending.request)
    return ops.submit_interpretation(
        pending.continuation, result, structural=structural,
        evidence=evidence, store=store, continuations=continuations,
    )


class ExchangeTest(unittest.TestCase):
    def test_suspend_then_submit_answers(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertTrue(pending.continuation)
            self.assertEqual(len(continuations), 1)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
            self.assertEqual(len(continuations), 0)
        finally:
            store.close()

    def test_unknown_continuation_unavailable(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    "cont-999",
                    m.SemanticInterpretationResult((), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_expired_continuation_abandoned(self):
        now = [datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]
        store_harness = _harness()
        structural, evidence, store = store_harness
        try:
            continuations = ContinuationStore(
                ttl_seconds=60, now=lambda: now[0]
            )
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            now[0] += datetime.timedelta(hours=1)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    _agent().perform(pending.request),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_reissue_once_then_abandoned(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            self.assertIsInstance(reissued, PendingInterpretation)
            self.assertNotEqual(
                reissued.continuation, pending.continuation
            )
            self.assertEqual(
                reissued.request, pending.request
            )
            with self.assertRaises(InterpretationIngressFailure):
                ops.reissue_interpretation(
                    reissued.continuation, continuations=continuations
                )
            with self.assertRaises(InterpretationUnavailable):
                ops.reissue_interpretation(
                    "cont-999", continuations=continuations
                )
        finally:
            store.close()

    def test_reissued_continuation_submits_normally(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            answer = ops.submit_interpretation(
                reissued.continuation, _agent().perform(reissued.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()

    def test_naive_clock_abandons(self):
        from span.shell.agent_exchange.continuations import SuspendedOperation

        naive = ContinuationStore(
            now=lambda: datetime.datetime(2026, 1, 1)
        )
        token = naive.pend(
            SuspendedOperation(
                op="explain", repository_id="repo-1",
                subject=m.Subject(_sid(), "main", None),
                request=_bare_request(),
                bounds=_bounds(),
                state=_state(),
            )
        )
        self.assertIsNone(naive.claim(token))

    def test_validation_failure_rejects_without_reissue(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            bad = m.CandidateSemanticClaim(
                subject=_sid(), kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("ghost", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id="repo-1",
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION
                ),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult((bad,), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            # Continuation consumed; nothing persisted.
            self.assertEqual(len(continuations), 0)
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_submitted_overflow_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            request = ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(max_candidate_claims=1),
            )
            pending = ops.explain(
                request, structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            overflow = m.SemanticInterpretationResult(
                tuple(
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
                        value=m.PurposeValue(f"s-{n}", ()),
                        evidence=(_ref("README.md"),),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    )
                    for n in range(3)
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, overflow,
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()


class DiscoveryTest(unittest.TestCase):
    def test_discovery_finds_identity_anchored_evidence(self):
        structural, evidence, store = _harness()
        try:
            subject = m.Subject(_sid(), "main", None)
            state = structural.repository_state("repo-1")
            selection = ops.discover_evidence(
                "repo-1", subject, structural=structural, evidence=evidence,
                bounds=_bounds(), state=state,
                authority_seeds=(_ref("README.md"),),
            )
            locators = {r.locator for r in selection.selected_refs}
            self.assertTrue({"README.md", "src/main.py"} <= locators)
        finally:
            store.close()


class ReuseTest(unittest.TestCase):
    def test_second_query_answers_without_suspension(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            seeds = (_ref("README.md"),)
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(), seeds, continuations,
            )
            second = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=seeds,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(
                [c.claim_id for c in answer.content.claims],
                [c.claim_id for c in second.content.claims],
            )
        finally:
            store.close()


class RefreshExchangeTest(unittest.TestCase):
    def _indexed(self, continuations=None):
        structural, evidence, store = _harness()
        continuations = continuations or ContinuationStore()
        answer = _run_exchange(
            _explain_request(), structural, evidence, store,
            _agent(), (_ref("README.md"),), continuations,
        )
        return structural, evidence, store, continuations, answer

    def test_nothing_stale_answers_directly(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            answer = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertTrue(answer.content.freshness_items)
        finally:
            store.close()

    def test_stale_suspends_then_resumes_current(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            content = answer.content
            self.assertIsInstance(content, m.StatusContent)
            self.assertTrue(content.changed_dependencies)
            self.assertEqual(
                content.refresh_scope,
                m.EvidenceScope(paths=("src/main.py",), evidence_refs=()),
            )
        finally:
            store.close()

    def test_failed_unit_preserved_as_stale(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            bad = m.SemanticInterpretationResult(
                (
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
                        value=m.PurposeValue("ghost", ()),
                        evidence=(
                            m.EvidenceRef(
                                evidence_id=m.EvidenceId("ev-ghost"),
                                repository_id="repo-1",
                                source_kind=(
                                    m.EvidenceSourceKind.SOURCE_CODE
                                ),
                                locator="ghost.py",
                            ),
                        ),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    ),
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, bad,
                    structural=structural, evidence=evidence_v2, store=store,
                    continuations=continuations,
                )
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertTrue(page.items)
        finally:
            store.close()

    def test_none_target_rejected(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            with self.assertRaises(ops.RefreshScopeError):
                ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id="repo-1", target=None, bounds=_bounds()
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_dirty_tree_uses_content_fingerprints(self):
        files = dict(FILES)
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            SUBJECTS,
            revision="r-dirty",
            dirty=True,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural,
            evidence=evidence,
            store=store,
        )
        try:
            continuations = ContinuationStore()
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(), (_ref("README.md"),), continuations,
            )
            for claim in answer.content.claims:
                self.assertIs(
                    claim.freshness.state, m.FreshnessState.CURRENT
                )
        finally:
            store.close()


class InitializeTest(unittest.TestCase):
    def test_init_returns_ready_without_interpretation(self):
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                    authority_seeds=(_ref("README.md"),),
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
            )
            self.assertEqual(result.repository_id, "repo-1")
            self.assertIs(
                result.readiness, m.RepositoryReadiness.READY
            )
            self.assertEqual(result.structural_source_status, "ready")
            self.assertTrue(
                result.evidence_inventory_status.startswith("ready:")
            )
            self.assertTrue(
                result.semantic_store_status.startswith("ready:schema-")
            )
            self.assertEqual(result.warnings, ())
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_init_signature_has_no_interpretation_input(self):
        import inspect

        params = inspect.signature(ops.initialize_repository).parameters
        self.assertNotIn("interpreter", params)
        self.assertNotIn("agent", params)
        fields = (
            ops.SemanticInitializeRepositoryRequest.__dataclass_fields__
        )
        self.assertNotIn("semantic_provider_config", fields)

    def test_init_rejects_empty_locator(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(ValueError):
                ops.initialize_repository(
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator="",
                        structural_provider_config="x",
                    ),
                    repository_id="repo-1",
                    structural=structural,
                    evidence=evidence,
                    store=store,
                )
        finally:
            store.close()

    def test_init_degraded_on_truncation(self):
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(max_evidence_units=1),
            )
            self.assertIs(
                result.readiness, m.RepositoryReadiness.DEGRADED
            )
            self.assertTrue(result.warnings)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
