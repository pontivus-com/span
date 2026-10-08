"""First end-to-end vertical slice (plan §15, Phase 1.10, as amended).

Synthetic repository + deterministic structural source + explicit
authority evidence + deterministic fixture agent (test stand-in for the
§11.12 agent boundary) → task → agent submission → strict ingress →
validation/authority/trust/freshness → SQLite → preflight → explain +
authority → SemanticAnswer.

Exercises: F-01 identity, F-02 purpose, F-03 membership, F-04
implementation location, F-05 responsibility, F-06 ownership/custody,
F-11 authority, F-12 invariant, F-17 provenance/trust/freshness, plus
ambiguity, conflict, missing authority, stale evidence, and the
suspend/submit exchange (single-use continuations, no inline
interpretation).

Acceptance proves: Span produces the request → deterministic test agent
returns typed interpretation → Span validates/materializes. Span never
calls a provider; the only execution is the test agent's `perform`.
"""

import unittest

from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import (
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.service_operations import (
    SemanticAuthorityRequest,
    SemanticExplainRequest,
    SemanticInitializeRepositoryRequest,
    authority,
    explain,
    initialize_repository,
    submit_interpretation,
)
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "pay-svc"

FILES_V1 = {
    "README.md": (
        "# pay-svc\n\nProcesses payments.\n\n"
        "Invariant: refunds never exceed the captured amount.\n"
    ),
    "OWNERSHIP.md": "# Ownership\n\nTeam payments owns pay-svc.\n",
    "src/payments.py": "class Handler:\n    def charge(self):\n        pass\n",
    "src/refunds.py": "class Handler:\n    def refund(self):\n        pass\n",
}

SUBJECTS = (
    InMemorySubject("pay-svc", m.SubjectKind.REPOSITORY, "pay-svc"),
    InMemorySubject("cap/payments", m.SubjectKind.CAPABILITY, "payments-cap"),
    InMemorySubject("src/payments.py", m.SubjectKind.COMPONENT, "payments"),
    InMemorySubject(
        "src/payments.py:Handler", m.SubjectKind.CODE_SYMBOL, "Handler"
    ),
    InMemorySubject(
        "src/refunds.py:Handler", m.SubjectKind.CODE_SYMBOL, "Handler"
    ),
)

EDGES = (
    InMemoryEdge(
        "src/payments.py:Handler",
        m.StructuralEdgeKind.DEFINES,
        "src/payments.py",
    ),
)


def _sid(locator, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(
        repository_id=REPO, subject_kind=kind, canonical_locator=locator
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=(
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(".md")
            else m.EvidenceSourceKind.SOURCE_CODE
        ),
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES_V1[path]),
    )


_QUOTES = {
    "README.md": "Processes payments",
    "OWNERSHIP.md": "Team payments owns pay-svc",
    "src/payments.py": "class Handler",
}


def _accepted(path, kind):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref(path),
            authority_kind=kind,
            status=m.AuthorityStatus.ACCEPTED,
        ),
        support=m.AuthoritySupport(
            quoted_span=_QUOTES[path],
            status_section=path,
            applicability_section=None,
        ),
    )


def _payments_candidates():
    sid = _sid("src/payments.py")
    cap = _sid("cap/payments", m.SubjectKind.CAPABILITY)
    interp = m.DerivationKind.SEMANTIC_INTERPRETATION
    return FixtureCandidates(
        claims=(
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("processes payments", (cap,)),
                evidence=(_ref("README.md"),),
                candidate_authority=_accepted(
                    "README.md", m.AuthorityKind.REPOSITORY_RULE
                ),
                basis=m.SemanticBasis(interp, "stated in README"),
            ),
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("sends receipts", ()),
                evidence=(_ref("README.md"),),
                basis=m.SemanticBasis(interp, "mentioned in README"),
            ),
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.CAPABILITY_MEMBERSHIP,
                value=m.CapabilityMembershipValue(cap, "processor"),
                evidence=(_ref("src/payments.py"),),
                basis=m.SemanticBasis(interp, "module docstring"),
            ),
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.RESPONSIBILITY,
                value=m.ResponsibilityValue(
                    "captures charges", "checkout path"
                ),
                evidence=(_ref("src/payments.py"),),
                basis=m.SemanticBasis(interp, "Handler.charge"),
            ),
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                value=m.OwnershipCustodyValue(
                    _sid("team/payments", m.SubjectKind.COMPONENT),
                    m.OwnershipRole.OWNER,
                    m.OwnershipExclusivity.EXCLUSIVE,
                ),
                evidence=(_ref("OWNERSHIP.md"),),
                candidate_authority=_accepted(
                    "OWNERSHIP.md", m.AuthorityKind.REPOSITORY_RULE
                ),
                basis=m.SemanticBasis(interp, "ownership record"),
            ),
            m.CandidateSemanticClaim(
                subject=sid, kind=m.ClaimKind.INVARIANT_CONSTRAINT,
                value=m.InvariantConstraintValue(
                    "refunds never exceed the captured amount",
                    "refund path",
                ),
                evidence=(_ref("README.md"),),
                candidate_authority=m.CandidateAuthority(
                    binding=m.AuthorityBinding(
                        evidence_ref=_ref("README.md"),
                        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                        status=m.AuthorityStatus.DRAFT,
                    ),
                    support=m.AuthoritySupport(
                        quoted_span="refunds never exceed",
                        status_section="README.md",
                        applicability_section=None,
                    ),
                ),
                basis=m.SemanticBasis(interp, "README invariant section"),
            ),
        ),
        relationships=(
            m.CandidateSemanticRelationship(
                source=_sid(
                    "src/payments.py:Handler", m.SubjectKind.CODE_SYMBOL
                ),
                kind=m.RelationshipKind.MEMBER_OF,
                target=sid,
                evidence=(_ref("src/payments.py"),),
                basis=m.SemanticBasis(interp, "Handler defined in payments"),
            ),
        ),
    )


def _harness(files=None):
    files = FILES_V1 if files is None else files
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        SUBJECTS,
        EDGES,
    )
    evidence = FixtureEvidenceSource(REPO, dict(files))
    store = SqliteSemanticStore(":memory:")
    initialize_repository(
        SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    agent = FixtureAgent({"src/payments.py": _payments_candidates()})
    return structural, evidence, store, agent


def _bounds():
    return DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds


def _seeds():
    return (_ref("README.md"), _ref("OWNERSHIP.md"))


def _explain_request(target):
    return SemanticExplainRequest(
        repository_id=REPO,
        target=m.SubjectSelector(
            exact_subject_id=None, name_or_locator=target,
            expected_kinds=(), retrieval_scope_hint=None,
        ),
        bounds=_bounds(),
    )


def _exchange(explain_request, structural, evidence, store, agent,
              seeds=None, continuations=None):
    """Drive the client protocol: explain, and if Span suspends, have the
    test agent perform the task and submit the result."""
    continuations = continuations or ContinuationStore()
    seeds = _seeds() if seeds is None else seeds
    first = explain(
        explain_request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    if isinstance(first, m.SemanticAnswer):
        return first
    assert isinstance(first, PendingInterpretation), type(first)
    result = agent.perform(first.request)
    return submit_interpretation(
        first.continuation, result, structural=structural,
        evidence=evidence, store=store, continuations=continuations,
    )


class VerticalSliceTest(unittest.TestCase):
    def test_explain_identity_purpose_membership_location(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _explain_request("src/payments.py"),
                structural, evidence, store, agent,
            )
            self.assertIs(
                answer.subject_resolution.ambiguity,
                m.ResolutionAmbiguity.RESOLVED,
            )
            sid = answer.subject_resolution.candidates[0].subject.subject_id
            self.assertEqual(sid.canonical_locator, "src/payments.py")
            content = answer.content
            self.assertIsInstance(content, m.ExplainContent)
            kinds = {c.kind for c in content.claims}
            self.assertTrue(
                {
                    m.ClaimKind.PURPOSE,
                    m.ClaimKind.CAPABILITY_MEMBERSHIP,
                    m.ClaimKind.RESPONSIBILITY,
                    m.ClaimKind.OWNERSHIP_CUSTODY,
                    m.ClaimKind.INVARIANT_CONSTRAINT,
                } <= kinds
            )
            self.assertEqual(len(content.relationships), 1)
            self.assertIs(
                content.relationships[0].kind, m.RelationshipKind.MEMBER_OF
            )
            self.assertTrue(content.implementation_locations)
            self.assertEqual(
                content.implementation_locations[0].location.locator,
                "src/payments.py",
            )
            for claim in content.claims:
                self.assertIsInstance(claim.trust, m.TrustState)
                self.assertIsInstance(
                    claim.freshness.state, m.FreshnessState
                )
            self.assertEqual(len(content.conflicts), 1)
            missing = [
                r for r in answer.resolution_requirements
                if r.kind is m.ResolutionKind.MISSING_AUTHORITY
            ]
            self.assertGreaterEqual(len(missing), 2)
            trusts = {c.trust for c in content.claims}
            self.assertTrue(
                {
                    m.TrustState.ESTABLISHED,
                    m.TrustState.PARTIAL,
                    m.TrustState.UNRESOLVED,
                } <= trusts
            )
        finally:
            store.close()

    def test_suspension_carries_bounded_task(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            pending = explain(
                _explain_request("src/payments.py"),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations, authority_seeds=_seeds(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            request = pending.request
            self.assertEqual(request.repository_id, REPO)
            self.assertTrue(request.evidence_units)
            self.assertTrue(request.allowed_claim_kinds)
            # Nothing indexed by suspension alone.
            page = store.load_claims(
                REPO, (_sid("src/payments.py"),), (), _bounds()
            )
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_continuation_single_use(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            pending = explain(
                _explain_request("src/payments.py"),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations, authority_seeds=_seeds(),
            )
            result = agent.perform(pending.request)
            submit_interpretation(
                pending.continuation, result, structural=structural,
                evidence=evidence, store=store, continuations=continuations,
            )
            with self.assertRaises(InterpretationUnavailable):
                submit_interpretation(
                    pending.continuation, result, structural=structural,
                    evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_shared_handler_name_is_ambiguous(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = explain(
                _explain_request("Handler"),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
                authority_seeds=_seeds(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(
                answer.subject_resolution.ambiguity,
                m.ResolutionAmbiguity.AMBIGUOUS,
            )
            self.assertEqual(len(answer.subject_resolution.candidates), 2)
            kinds = {
                r.kind for r in answer.resolution_requirements
            }
            self.assertIn(m.ResolutionKind.AMBIGUOUS_IDENTITY, kinds)
        finally:
            store.close()

    def test_authority_returns_governing_bindings(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            seeds = _seeds()
            pending = authority(
                SemanticAuthorityRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        exact_subject_id=None,
                        name_or_locator="src/payments.py",
                        expected_kinds=(), retrieval_scope_hint=None,
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations, authority_seeds=seeds,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = submit_interpretation(
                pending.continuation, agent.perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            content = answer.content
            self.assertIsInstance(content, m.AuthorityContent)
            statuses = {b.status for b in content.governing_bindings}
            self.assertIn(m.AuthorityStatus.ACCEPTED, statuses)
            locators = {
                b.evidence_ref.locator for b in content.governing_bindings
            }
            self.assertTrue({"README.md", "OWNERSHIP.md"} <= locators)
            kinds = {r.kind for r in content.unresolved}
            self.assertIn(m.ResolutionKind.MISSING_AUTHORITY, kinds)
            self.assertEqual(len(content.conflicts), 1)
        finally:
            store.close()

    def test_source_change_marks_dependent_claims_stale(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            first = _exchange(
                _explain_request("src/payments.py"),
                structural, evidence, store, agent,
                continuations=continuations,
            )
            states = {
                c.claim_id.value: c.freshness.state
                for c in first.content.claims
            }
            self.assertTrue(
                all(s is m.FreshnessState.CURRENT for s in states.values())
            )
            changed = dict(FILES_V1)
            changed["src/payments.py"] = (
                "class Handler:\n    def charge(self):\n        pass\n"
                "    def void(self):\n        pass\n"
            )
            evidence_v2 = FixtureEvidenceSource(REPO, changed)
            second = _exchange(
                _explain_request("src/payments.py"),
                structural, evidence_v2, store, agent,
                continuations=continuations,
            )
            states = {
                c.claim_id.value: (c.freshness.state, c.kind)
                for c in second.content.claims
            }
            stale_kinds = {
                kind for state, kind in states.values()
                if state is m.FreshnessState.STALE
            }
            current_kinds = {
                kind for state, kind in states.values()
                if state is m.FreshnessState.CURRENT
            }
            self.assertTrue(
                {
                    m.ClaimKind.CAPABILITY_MEMBERSHIP,
                    m.ClaimKind.RESPONSIBILITY,
                } <= stale_kinds
            )
            self.assertTrue(
                {
                    m.ClaimKind.PURPOSE,
                    m.ClaimKind.OWNERSHIP_CUSTODY,
                    m.ClaimKind.INVARIANT_CONSTRAINT,
                } <= current_kinds
            )
            stale_reqs = [
                r for r in second.resolution_requirements
                if r.kind is m.ResolutionKind.STALE_EVIDENCE
            ]
            self.assertTrue(stale_reqs)
        finally:
            store.close()

    def test_failed_unit_rejected_atomically(self):
        structural, evidence, store, _ = _harness()
        try:
            continuations = ContinuationStore()
            pending = explain(
                _explain_request("src/payments.py"),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations, authority_seeds=_seeds(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            bad = m.CandidateSemanticClaim(
                subject=_sid("src/payments.py"), kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("ghost", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id=REPO,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
                basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION),
            )
            with self.assertRaises(InterpretationUnitRejected):
                submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult((bad,), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            page = store.load_claims(
                REPO, (_sid("src/payments.py"),), (), _bounds()
            )
            self.assertEqual(page.items, ())
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
