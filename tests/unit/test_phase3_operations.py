"""Phase 3 operation tests (plan §11.5/§11.6/§11.8, §11.5.1, §11.9,
F-13/F-14/F-15).

Deterministic throughout; the FixtureAgent stands in for the invoking
agent. Covers trace frontier/direction/filter/boundary/suspend,
status NORMAL/HOOK_FAST/read-only proof, impact brief completeness and
the ChangeCondition derivation table, and truncation tokens.
"""

import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service_operations as ops
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

REPO = "flow-svc"

FILES = {
    "README.md": "# flow-svc\n\nMoves records.\n",
    "OWNERSHIP.md": "# Ownership\n\nTeam flow owns flow-svc.\n",
    "config.yaml": "workers: 4\n",
    "src/flow.py": "class Pipe:\n    pass\n",
    "src/store.py": "class Ledger:\n    pass\n",
}

SUBJECTS = (
    InMemorySubject("cap/flow", m.SubjectKind.CAPABILITY, "flow-cap"),
    InMemorySubject("src/flow.py", m.SubjectKind.COMPONENT, "flow"),
    InMemorySubject(
        "src/flow.py:Pipe", m.SubjectKind.CODE_SYMBOL, "Pipe"
    ),
    InMemorySubject("src/store.py", m.SubjectKind.COMPONENT, "store"),
    InMemorySubject("conf/workers", m.SubjectKind.CONFIGURATION, "workers"),
    InMemorySubject("contract/api", m.SubjectKind.CONTRACT, "api"),
    InMemorySubject(
        "test/test_flow.py", m.SubjectKind.TEST_OR_GATE, "flow-test"
    ),
)

EDGES = (
    InMemoryEdge(
        "src/flow.py:Pipe", m.StructuralEdgeKind.DEFINES, "src/flow.py"
    ),
    InMemoryEdge(
        "src/flow.py", m.StructuralEdgeKind.REFERENCES, "src/store.py"
    ),
    InMemoryEdge(
        "src/flow.py", m.StructuralEdgeKind.REFERENCES,
        "test/test_flow.py",
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
            if path.endswith((".md", ".yaml"))
            else m.EvidenceSourceKind.SOURCE_CODE
        ),
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


_QUOTES = {
    "README.md": "Moves records",
    "OWNERSHIP.md": "Team flow owns flow-svc",
    "config.yaml": "workers: 4",
    "src/flow.py": "class Pipe",
}


def _accepted(path, kind, applicability=None):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref(path),
            authority_kind=kind,
            status=m.AuthorityStatus.ACCEPTED,
            applicability=m.AuthorityApplicability(
                subject_scope=(), description=applicability
            ),
        ),
        support=m.AuthoritySupport(
            quoted_span=_QUOTES[path],
            status_section=path,
            applicability_section=path if applicability else None,
        ),
    )


def _candidates():
    flow = _sid("src/flow.py")
    cap = _sid("cap/flow", m.SubjectKind.CAPABILITY)
    store = _sid("src/store.py")
    test = _sid("test/test_flow.py", m.SubjectKind.TEST_OR_GATE)
    interp = m.DerivationKind.SEMANTIC_INTERPRETATION
    return {
        "src/flow.py": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.PURPOSE,
                    value=m.PurposeValue("moves records", (cap,)),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "README states the flow purpose",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.CONFIGURATION_ENVIRONMENT,
                    value=m.ConfigurationEnvironmentValue(
                        "worker count",
                        _sid("conf/workers", m.SubjectKind.CONFIGURATION),
                    ),
                    evidence=(_ref("config.yaml"),),
                    candidate_authority=_accepted(
                        "config.yaml",
                        m.AuthorityKind.CONFIGURATION_RUNTIME,
                    ),
                    basis=m.SemanticBasis(
                        interp, "config declares the worker count",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.LIFECYCLE_STATE,
                    value=m.LifecycleStateValue(m.LifecyclePhase.USE),
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "flow source shows active use",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.VERIFICATION,
                    value=m.VerificationValue(
                        test, m.VerificationKind.TEST,
                        m.VerificationCurrency.CANDIDATE,
                    ),
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp, "flow test is a verification candidate",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.VERIFICATION,
                    value=m.VerificationValue(
                        test, m.VerificationKind.GATE,
                        m.VerificationCurrency.CURRENT_PASS,
                        observed_revision="fp-1",
                    ),
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "flow gate passed at the observed revision",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                    value=m.OwnershipCustodyValue(
                        _sid("team/flow"), m.OwnershipRole.OWNER,
                        m.OwnershipExclusivity.EXCLUSIVE,
                    ),
                    evidence=(_ref("OWNERSHIP.md"),),
                    candidate_authority=_accepted(
                        "OWNERSHIP.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "ownership record names the flow owner",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.INVARIANT_CONSTRAINT,
                    value=m.InvariantConstraintValue("records are immutable"),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "README states the immutability invariant",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.REPRESENTATION_CONTRACT,
                    value=m.RepresentationContractValue(
                        "wire",
                        _sid("contract/api", m.SubjectKind.CONTRACT),
                        m.RepresentationDirection.SOURCE,
                    ),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "README states the wire representation contract",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow, kind=m.ClaimKind.CAPABILITY_MEMBERSHIP,
                    value=m.CapabilityMembershipValue(cap),
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp, "flow source shows capability membership",
                    ),
                ),
            ),
            relationships=(
                m.CandidateSemanticRelationship(
                    source=flow, kind=m.RelationshipKind.CROSSES_BOUNDARY,
                    target=store,
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp, "flow source crosses into the store",
                    ),
                ),
                m.CandidateSemanticRelationship(
                    source=test, kind=m.RelationshipKind.VERIFIED_BY,
                    target=flow,
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp, "flow test verifies the flow",
                    ),
                ),
            ),
        ),
        "contract/api": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=_sid(
                        "contract/api", m.SubjectKind.CONTRACT
                    ),
                    kind=m.ClaimKind.PURPOSE,
                    value=m.PurposeValue("public record API", ()),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md",
                        m.AuthorityKind.CONTRACT_SPECIFICATION,
                        "public external API surface",
                    ),
                    basis=m.SemanticBasis(
                        interp, "README states the public API purpose",
                    ),
                ),
            ),
            relationships=(),
        ),
    }


def _harness(files=None):
    files = FILES if files is None else files
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        SUBJECTS,
        EDGES,
    )
    evidence = FixtureEvidenceSource(REPO, dict(files))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store, FixtureAgent(_candidates())


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _seeds():
    return (_ref("README.md"), _ref("OWNERSHIP.md"), _ref("config.yaml"))


def _exchange(request, op, structural, evidence, store, agent,
              seeds=None, continuations=None, max_rounds=8):
    """Drive the client protocol to an answer: operate, and while Span
    suspends (chained continuations for multi-subject operations),
    have the test agent perform each task and submit each result."""
    continuations = continuations or ContinuationStore()
    seeds = _seeds() if seeds is None else seeds
    current = op(
        request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    for _ in range(max_rounds):
        if isinstance(current, m.SemanticAnswer):
            return current
        assert isinstance(current, PendingInterpretation), type(current)
        result = agent.perform(current.request)
        current = ops.submit_interpretation(
            current.continuation, result, structural=structural,
            evidence=evidence, store=store, continuations=continuations,
        )
    raise AssertionError("exchange did not settle to an answer")


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


def _impact_request(kind=ops.ChangeKind.BEHAVIOR, description=None,
                     affected=()):
    return ops.SemanticImpactRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, "src/flow.py", (), None),
        change_kind=kind,
        change_description=description,
        bounds=_bounds(),
        affected_assertions=tuple(affected),
    )


class TraceTest(unittest.TestCase):
    def test_frontier_rels_edges_context(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _trace_request(), ops.trace,
                structural, evidence, store, agent,
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
                ops.trace, structural, evidence, store, agent,
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
                _trace_request(
                    relationship_filter=(m.RelationshipKind.VERIFIED_BY,)
                ),
                ops.trace, structural, evidence, store, agent,
            )
            kinds = {r.kind for r in answer.content.relationships}
            self.assertEqual(kinds, {m.RelationshipKind.VERIFIED_BY})
            bounded = _exchange(
                _trace_request(boundary_only=True),
                ops.trace, structural, evidence, store, agent,
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
                _trace_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
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
    def test_normal_full_answer(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _status_request(), ops.status,
                structural, evidence, store, agent,
            )
            content = answer.content
            self.assertIsInstance(content, m.StatusContent)
            self.assertTrue(content.freshness_items)
            # F-15: candidate and current-pass verification distinguished.
            currencies = {
                v.currency for v in content.verification_currency
            }
            self.assertEqual(
                currencies,
                {
                    m.VerificationCurrency.CANDIDATE,
                    m.VerificationCurrency.CURRENT_PASS,
                },
            )
            self.assertEqual(content.refresh_scope.paths, ())
        finally:
            store.close()

    def test_none_target_readiness_only(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = ops.status(
                _status_request(target=None),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsInstance(answer.content, m.StatusContent)
            self.assertEqual(answer.content.freshness_items, ())
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
                _status_request(), structural=structural,
                evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(
                answer.content.readiness,
                m.RepositoryReadiness.UNINITIALIZED,
            )
            self.assertTrue(
                any(
                    "span_initialize_repository" in r.description
                    for r in answer.resolution_requirements
                )
            )
            notice = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/flow.py", (), None
                    ),
                    bounds=_bounds(),
                    mode=m.StatusMode.HOOK_FAST,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(
                notice.readiness, m.RepositoryReadiness.UNINITIALIZED
            )
            self.assertIn("span_initialize_repository",
                          notice.recommended_action)
            # Still uninitialized: nothing was bootstrapped.
            self.assertIsNone(store.load_repository_state(REPO))
            explained = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "src/flow.py", (), None
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
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
                    _status_request(
                        target=m.ClaimRef(id=m.ClaimId("c-1"))
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_known_claim_ref_target_served(self):
        structural, evidence, store, agent = _harness()
        try:
            indexed = _exchange(
                _status_request(), ops.status,
                structural, evidence, store, agent,
            )
            self.assertTrue(indexed.content.claims)
            target = m.ClaimRef(id=indexed.content.claims[0].claim_id)
            answer = ops.status(
                _status_request(target=target),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIsInstance(answer.content, m.StatusContent)
            carried = {
                c.claim_id.value for c in answer.content.claims
            }
            self.assertIn(target.id.value, carried)
        finally:
            store.close()

    def test_hook_fast_read_only_proof(self):
        structural, evidence, store, agent = _harness()
        try:
            continuations = ContinuationStore()
            _exchange(
                _status_request(), ops.status,
                structural, evidence, store, agent,
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
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(notice, m.HookStatusNotice)
            self.assertIs(notice.readiness, m.RepositoryReadiness.READY)
            self.assertGreater(notice.stale_count, 0)
            self.assertTrue(notice.recommended_action)
            # Read-only proof: the store still shows CURRENT (no mark).
            page = store.load_claims(
                REPO, (_sid("src/flow.py"),), (), _bounds()
            )
            current = [
                c for c in page.items
                if c.kind is m.ClaimKind.PURPOSE
            ]
            self.assertTrue(current)
            self.assertTrue(
                all(
                    c.freshness.state is m.FreshnessState.CURRENT
                    for c in current
                )
            )
        finally:
            store.close()

    def test_hook_fast_none_is_baseline_only(self):
        structural, evidence, store, agent = _harness()
        try:
            notice = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=None, bounds=_bounds(),
                    mode=m.StatusMode.HOOK_FAST,
                ),
                structural=structural, evidence=evidence, store=store,
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
            value=m.OwnershipCustodyValue(
                _sid(owner), m.OwnershipRole.OWNER,
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
                value=m.PurposeValue(f"s{n}", ()),
                evidence=(_ref("README.md"),),
                trust=m.TrustState.UNRESOLVED,
                freshness=m.Freshness(
                    m.FreshnessState.CURRENT, reason="t"
                ),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            for n in range(4)
        )
        claims = (a, b) + filler
        conflicts = (m.SemanticConflict(
            left=m.ClaimRef(id=a.claim_id),
            right=m.ClaimRef(id=b.claim_id),
        ),)
        for budget in range(1, 8):
            with self.subTest(budget=budget):
                kept_c, kept_r, kept_conf, truncated, _ = (
                    ops._select_answer_items(
                        claims, (), conflicts, budget
                    )
                )
                kept_ids = {c.claim_id.value for c in kept_c}
                for pair in kept_conf:
                    self.assertIn(pair.left.id.value, kept_ids)
                    self.assertIn(pair.right.id.value, kept_ids)


class ImpactTest(unittest.TestCase):
    def _indexed(self):
        structural, evidence, store, agent = _harness()
        answer = _exchange(
            _impact_request(), ops.impact,
            structural, evidence, store, agent,
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
                self._refs_for(
                    first, {m.ClaimKind.INVARIANT_CONSTRAINT}
                )
                + [
                    ref for ref in self._refs_for(
                        first, {
                            m.ClaimKind.PURPOSE,
                            m.ClaimKind.OWNERSHIP_CUSTODY,
                        }
                    )[:1]
                ]
                + self._refs_for(
                    first, {m.RelationshipKind.CROSSES_BOUNDARY}
                )
            )
            self.assertTrue(affected)
            answer = _exchange(
                _impact_request(affected=affected), ops.impact,
                structural, evidence, store, agent,
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
            self.assertIn(
                m.ImpactEstablishment.STRUCTURAL_POSSIBILITY, establishments
            )
            # Verification + requirements present; refs resolve in-answer.
            self.assertTrue(answer.content.verification)
            carried = {
                c.claim_id.value for c in answer.content.claims
            } | {
                r.relationship_id.value for r in answer.content.relationships
            }
            for ref in (
                list(answer.content.target_context)
                + list(answer.content.verification)
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
            invariant = self._refs_for(
                first, {m.ClaimKind.INVARIANT_CONSTRAINT}
            )
            self.assertTrue(invariant)
            named = _exchange(
                _impact_request(affected=invariant), ops.impact,
                structural, evidence, store, agent,
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
            seeds = _seeds()
            by_kind = {}
            for kind in (
                ops.ChangeKind.OWNERSHIP, ops.ChangeKind.REPRESENTATION,
                ops.ChangeKind.CONFIGURATION, ops.ChangeKind.LIFECYCLE,
            ):
                answer = _exchange(
                    _impact_request(kind), ops.impact,
                    structural, evidence, store, agent,
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
                ops.impact, structural, evidence, store, agent,
                continuations=continuations,
            )
            other_conds = set(other.content.change_conditions)
            # Pure kind-gated rows are suppressed under OTHER ...
            self.assertNotIn(
                m.ChangeCondition.OWNERSHIP_CHANGE, other_conds
            )
            self.assertNotIn(
                m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE,
                other_conds,
            )
            # ... proposal-sensitive rows need typed assertions ...
            self.assertNotIn(m.ChangeCondition.AUTHORITY_CHANGE, other_conds)
            self.assertNotIn(m.ChangeCondition.INVARIANT_CHANGE, other_conds)
            # ... but independently established presence dimensions apply.
            self.assertIn(
                m.ChangeCondition.CONFIGURATION_CHANGE, other_conds
            )
        finally:
            store.close()

    def test_public_contract_change(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        None, "contract/api", (), None
                    ),
                    change_kind=ops.ChangeKind.BEHAVIOR,
                    change_description=None,
                    bounds=_bounds(),
                ),
                ops.impact, structural, evidence, store, agent,
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
                        target=m.SubjectSelector(
                            None, "src/flow.py", (), None
                        ),
                        change_kind=ops.ChangeKind.OTHER,
                        change_description=None,
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                    authority_seeds=_seeds(),
                )
        finally:
            store.close()

    def test_second_page_retrieval(self):
        """Pagination is explicit and redeemable (plan I-39).

        A bounded status over many claims returns a `pg:` cursor;
        resubmitting it yields the remaining items with no repeats and
        no dangling references.
        """
        structural, evidence, store, agent = _harness()
        try:
            first = _exchange(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(max_results=4),
                ),
                ops.status, structural, evidence, store, agent,
            )
            token = first.bound_info.continuation_token
            self.assertTrue(first.bound_info.truncated)
            self.assertTrue(token.startswith("pg:"))
            first_ids = {
                item.item.id.value
                for item in first.content.freshness_items
            }
            second = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/flow.py", (), None),
                    bounds=_bounds(max_results=50),
                    page_token=token,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            second_ids = {
                item.item.id.value
                for item in second.content.freshness_items
            }
            self.assertFalse(first_ids & second_ids)
            self.assertTrue(second_ids)
            carried = {
                c.claim_id.value for c in second.content.claims
            } | {
                r.relationship_id.value
                for r in second.content.relationships
            }
            for item in second.content.freshness_items:
                self.assertIn(item.item.id.value, carried)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
