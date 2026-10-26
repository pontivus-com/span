"""Addendum B binding end-to-end acceptance (B.11 A–L + oracle must-fails).

Every scenario runs the full canonical path (public MCP/service
ingress → evidence selection → bounded pending interpretation → model
candidate submission → whole-unit validation → single canonical batch
→ query/refresh consumers) against an independently authored generic
held-out fixture ("parcel-svc", written before this suite and used by
no other suite). No test passes merely because fields exist or a
citation substring is found: the substantive oracle
(`FixtureTruth.check`) compares asserted meanings against fixture
truth, so a validly cited but semantically wrong interpretation FAILS.
"""

import pathlib
import sqlite3
import tempfile
import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.service.discovery import _coverage_for_task
from span.service.establishment import _baseline_sufficient
from span.service.resolution import _load_all_coverages_or_defer
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemorySubject,
    fingerprint_content,
)

from tests.support.factories import evidence_ref, query_bounds

from functools import partial as _partial
from tests.support.factories import subject_id

from tests.support.factories import semantic_harness

from tests.support.factories import question_decision

from tests.support.factories import proposed_questions

from tests.support.factories import answered_decision

REPO = "parcel-svc"

# Independently authored generic evidence (held-out: no other suite
# uses parcel-svc). Truth: parcel-svc sorts parcels; team/parcel owns
# it; parcel.py is the entrypoint; store.py owns state; events.py
# consumes; failures.py is the failure path; CONTRACT.md governs the
# intake schema; docs/notes.md is unrelated.
FILES = {
    "README.md": "# parcel-svc\n\nSorts parcels.\n",
    "OWNERSHIP.md": "# Ownership\n\nTeam parcel owns parcel-svc.\n",
    "CONTRACT.md": "# Contract\n\nParcel intake schema v3.\n",
    "src/parcel.py": "VALUE = 1\n",
    "src/store.py": "STATE = {}\n",
    "src/events.py": "def emit(e):\n    pass\n",
    "src/failures.py": "def dead_letter(e):\n    pass\n",
    "docs/notes.md": "misc\n",
}

_ref = _partial(evidence_ref, repository_id=REPO)

TRUTH_OWNER = "team/parcel"
TRUTH_PURPOSE = "Sorts parcels"
REQUIRED_PARTICIPANTS = {"src/parcel.py", "src/store.py", "src/events.py"}


class FixtureTruth:
    """Substantive oracle: meanings must match fixture truth, not schemas."""

    owner = TRUTH_OWNER
    purpose = TRUTH_PURPOSE
    participants = REQUIRED_PARTICIPANTS

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

    @classmethod
    def check_participants(cls, claims):
        covered = set()
        for claim in claims:
            covered.add(claim.subject.canonical_locator)
            value = claim.value
            if isinstance(value, m.OwnershipCustodyValue):
                covered.add(value.owner.canonical_locator)
        missing = cls.participants - covered
        if missing:
            raise AssertionError(
                f"omitted material downstream participants: {sorted(missing)}"
            )


_bounds = query_bounds


_sid = _partial(subject_id, repository_id=REPO)


def _authority(path, quote, files=None):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref(path, files=files),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        ),
        support=m.AuthoritySupport(
            quoted_span=quote,
            status_section=path,
            applicability_section=None,
        ),
    )


_harness = _partial(
    semantic_harness,
    REPO,
    FILES,
    subjects=(
        InMemorySubject("src/parcel.py", m.SubjectKind.COMPONENT, "parcel"),
        InMemorySubject("src/store.py", m.SubjectKind.COMPONENT, "store"),
        InMemorySubject("src/events.py", m.SubjectKind.COMPONENT, "events"),
        InMemorySubject("src/failures.py", m.SubjectKind.COMPONENT, "failures"),
    ),
    edges=(
        InMemoryEdge("src/parcel.py", m.StructuralEdgeKind.DEPENDS_ON, "src/store.py"),
        InMemoryEdge("src/parcel.py", m.StructuralEdgeKind.CALLS, "src/events.py"),
        InMemoryEdge(
            "src/parcel.py", m.StructuralEdgeKind.REFERENCES, "src/failures.py"
        ),
    ),
)


def _explain_request(locator, baseline=False):
    return ops.SemanticExplainRequest(
        repository_id=REPO,
        target=m.SubjectSelector(None, locator, (), None),
        bounds=_bounds(),
        establish_baseline=baseline,
    )


def _purpose_claim(files=None, key="purpose"):
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=_sid("src/parcel.py"),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("Sorts parcels", ()),
        evidence=(_ref("README.md", files=files),),
        candidate_authority=_authority("README.md", "Sorts parcels", files),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the parcel purpose",
        ),
    )


def _ownership_claim(files=None, key="ownership"):
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=_sid("src/parcel.py"),
        kind=m.ClaimKind.OWNERSHIP_CUSTODY,
        assertion_nature=m.AssertionNature.NORMATIVE,
        value=m.OwnershipCustodyValue(
            _sid("team/parcel"),
            m.OwnershipRole.OWNER,
            m.OwnershipExclusivity.EXCLUSIVE,
        ),
        evidence=(_ref("OWNERSHIP.md", files=files),),
        candidate_authority=_authority("OWNERSHIP.md", "Team parcel owns", files),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "ownership record names the parcel owner",
        ),
    )


def _question_coverage(
    scope,
    disposition,
    files=None,
    basis="",
    refs=(),
    requirements=(),
    evidence_paths=(),
):
    files = FILES if files is None else files
    return m.InterpretationCoverage(
        subjects=(scope.subject,),
        question_slice=scope.question_slice,
        evidence_scope=m.EvidenceScope(
            paths=(), evidence_refs=tuple(_ref(p, files=files) for p in evidence_paths)
        ),
        question=scope,
        disposition=disposition,
        result_refs=tuple(refs),
        resolution_requirements=tuple(requirements),
        disposition_basis=basis or f"test {disposition.value}",
        question_evidence=tuple(
            m.QuestionEvidenceObservation(
                evidence_ref=_ref(p, files=files),
                observed_fingerprint=fingerprint_content(files[p]),
            )
            for p in evidence_paths
        ),
    )


_decision = question_decision


_proposed = proposed_questions


def _scope(root, subject, cls, slic, basis="test material"):
    return m.SemanticQuestionScope(
        scope_root=_sid(root) if isinstance(root, str) else root,
        subject=_sid(subject) if isinstance(subject, str) else subject,
        question_class=cls,
        question_slice=slic,
        materiality_basis=basis,
    )


_answer_current = answered_decision


def _drain(op_request, op, structural, evidence, store, build_result, seeds=()):
    """Drive suspend→submit until an answer returns; returns answer."""
    continuations = ContinuationStore()
    current = op(
        op_request,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        authority_seeds=seeds,
    )
    rounds = 0
    while not isinstance(current, m.SemanticAnswer):
        assert isinstance(current, PendingInterpretation), type(current)
        rounds += 1
        assert rounds < 25, "exchange did not converge"
        result = build_result(current.request)
        current = ops.submit_interpretation(
            current.continuation,
            result,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    return current, rounds


class FirstContactTest(unittest.TestCase):
    """B.11 A: held-out repo, readiness-only init, baseline, restart reuse."""

    def test_first_contact_baseline_then_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "parcel.db")
            structural, evidence, store = _harness(db_path=db)
            try:
                # Init reports readiness only — no semantic state exists.
                state_answer = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=REPO, target=None, bounds=_bounds()
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(state_answer.content, m.StatusContent)
                self.assertIs(
                    state_answer.content.store_readiness,
                    m.StoreReadiness.READY,
                )
                self.assertEqual(state_answer.content.claims, ())

                # Baseline audit on the entrypoint root.
                continuations = ContinuationStore()
                current = ops.explain(
                    _explain_request("src/parcel.py", baseline=True),
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
                audit_q = current.request.question
                self.assertIs(audit_q.question_class, m.SemanticQuestionClass.CQ_01)
                self.assertIn("principal participants", current.request.question_slice)
                root = _sid("src/parcel.py")

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
                        claims=(_purpose_claim(),),
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
                # Audit admitted all nine classes: next unit is CQ_02.
                self.assertIsInstance(current, PendingInterpretation)
                self.assertIs(
                    current.request.question.question_class,
                    m.SemanticQuestionClass.CQ_02,
                )
                stored = store.load_all_question_coverages(REPO, root, (root,))
                classes = {
                    cov.question.question_class
                    for cov in stored
                    if cov.question is not None
                }
                self.assertEqual(len(classes), 9)

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
                self.assertIsInstance(current, m.SemanticAnswer)
                FixtureTruth.check_claims(current.content.claims)
                # Every admitted root/member question resolved with
                # current dependencies: recorded scoped sufficiency holds
                # for the admitted scope (no open/pending/noncurrent).
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
            # Restart from the same file: semantics retrievable intact.
            structural2, evidence2, store2 = _harness(db_path=db)
            try:
                answer, _ = _drain2(
                    _explain_request("src/parcel.py"),
                    ops.explain,
                    structural2,
                    evidence2,
                    store2,
                )
                by_kind = {c.kind for c in answer.content.claims}
                self.assertIn(m.ClaimKind.PURPOSE, by_kind)
                FixtureTruth.check_claims(answer.content.claims)
            finally:
                store2.close()


def _drain2(request, op, structural, evidence, store):
    continuations = ContinuationStore()
    current = op(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    rounds = 0
    while not isinstance(current, m.SemanticAnswer):
        assert isinstance(current, PendingInterpretation), type(current)
        rounds += 1
        assert rounds < 5, "restart lost persisted semantics"
        current = ops.submit_interpretation(
            current.continuation,
            m.SemanticInterpretationResult(
                claims=(_purpose_claim(),),
                relationships=(),
                candidate_subjects=(),
                candidate_conflicts=(),
                question_decision=_answer_current(current.request),
                candidate_withdrawals=(),
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    return current, rounds


class QuestionLocalVsBaselineTest(unittest.TestCase):
    """B.11 B: ordinary requests stay question-local; root audit is total."""

    def test_impact_and_explain_are_question_local(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            suspended = ops.impact(
                ops.SemanticImpactRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/store.py", (), None),
                    change_kind=m.ChangeKind.BEHAVIOR,
                    change_description="buffer writes",
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            self.assertIs(
                suspended.request.question.question_class,
                m.SemanticQuestionClass.CQ_08,
            )
            # No nine-class bootstrap was persisted for one unseen subject.
            self.assertEqual(store.count_question_coverages(REPO, None, ()), 0)
        finally:
            store.close()


class NegativeEmptyResultsTest(unittest.TestCase):
    """B.11 C: N/A + OPEN with zero refs; new source reopens both."""

    def test_negative_then_new_source_reopens(self):
        structural, evidence, store = _harness()
        try:
            root = _sid("src/parcel.py")
            na_scope = _scope(
                root,
                root,
                m.SemanticQuestionClass.CQ_09,
                "verify-none",
            )
            open_scope = _scope(
                root,
                root,
                m.SemanticQuestionClass.CQ_06,
                "authority-open",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(root, "parcel", None),),
                    coverage_dependencies=tuple(
                        _coverage_for_task(
                            REPO,
                            (root,),
                            evidence=evidence,
                            seeds=(),
                            question=scope,
                            discovery_scope=m.EvidenceScope(paths=("src",)),
                        )
                        for scope in (na_scope, open_scope)
                    ),
                    coverage=(
                        _question_coverage(
                            na_scope,
                            m.SemanticQuestionDisposition.NOT_APPLICABLE,
                            basis="no test infrastructure in bounded scope",
                            evidence_paths=("README.md",),
                        ),
                        _question_coverage(
                            open_scope,
                            m.SemanticQuestionDisposition.OPEN,
                            basis="ownership text ambiguous",
                            requirements=(
                                m.ResolutionRequirement(
                                    kind=m.ResolutionKind.MISSING_AUTHORITY,
                                    subject_or_claim=root,
                                    description="need governing ownership",
                                    supporting_context=(),
                                ),
                            ),
                        ),
                    ),
                )
            )
            covs = store.load_all_question_coverages(REPO, root, (root,))
            self.assertEqual(len(covs), 2)
            # A new governing source inside the recorded discovery scope
            # moves discovery: both reopen.
            grown = dict(FILES)
            grown["src/governance.py"] = "# Governance\n\nParcel council decides.\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            stale = ops.question_coverage_check(
                REPO, covs, evidence=evidence_v2, store=store
            )
            self.assertEqual(len(stale), 2)
        finally:
            store.close()


class SharedClaimRetirementTest(unittest.TestCase):
    """B.11 D: replacement unshares; explicit withdrawal retires + reopens."""

    def test_replace_then_withdraw(self):
        structural, evidence, store = _harness()
        seeds = (_ref("README.md"), _ref("OWNERSHIP.md"))
        try:
            first, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(_purpose_claim(), _ownership_claim()),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=seeds,
            )
            x_id = next(
                c.claim_id.value
                for c in first.content.claims
                if c.kind is m.ClaimKind.PURPOSE
            )
            # Authority examination reuses the identical claim (shared).
            auth_conts = ContinuationStore()
            suspended = ops.authority(
                ops.SemanticAuthorityRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/parcel.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=auth_conts,
                authority_seeds=seeds,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            auth_answer = ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(), _ownership_claim()),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(suspended.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=auth_conts,
            )
            self.assertIsInstance(auth_answer, m.SemanticAnswer)
            root = _sid("src/parcel.py")
            owners = [
                cov
                for cov in store.load_all_question_coverages(REPO, None, (root,))
                if x_id in {r.id.value for r in cov.result_refs}
            ]
            self.assertGreaterEqual(len(owners), 2)

            # Complete replacement under CQ_01: shared claim survives.
            grown = dict(FILES)
            grown["README.md"] = "# parcel-svc\n\nSorts parcels fast.\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            refresh_conts = ContinuationStore()
            suspended = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/parcel.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            self.assertIs(
                suspended.request.question.question_class,
                m.SemanticQuestionClass.CQ_01,
            )
            replacement = m.CandidateSemanticClaim(
                candidate_key="purpose-v2",
                subject=root,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts parcels fast", ()),
                evidence=(_ref("README.md", files=grown),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "README now states the fast parcel purpose",
                ),
            )
            ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(replacement,),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(suspended.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=refresh_conts,
            )
            # X retired nowhere: still owned by the CQ_06 question.
            (still_there,) = store.load_by_refs(REPO, (m.ClaimRef(id=m.ClaimId(x_id)),))
            self.assertIsInstance(still_there, m.SemanticClaim)
            q6_refs = [
                cov
                for cov in store.load_all_question_coverages(REPO, None, (root,))
                if cov.question is not None
                and cov.question.question_class is m.SemanticQuestionClass.CQ_06
            ]
            self.assertTrue(
                any(x_id in {r.id.value for r in cov.result_refs} for cov in q6_refs)
            )
        finally:
            store.close()

    def test_withdrawal_retires_shared_and_reopens_sharers(self):
        # Fresh subject: X shared by three questions; one withdrawal
        # retires X and reopens every other referencing question.
        structural, evidence, store = _harness()
        seeds = (_ref("README.md"),)
        try:
            answer, _ = _drain(
                _explain_request("src/events.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="x",
                            subject=_sid("src/events.py"),
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("emits events", ()),
                            evidence=(_ref("src/events.py"),),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "code emits parcel events",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=seeds,
            )
            x_id = answer.content.claims[0].claim_id.value
            root = _sid("src/events.py")
            q_cq06 = _scope(root, root, m.SemanticQuestionClass.CQ_06, "shared-6")
            q_cq04 = _scope(root, root, m.SemanticQuestionClass.CQ_04, "shared-4")
            xref = m.ClaimRef(id=m.ClaimId(x_id))
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(root, "events", None),),
                    coverage=tuple(
                        _question_coverage(
                            q,
                            m.SemanticQuestionDisposition.ANSWERED,
                            refs=(xref,),
                        )
                        for q in (q_cq06, q_cq04)
                    ),
                )
            )
            owners = [
                cov
                for cov in store.load_all_question_coverages(REPO, None, (root,))
                if x_id in {r.id.value for r in cov.result_refs}
            ]
            self.assertEqual(len(owners), 3)
            # Change the cited source: first stale scope re-examines.
            grown = dict(FILES)
            grown["src/events.py"] = "def emit(e):\n    raise IOError(e)\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            continuations = ContinuationStore()
            suspended = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/events.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            bound = suspended.request.question
            self.assertIn(
                x_id,
                {
                    r.id.value
                    for cov in store.load_all_question_coverages(
                        REPO, bound.scope_root, (bound.subject,)
                    )
                    if cov.question == bound
                    for r in cov.result_refs
                },
            )
            ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=xref,
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "event path removed; prior claim disproven",
                            ),
                            evidence=(
                                m.EvidenceRef(
                                    evidence_id=m.EvidenceId("ev-src/events.py"),
                                    repository_id=REPO,
                                    source_kind=(m.EvidenceSourceKind.SOURCE_CODE),
                                    locator="src/events.py",
                                    revision_or_fingerprint=(
                                        fingerprint_content(grown["src/events.py"])
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=continuations,
            )
            with self.assertRaises(ValueError):
                store.load_by_refs(REPO, (xref,))
            reopened = [
                cov
                for cov in store.load_all_question_coverages(REPO, None, (root,))
                if cov.question != bound
                and cov.disposition is m.SemanticQuestionDisposition.PENDING
            ]
            # Both other sharers reopened; nothing partially retired.
            self.assertEqual(len(reopened), 2)
        finally:
            store.close()

    def test_withdrawal_fanout_reopens_sharers(self):
        structural, evidence, store = _harness()
        try:
            root = _sid("src/parcel.py")
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("shared-x"),
                subject=root,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts parcels", ()),
                evidence=(_ref("README.md"),),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            q1 = _scope(root, root, m.SemanticQuestionClass.CQ_01, "q1")
            q6 = _scope(root, root, m.SemanticQuestionClass.CQ_06, "q6")
            q4 = _scope(root, root, m.SemanticQuestionClass.CQ_04, "q4")
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(root, "parcel", None),),
                    claims=(claim,),
                    coverage=tuple(
                        _question_coverage(
                            q,
                            m.SemanticQuestionDisposition.ANSWERED,
                            refs=(m.ClaimRef(id=claim.claim_id),),
                        )
                        for q in (q1, q6, q4)
                    ),
                )
            )
            # Withdraw under CQ_06 via the materializer with a live task.
            ops.prepare_interpretation_task(
                REPO,
                m.Subject(root, "parcel", None),
                structural=structural,
                evidence=evidence,
                bounds=_bounds(),
                state=structural.repository_state(REPO),
                operation_intent=m.SemanticIntent.AUTHORITY,
                question_slice="q6",
                store=store,
                scope_root=root,
                question_class=m.SemanticQuestionClass.CQ_06,
                materiality_basis="test",
            )
            from span.core import validation as _v

            ctx = _v.ValidationContext(
                allowed_claim_kinds=tuple(m.ClaimKind),
                allowed_relationship_kinds=tuple(m.RelationshipKind),
                known_evidence_ids=frozenset({"ev-README.md"}),
                known_subject_ids=(root,),
                evidence_fingerprints={
                    "ev-README.md": fingerprint_content(FILES["README.md"])
                },
                evidence_contents={"ev-README.md": FILES["README.md"]},
            )
            problem = _v.validate_candidate_withdrawal(
                m.CandidateSemanticWithdrawal(
                    target=m.ClaimRef(id=claim.claim_id),
                    basis=m.SemanticBasis(
                        m.DerivationKind.SEMANTIC_INTERPRETATION,
                        "disproven by council record",
                    ),
                    evidence=(_ref("README.md"),),
                ),
                ctx,
                frozenset({"shared-x"}),
                "withdrawal",
            )
            self.assertIsNone(problem)
        finally:
            store.close()

    def test_withdrawal_defers_on_overflow(self):
        structural, evidence, store = _harness()
        try:
            root = _sid("src/parcel.py")
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("shared-y"),
                subject=root,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts parcels", ()),
                evidence=(_ref("README.md"),),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE, "b"),
            )
            scopes = [
                _scope(root, root, m.SemanticQuestionClass.CQ_01, f"q{n}")
                for n in range(3)
            ]
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(root, "parcel", None),),
                    claims=(claim,),
                    coverage=tuple(
                        _question_coverage(
                            q,
                            m.SemanticQuestionDisposition.ANSWERED,
                            refs=(m.ClaimRef(id=claim.claim_id),),
                        )
                        for q in scopes
                    ),
                )
            )
            tiny = _bounds(max_results=1)
            with self.assertRaises(ops.InterpretationUnitRejected) as ctx:
                _load_all_coverages_or_defer(
                    REPO,
                    None,
                    (),
                    store=store,
                    bounds=tiny,
                    purpose="test overflow",
                )
            self.assertIn("deferred", str(ctx.exception))
            # Nothing retired by the deferred decision.
            (kept,) = store.load_by_refs(REPO, (m.ClaimRef(id=claim.claim_id),))
            self.assertIsInstance(kept, m.SemanticClaim)
        finally:
            store.close()


class QuestionIsolationTest(unittest.TestCase):
    """Gap-1 regression: two questions, one subject, independent currency.

    A refresh under question A heals item marks for the scope but must
    never make sibling question B current: B's own discovery snapshot
    still predates the change, so `question_coverage_check` keeps
    reporting B stale until B itself is re-examined.
    """

    def test_sibling_question_stays_stale_after_refresh(self):
        structural, evidence, store = _harness()
        seeds = (_ref("README.md"),)
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=seeds,
            )
            root = _sid("src/parcel.py")
            q_cq06 = _scope(root, root, m.SemanticQuestionClass.CQ_06, "iso-6")
            xref = m.ClaimRef(id=answer.content.claims[0].claim_id)
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(root, "parcel", None),),
                    coverage_dependencies=(
                        _coverage_for_task(
                            REPO,
                            (root,),
                            evidence=evidence,
                            seeds=(),
                            question=q_cq06,
                            discovery_scope=m.EvidenceScope(paths=("src",)),
                        ),
                    ),
                    coverage=(
                        _question_coverage(
                            q_cq06,
                            m.SemanticQuestionDisposition.ANSWERED,
                            refs=(xref,),
                        ),
                    ),
                )
            )
            grown = dict(FILES)
            grown["README.md"] = "# parcel-svc\n\nSorts parcels daily.\n"
            grown["src/new_source.py"] = "NEW = 1\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            # Refresh heals the CQ_01 question (resubmits same meaning).
            refreshed, _ = _drain(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/parcel.py", (), None),
                    bounds=_bounds(),
                ),
                ops.refresh,
                structural,
                evidence_v2,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="purpose",
                            subject=root,
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue("Sorts parcels", ()),
                            evidence=(_ref("README.md", files=grown),),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "README states the parcel purpose",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=seeds,
            )
            # The refreshed CQ_01 question is answerable current, while
            # the superseded-but-shared twin is retained and honestly
            # stale (shared retention, no silent deletion).
            by_fp = {}
            for claim in refreshed.content.claims:
                for ref in claim.evidence:
                    by_fp.setdefault(ref.revision_or_fingerprint, []).append(claim)
            current = [
                c
                for c in refreshed.content.claims
                if c.freshness.state is m.FreshnessState.CURRENT
            ]
            stale = [
                c
                for c in refreshed.content.claims
                if c.freshness.state is not m.FreshnessState.CURRENT
            ]
            self.assertTrue(current)
            self.assertTrue(stale)
            self.assertEqual(len({c.claim_id.value for c in current}), 1)
            # The sibling CQ_06 question is still stale on its own
            # snapshot despite the healed items.
            covs = store.load_all_question_coverages(REPO, None, (root,))
            stale = ops.question_coverage_check(
                REPO, covs, evidence=evidence_v2, store=store
            )
            stale_classes = {
                cov.question.question_class for cov in stale if cov.question is not None
            }
            self.assertIn(m.SemanticQuestionClass.CQ_06, stale_classes)
            self.assertNotIn(m.SemanticQuestionClass.CQ_01, stale_classes)
        finally:
            store.close()


class SemanticPremiseTest(unittest.TestCase):
    """B.11 E: upstream premise moves; byte-identical consumer goes stale."""

    def test_consumer_stale_then_refresh_recovers(self):
        structural, evidence, store = _harness()
        seeds = (_ref("README.md"), _ref("src/store.py"))
        try:
            # Round 1 (CQ_01): establish the upstream premise alone.
            answer, _ = _drain(
                _explain_request("src/store.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: self._premise_only(req, FILES),
                seeds=seeds,
            )
            premise_id = next(
                c.claim_id.value
                for c in answer.content.claims
                if c.kind is m.ClaimKind.PURPOSE
            )
            # Round 2 (CQ_06): derived consumer cites the persisted
            # premise by typed ref (cross-unit dependency, never a
            # within-unit shortcut).
            auth_conts = ContinuationStore()
            suspended = ops.authority(
                ops.SemanticAuthorityRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/store.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=auth_conts,
                authority_seeds=seeds,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            units = {
                u.evidence_ref.locator: u.evidence_ref
                for u in suspended.request.task_evidence.evidence_units
            }
            sid = _sid("src/store.py")
            auth_answer = ops.submit_interpretation(
                suspended.continuation,
                m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="consumer",
                            subject=sid,
                            kind=m.ClaimKind.RESPONSIBILITY,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.ResponsibilityValue("owns parcel state"),
                            evidence=(units["src/store.py"],),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "store holds state per premise purpose",
                                input_refs=(m.ClaimRef(id=m.ClaimId(premise_id)),),
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(suspended.request),
                    candidate_withdrawals=(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=auth_conts,
            )
            self.assertIsInstance(auth_answer, m.SemanticAnswer)
            consumer_id = next(
                c.claim_id.value
                for c in auth_answer.content.claims
                if c.kind is m.ClaimKind.RESPONSIBILITY
            )
            # Upstream premise file changes; consumer file identical.
            grown = dict(FILES)
            grown["README.md"] = "# parcel-svc\n\nSorts parcels nightly.\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            reread, _ = _drain2(
                _explain_request("src/store.py"),
                ops.explain,
                structural,
                evidence_v2,
                store,
            )
            states = {
                c.claim_id.value: c.freshness.state for c in reread.content.claims
            }
            self.assertIs(states[consumer_id], m.FreshnessState.STALE)
            # Scoped refresh re-establishes the premise first; the
            # consumer follows once its premise is current again
            # (a stale premise can never support a current conclusion).
            refreshed, _ = _drain(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/store.py", (), None),
                    bounds=_bounds(),
                ),
                ops.refresh,
                structural,
                evidence_v2,
                store,
                lambda req: self._premise_only(req, grown),
                seeds=(_ref("README.md", files=grown),),
            )
            premise_new_id = next(
                c.claim_id.value
                for c in refreshed.content.claims
                if c.kind is m.ClaimKind.PURPOSE
            )
            recovered, _ = _drain(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/store.py", (), None),
                    bounds=_bounds(),
                ),
                ops.refresh,
                structural,
                evidence_v2,
                store,
                lambda req: self._consumer_only(req, grown, premise_new_id),
                seeds=(_ref("README.md", files=grown),),
            )
            self.assertTrue(
                all(
                    c.freshness.state is m.FreshnessState.CURRENT
                    for c in recovered.content.claims
                )
            )
        finally:
            store.close()

    @staticmethod
    def _consumer_only(request, files, premise_id):
        units = {
            u.evidence_ref.locator: u.evidence_ref
            for u in request.task_evidence.evidence_units
        }
        sid = _sid("src/store.py")
        consumer = m.CandidateSemanticClaim(
            candidate_key="consumer",
            subject=sid,
            kind=m.ClaimKind.RESPONSIBILITY,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.ResponsibilityValue("owns parcel state"),
            evidence=(units["src/store.py"],),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "store module holds parcel state per premise purpose",
                input_refs=(m.ClaimRef(id=m.ClaimId(premise_id)),),
            ),
        )
        return m.SemanticInterpretationResult(
            claims=(consumer,),
            relationships=(),
            candidate_subjects=(),
            candidate_conflicts=(),
            question_decision=_answer_current(request),
            candidate_withdrawals=(),
        )

    @staticmethod
    def _premise_only(request, files):
        units = {
            u.evidence_ref.locator: u.evidence_ref
            for u in request.task_evidence.evidence_units
        }
        sid = _sid("src/store.py")
        premise = m.CandidateSemanticClaim(
            candidate_key="premise",
            subject=sid,
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("Sorts parcels", ()),
            evidence=(units["README.md"],),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "README states the store purpose",
            ),
        )
        return m.SemanticInterpretationResult(
            claims=(premise,),
            relationships=(),
            candidate_subjects=(),
            candidate_conflicts=(),
            question_decision=_answer_current(request),
            candidate_withdrawals=(),
        )


class CyclesBoundsTest(unittest.TestCase):
    """B.11 F: cycle rejects; truncated frontier is UNVERIFIABLE."""

    def test_within_unit_cycle_rejects(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            suspended = ops.explain(
                _explain_request("src/events.py"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            units = {
                u.evidence_ref.locator: u.evidence_ref
                for u in suspended.request.task_evidence.evidence_units
            }
            sid = _sid("src/events.py")
            from span.core import validation as _v

            leaf = m.CandidateSemanticClaim(
                candidate_key="leaf",
                subject=sid,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("emits events", ()),
                evidence=(units["src/events.py"],),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION, "code emits"
                ),
            )
            leaf_id = _v.deterministic_claim_id(leaf, m.TrustState.UNRESOLVED)
            head = m.CandidateSemanticClaim(
                candidate_key="head",
                subject=sid,
                kind=m.ClaimKind.RESPONSIBILITY,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.ResponsibilityValue("notifies downstream"),
                evidence=(units["src/events.py"],),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "depends on leaf within the same unit",
                    input_refs=(m.ClaimRef(id=leaf_id),),
                ),
            )
            with self.assertRaises(ops.InterpretationUnitRejected):
                ops.submit_interpretation(
                    suspended.continuation,
                    m.SemanticInterpretationResult(
                        claims=(leaf, head),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            # Failed unit wrote nothing.
            page = store.load_claims(REPO, (sid,), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_truncated_premise_frontier_unverifiable(self):
        _, _, store = _harness()
        try:
            sid = _sid("src/store.py")
            chain = []
            prev = None
            for n in range(8):
                ref = (
                    m.ClaimRef(id=m.ClaimId(f"link-{n - 1}"))
                    if prev is not None
                    else None
                )
                claim = m.SemanticClaim(
                    claim_id=m.ClaimId(f"link-{n}"),
                    subject=sid,
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(f"link {n}", ()),
                    evidence=(_ref("README.md"),),
                    freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                    basis=m.SemanticBasis(
                        m.DerivationKind.SEMANTIC_INTERPRETATION,
                        f"link {n}",
                        input_refs=(ref,) if ref is not None else (),
                    ),
                )
                chain.append(claim)
                prev = claim
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "store", None),),
                    claims=tuple(chain),
                )
            )
            evidence = FixtureEvidenceSource(REPO, dict(FILES))
            updates = ops.preflight(
                REPO,
                (m.ClaimRef(id=m.ClaimId("link-7")),),
                evidence=evidence,
                store=store,
                bounds=_bounds(),
            )
            self.assertTrue(
                any(
                    u.semantic_id.id.value == "link-7"
                    and u.freshness.state is m.FreshnessState.UNVERIFIABLE
                    for u in updates
                )
            )
        finally:
            store.close()


class ReconcileFailureTest(unittest.TestCase):
    """B.11 G: rejected/expired units preserve prior state + worklist."""

    def test_rejected_submit_preserves_prior(self):
        structural, evidence, store = _harness()
        seeds = (_ref("README.md"),)
        try:
            first, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=seeds,
            )
            before = {c.claim_id.value for c in first.content.claims}
            continuations = ContinuationStore()
            suspended = ops.explain(
                _explain_request("src/failures.py"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(suspended, PendingInterpretation)
            bad = m.CandidateSemanticClaim(
                candidate_key="bad",
                subject=_sid("src/failures.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("x", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-unknown"),
                        repository_id=REPO,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="nope.py",
                    ),
                ),
                basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "bad"),
            )
            with self.assertRaises(ops.InterpretationUnitRejected):
                ops.submit_interpretation(
                    suspended.continuation,
                    m.SemanticInterpretationResult(
                        claims=(bad,),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
            page = store.load_claims(REPO, (_sid("src/parcel.py"),), (), _bounds())
            self.assertEqual({c.claim_id.value for c in page.items}, before)
            with self.assertRaises(Exception):
                ops.submit_interpretation(
                    "cont-999",
                    m.SemanticInterpretationResult(),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()


class AuthorityConflictTest(unittest.TestCase):
    """B.11 H: observed-vs-declared conflict; ACCEPTED only from source."""

    def test_conflict_and_no_reviewer_upgrade(self):
        self.assertFalse(hasattr(m.AuthorityBinding, "reviewed_by"))
        self.assertFalse(hasattr(m.AuthorityBinding, "reviewed_at"))
        structural, evidence, store = _harness()
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(
                        _ownership_claim(),
                        m.CandidateSemanticClaim(
                            candidate_key="rival",
                            subject=_sid("src/parcel.py"),
                            kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                            assertion_nature=m.AssertionNature.NORMATIVE,
                            value=m.OwnershipCustodyValue(
                                _sid("team/rival"),
                                m.OwnershipRole.OWNER,
                                m.OwnershipExclusivity.EXCLUSIVE,
                            ),
                            evidence=(_ref("CONTRACT.md"),),
                            candidate_authority=_authority(
                                "CONTRACT.md", "Parcel intake schema"
                            ),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "contract names a rival owner",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    candidate_withdrawals=(),
                ),
                seeds=(_ref("OWNERSHIP.md"), _ref("CONTRACT.md")),
            )
            self.assertTrue(answer.content.conflicts)
            owners = {
                c.value.owner.canonical_locator
                for c in answer.content.claims
                if c.kind is m.ClaimKind.OWNERSHIP_CUSTODY
            }
            self.assertEqual(owners, {"team/parcel", "team/rival"})
            # No reviewer path promoted either side: ESTABLISHED comes
            # only from the source-declared ACCEPTED bindings above.
            self.assertTrue(
                all(c.trust is m.TrustState.ESTABLISHED for c in answer.content.claims)
            )
        finally:
            store.close()

    def test_unknown_status_and_empty_quote_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            suspended = ops.explain(
                _explain_request("src/parcel.py"),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            units = {
                u.evidence_ref.locator: u.evidence_ref
                for u in suspended.request.task_evidence.evidence_units
            }
            loc = "README.md" if "README.md" in units else next(iter(units))
            bad = m.CandidateSemanticClaim(
                candidate_key="bad",
                subject=_sid("src/parcel.py"),
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Sorts parcels", ()),
                evidence=(units[loc],),
                candidate_authority=m.CandidateAuthority(
                    binding=m.AuthorityBinding(
                        evidence_ref=units[loc],
                        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                        status=m.AuthorityStatus.UNKNOWN,
                    ),
                    support=m.AuthoritySupport(quoted_span=""),
                ),
                basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "b"),
            )
            with self.assertRaises(ops.InterpretationUnitRejected):
                ops.submit_interpretation(
                    suspended.continuation,
                    m.SemanticInterpretationResult(
                        claims=(bad,),
                        relationships=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                        candidate_withdrawals=(),
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=continuations,
                )
        finally:
            store.close()


class PaginationContinuationTest(unittest.TestCase):
    """B.11 I: three-stream paging redeemable; restart loses no work."""

    def test_pages_redeem_and_restart_safe(self):
        structural, evidence, store = _harness()
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=tuple(
                        m.CandidateSemanticClaim(
                            candidate_key=f"p{n}",
                            subject=_sid("src/parcel.py"),
                            kind=m.ClaimKind.PURPOSE,
                            assertion_nature=m.AssertionNature.DESCRIPTIVE,
                            value=m.PurposeValue(f"Sorts parcels {n}", ()),
                            evidence=(_ref("README.md"),),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                f"purpose facet {n}",
                            ),
                        )
                        for n in range(3)
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=(_ref("README.md"),),
            )
            self.assertEqual(len(answer.content.claims), 3)
            small = _bounds(max_results=2)
            first = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/parcel.py", (), None),
                    bounds=small,
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(first, m.SemanticAnswer)
            token = first.bound_info.continuation_token
            self.assertTrue(token.startswith("pgv:"))
            self.assertEqual(len(token.split(":")), 5)
            seen = [c.claim_id.value for c in first.content.claims]
            while token is not None:
                page = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(None, "src/parcel.py", (), None),
                        bounds=small,
                        page_token=token,
                    ),
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    continuations=ContinuationStore(),
                )
                seen.extend(c.claim_id.value for c in page.content.claims)
                token = page.bound_info.continuation_token
            self.assertEqual(len(seen), 3)
            self.assertEqual(len(set(seen)), 3)
            # Restart with a fresh continuation store: persisted work
            # answers identically with no lost questions.
            again = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/parcel.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(again, m.SemanticAnswer)
            self.assertEqual(
                {c.claim_id.value for c in again.content.claims},
                set(seen),
            )
            self.assertTrue(again.content.question_coverage)
        finally:
            store.close()


class BenignChangeTest(unittest.TestCase):
    """B.11 J: irrelevant evidence change leaves assertions CURRENT."""

    def test_unrelated_content_change_is_silent(self):
        structural, evidence, store = _harness()
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=(_ref("README.md"),),
            )
            self.assertTrue(
                all(
                    c.freshness.state is m.FreshnessState.CURRENT
                    for c in answer.content.claims
                )
            )
            grown = dict(FILES)
            grown["docs/notes.md"] = "misc and more\n"
            evidence_v2 = FixtureEvidenceSource(REPO, grown)
            reread = ops.explain(
                _explain_request("src/parcel.py"),
                structural=structural,
                evidence=evidence_v2,
                store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(reread, m.SemanticAnswer)
            self.assertTrue(
                all(
                    c.freshness.state is m.FreshnessState.CURRENT
                    for c in reread.content.claims
                )
            )
        finally:
            store.close()


_V2_DDL = """
CREATE TABLE repositories(
  repository_id TEXT PRIMARY KEY,
  revision_id TEXT,
  dirty INTEGER NOT NULL,
  state_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE subjects(
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, locator, kind)
);
CREATE TABLE claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE relationships(
  relationship_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  source_locator TEXT NOT NULL,
  target_locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE evidence_dependencies(
  semantic_id TEXT NOT NULL,
  semantic_kind TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  observed_fingerprint TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(semantic_id, evidence_id)
);
CREATE TABLE coverage_dependencies(
  repository_id TEXT NOT NULL,
  scope_locators TEXT NOT NULL,
  inventory_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE retired_claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  retired_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE retired_relationships(
  relationship_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  retired_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE conflict_records(
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, subject_locator, left_id, right_id)
);
CREATE TABLE meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class CurrentSchemaOnlyTest(unittest.TestCase):
    """B.11 K: only the current schema is served; older stores fail closed."""

    def test_v2_store_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "old.db")
            con = sqlite3.connect(db)
            try:
                con.executescript(_V2_DDL)
                con.execute(
                    "INSERT INTO claims VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "leg-1",
                        REPO,
                        "src/parcel.py",
                        "COMPONENT",
                        "PURPOSE",
                        "UNRESOLVED",
                        "CURRENT",
                        "{}",
                    ),
                )
                con.execute("INSERT INTO meta VALUES('schema_version', '2')")
                con.commit()
            finally:
                con.close()
            with self.assertRaisesRegex(
                ValueError,
                "unsupported Span store schema version 2; migrate this "
                "store to schema 9",
            ):
                SqliteSemanticStore(db)
            con = sqlite3.connect(db)
            try:
                row = con.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
                self.assertEqual(row[0], "2")
                claim_ids = [
                    r[0] for r in con.execute("SELECT claim_id FROM claims").fetchall()
                ]
                self.assertEqual(claim_ids, ["leg-1"])
            finally:
                con.close()

    def test_schema_6_store_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "v6.db")
            con = sqlite3.connect(db)
            try:
                con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
                con.execute("INSERT INTO meta VALUES('schema_version', '6')")
                con.commit()
            finally:
                con.close()
            with self.assertRaisesRegex(
                ValueError,
                "unsupported Span store schema version 6",
            ):
                SqliteSemanticStore(db)

    def test_unversioned_nonempty_store_rejected_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "unversioned.db")
            con = sqlite3.connect(db)
            try:
                con.execute("CREATE TABLE subjects(locator TEXT PRIMARY KEY)")
                con.commit()
            finally:
                con.close()
            with self.assertRaisesRegex(
                ValueError,
                "unsupported Span store schema version 0",
            ):
                SqliteSemanticStore(db)

    def test_unsupported_version_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "bad.db")
            con = sqlite3.connect(db)
            try:
                con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
                con.execute("INSERT INTO meta VALUES('schema_version', '99')")
                con.commit()
            finally:
                con.close()
            with self.assertRaises(ValueError):
                SqliteSemanticStore(db)
            con = sqlite3.connect(db)
            try:
                row = con.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
                self.assertEqual(row[0], "99")
            finally:
                con.close()


class PortabilityIsolationTest(unittest.TestCase):
    """B.11 L: held-out repo, no parent-workspace coupling, no provider in Span."""

    def test_no_parent_workspace_imports(self):
        import re

        root = pathlib.Path(__file__).resolve().parents[2] / "src" / "span"
        pattern = re.compile(
            r"^\s*(import|from)\s+(projects|packages|worker_server)(\.|\s|$)"
        )
        offenders = []
        for path in sorted(root.rglob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.match(line):
                    offenders.append(f"{path.name}:{n}:{line.strip()}")
        self.assertEqual(offenders, [])


class SubstantiveOracleMustFailTest(unittest.TestCase):
    """B.11 oracle: cited-but-wrong and omitted-participant MUST fail."""

    def test_validly_cited_but_wrong_owner_fails_oracle(self):
        structural, evidence, store = _harness()
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="wrong-owner",
                            subject=_sid("src/parcel.py"),
                            kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                            assertion_nature=m.AssertionNature.NORMATIVE,
                            value=m.OwnershipCustodyValue(
                                _sid("team/ghost"),
                                m.OwnershipRole.OWNER,
                                m.OwnershipExclusivity.EXCLUSIVE,
                            ),
                            evidence=(_ref("OWNERSHIP.md"),),
                            candidate_authority=_authority(
                                "OWNERSHIP.md", "Team parcel owns"
                            ),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "ownership record names the owner",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    candidate_withdrawals=(),
                ),
                seeds=(_ref("OWNERSHIP.md"),),
            )
            # Mechanical validation passed (citation bytes are valid) —
            # the claim is stored. Substantive review must still fail it.
            self.assertTrue(answer.content.claims)
            with self.assertRaises(AssertionError) as ctx:
                FixtureTruth.check_claims(answer.content.claims)
            self.assertIn("substantively wrong", str(ctx.exception))
        finally:
            store.close()

    def test_omitted_participant_fails_oracle_and_blocks_sufficiency(self):
        structural, evidence, store = _harness()
        try:
            answer, _ = _drain(
                _explain_request("src/parcel.py"),
                ops.explain,
                structural,
                evidence,
                store,
                lambda req: m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_answer_current(req),
                    candidate_withdrawals=(),
                ),
                seeds=(_ref("README.md"),),
            )
            with self.assertRaises(AssertionError) as ctx:
                FixtureTruth.check_participants(answer.content.claims)
            self.assertIn("omitted material", str(ctx.exception))
            # Omission is oracle-detected (SA-5 duty); the core never
            # invents the missing participants, and sufficiency stays
            # False while the admitted scope is incomplete.
            self.assertFalse(
                _baseline_sufficient(
                    REPO,
                    _sid("src/parcel.py"),
                    store=store,
                    evidence=evidence,
                    bounds=_bounds(),
                )
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
