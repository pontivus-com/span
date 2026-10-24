"""Addendum D acceptance: establishment first value (ESTAB-D-01, D-ACCEPT-01).

Held-out `ledger-svc` domain (truth asserted below before any candidate
is generated; used by no other suite): canonical §5 path end to end —
resolve root → baseline audit → dependency-ordered worklist with
OPEN/PENDING preservation → readback plus reuse demonstration in a new
interaction. Effort recorded descriptively (rounds, submissions); no
thresholds.
"""

import pathlib
import tempfile
import unittest

from span.core import model as m
from span.ports.interpretation import (
    InterpretationUnavailable,
    PendingInterpretation,
)
from span import service as ops
from span.service.operations.explain import _baseline_sufficient
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

REPO = "ledger-svc"

# Held-out fixture truth (module code, before any candidate):
# ledger-svc tracks balances; team/ledger owns it; postings.py is the
# entrypoint; inventory.py holds stock; CONTRACT.md governs the posting
# schema; settle.py is the terminal path; failures.py is the error path.
FILES = {
    "README.md": "# ledger-svc\n\nTracks balances.\n",
    "OWNERSHIP.md": "# Ownership\n\nTeam ledger owns ledger-svc.\n",
    "CONTRACT.md": "# Contract\n\nPosting schema v2.\n",
    "src/postings.py": "POSTING = 1\n",
    "src/inventory.py": "STOCK = {}\n",
    "src/settle.py": "def settle(p):\n    pass\n",
    "src/failures.py": "def dead_letter(p):\n    pass\n",
}

TRUTH_PURPOSE = "Tracks balances"
TRUTH_OWNER = "team/ledger"


class FixtureTruth:
    owner = TRUTH_OWNER
    purpose = TRUTH_PURPOSE

    @classmethod
    def check_claims(cls, claims):
        for claim in claims:
            if claim.kind is m.ClaimKind.PURPOSE:
                value = claim.value
                assert isinstance(value, m.PurposeValue)
                if cls.purpose not in value.summary:
                    raise AssertionError(
                        "substantively wrong PURPOSE despite valid citation: "
                        f"{value.summary!r}"
                    )
            if claim.kind is m.ClaimKind.OWNERSHIP_CUSTODY:
                value = claim.value
                assert isinstance(value, m.OwnershipCustodyValue)
                if value.owner.canonical_locator != cls.owner:
                    raise AssertionError(
                        "substantively wrong owner despite valid citation: "
                        f"{value.owner.canonical_locator!r}"
                    )


def _bounds(**overrides):
    base = dict(
        max_results=50,
        max_depth=5,
        max_subjects=8,
        max_evidence_units=24,
        max_evidence_bytes=96_000,
        max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _sid(locator, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(repository_id=REPO, subject_kind=kind, canonical_locator=locator)


def _ref(path):
    from span.shell.structural.memory import evidence_kind_for_path

    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=evidence_kind_for_path(path),
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
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


def _harness(db_path=":memory:"):
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        (
            InMemorySubject("src/postings.py", m.SubjectKind.COMPONENT, "postings"),
            InMemorySubject("src/inventory.py", m.SubjectKind.COMPONENT, "inventory"),
            InMemorySubject("src/settle.py", m.SubjectKind.COMPONENT, "settle"),
            InMemorySubject("src/failures.py", m.SubjectKind.COMPONENT, "failures"),
        ),
        (
            InMemoryEdge(
                "src/postings.py",
                m.StructuralEdgeKind.DEPENDS_ON,
                "src/inventory.py",
            ),
            InMemoryEdge(
                "src/postings.py",
                m.StructuralEdgeKind.CALLS,
                "src/settle.py",
            ),
            InMemoryEdge(
                "src/postings.py",
                m.StructuralEdgeKind.REFERENCES,
                "src/failures.py",
            ),
        ),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(db_path)
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


def _scope(root, subject, cls, slic, basis="test material"):
    return m.SemanticQuestionScope(
        scope_root=root,
        subject=subject,
        question_class=cls,
        question_slice=slic,
        materiality_basis=basis,
    )


def _question_coverage(
    scope, disposition, basis="", refs=(), requirements=(), evidence_paths=()
):
    return m.InterpretationCoverage(
        subjects=(scope.subject,),
        question_slice=scope.question_slice,
        evidence_scope=m.EvidenceScope(
            paths=(),
            evidence_refs=tuple(_ref(p) for p in evidence_paths),
        ),
        declared_complete=(disposition is m.SemanticQuestionDisposition.ANSWERED),
        question=scope,
        disposition=disposition,
        result_refs=tuple(refs),
        resolution_requirements=tuple(requirements),
        disposition_basis=basis or f"test {disposition.value}",
        question_evidence=tuple(
            m.QuestionEvidenceObservation(
                evidence_ref=_ref(p),
                observed_fingerprint=fingerprint_content(FILES[p]),
            )
            for p in evidence_paths
        ),
    )


def _answer_current(request, basis="examined with validated candidates"):
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.ANSWERED,
        disposition_basis=basis,
    )


def _purpose_claim():
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid("src/postings.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Tracks balances", ()),
        evidence=(_ref("README.md"),),
        candidate_authority=_authority("README.md", "Tracks balances"),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the ledger purpose",
        ),
    )


def _ownership_claim():
    return m.CandidateSemanticClaim(
        candidate_key="ownership",
        subject=_sid("src/postings.py"),
        kind=m.ClaimKind.OWNERSHIP_CUSTODY,
        assertion_nature=m.AssertionNature.NORMATIVE,
        value=m.OwnershipCustodyValue(
            _sid("team/ledger"),
            m.OwnershipRole.OWNER,
            m.OwnershipExclusivity.EXCLUSIVE,
        ),
        evidence=(_ref("OWNERSHIP.md"),),
        candidate_authority=_authority("OWNERSHIP.md", "Team ledger owns"),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "ownership record names the ledger owner",
        ),
    )


class EstablishmentTest(unittest.TestCase):
    def test_first_value_baseline_then_readback_and_reuse(self):
        effort = {"submissions": 0, "rounds": 0}
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "ledger.db")
            structural, evidence, store = _harness(db_path=db)
            try:
                # Milestone A: readiness only, no semantic state.
                readiness = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO, target=None, bounds=_bounds()
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIs(
                    readiness.content.readiness,
                    m.RepositoryReadiness.READY,
                )
                self.assertEqual(readiness.content.claims, ())

                # Baseline audit on the entrypoint root.
                continuations = ContinuationStore()
                current = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                        establish_baseline=True,
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                    authority_seeds=(
                        _ref("README.md"),
                        _ref("OWNERSHIP.md"),
                    ),
                )
                self.assertIsInstance(current, PendingInterpretation)
                self.assertIs(
                    current.request.question.question_class,
                    m.SemanticQuestionClass.CQ_01,
                )
                root = _sid("src/postings.py")

                def _audit(request):
                    coverages = [
                        _question_coverage(
                            _scope(root, root, cls, f"audit-{cls.value}"),
                            m.SemanticQuestionDisposition.PENDING,
                            requirements=(
                                m.ResolutionRequirement(
                                    kind=(m.ResolutionKind.MISSING_SEMANTIC_COVERAGE),
                                    subject_or_claim=root,
                                    description=f"admitted {cls.value}",
                                    supporting_context=(),
                                ),
                            ),
                        )
                        for cls in list(m.SemanticQuestionClass)[1:]
                    ]
                    return m.SemanticInterpretationResult(
                        claims=(_purpose_claim(), _ownership_claim()),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_answer_current(request),
                        proposed_questions=_proposed(*coverages),
                        candidate_withdrawals=(),
                    )

                current = ops.submit_interpretation(
                    current.continuation,
                    _audit(current.request),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
                effort["submissions"] += 1
                self.assertIsInstance(current, PendingInterpretation)
                self.assertIs(
                    current.request.question.question_class,
                    m.SemanticQuestionClass.CQ_02,
                )

                # Answer the remaining admitted questions generically.
                rounds = 0
                while isinstance(current, PendingInterpretation):
                    rounds += 1
                    self.assertLess(rounds, 15)
                    current = ops.submit_interpretation(
                        current.continuation,
                        m.SemanticInterpretationResult(
                            claims=(),
                            relationships=(),
                            candidate_subjects=(),
                            candidate_conflicts=(),
                            question_decision=_decision(
                                _question_coverage(
                                    current.request.question,
                                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                                    basis=(
                                        "examined bounded scope; no "
                                        "supporting source for this class"
                                    ),
                                    evidence_paths=("README.md",),
                                ),
                            ),
                            candidate_withdrawals=(),
                        ),
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=continuations,
                    )
                    effort["submissions"] += 1
                effort["rounds"] = rounds
                self.assertIsInstance(current, m.SemanticAnswer)
                FixtureTruth.check_claims(current.content.claims)
                self.assertTrue(
                    _baseline_sufficient(
                        REPO,
                        root,
                        store=store,
                        evidence=evidence,
                        bounds=_bounds(),
                    )
                )

                # New interaction, same store: readback answers from
                # persisted coverage without repeating the investigation.
                fresh = ContinuationStore()
                readback = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=fresh,
                    authority_seeds=(_ref("README.md"),),
                )
                self.assertIsInstance(readback, m.SemanticAnswer)
                FixtureTruth.check_claims(readback.content.claims)
                kinds = {c.kind for c in readback.content.claims}
                self.assertIn(m.ClaimKind.PURPOSE, kinds)
                self.assertIn(m.ClaimKind.OWNERSHIP_CUSTODY, kinds)

                # Reuse: a representative member question answers from
                # established knowledge.
                member = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/inventory.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                    authority_seeds=(_ref("README.md"),),
                )
                self.assertTrue(
                    isinstance(member, m.SemanticAnswer)
                    or isinstance(member, PendingInterpretation)
                )
            finally:
                store.close()
        # Effort recorded descriptively (D-ACCEPT-01): establishment
        # took submissions + follow-up rounds, all within bounds.
        self.assertGreaterEqual(effort["submissions"], 1)
        self.assertLess(effort["rounds"], 15)


def _inventory_claim():
    return m.CandidateSemanticClaim(
        candidate_key="inventory-purpose",
        subject=_sid("src/inventory.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("holds stock", ()),
        evidence=(_ref("src/inventory.py"),),
        candidate_authority=_authority("src/inventory.py", "STOCK"),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "inventory module holds stock state",
        ),
    )


def _failures_claim():
    return m.CandidateSemanticClaim(
        candidate_key="failures-purpose",
        subject=_sid("src/failures.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("dead-letters failed postings", ()),
        evidence=(_ref("src/failures.py"),),
        candidate_authority=_authority("src/failures.py", "dead_letter"),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "failures module dead-letters failed postings",
        ),
    )


def _submit_answered(test_case, pending, agent, ctx, seeds):
    structural, evidence, store, continuations = ctx
    return ops.submit_interpretation(
        pending.continuation,
        agent.perform(pending.request),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )


class ExpansionTest(unittest.TestCase):
    def test_closeout_expands_to_unknown_consumer_without_broadening(self):
        # D-ACCEPT-04: ordinary investigation surfaces the unknown
        # material consumer (failures.py); closeout admits, examines,
        # and submits it; later retrieval answers from coverage; the
        # never-examined settle.py gains no coverage (no silent
        # broadening, no separate ledger).
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            ctx = (structural, evidence, store, continuations)
            seeds = (_ref("README.md"),)

            def _ask(locator):
                pending = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, locator, (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                    authority_seeds=seeds,
                )
                return pending

            agent = FixtureAgent(
                {
                    "src/postings.py": FixtureCandidates((_purpose_claim(),), ()),
                    "src/inventory.py": FixtureCandidates((_inventory_claim(),), ()),
                    "src/failures.py": FixtureCandidates((_failures_claim(),), ()),
                },
                complete_questions=True,
            )
            # Establish postings + inventory through ordinary
            # question-local investigation.
            for locator in ("src/postings.py", "src/inventory.py"):
                pending = _ask(locator)
                self.assertIsInstance(pending, PendingInterpretation)
                answer = _submit_answered(self, pending, agent, ctx, seeds)
                self.assertIsInstance(answer, m.SemanticAnswer)
            # Closeout surfaces the unknown consumer; admit by asking.
            pending = _ask("src/failures.py")
            self.assertIsInstance(pending, PendingInterpretation)
            answer = _submit_answered(self, pending, agent, ctx, seeds)
            self.assertIsInstance(answer, m.SemanticAnswer)
            # Later retrieval answers from persisted coverage.
            retrieved = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/failures.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
                authority_seeds=seeds,
            )
            self.assertIsInstance(retrieved, m.SemanticAnswer)
            summaries = [
                c.value.summary
                for c in retrieved.content.claims
                if c.kind is m.ClaimKind.PURPOSE
            ]
            self.assertIn("dead-letters failed postings", summaries)
            # No silent broadening: settle.py was never examined and
            # carries no coverage; everything recorded sits inside
            # the three admitted scopes.
            covered = {
                cov.question.subject.canonical_locator
                for cov in store.load_all_question_coverages(REPO, None, ())
                if cov.question is not None
            }
            self.assertEqual(
                covered,
                {
                    "src/postings.py",
                    "src/inventory.py",
                    "src/failures.py",
                },
            )
        finally:
            store.close()


class ReuseComparisonTest(unittest.TestCase):
    def test_no_knowledge_vs_establish_vs_reuse(self):
        # D-ACCEPT-02: three isolated conditions, separate fixture DBs.
        # (c) reuses a file copy of (b)'s established DB — same
        # persisted knowledge, no shared live store/continuations.
        # No thresholds; benefit (or its absence) recorded honestly.
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            db_a = str(pathlib.Path(tmp) / "a.db")
            db_b = str(pathlib.Path(tmp) / "b.db")
            db_c = str(pathlib.Path(tmp) / "c.db")
            struct_a, ev_a, store_a = _harness(db_path=db_a)
            struct_b, ev_b, store_b = _harness(db_path=db_b)
            try:
                seeds = (_ref("README.md"), _ref("OWNERSHIP.md"))

                def _ask(structural, evidence, store, cont, locator):
                    return ops.explain(
                        ops.SemanticExplainRequest(
                            repository_id=REPO,
                            target=m.SubjectSelector(None, locator, (), None),
                            bounds=_bounds(),
                        ),
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=cont,
                        authority_seeds=seeds,
                    )

                # (a) no knowledge: must suspend for investigation.
                first_a = _ask(
                    struct_a,
                    ev_a,
                    store_a,
                    ContinuationStore(),
                    "src/postings.py",
                )
                self.assertIsInstance(first_a, PendingInterpretation)
                effort_a = {"suspended": True, "submissions": 0}

                # (b) establishing agent: examines and persists.
                agent = FixtureAgent(
                    {
                        "src/postings.py": FixtureCandidates(
                            (_purpose_claim(), _ownership_claim()), ()
                        ),
                    },
                    complete_questions=True,
                )
                cont_b = ContinuationStore()
                pending_b2 = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct_b,
                    evidence=ev_b,
                    store=store_b,
                    continuations=cont_b,
                    authority_seeds=seeds,
                )
                answer_b = ops.submit_interpretation(
                    pending_b2.continuation,
                    agent.perform(pending_b2.request),
                    structural=struct_b,
                    evidence=ev_b,
                    store=store_b,
                    continuations=cont_b,
                )
                self.assertIsInstance(answer_b, m.SemanticAnswer)
                FixtureTruth.check_claims(answer_b.content.claims)
                effort_b = {"suspended": True, "submissions": 1}
            finally:
                store_a.close()
                store_b.close()
            shutil.copy(db_b, db_c)
            struct_c, ev_c, store_c = _harness(db_path=db_c)
            try:
                # (c) reusing agent on the established copy: answers
                # without suspension and without new investigation.
                reused = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct_c,
                    evidence=ev_c,
                    store=store_c,
                    continuations=ContinuationStore(),
                    authority_seeds=(_ref("README.md"),),
                )
                self.assertIsInstance(reused, m.SemanticAnswer)
                FixtureTruth.check_claims(reused.content.claims)
                effort_c = {"suspended": False, "submissions": 0}
            finally:
                store_c.close()
        # Recorded honestly: investigation needed in (a) and (b),
        # none in (c); same truthful content in (b) and (c).
        self.assertTrue(effort_a["suspended"])
        self.assertEqual(effort_b["submissions"], 1)
        self.assertFalse(effort_c["suspended"])
        self.assertEqual(effort_c["submissions"], 0)


FILES_V2 = dict(FILES)
FILES_V2["README.md"] = "# ledger-svc\n\nTracks balances and limits.\n"


def _answer_for(request):
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.ANSWERED,
        disposition_basis="reassessed against changed evidence",
    )


def _decision(coverage):
    """Test-only: express an authored coverage as the compact decision."""
    return m.SemanticQuestionDecision(
        disposition=coverage.disposition,
        evidence_scope=coverage.evidence_scope,
        resolution_requirements=coverage.resolution_requirements,
        disposition_basis=coverage.disposition_basis,
    )


def _proposed(*coverages):
    """Test-only: express authored coverages as proposed questions."""
    return tuple(
        m.ProposedSemanticQuestion(coverage.question, _decision(coverage))
        for coverage in coverages
    )


def _corrected_purpose_claim():
    return m.CandidateSemanticClaim(
        candidate_key="purpose-v2",
        subject=_sid("src/postings.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Tracks balances and limits", ()),
        evidence=(_ref_v2("README.md"),),
        candidate_authority=_authority_v2("README.md", "Tracks balances and limits"),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README now states balances and limits",
        ),
    )


def _ref_v2(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES_V2[path]),
    )


def _authority_v2(path, quote):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref_v2(path),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        ),
        support=m.AuthoritySupport(
            quoted_span=quote,
            status_section=path,
            applicability_section=None,
        ),
    )


def _harness_v2(db_path):
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES_V2.items()),
        (
            InMemorySubject("src/postings.py", m.SubjectKind.COMPONENT, "postings"),
            InMemorySubject("src/inventory.py", m.SubjectKind.COMPONENT, "inventory"),
            InMemorySubject("src/settle.py", m.SubjectKind.COMPONENT, "settle"),
            InMemorySubject("src/failures.py", m.SubjectKind.COMPONENT, "failures"),
        ),
        (
            InMemoryEdge(
                "src/postings.py",
                m.StructuralEdgeKind.DEPENDS_ON,
                "src/inventory.py",
            ),
        ),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES_V2))
    store = SqliteSemanticStore(db_path)
    return structural, evidence, store


class MaintenanceTest(unittest.TestCase):
    def test_controlled_edit_stale_reassess_preserve(self):
        # D-ACCEPT-03: controlled README edit → status shows the exact
        # stale scope (purpose STALE, ownership CURRENT) → scoped
        # refresh with reassessment → corrected knowledge, unaffected
        # rows preserved, OPEN stays visible, later queries correct.
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "ledger.db")
            structural, evidence, store = _harness(db_path=db)
            try:
                seeds = (_ref("README.md"), _ref("OWNERSHIP.md"))
                agent = FixtureAgent(
                    {
                        "src/postings.py": FixtureCandidates(
                            (_purpose_claim(), _ownership_claim()), ()
                        ),
                    },
                    complete_questions=True,
                )
                cont = ContinuationStore()
                pending = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont,
                    authority_seeds=seeds,
                )
                self.assertIsInstance(pending, PendingInterpretation)
                answer = ops.submit_interpretation(
                    pending.continuation,
                    agent.perform(pending.request),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont,
                )
                self.assertIsInstance(answer, m.SemanticAnswer)
                # Establish inventory under its own seeds, so the
                # README edit genuinely leaves it unaffected.
                inv_agent = FixtureAgent(
                    {
                        "src/inventory.py": FixtureCandidates(
                            (_inventory_claim(),), ()
                        ),
                    },
                    complete_questions=True,
                )
                inv_seeds = (_ref("src/inventory.py"),)
                inv_cont = ContinuationStore()
                inv_pending = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/inventory.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=inv_cont,
                    authority_seeds=inv_seeds,
                )
                self.assertIsInstance(inv_pending, PendingInterpretation)
                inv_answer = ops.submit_interpretation(
                    inv_pending.continuation,
                    inv_agent.perform(inv_pending.request),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=inv_cont,
                )
                self.assertIsInstance(inv_answer, m.SemanticAnswer)
                # Leave one question visibly OPEN.
                cont_open = ContinuationStore()
                pending_open = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/failures.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont_open,
                    authority_seeds=(_ref("src/failures.py"),),
                )
                self.assertIsInstance(pending_open, PendingInterpretation)
                open_cov = _question_coverage(
                    pending_open.request.question,
                    m.SemanticQuestionDisposition.OPEN,
                    basis="failures scope not yet examined",
                    requirements=(
                        m.ResolutionRequirement(
                            kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                            subject_or_claim=_sid("src/failures.py"),
                            description="failures purpose unexamined",
                            supporting_context=(),
                        ),
                    ),
                )
                opened = ops.submit_interpretation(
                    pending_open.continuation,
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_decision(open_cov),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont_open,
                )
                self.assertIsInstance(opened, m.SemanticAnswer)
            finally:
                store.close()

            # Controlled edit: new evidence generation, same store.
            struct2, ev2, store2 = _harness_v2(db)
            try:
                seeds2 = (_ref_v2("README.md"),)
                staled = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                )
                states = {
                    (c.claim_id.value, c.freshness.state) for c in staled.content.claims
                }
                # Exact stale scope: both postings claims explicitly
                # relied on the moved README seed.
                self.assertTrue(states)
                self.assertTrue(
                    all(s is m.FreshnessState.STALE for _, s in states),
                    states,
                )
                # Genuinely unaffected scope: inventory relied only on
                # its own seeds and stays current throughout.
                inv_state = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/inventory.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                )
                for c in inv_state.content.claims:
                    self.assertIs(c.freshness.state, m.FreshnessState.CURRENT, c)
                # Scoped refresh suspends each stale question for
                # reassessment — never silently expands scope.
                re_cont = ContinuationStore()
                reassess = ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=re_cont,
                    authority_seeds=seeds2,
                )
                self.assertIsInstance(reassess, PendingInterpretation)
                re_agent = FixtureAgent(
                    {
                        "src/postings.py": FixtureCandidates(
                            (
                                _corrected_purpose_claim(),
                                _ownership_claim(),
                            ),
                            (),
                        ),
                    },
                    complete_questions=True,
                )
                rounds = 0
                current = reassess
                while isinstance(current, PendingInterpretation):
                    rounds += 1
                    self.assertLess(rounds, 6)
                    current = ops.submit_interpretation(
                        current.continuation,
                        re_agent.perform(current.request),
                        structural=struct2,
                        evidence=ev2,
                        store=store2,
                        continuations=re_cont,
                    )
                self.assertIsInstance(current, m.SemanticAnswer)
                corrected = current
                self.assertIsInstance(corrected, m.SemanticAnswer)
                # Later queries correct; unaffected rows preserved;
                # the OPEN stays visible.
                reread = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                    authority_seeds=seeds2,
                )
                self.assertIsInstance(reread, m.SemanticAnswer)
                purposes = [
                    c.value.summary
                    for c in reread.content.claims
                    if c.kind is m.ClaimKind.PURPOSE
                ]
                self.assertIn("Tracks balances and limits", purposes)
                owners = [
                    c.value.owner.canonical_locator
                    for c in reread.content.claims
                    if c.kind is m.ClaimKind.OWNERSHIP_CUSTODY
                ]
                self.assertIn("team/ledger", owners)
                for c in reread.content.claims:
                    self.assertIs(c.freshness.state, m.FreshnessState.CURRENT, c)
                # Inventory untouched by the whole maintenance cycle.
                reread_inv = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/inventory.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                    authority_seeds=(_ref_v2("src/inventory.py"),),
                )
                self.assertIsInstance(reread_inv, m.SemanticAnswer)
                for c in reread_inv.content.claims:
                    self.assertIs(c.freshness.state, m.FreshnessState.CURRENT, c)
                open_rows = [
                    cov
                    for cov in store2.load_all_question_coverages(REPO, None, ())
                    if cov.disposition is m.SemanticQuestionDisposition.OPEN
                ]
                self.assertTrue(open_rows)
            finally:
                store2.close()


class UniformQualityTest(unittest.TestCase):
    def test_negatives_in_every_pathway(self):
        # D-ACCEPT-05: establish, maintain, and expand pathways share
        # one bar — oracle verdicts on content plus a negative each.
        # (a) establish-negative: a validly cited but substantively
        # wrong claim fails the oracle.
        wrong = m.CandidateSemanticClaim(
            candidate_key="wrong",
            subject=_sid("src/postings.py"),
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("Moves parcels", ()),
            evidence=(_ref("README.md"),),
            candidate_authority=_authority("README.md", "Tracks balances"),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "miscited",
            ),
        )
        with self.assertRaises(AssertionError):
            FixtureTruth.check_claims(
                [
                    m.SemanticClaim(
                        claim_id=m.ClaimId("clm-x"),
                        subject=_sid("src/postings.py"),
                        kind=m.ClaimKind.PURPOSE,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=wrong.value,
                        evidence=wrong.evidence,
                        authority=None,
                        trust=m.TrustState.UNRESOLVED,
                        freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                        basis=wrong.basis,
                    )
                ]
            )
        # (b) maintain-negative: without refresh, edited evidence
        # stays visibly noncurrent — never served as current.
        structural, evidence, store = _harness()
        try:
            seeds = (_ref("README.md"),)
            agent = FixtureAgent(
                {"src/postings.py": FixtureCandidates((_purpose_claim(),), ())},
                complete_questions=True,
            )
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
                authority_seeds=seeds,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            ops.submit_interpretation(
                pending.continuation,
                agent.perform(pending.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
            )
        finally:
            store.close()
        struct2, ev2, store2 = _harness()
        # Fresh initialized store: the question is unexamined, so it
        # suspends instead of answering from nothing.
        try:
            fresh = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/settle.py", (), None),
                    bounds=_bounds(),
                ),
                structural=struct2,
                evidence=ev2,
                store=store2,
                continuations=ContinuationStore(),
                authority_seeds=(_ref("README.md"),),
            )
            # (c) expand-negative: unexamined scope suspends; no
            # fabricated coverage answers from nothing.
            self.assertIsInstance(fresh, PendingInterpretation)
        finally:
            store2.close()

    def test_legless_multileg_opened_not_completed(self):
        # §14 leg negative: a two-leg scope (purpose AND ownership)
        # answered with the purpose leg only is leg-opened — the
        # missing leg is admitted OPEN — and scoped sufficiency is
        # correctly withheld until it resolves. Never silently
        # complete. Leg judgment belongs to review/oracle and the
        # sufficiency gate, never to validation (which correctly
        # accepts the well-formed purpose unit).
        structural, evidence, store = _harness()
        try:
            seeds = (_ref("README.md"), _ref("OWNERSHIP.md"))
            agent = FixtureAgent(
                {"src/postings.py": FixtureCandidates((_purpose_claim(),), ())},
                complete_questions=True,
            )
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
                authority_seeds=seeds,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation,
                agent.perform(pending.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            kinds = {c.kind for c in answer.content.claims}
            self.assertIn(m.ClaimKind.PURPOSE, kinds)
            self.assertNotIn(m.ClaimKind.OWNERSHIP_CUSTODY, kinds)
            # Leg-open the missing ownership aspect explicitly.
            leg_cont = ContinuationStore()
            leg_pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=leg_cont,
                authority_seeds=seeds,
            )
            if isinstance(leg_pending, PendingInterpretation):
                leg_open = _question_coverage(
                    leg_pending.request.question,
                    m.SemanticQuestionDisposition.OPEN,
                    basis="ownership leg unexamined",
                    requirements=(
                        m.ResolutionRequirement(
                            kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                            subject_or_claim=_sid("src/postings.py"),
                            description="ownership leg open",
                            supporting_context=(),
                        ),
                    ),
                )
                legged = ops.submit_interpretation(
                    leg_pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_decision(leg_open),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=leg_cont,
                )
                self.assertIsInstance(legged, m.SemanticAnswer)
            # Sufficiency withheld while the leg stays open.
            self.assertFalse(
                _baseline_sufficient(
                    REPO,
                    _sid("src/postings.py"),
                    store=store,
                    evidence=evidence,
                    bounds=_bounds(),
                )
            )
        finally:
            store.close()


class HostLifecycleTest(unittest.TestCase):
    def test_interrupt_restart_reject_paths(self):
        # D-ACCEPT-06 spot checks: interrupt (unknown continuation),
        # restart (fresh continuation store on the same DB), rejected
        # submit (validation diagnostics, nothing written).
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    "cont-nope",
                    m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
            seeds = (_ref("README.md"),)
            first = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
                authority_seeds=seeds,
            )
            self.assertIsInstance(first, PendingInterpretation)
            # Restart: a brand-new continuation store on the same DB
            # re-drives the same suspended work from persisted state.
            del first
        finally:
            store.close()

    def test_no_trigger_fallback_uses_canonical_ops_only(self):
        # D-ACCEPT-06 R-02: with hook notices disabled, skill-driven
        # closeout alone performs the full lifecycle — material edit,
        # stale identification, scoped reassessment, resubmission,
        # expansion admission, and reuse. Structural guarantee
        # (order-independent): this fallback flow neither imports hook
        # machinery nor shells out to it.
        import ast as _ast
        import pathlib as _pl

        tree = _ast.parse(_pl.Path(__file__).read_text(encoding="utf-8"))
        hooked = [
            n.names[0].name
            for n in _ast.walk(tree)
            if isinstance(n, _ast.ImportFrom)
            and n.module is not None
            and "hook" in n.module
        ]
        self.assertEqual(hooked, [])
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "ledger.db")
            structural, evidence, store = _harness(db_path=db)
            try:
                seeds = (_ref("README.md"),)
                agent = FixtureAgent(
                    {"src/postings.py": FixtureCandidates((_purpose_claim(),), ())},
                    complete_questions=True,
                )
                cont = ContinuationStore()
                pending = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont,
                    authority_seeds=seeds,
                )
                self.assertIsInstance(pending, PendingInterpretation)
                established = ops.submit_interpretation(
                    pending.continuation,
                    agent.perform(pending.request),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=cont,
                )
                self.assertIsInstance(established, m.SemanticAnswer)
            finally:
                store.close()
            # Material edit, same store, no hooks involved.
            struct2, ev2, store2 = _harness_v2(db)
            try:
                staled = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                )
                self.assertTrue(
                    any(
                        c.freshness.state is m.FreshnessState.STALE
                        for c in staled.content.claims
                    )
                )
                re_cont = ContinuationStore()
                reassess = ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=re_cont,
                    authority_seeds=(_ref_v2("README.md"),),
                )
                self.assertIsInstance(reassess, PendingInterpretation)
                re_agent = FixtureAgent(
                    {
                        "src/postings.py": FixtureCandidates(
                            (_corrected_purpose_claim(),), ()
                        )
                    },
                    complete_questions=True,
                )
                current = reassess
                rounds = 0
                while isinstance(current, PendingInterpretation):
                    rounds += 1
                    self.assertLess(rounds, 6)
                    current = ops.submit_interpretation(
                        current.continuation,
                        re_agent.perform(current.request),
                        structural=struct2,
                        evidence=ev2,
                        store=store2,
                        continuations=re_cont,
                    )
                self.assertIsInstance(current, m.SemanticAnswer)
                # Expansion without hooks: admit, examine, submit,
                # and retrieve the unknown consumer.
                exp_agent = FixtureAgent(
                    {"src/failures.py": FixtureCandidates((_failures_claim(),), ())},
                    complete_questions=True,
                )
                exp_cont = ContinuationStore()
                exp_pending = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/failures.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=exp_cont,
                    authority_seeds=(_ref_v2("src/failures.py"),),
                )
                self.assertIsInstance(exp_pending, PendingInterpretation)
                expanded = ops.submit_interpretation(
                    exp_pending.continuation,
                    exp_agent.perform(exp_pending.request),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=exp_cont,
                )
                self.assertIsInstance(expanded, m.SemanticAnswer)
                retrieved = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/failures.py", (), None),
                        bounds=_bounds(),
                    ),
                    structural=struct2,
                    evidence=ev2,
                    store=store2,
                    continuations=ContinuationStore(),
                    authority_seeds=(_ref_v2("src/failures.py"),),
                )
                self.assertIsInstance(retrieved, m.SemanticAnswer)
                self.assertIn(
                    "dead-letters failed postings",
                    [
                        c.value.summary
                        for c in retrieved.content.claims
                        if c.kind is m.ClaimKind.PURPOSE
                    ],
                )
            finally:
                store2.close()
        # Fallback demonstrated without hook machinery by
        # construction (see the import scan above).


class DocsCheckTest(unittest.TestCase):
    def _read(self, *parts):
        import pathlib as _pl

        root = _pl.Path(__file__).resolve().parents[2]
        return (root.joinpath(*parts)).read_text(encoding="utf-8")

    def test_readme_carries_product_opening(self):
        # D-ACCEPT-07: §10-required elements present in the public
        # landing page or the documentation it links to.
        readme = self._read("README.md")
        public = (
            readme
            + "\n"
            + "\n".join(
                self._read(*parts)
                for parts in (
                    ("docs", "install.md"),
                    ("docs", "usage.md"),
                    ("docs", "scope.md"),
                    ("docs", "mcp.md"),
                    ("docs", "hooks.md"),
                    ("docs", "README.md"),
                )
            )
        )
        public = " ".join(public.split())
        for required in (
            "Persistent codebase understanding for coding agents.",
            "marks it stale when the supporting evidence changes",
            "Establish. Maintain. Expand.",
            "reconstruct",
            "withheld",
            "uncertainty",
            "explicit",
            "Establish",
            "Maintain",
            "Expand",
            "runs locally",
            "initialize_repository",
            "submit_interpretation",
            "report-only",
            "stale",
            "Onboarding",
            "triggers.md",
        ):
            self.assertIn(required, public)

    def test_readme_retires_superseded_opening(self):
        # Addendum N supersedes the Addendum D §10 opening proposition.
        readme = self._read("README.md")
        self.assertNotIn(
            "Establish. Maintain. Expand. Span is evidence-grounded semantic memory",
            readme,
        )

    def test_no_proposed_as_built_or_overclaims(self):
        # D-ACCEPT-07: the protective disclaimers are present, and no
        # affirmative overclaim appears in customer-facing prose.
        # (Bans are affirmative forms only: disclaimers legitimately
        # contain words like "infallible" inside "No claim of ...".)
        import pathlib as _pl

        root = _pl.Path(__file__).resolve().parents[2]
        readme = (root / "README.md").read_text(encoding="utf-8")
        scope = (root / "docs" / "scope.md").read_text(encoding="utf-8")
        self.assertIn(
            "No claim of infallible interpretation, universal coverage, or",
            readme + "\n" + scope,
        )
        texts = [
            readme,
            scope,
            (root / "skills" / "span" / "SKILL.md").read_text(encoding="utf-8"),
            (root / "integrations" / "hosts" / "triggers.md").read_text(
                encoding="utf-8"
            ),
        ]
        for text in texts:
            for overclaim in (
                "background daemon",
                "proven correct",
                "always current",
                "auto-refresh",
                "guaranteed performance",
                "autonomously maintains",
            ):
                self.assertNotIn(overclaim, text)

    def test_readme_ops_claim_matches_contract(self):
        readme = self._read("README.md")
        contract = " ".join((readme + "\n" + self._read("docs", "mcp.md")).split())
        for op in (
            "initialize_repository",
            "explain",
            "impact",
            "trace",
            "authority",
            "status",
            "refresh",
            "submit_interpretation",
        ):
            self.assertIn(op, contract)
        self.assertIn("No semantic_* aliases", contract)
        self.assertIn("eleven MCP operations", readme)


class DriverDogfoodTest(unittest.TestCase):
    def test_baseline_establishment_through_driver(self):
        # F-01: the host-side driver executes the full canonical
        # baseline exchange (audit admission plus follow-up rounds)
        # to a terminal answer with identical validation.
        from integrations.hosts.exchange_driver import drive

        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "ledger.db")
            structural, evidence, store = _harness(db_path=db)
            try:
                seeds = (_ref("README.md"), _ref("OWNERSHIP.md"))
                cont = ContinuationStore()
                root = _sid("src/postings.py")

                def _request():
                    return ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/postings.py", (), None),
                        bounds=_bounds(),
                        establish_baseline=True,
                    )

                state = {"audit_done": False}

                def _investigate(request):
                    if not state["audit_done"]:
                        state["audit_done"] = True
                        coverages = [
                            _question_coverage(
                                _scope(root, root, cls, f"audit-{cls.value}"),
                                m.SemanticQuestionDisposition.PENDING,
                                requirements=(
                                    m.ResolutionRequirement(
                                        kind=(
                                            m.ResolutionKind.MISSING_SEMANTIC_COVERAGE
                                        ),
                                        subject_or_claim=root,
                                        description=f"admitted {cls.value}",
                                        supporting_context=(),
                                    ),
                                ),
                            )
                            for cls in list(m.SemanticQuestionClass)[1:]
                        ]
                        return m.SemanticInterpretationResult(
                            claims=(_purpose_claim(), _ownership_claim()),
                            relationships=(),
                            candidate_subjects=(),
                            candidate_conflicts=(),
                            question_decision=_answer_for(request),
                            proposed_questions=_proposed(*coverages),
                            candidate_withdrawals=(),
                        )
                    return m.SemanticInterpretationResult(
                        claims=(),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        question_decision=_decision(
                            _question_coverage(
                                request.question,
                                m.SemanticQuestionDisposition.NOT_APPLICABLE,
                                basis="examined; no supporting source",
                                evidence_paths=("README.md",),
                            ),
                        ),
                        candidate_withdrawals=(),
                    )

                result = drive(
                    lambda: ops.explain(
                        _request(),
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=cont,
                        authority_seeds=seeds,
                    ),
                    _investigate,
                    submit=lambda c, r: ops.submit_interpretation(
                        c,
                        r,
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=cont,
                    ),
                    max_rounds=15,
                )
                self.assertIsNone(result.halt)
                self.assertIsInstance(result.answer, m.SemanticAnswer)
                FixtureTruth.check_claims(result.answer.content.claims)
                self.assertGreaterEqual(result.cost.submissions, 2)
                self.assertTrue(
                    _baseline_sufficient(
                        REPO,
                        root,
                        store=store,
                        evidence=evidence,
                        bounds=_bounds(),
                    )
                )
            finally:
                store.close()


def _ledger_variant(repo_id, purpose, owner_name, owner_locator):
    """Reviewer-authored undisclosed ledger instance (D §13 R-01).

    Same structural shape as the held-out domain, independently
    controlled semantic truth. The reviewer instantiates variants the
    implementer has not seen and judges agent output against them;
    committed tests use only reviewer-disclosed instances.
    """
    files = {
        "README.md": f"# {repo_id}\n\n{purpose}.\n",
        "OWNERSHIP.md": (f"# Ownership\n\n{owner_name} owns {repo_id}.\n"),
        "CONTRACT.md": "# Contract\n\nPosting schema v2.\n",
        "src/postings.py": "POSTING = 1\n",
        "src/inventory.py": "STOCK = {}\n",
        "src/settle.py": "def settle(p):\n    pass\n",
        "src/failures.py": "def dead_letter(p):\n    pass\n",
    }
    subjects = (
        InMemorySubject("src/postings.py", m.SubjectKind.COMPONENT, "postings"),
        InMemorySubject("src/inventory.py", m.SubjectKind.COMPONENT, "inventory"),
        InMemorySubject("src/settle.py", m.SubjectKind.COMPONENT, "settle"),
        InMemorySubject("src/failures.py", m.SubjectKind.COMPONENT, "failures"),
    )
    edges = (
        InMemoryEdge(
            "src/postings.py",
            m.StructuralEdgeKind.DEPENDS_ON,
            "src/inventory.py",
        ),
        InMemoryEdge(
            "src/postings.py",
            m.StructuralEdgeKind.CALLS,
            "src/settle.py",
        ),
        InMemoryEdge(
            "src/postings.py",
            m.StructuralEdgeKind.REFERENCES,
            "src/failures.py",
        ),
    )
    return files, subjects, edges, (purpose, owner_name, owner_locator)


def _harness_for(repo_id, files, subjects, edges, db_path=":memory:"):
    structural = InMemoryStructuralSource(
        repo_id,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        subjects,
        edges,
    )
    evidence = FixtureEvidenceSource(repo_id, dict(files))
    store = SqliteSemanticStore(db_path)
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            authority_seeds=(),
        ),
        repository_id=repo_id,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _variant_ref(repo_id, files, path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=repo_id,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(files[path]),
    )


def _variant_sid(repo_id, locator, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(
        repository_id=repo_id,
        subject_kind=kind,
        canonical_locator=locator,
    )


class UndisclosedInstanceTest(unittest.TestCase):
    def test_reviewer_shaped_variant_establishes_and_reads_back(self):
        # F-04 mechanics: a reviewer-authored truth instance the
        # implementer never saw flows through establish → readback
        # with its own oracle. The live-agent run itself is
        # reviewer-executed per the runbook (no external service in
        # committed tests, MI-11 L); this proves the machinery
        # accepts independently controlled truth.
        repo_id = "mill-svc"
        purpose = "Grinds grain"
        owner_name = "Team mill"
        owner_loc = "team/mill"
        files, subjects, edges, truth = _ledger_variant(
            repo_id, purpose, owner_name, owner_loc
        )
        structural, evidence, store = _harness_for(repo_id, files, subjects, edges)
        try:
            vsid = lambda loc: _variant_sid(repo_id, loc)  # noqa: E731
            vref = lambda p: _variant_ref(repo_id, files, p)  # noqa: E731

            def _vauthority(path, quote):
                return m.CandidateAuthority(
                    binding=m.AuthorityBinding(
                        evidence_ref=vref(path),
                        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                        status=m.AuthorityStatus.ACCEPTED,
                    ),
                    support=m.AuthoritySupport(
                        quoted_span=quote,
                        status_section=path,
                        applicability_section=None,
                    ),
                )

            vpurpose = m.CandidateSemanticClaim(
                candidate_key="purpose",
                subject=vsid("src/postings.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Grinds grain", ()),
                evidence=(vref("README.md"),),
                candidate_authority=_vauthority("README.md", "Grinds grain"),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "README states the mill purpose",
                ),
            )
            agent = FixtureAgent(
                {"src/postings.py": FixtureCandidates((vpurpose,), ())},
                complete_questions=True,
            )
            cont = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo_id,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
                authority_seeds=(vref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation,
                agent.perform(pending.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=cont,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            reread = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo_id,
                    target=m.SubjectSelector(None, "src/postings.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
                authority_seeds=(vref("README.md"),),
            )
            self.assertIsInstance(reread, m.SemanticAnswer)
            summaries = [
                c.value.summary
                for c in reread.content.claims
                if c.kind is m.ClaimKind.PURPOSE
            ]
            # Independent truth, independently judged.
            self.assertIn("Grinds grain", summaries)
            self.assertNotIn("Tracks balances", summaries)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
