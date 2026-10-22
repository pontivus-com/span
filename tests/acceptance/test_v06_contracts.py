"""v0.6 contract acceptance paths (plan §16 rework scope, §21 items 20–21).

Each path exercises one closed v0.5 gap end to end through public
service behavior only:

- successful withdrawal of an old claim on refresh (I-37);
- new superseding evidence invalidating coverage, then recovery ( §8.5);
- documentation-only subject registration and ref-targeted query (§4.11);
- multi-unit interpretation chaining distinct from pagination (I-39).

Second-page retrieval is pinned in
``tests/unit/test_phase3_operations.py::ImpactTest::test_second_page_retrieval``.
"""

import datetime
import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
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

REPO = "v06-svc"

FILES = {
    "README.md": "# v06-svc\n\nBilling capability.\n",
    "OWNERSHIP.md": "# Ownership\n\nTeam ledger owns billing.\n",
    "src/billing.py": "CHARGE = 1\n",
}


def _sid(locator, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(
        repository_id=REPO, subject_kind=kind, canonical_locator=locator
    )


def _ref(path, files=None):
    files = FILES if files is None else files
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.DOCUMENTATION
        if path.endswith(".md")
        else m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(files[path]),
    )


def _authority(path, quote):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref(path),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        ),
        support=m.AuthoritySupport(
            quoted_span=quote,
            status_section=path,
            applicability_section=None,
        ),
    )


def _billing_claims(with_ownership=True):
    sid = _sid("src/billing.py")
    interp = m.DerivationKind.SEMANTIC_INTERPRETATION
    claims = [
        m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=sid, kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("billing capability", ()),
            evidence=(_ref("README.md"),),
            candidate_authority=_authority(
                "README.md", "Billing capability"
            ),
            basis=m.SemanticBasis(
                interp, "README states the billing purpose"
            ),
        ),
        m.CandidateSemanticClaim(
            candidate_key="invariant",
            subject=sid, kind=m.ClaimKind.INVARIANT_CONSTRAINT,
        assertion_nature=m.AssertionNature.NORMATIVE,
            value=m.InvariantConstraintValue("no partial capture"),
            evidence=(_ref("README.md"),),
            candidate_authority=_authority(
                "README.md", "Billing capability"
            ),
            basis=m.SemanticBasis(
                interp, "README states the capture invariant"
            ),
        ),
    ]
    if with_ownership:
        claims.append(
            m.CandidateSemanticClaim(
                candidate_key="ownership",
                subject=sid, kind=m.ClaimKind.OWNERSHIP_CUSTODY,
        assertion_nature=m.AssertionNature.NORMATIVE,
                value=m.OwnershipCustodyValue(
                    _sid("team/ledger"), m.OwnershipRole.OWNER,
                    m.OwnershipExclusivity.EXCLUSIVE,
                ),
                evidence=(_ref("OWNERSHIP.md"),),
                candidate_authority=_authority(
                    "OWNERSHIP.md", "Team ledger owns"
                ),
                basis=m.SemanticBasis(
                    interp, "ownership record names the ledger owner"
                ),
            )
        )
    return tuple(claims)


def _harness(files=None, claims=None, complete_questions=True):
    files = FILES if files is None else files
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        (InMemorySubject("src/billing.py", m.SubjectKind.COMPONENT, "b"),),
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
    agent = FixtureAgent(
        {
            "src/billing.py": FixtureCandidates(
                claims=(
                    _billing_claims()
                    if claims is None else claims
                ),
                relationships=(),
            )
        },
        # Addendum C C-05 cutover: fixture completes the bound
        # question explicitly; claims alone never complete.
        complete_questions=complete_questions,
    )
    return structural, evidence, store, agent


def _bounds():
    from span.service import DEFAULT_SERVICE_BOUNDS_POLICY

    return DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds


def _exchange(request, op, structural, evidence, store, agent,
              seeds=(), rounds=0):
    continuations = ContinuationStore()
    current = op(
        request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    while not isinstance(current, m.SemanticAnswer):
        assert isinstance(current, PendingInterpretation), type(current)
        rounds += 1
        result = agent.perform(current.request)
        current = ops.submit_interpretation(
            current.continuation, result, structural=structural,
            evidence=evidence, store=store, continuations=continuations,
        )
    return current, rounds


def _trace_request():
    from span.ports.structural import StructuralDirection

    return ops.SemanticTraceRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/billing.py", (), None),
        direction=StructuralDirection.BOTH,
        relationship_filter=None,
        boundary_only=False,
        bounds=_bounds(),
    )


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/billing.py", (), None),
        bounds=_bounds(),
    )


class WithdrawalTest(unittest.TestCase):
    def test_successful_refresh_withdraws_old_claim(self):
        structural, evidence, store, agent = _harness()
        try:
            first, _ = _exchange(
                _explain_request(), ops.explain,
                structural, evidence, store, agent,
            )
            kinds = {c.kind for c in first.content.claims}
            self.assertIn(m.ClaimKind.OWNERSHIP_CUSTODY, kinds)
            # The ownership declaration disappears from the source.
            changed = dict(FILES)
            changed["OWNERSHIP.md"] = (
                "# Ownership\n\nTeam ledger owns billing.\n"
                "Steward on call.\n"
            )
            evidence_v2 = FixtureEvidenceSource(REPO, changed)
            lean_agent = FixtureAgent(
                {
                    "src/billing.py": FixtureCandidates(
                        claims=_billing_claims(with_ownership=False),
                        relationships=(),
                    )
                },
                complete_questions=True,
            )
            refreshed, _ = _exchange(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.refresh, structural, evidence_v2, store, lean_agent,
            )
            self.assertIsInstance(
                refreshed.content, m.StatusContent
            )
            second, _ = _exchange(
                _explain_request(), ops.explain,
                structural, evidence_v2, store, lean_agent,
            )
            kinds = {c.kind for c in second.content.claims}
            self.assertNotIn(m.ClaimKind.OWNERSHIP_CUSTODY, kinds)
            self.assertIn(m.ClaimKind.PURPOSE, kinds)
            # Retired history is preserved, never silently discarded.
            rows = store._db.execute(
                "SELECT claim_id FROM retired_claims"
            ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            store.close()


class SupersedingEvidenceTest(unittest.TestCase):
    def test_scope_bound_membership_vs_cited_change_then_recovers(self):
        """J-1: discovery membership is bounded by the subject's scope, so
        a new out-of-scope file does not invalidate coverage (J-A1), while
        a changed *cited* source stales exactly its dependents (J-A3,
        MI-07 partial staleness). Explicit refresh recovers."""
        structural, evidence, store, agent = _harness()
        try:
            first, _ = _exchange(
                _explain_request(), ops.explain,
                structural, evidence, store, agent,
            )
            self.assertTrue(
                all(
                    c.freshness.state is m.FreshnessState.CURRENT
                    for c in first.content.claims
                )
            )
            # A new authority document OUTSIDE the subject's bounded
            # discovery scope; no existing bytes change. Coverage stays
            # current (J-A1).
            grown = dict(FILES)
            grown["docs/charter.md"] = (
                "# Charter\n\nLedger governs billing.\n"
            )
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            still_current, _ = _exchange(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.status, structural, evidence_v2, store, agent,
            )
            out_of_scope_states = {
                item.item.id.value: item.freshness.state
                for item in still_current.content.freshness_items
            }
            self.assertTrue(out_of_scope_states)
            self.assertTrue(
                all(
                    s is m.FreshnessState.CURRENT
                    for s in out_of_scope_states.values()
                ),
                "out-of-scope membership change must not invalidate",
            )
            # A change to a source the assertions cite (a direct evidence
            # dependency, not discovery membership) still stales exactly
            # its dependents and leaves unrelated ones current (J-A3).
            changed = dict(grown)
            changed["README.md"] = (
                "# v06-svc\n\nBilling capability changed.\n"
            )
            evidence_v3 = FixtureEvidenceSource(REPO, changed)
            stale_answer, _ = _exchange(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.status, structural, evidence_v3, store, agent,
            )
            states = {
                item.item.id.value: item.freshness.state
                for item in stale_answer.content.freshness_items
            }
            self.assertTrue(states)
            self.assertTrue(
                any(
                    s is not m.FreshnessState.CURRENT
                    for s in states.values()
                ),
                "a changed cited source must stale its dependents",
            )
            self.assertTrue(
                any(
                    s is m.FreshnessState.CURRENT
                    for s in states.values()
                ),
                "unrelated dependents stay current (MI-07)",
            )
            # Explicit refresh re-resolves and recovers.
            _exchange(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.refresh, structural, evidence_v3, store, agent,
            )
            recovered, _ = _exchange(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.status, structural, evidence_v3, store, agent,
            )
            self.assertTrue(
                all(
                    item.freshness.state is m.FreshnessState.CURRENT
                    for item in recovered.content.freshness_items
                )
            )
        finally:
            store.close()


class DocumentationOnlySubjectTest(unittest.TestCase):
    def test_register_and_query_doc_only_capability(self):
        structural, evidence, store, _ = _harness()
        billing = _sid("src/billing.py")
        cap_subject = m.CandidateSubject(
            provisional_locator="cap/billing",
            kind=m.SubjectKind.CAPABILITY,
            display_name="Billing",
            evidence=(_ref("README.md"),),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "README describes the billing capability",
            ),
        )
        cap_claim = m.CandidateSemanticClaim(
            candidate_key="cap-purpose",
            subject=m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.CAPABILITY,
                canonical_locator="cap/billing",
            ),
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("billing capability", ()),
            evidence=(_ref("README.md"),),
            candidate_authority=_authority(
                "README.md", "Billing capability"
            ),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "README states the billing capability purpose",
            ),
        )
        agent = FixtureAgent(
            {
                "src/billing.py": FixtureCandidates(
                    claims=_billing_claims(),
                    relationships=(),
                    subjects=(cap_subject,),
                ),
            }
        )
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural,
                evidence=evidence, store=store,
                continuations=continuations, authority_seeds=(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            result = agent.perform(pending.request)
            # Same-unit claim on the proposed subject: validated
            # against the unit's own subject proposals.
            result = m.SemanticInterpretationResult(
                claims=tuple(result.claims) + (cap_claim,),
                relationships=result.relationships,
                governing_source_refs=result.governing_source_refs,
                diagnostics=result.diagnostics,
                candidate_subjects=result.candidate_subjects,
                candidate_conflicts=result.candidate_conflicts,
            )
            answer = ops.submit_interpretation(
                pending.continuation, result, structural=structural,
                evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            cap_id = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.CAPABILITY,
                canonical_locator="cap/billing",
            )
            registered = store.load_subjects(REPO, (cap_id,))
            self.assertEqual(len(registered), 1)
            self.assertEqual(registered[0].display_name, "Billing")
            # Ref-targeted authority reaches the doc-only subject
            # without structural resolution.
            claims = store.load_claims(REPO, (cap_id,), (), _bounds())
            self.assertTrue(claims.items)
            auth = ops.authority(
                ops.SemanticAuthorityRequest(
                    repository_id=REPO,
                    target=m.ClaimRef(id=claims.items[0].claim_id),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(auth, m.SemanticAnswer)
            self.assertTrue(auth.content.governing_bindings)
        finally:
            store.close()


class MultiUnitChainTest(unittest.TestCase):
    def test_successive_frontiers_chain_continuations(self):
        from span.shell.structural.memory import (
            InMemoryEdge,
            InMemorySubject as _S,
        )
        from span.ports.structural import StructuralDirection
        from span.ports.structural import StructuralDirection

        structural = InMemoryStructuralSource(
            REPO,
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            (
                InMemorySubject(
                    "src/billing.py", m.SubjectKind.COMPONENT, "b"
                ),
                _S("src/ledger.py", m.SubjectKind.COMPONENT, "ledger"),
            ),
            (
                InMemoryEdge(
                    "src/billing.py",
                    m.StructuralEdgeKind.REFERENCES,
                    "src/ledger.py",
                ),
            ),
        )
        evidence = FixtureEvidenceSource(REPO, dict(FILES))
        store = SqliteSemanticStore(":memory:")
        agent = FixtureAgent(
            {
                "src/billing.py": FixtureCandidates(
                    claims=_billing_claims(), relationships=()
                )
            }
        )
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
        try:
            answer, rounds = _exchange(
                ops.SemanticTraceRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                ops.trace, structural, evidence, store, agent,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            # Target unit plus at least one frontier unit: successions
            # return fresh PendingInterpretations, never a new type.
            self.assertGreaterEqual(rounds, 2)
        finally:
            store.close()

    def test_interrupted_chain_recovers_by_reissue(self):
        """Interrupted sessions recover idempotently (G-04).

        A continuation that expires mid-chain abandons only that
        exchange step; the agent re-issues the original operation and
        the chain settles to an answer. No partial unit is kept, and
        nothing is laundered.
        """
        from span.ports.interpretation import InterpretationUnavailable
        from span.shell.structural.memory import (
            InMemoryEdge as _Edge,
        )
        from span.shell.structural.memory import (
            InMemorySubject as _S,
        )

        structural = InMemoryStructuralSource(
            REPO,
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            (
                InMemorySubject(
                    "src/billing.py", m.SubjectKind.COMPONENT, "b"
                ),
                _S("src/ledger.py", m.SubjectKind.COMPONENT, "ledger"),
            ),
            (
                _Edge(
                    "src/billing.py",
                    m.StructuralEdgeKind.REFERENCES,
                    "src/ledger.py",
                ),
            ),
        )
        evidence = FixtureEvidenceSource(REPO, dict(FILES))
        store = SqliteSemanticStore(":memory:")
        agent = FixtureAgent(
            {
                "src/billing.py": FixtureCandidates(
                    claims=_billing_claims(), relationships=()
                )
            }
        )
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
        try:
            doomed_times = [
                datetime.datetime(
                    2026, 1, 1, tzinfo=datetime.timezone.utc
                ),
                datetime.datetime(
                    2026, 1, 1, 1, tzinfo=datetime.timezone.utc
                ),
            ]
            doomed = ContinuationStore(now=lambda: doomed_times.pop(0))
            first = ops.trace(
                _trace_request(), structural=structural,
                evidence=evidence, store=store,
                continuations=doomed, authority_seeds=(),
            )
            self.assertIsInstance(first, PendingInterpretation)
            result = agent.perform(first.request)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    first.continuation, result, structural=structural,
                    evidence=evidence, store=store,
                    continuations=doomed,
                )
            # Nothing materialized from the abandoned step.
            page = store.load_claims(
                REPO, (_sid("src/billing.py"),), (), _bounds()
            )
            self.assertEqual(page.items, ())
            # Re-issue the original operation; the chain settles.
            answer, _ = _exchange(
                _trace_request(), ops.trace,
                structural, evidence, store, agent,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
        finally:
            store.close()


class RetiredOwnerTest(unittest.TestCase):
    def test_retired_owner_owns_nothing(self):
        """MI-11 B: a superseded owner must own nothing live.

        Ownership moves from team/ledger to team/billing through a new
        declaration; refresh retires the old claim atomically. No live
        claim may then name the retired owner in any owner-like role,
        while retired history preserves the prior assertion.
        """
        structural, evidence, store, agent = _harness()
        try:
            first, _ = _exchange(
                _explain_request(), ops.explain,
                structural, evidence, store, agent,
            )
            owners = {
                c.value.owner.canonical_locator
                for c in first.content.claims
                if c.kind is m.ClaimKind.OWNERSHIP_CUSTODY
            }
            self.assertEqual(owners, {"team/ledger"})
            changed = dict(FILES)
            changed["OWNERSHIP.md"] = (
                "# Ownership\n\nTeam ledger owns billing.\n"
                "Team billing owns billing.\n"
            )
            evidence_v2 = FixtureEvidenceSource(REPO, changed)
            sid = _sid("src/billing.py")
            new_owner = _sid("team/billing")
            successor = m.CandidateSemanticClaim(
                candidate_key="ownership",
                subject=sid, kind=m.ClaimKind.OWNERSHIP_CUSTODY,
        assertion_nature=m.AssertionNature.NORMATIVE,
                value=m.OwnershipCustodyValue(
                    new_owner, m.OwnershipRole.OWNER,
                    m.OwnershipExclusivity.EXCLUSIVE,
                ),
                evidence=(_ref("OWNERSHIP.md", changed),),
                candidate_authority=m.CandidateAuthority(
                    binding=m.AuthorityBinding(
                        evidence_ref=_ref("OWNERSHIP.md", changed),
                        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                        status=m.AuthorityStatus.ACCEPTED,
                    ),
                    support=m.AuthoritySupport(
                        quoted_span="Team billing owns",
                        status_section="OWNERSHIP.md",
                        applicability_section=None,
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "ownership record names the billing owner",
                ),
            )
            successor_agent = FixtureAgent(
                {
                    "src/billing.py": FixtureCandidates(
                        claims=tuple(
                            c for c in _billing_claims()
                            if c.kind is not m.ClaimKind.OWNERSHIP_CUSTODY
                        ) + (successor,),
                        relationships=(),
                    )
                },
                complete_questions=True,
            )
            _exchange(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/billing.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                ops.refresh, structural, evidence_v2, store,
                successor_agent,
            )
            second, _ = _exchange(
                _explain_request(), ops.explain,
                structural, evidence_v2, store, successor_agent,
            )
            live_owners = set()
            for claim in second.content.claims:
                value = claim.value
                if isinstance(value, m.OwnershipCustodyValue):
                    live_owners.add(value.owner.canonical_locator)
                if isinstance(value, m.TransformationOwnershipValue):
                    live_owners.add(value.transformer.canonical_locator)
            self.assertEqual(live_owners, {"team/billing"})
            rows = store._db.execute(
                "SELECT claim_id FROM retired_claims"
            ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
