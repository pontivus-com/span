"""Exchange-driver tests (addendum D TOOL-D-01, §6).

The host-side driver runs the canonical submit loop without touching
semantic content. Service-backed cases prove driven exchanges validate
identically to the manual loop across all result fields; stub cases
prove halt, reissue, budget, and cost behavior.
"""

import datetime
import unittest

from span.core import model as m
from span.core.validation import (
    InterpretationUnitRejected as _InterpretationUnitRejected,
)
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span import service as ops
from span.service.discovery import _inventory_snapshot, _read_units_within_bytes
from span.service.resolution import _resolve_query_subject
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
from integrations.hosts.exchange_driver import (
    DriveResult,
    drive,
)

REPO = "repo-1"

FILES = {
    "README.md": "# svc\n\nDoes things.\n",
    "src/main.py": "VALUE = 1\n",
}

SUBJECTS = (
    InMemorySubject("src/main.py", m.SubjectKind.COMPONENT, "main"),
)


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _sid():
    return m.SubjectId(
        repository_id=REPO, subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator="src/main.py",
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose-main",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
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


def _agent(complete_questions=False):
    return FixtureAgent(
        {"src/main.py": FixtureCandidates((_candidate(),), ())},
        complete_questions=complete_questions,
    )


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        SUBJECTS,
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural, evidence=evidence, store=store,
    )
    return structural, evidence, store


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/main.py", (), None),
        bounds=_bounds(),
    )


class DriverServiceTest(unittest.TestCase):
    def test_driven_answer_matches_manual_loop(self):
        # Identical validation across all result fields: same harness
        # shape twice (separate stores), driven vs manual loop.
        structural, evidence, store = _harness()
        structural2, evidence2, store2 = _harness()
        try:
            cont = ContinuationStore()
            seeds = (_ref("README.md"),)
            agent = _agent(complete_questions=True)
            driven = drive(
                lambda: ops.explain(
                    _explain_request(), structural=structural,
                    evidence=evidence, store=store,
                    continuations=cont, authority_seeds=seeds,
                ),
                agent.perform,
                submit=lambda c, r: ops.submit_interpretation(
                    c, r, structural=structural, evidence=evidence,
                    store=store, continuations=cont,
                ),
                reissue=lambda: ops.explain(
                    _explain_request(), structural=structural,
                    evidence=evidence, store=store,
                    continuations=cont, authority_seeds=seeds,
                ),
                max_rounds=8,
            )
            self.assertIsNone(driven.halt)
            self.assertIsInstance(driven.answer, m.SemanticAnswer)
            cont2 = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural2,
                evidence=evidence2, store=store2,
                continuations=cont2, authority_seeds=seeds,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            manual = ops.submit_interpretation(
                pending.continuation, agent.perform(pending.request),
                structural=structural2, evidence=evidence2,
                store=store2, continuations=cont2,
            )
            self.assertIsInstance(manual, m.SemanticAnswer)
            # Same validated material field for field.
            self.assertEqual(driven.answer.intent, manual.intent)
            self.assertEqual(
                [c.claim_id for c in driven.answer.content.claims],
                [c.claim_id for c in manual.content.claims],
            )
            self.assertEqual(
                driven.answer.content.evidence if hasattr(
                    driven.answer.content, "evidence") else (),
                manual.content.evidence if hasattr(
                    manual.content, "evidence") else (),
            )
            self.assertEqual(
                driven.answer.resolution_requirements,
                manual.resolution_requirements,
            )
            self.assertEqual(driven.cost.submissions, 1)
            self.assertEqual(driven.cost.reissues, 0)
            self.assertGreaterEqual(driven.cost.elapsed_ms, 0)
        finally:
            store.close()
            store2.close()

    def test_driver_rejection_matches_direct_diagnostics(self):
        structural, evidence, store = _harness()
        try:
            cont = ContinuationStore()
            seeds = (_ref("README.md"),)
            pending = ops.explain(
                _explain_request(), structural=structural,
                evidence=evidence, store=store,
                continuations=cont, authority_seeds=seeds,
            )
            self.assertIsInstance(pending, PendingInterpretation)

            def _bad(_request):
                return m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="bad",
                            subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("no evidence", ()),
                            evidence=(),
                            candidate_authority=None,
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "uncited",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    proposed_question_coverages=(),
                    candidate_withdrawals=(),
                )

            try:
                ops.submit_interpretation(
                    pending.continuation, _bad(pending.request),
                    structural=structural, evidence=evidence,
                    store=store, continuations=cont,
                )
                direct = ()
            except _InterpretationUnitRejected as exc:
                direct = exc.diagnostics
            self.assertTrue(direct)

            cont2 = ContinuationStore()
            driven = drive(
                lambda: ops.explain(
                    _explain_request(), structural=structural,
                    evidence=evidence, store=store,
                    continuations=cont2, authority_seeds=seeds,
                ),
                _bad,
                submit=lambda c, r: ops.submit_interpretation(
                    c, r, structural=structural, evidence=evidence,
                    store=store, continuations=cont2,
                ),
                reissue=lambda: ops.explain(
                    _explain_request(), structural=structural,
                    evidence=evidence, store=store,
                    continuations=cont2, authority_seeds=seeds,
                ),
                max_rounds=8,
            )
            self.assertIsNone(driven.answer)
            self.assertIsNotNone(driven.halt)
            self.assertEqual(driven.halt.kind, "validation")
            self.assertEqual(tuple(driven.halt.diagnostics), tuple(direct))
        finally:
            store.close()


class DriverMechanicsTest(unittest.TestCase):
    def _stubs(self):
        structural, evidence, store = _harness()
        cont = ContinuationStore()
        pending = ops.explain(
            _explain_request(), structural=structural,
            evidence=evidence, store=store,
            continuations=cont, authority_seeds=(_ref("README.md"),),
        )
        self.assertIsInstance(pending, PendingInterpretation)
        answer = ops.submit_interpretation(
            pending.continuation,
            _agent(complete_questions=True).perform(pending.request),
            structural=structural, evidence=evidence,
            store=store, continuations=cont,
        )
        self.assertIsInstance(answer, m.SemanticAnswer)
        store.close()
        return pending, answer

    def test_expired_continuation_reissues_once(self):
        pending, answer = self._stubs()
        calls = {"submit": 0}

        def _flaky_submit(_continuation, _result):
            calls["submit"] += 1
            if calls["submit"] == 1:
                raise InterpretationUnavailable("expired: cont-9")
            return answer

        result = drive(
            lambda: pending,
            lambda _request: _agent().perform(_request),
            submit=_flaky_submit,
            reissue=lambda: answer,
            max_rounds=8,
        )
        self.assertIsNone(result.halt)
        self.assertIs(result.answer, answer)
        self.assertEqual(result.cost.reissues, 1)
        self.assertEqual(result.cost.submissions, 0)

    def test_round_budget_halts(self):
        pending, _ = self._stubs()
        other = PendingInterpretation(
            continuation="cont-x", request=pending.request,
        )
        result = drive(
            lambda: pending,
            lambda _request: _agent().perform(_request),
            submit=lambda _c, _r: other,
            reissue=lambda: other,
            max_rounds=3,
        )
        self.assertIsNone(result.answer)
        self.assertEqual(result.halt.kind, "round_budget")
        self.assertEqual(result.cost.submissions, 3)

    def test_nonpositive_budget_rejected(self):
        pending, answer = self._stubs()
        with self.assertRaises(ValueError):
            drive(
                lambda: answer, lambda _r: _agent().perform(pending.request),
                submit=lambda _c, _r: answer, reissue=lambda: answer,
                max_rounds=0,
            )

    def test_result_invariant(self):
        with self.assertRaises(ValueError):
            DriveResult(answer=None, halt=None, cost=None)  # type: ignore[arg-type]

    def test_ingress_halt(self):
        pending, _ = self._stubs()

        def _bad_submit(_c, _r):
            raise InterpretationIngressFailure("bad shape")

        result = drive(
            lambda: pending,
            lambda _request: _agent().perform(_request),
            submit=_bad_submit,
            reissue=lambda: pending,
            max_rounds=8,
        )
        self.assertEqual(result.halt.kind, "ingress")


if __name__ == "__main__":
    unittest.main()
