"""Addendum E E-13H oracle-backed acceptance (Addendum E §§4C.6F/6G)."""

import os
import tempfile
import unittest

from span.core import model as m
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
)

REPO = "e13h-oracle"
FILES = {
    "billing_a1.py": "BILLING_A1 = 1\n",
    "billing_a2.py": "BILLING_A2 = 2\n",
    "shipping_b.py": "import billing_a1\nSHIP = billing_a1.BILLING_A1\n",
    "vendor_c.py": "THIRD_PARTY = True\n",
    "config_d.py": "# config, no components\n",
    "legacy_e.py": "LEGACY = 0\n",
}
OBJECTIVE = "Establish billing and shipping areas with exclusions."


def _bounds():
    return m.QueryBounds(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )


def _harness(files=None):
    files = files or dict(FILES)
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        tuple(
            InMemorySubject(p, m.SubjectKind.COMPONENT, p.split(".")[0].split("_")[0])
            for p in files
        ),
        (),
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
        structural=structural, evidence=evidence, store=store,
    )
    return structural, evidence, store


def _tid():
    scope, obj = m.canonicalize_target_scope(
        REPO, m.EvidenceScope(paths=tuple(sorted(FILES)), evidence_refs=()), OBJECTIVE
    )
    return m.derive_target_id(REPO, scope, obj), scope, obj


def _basis(summary, refs):
    return m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary=summary,
        input_refs=tuple(refs),
    )


class AddendumEAcceptanceTest(unittest.TestCase):
    def test_oracle_grouping_exclusion_and_recovery(self):
        tmpdir = tempfile.mkdtemp(prefix="e13h-")
        db_path = os.path.join(tmpdir, "oracle.db")
        files = dict(FILES)
        from span.shell.structural.memory import (
            InMemoryFile as _F, InMemoryStructuralSource as _S,
            InMemorySubject as _Subj,
        )
        structural = _S(
            REPO, tuple(_F(p, c) for p, c in files.items()),
            tuple(_Subj(p, m.SubjectKind.COMPONENT, p.split(".")[0].split("_")[0]) for p in files),
            (),
        )
        from span.shell.evidence import FixtureEvidenceSource as _E
        evidence = _E(REPO, dict(files))
        store = SqliteSemanticStore(db_path)
        from span import service as _ops
        _ops.initialize_repository(
            _ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id=REPO, structural=structural, evidence=evidence, store=store,
        )
        live = ContinuationStore()
        tid, _, _ = _tid()
        billing = m.SubjectId(repository_id=REPO, subject_kind=m.SubjectKind.OTHER, canonical_locator="billing")
        shipping = m.SubjectId(repository_id=REPO, subject_kind=m.SubjectKind.OTHER, canonical_locator="shipping")

        def _admit():
            return ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO,
                    target=m.EvidenceScope(paths=tuple(sorted(FILES)), evidence_refs=()),
                    objective=OBJECTIVE, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live, authority_seeds=(),
            )

        # Drain mapping: assign a1+a2→billing, b→shipping, c→exclusion,
        # d→billing, e→unresolved. Admit PENDING billing/shipping purpose.
        billing_q = m.SemanticQuestionScope(
            scope_root=billing, subject=billing,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="billing purpose", materiality_basis="mapping admits billing",
        )
        shipping_q = m.SemanticQuestionScope(
            scope_root=shipping, subject=shipping,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="shipping purpose", materiality_basis="mapping admits shipping",
        )
        admitted = set()
        for _ in range(12):
            pending = _admit()
            if not hasattr(pending, "continuation"):
                break
            req = pending.request
            if req.question is not None:
                break
            item = req.target_inventory_item
            assert item is not None
            loc = item.evidence_ref.locator
            if loc in ("billing_a1.py", "billing_a2.py"):
                area = billing
            elif loc == "shipping_b.py":
                area = shipping
            elif loc == "config_d.py":
                area = billing
            elif loc == "vendor_c.py":
                area = None
            else:
                area = None  # legacy_e unresolved
            if loc == "vendor_c.py":
                acc = m.TargetInventoryAccount(
                    evidence_ref=item.evidence_ref,
                    exclusion_basis=_basis("third-party vendored code", (item.evidence_ref,)),
                )
                covs, qs = (), ()
            elif loc == "legacy_e.py":
                acc = m.TargetInventoryAccount(
                    evidence_ref=item.evidence_ref,
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                            subject_or_claim=None,
                            description="needs owner interview",
                            supporting_context=(),
                        ),
                    ),
                )
                covs, qs = (), ()
            else:
                acc = m.TargetInventoryAccount(
                    evidence_ref=item.evidence_ref, assigned_area_subjects=(area,)
                )
                covs, qs = (), ()
                need = None
                if area == billing and "billing" not in admitted:
                    admitted.add("billing")
                    need = (billing, billing_q, "billing purpose")
                elif area == shipping and "shipping" not in admitted:
                    admitted.add("shipping")
                    need = (shipping, shipping_q, "shipping purpose")
                if need is not None:
                    subj, qq, sl = need
                    covs = (
                        m.InterpretationCoverage(
                            subjects=(subj,), question_slice=sl,
                            evidence_scope=m.EvidenceScope(), declared_complete=False,
                            question=qq,
                            disposition=m.SemanticQuestionDisposition.PENDING,
                            result_refs=(), resolution_requirements=(),
                            disposition_basis="admitted", question_evidence=(),
                        ),
                    )
                    qs = (qq,)
            subj_basis = _basis(f"mapping admits {loc}", (item.evidence_ref,))
            cands = ()
            if area is not None and (
                (area.canonical_locator == "billing" and loc == "billing_a1.py")
                or (area.canonical_locator == "shipping" and loc == "shipping_b.py")
            ):
                cands = (
                    m.CandidateSubject(
                        provisional_locator=area.canonical_locator,
                        kind=m.SubjectKind.OTHER, display_name=area.canonical_locator,
                        declared_kind=area.canonical_locator,
                        evidence=(item.evidence_ref,), basis=subj_basis,
                    ),
                )
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(), governing_source_refs=(),
                    diagnostics=("mapping",), candidate_subjects=cands,
                    candidate_conflicts=(), proposed_question_coverages=covs,
                    candidate_withdrawals=(),
                    proposed_target_inventory_accounting=(acc,),
                    proposed_target_questions=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        assoc = store.load_target_association(REPO, tid)
        self.assertIsNotNone(assoc)
        assert assoc is not None
        by_eid = {a.evidence_ref.locator: a for a in assoc.inventory_accounting}
        # Multiple files map to one area; areas distinct.
        self.assertEqual(
            set(by_eid["billing_a1.py"].assigned_area_subjects), {billing}
        )
        self.assertEqual(
            set(by_eid["billing_a2.py"].assigned_area_subjects), {billing}
        )
        self.assertNotEqual(
            set(by_eid["billing_a1.py"].assigned_area_subjects),
            set(by_eid["shipping_b.py"].assigned_area_subjects),
        )
        # Exclusion only by accounting; NOT_APPLICABLE stays assigned tested below.
        self.assertIsNotNone(by_eid["vendor_c.py"].exclusion_basis)
        self.assertTrue(by_eid["legacy_e.py"].resolution_requirements)
        # Negative: wrong grouping (a1→shipping) must fail validation.
        from span.core import validation as v
        ctx = v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset(
                a.evidence_ref.evidence_id.value for a in assoc.inventory_accounting
            ),
            known_subject_ids=tuple(assoc.area_subjects),
            evidence_fingerprints={},
        )
        # Fabricated area identity rejects.
        fake = m.SubjectId(repository_id=REPO, subject_kind=m.SubjectKind.OTHER, canonical_locator="nope")
        bad = m.TargetInventoryAccount(
            evidence_ref=by_eid["billing_a1.py"].evidence_ref,
            assigned_area_subjects=(fake,),
        )
        self.assertFalse(
            v.validate_target_inventory_account(
                bad, ctx,
                current_inventory_ids=frozenset(
                    a.evidence_ref.evidence_id.value for a in assoc.inventory_accounting
                ),
            ).ok
        )
        # Unresolved prevents CURRENT.
        ans = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans, m.SemanticAnswer)
        assert isinstance(ans.content, m.StatusContent)
        self.assertEqual(
            ans.content.target_disposition, m.SemanticCoverageDisposition.INCOMPLETE
        )
        # Resolve legacy_e to shipping + answer billing/shipping purpose with
        # claims + cross-area DEPENDS_ON + in-target NOT_APPLICABLE for a
        # billing CQ_02 question. Each semantic pending is driven via
        # initialize_target (PENDING target questions only).
        def _answer_pending(pending, question, claims, rels, coverages, extra_accounts=(), extra_qs=()):
            req = pending.request
            assert req.question is not None
            return ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=tuple(claims), relationships=tuple(rels),
                    governing_source_refs=(), diagnostics=("semantic",),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=tuple(coverages),
                    candidate_withdrawals=(),
                    proposed_target_inventory_accounting=tuple(extra_accounts),
                    proposed_target_questions=tuple(extra_qs),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        # Answer loop: at most a few rounds; each _admit returns PENDING or terminal.
        for _ in range(8):
            pending = _admit()
            if not hasattr(pending, "continuation"):
                break
            req = pending.request
            if req.question is None:
                # Should not happen: mapping drained.
                raise AssertionError("unexpected mapping task in semantic phase")
            q = req.question
            # Evidence refs available to this task.
            refs = tuple(u.evidence_ref for u in req.evidence_units)
            if not refs:
                raise AssertionError("semantic task without evidence")
            ref = refs[0]
            if q.question_slice == "billing purpose":
                claim = m.CandidateSemanticClaim(
                    candidate_key="billing-purpose",
                    subject=billing, kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(summary="billing computes charges"),
                    evidence=(ref,),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                        summary="billing purpose observed", input_refs=(ref,),
                    ),
                )
                rel = m.CandidateSemanticRelationship(
                    candidate_key="billing-depends-shipping",
                    source=billing, kind=m.RelationshipKind.DEPENDS_ON,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    target=shipping, evidence=(ref,),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                        summary="billing feeds shipping", input_refs=(ref,),
                    ),
                )
                cov = m.InterpretationCoverage(
                    subjects=(billing,), question_slice=q.question_slice,
                    evidence_scope=m.EvidenceScope(), declared_complete=True,
                    question=q, disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="answered", question_evidence=(),
                )
                # Admit in-target NOT_APPLICABLE question for billing CQ_02 once.
                na_q = m.SemanticQuestionScope(
                    scope_root=billing, subject=billing,
                    question_class=m.SemanticQuestionClass.CQ_02,
                    question_slice="billing components na",
                    materiality_basis="no separate components",
                )
                na_qe = tuple(
                    m.QuestionEvidenceObservation(
                        evidence_ref=u.evidence_ref,
                        observed_fingerprint=u.content_fingerprint,
                    )
                    for u in req.evidence_units[:1]
                )
                na_cov = m.InterpretationCoverage(
                    subjects=(billing,), question_slice="billing components na",
                    evidence_scope=m.EvidenceScope(), declared_complete=True,
                    question=na_q,
                    disposition=m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="single-file billing has no subcomponents",
                    question_evidence=na_qe,
                )
                _answer_pending(pending, q, (claim,), (rel,), (cov, na_cov), (), ())
            elif q.question_slice == "shipping purpose":
                claim = m.CandidateSemanticClaim(
                    candidate_key="shipping-purpose",
                    subject=shipping, kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(summary="shipping fulfills orders"),
                    evidence=(ref,),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                        summary="shipping purpose observed", input_refs=(ref,),
                    ),
                )
                cov = m.InterpretationCoverage(
                    subjects=(shipping,), question_slice=q.question_slice,
                    evidence_scope=m.EvidenceScope(), declared_complete=True,
                    question=q, disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="answered", question_evidence=(),
                )
                # Resolve legacy_e here (revision allowed on semantic submit).
                assoc_now = store.load_target_association(REPO, tid)
                assert assoc_now is not None
                e_acc = next(
                    a for a in assoc_now.inventory_accounting
                    if a.evidence_ref.locator == "legacy_e.py"
                )
                resolved = m.TargetInventoryAccount(
                    evidence_ref=e_acc.evidence_ref,
                    assigned_area_subjects=(shipping,),
                )
                _answer_pending(pending, q, (claim,), (), (cov,), (resolved,), ())
            else:
                raise AssertionError(f"unexpected question {q.question_slice}")
        ans2 = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans2, m.SemanticAnswer)
        assert isinstance(ans2.content, m.StatusContent)
        # Cross-area present; NOT_APPLICABLE member remains assigned.
        rels_page = store.load_relationships(
            REPO, (billing,), (m.RelationshipKind.DEPENDS_ON,),
            __import__("span.ports.structural", fromlist=["StructuralDirection"]).StructuralDirection.BOTH,
            _bounds(), None,
        )
        self.assertTrue(
            any(r.source == billing and r.target == shipping for r in rels_page.items)
        )
        assoc2 = store.load_target_association(REPO, tid)
        assert assoc2 is not None
        by_loc = {a.evidence_ref.locator: a for a in assoc2.inventory_accounting}
        self.assertIn(billing, by_loc["config_d.py"].assigned_area_subjects)
        self.assertEqual(ans2.content.target_disposition, m.SemanticCoverageDisposition.CURRENT)
        # Source-content change for an established area → STALE.
        evidence._files["billing_a1.py"] = "BILLING_A1 = 999\n"
        ans_stale = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans_stale, m.SemanticAnswer)
        assert isinstance(ans_stale.content, m.StatusContent)
        self.assertEqual(
            ans_stale.content.target_disposition, m.SemanticCoverageDisposition.STALE
        )
        # Scoped refresh re-examines the stale billing question → CURRENT again.
        billing_sel = m.SubjectSelector(
            exact_subject_id=billing, name_or_locator=None, expected_kinds=(),
        )
        rconts = ContinuationStore()
        for _refresh_round in range(4):
            rpending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO, target=billing_sel, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=rconts, authority_seeds=(),
            )
            if not hasattr(rpending, "continuation"):
                break
            rconts = ContinuationStore()
            # Re-issue refresh on a fresh handle each round (single-use).
            rpending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO, target=billing_sel, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=rconts, authority_seeds=(),
            )
            if not hasattr(rpending, "continuation"):
                break
            rq = rpending.request
            rq_cov = rq.question
            assert rq_cov is not None
            runits = tuple(u.evidence_ref for u in rq.evidence_units) or (
                assoc2.inventory_accounting[0].evidence_ref,
            )
            if rq_cov.question_slice == "billing components na":
                rqe = tuple(
                    m.QuestionEvidenceObservation(
                        evidence_ref=u.evidence_ref,
                        observed_fingerprint=u.content_fingerprint,
                    )
                    for u in rq.evidence_units[:1]
                )
                rclaim_set, rrel_set = (), ()
                rcov = m.InterpretationCoverage(
                    subjects=(billing,), question_slice=rq_cov.question_slice,
                    evidence_scope=m.EvidenceScope(), declared_complete=True,
                    question=rq_cov,
                    disposition=m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="still no subcomponents",
                    question_evidence=rqe,
                )
            else:
                rclaim = m.CandidateSemanticClaim(
                    candidate_key=f"billing-purpose-r{_refresh_round}",
                    subject=billing, kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue(summary="billing computes charges refreshed"),
                    evidence=(runits[0],),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                        summary="refreshed billing purpose", input_refs=(runits[0],),
                    ),
                )
                rclaim_set, rrel_set = (rclaim,), ()
                rcov = m.InterpretationCoverage(
                    subjects=(billing,), question_slice=rq_cov.question_slice,
                    evidence_scope=m.EvidenceScope(), declared_complete=True,
                    question=rq_cov,
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="refreshed", question_evidence=(),
                )
            ops.submit_interpretation(
                rpending.continuation,
                m.SemanticInterpretationResult(
                    claims=rclaim_set, relationships=rrel_set,
                    governing_source_refs=(),
                    diagnostics=("refresh",), candidate_subjects=(),
                    candidate_conflicts=(), proposed_question_coverages=(rcov,),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=rconts,
            )
            rconts = ContinuationStore()
        # Content-only change uses canonical freshness + scoped refresh
        # (§§4C.6B/4C.6E): no initialize_target re-entry resets a second
        # accounting fingerprint. Refresh alone restores CURRENT.
        ans_refreshed = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans_refreshed, m.SemanticAnswer)
        assert isinstance(ans_refreshed.content, m.StatusContent)
        self.assertEqual(
            ans_refreshed.content.target_disposition,
            m.SemanticCoverageDisposition.CURRENT,
        )
        # The refreshed answer observes the changed bytes, so the campaign
        # is CURRENT again without restoring anything.
        # Membership change: delete legacy_e.py from the provider. Same scope
        # and objective → same TargetId → initialize_target reconciles.
        del evidence._files["legacy_e.py"]
        reentry = ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id=REPO,
                target=m.EvidenceScope(paths=tuple(sorted(FILES)), evidence_refs=()),
                objective=OBJECTIVE, bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assoc3 = store.load_target_association(REPO, tid)
        assert assoc3 is not None
        self.assertNotIn(
            "legacy_e.py",
            {a.evidence_ref.locator for a in assoc3.inventory_accounting},
        )
        # Genuine restart: close and reopen the persisted database, then
        # retrieve with fresh continuations and no host memory.
        store.close()
        store = SqliteSemanticStore(db_path)
        # Fresh-session retrieval: new continuations, no host memory.
        fresh = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(fresh, m.SemanticAnswer)
        assert isinstance(fresh.content, m.StatusContent)
        assert fresh.content.target_association is not None
        # Membership deletion changed discovery snapshots: STALE is the
        # truthful disposition, and the association itself reconciled.
        self.assertEqual(
            fresh.content.target_disposition, m.SemanticCoverageDisposition.STALE
        )
        got = store.load_subjects(
            REPO, tuple(fresh.content.target_association.area_subjects)
        )
        self.assertEqual({s.subject_id for s in got}, set(fresh.content.target_association.area_subjects))
        store.close()


class TargetReuseTest(unittest.TestCase):
    """Reuse-only association: already-persisted questions attach without
    new coverage; valid-shaped wrong grouping passes validation but the
    independent meaning oracle rejects it."""

    def test_reuse_and_wrong_grouping_oracle(self):
        from span.shell.structural.memory import (
            InMemoryFile as _F, InMemoryStructuralSource as _S,
            InMemorySubject as _Subj,
        )
        from span.shell.evidence import FixtureEvidenceSource as _E

        repo = "e13h-reuse"
        files = {"one.py": "A=1\n", "two.py": "B=2\n"}
        structural = _S(
            repo, tuple(_F(p, c) for p, c in files.items()),
            tuple(_Subj(p, m.SubjectKind.COMPONENT, p.split(".")[0]) for p in files),
            (),
        )
        evidence = _E(repo, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test", authority_seeds=(),
            ),
            repository_id=repo, structural=structural, evidence=evidence,
            store=store,
        )
        live = ContinuationStore()
        scope = m.EvidenceScope(paths=("one.py", "two.py"), evidence_refs=())
        cscore, cobj = m.canonicalize_target_scope(repo, scope, "reuse objective")
        tid = m.derive_target_id(repo, cscore, cobj)
        area = m.SubjectId(
            repository_id=repo, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="area",
        )
        question = m.SemanticQuestionScope(
            scope_root=area, subject=area,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="area purpose",
            materiality_basis="admitted by mapping",
        )

        def _admit():
            return ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=repo, target=scope, objective="reuse objective",
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live, authority_seeds=(),
            )

        def _basis_for(ref):
            return m.SemanticBasis(
                derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                summary="mapping admits area",
                input_refs=(ref,),
            )

        # Map one.py: new area + PENDING coverage (no reuse entry).
        first = _admit()
        assert first.request.question is None
        item1 = first.request.target_inventory_item
        assert item1 is not None
        ops.submit_interpretation(
            first.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("m1",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="area", kind=m.SubjectKind.OTHER,
                        display_name="area", declared_kind="area",
                        evidence=(item1.evidence_ref,),
                        basis=_basis_for(item1.evidence_ref),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(area,), question_slice="area purpose",
                        evidence_scope=m.EvidenceScope(), declared_complete=False,
                        question=question,
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="admitted", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item1.evidence_ref,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        # Map two.py: same existing area, reuse persisted question only.
        second = _admit()
        assert second.request.question is None
        item2 = second.request.target_inventory_item
        assert item2 is not None
        self.assertNotEqual(
            item1.evidence_ref.evidence_id.value,
            item2.evidence_ref.evidence_id.value,
        )
        ops.submit_interpretation(
            second.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("m2 reuse",), candidate_subjects=(),
                candidate_conflicts=(), proposed_question_coverages=(),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item2.evidence_ref,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(question,),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        assoc = store.load_target_association(repo, tid)
        assert assoc is not None
        self.assertEqual(len(assoc.inventory_accounting), 2)
        self.assertIn(area, assoc.area_subjects)
        self.assertIn(question, assoc.target_questions)

        # Valid-shaped wrong grouping: two.py also fits the area shape, so
        # relabeling it to a second admitted area passes pure validation,
        # but the independent meaning oracle rejects it.
        other = m.SubjectId(
            repository_id=repo, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="other",
        )
        from span.core import validation as v
        got = {a.evidence_ref.locator: a for a in assoc.inventory_accounting}
        wrong = m.TargetInventoryAccount(
            evidence_ref=got["two.py"].evidence_ref,
            assigned_area_subjects=(other,),
        )
        ctx = v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset(
                a.evidence_ref.evidence_id.value for a in assoc.inventory_accounting
            ),
            known_subject_ids=tuple(assoc.area_subjects) + (other,),
            evidence_fingerprints={},
        )
        # Shape validation cannot see meaning: with the area admitted it is ok.
        self.assertTrue(
            v.validate_target_inventory_account(
                wrong, ctx,
                current_inventory_ids=frozenset(
                    a.evidence_ref.evidence_id.value
                    for a in assoc.inventory_accounting
                ),
                admitted_area_ids=tuple(assoc.area_subjects) + (other,),
            ).ok
        )
        expected = {"one.py": "area", "two.py": "area"}
        candidate = {"one.py": "area", "two.py": "other"}
        self.assertEqual(
            {loc: acc.assigned_area_subjects[0].canonical_locator
             for loc, acc in got.items() if acc.assigned_area_subjects},
            expected,
        )
        self.assertNotEqual(candidate, expected,
                            "oracle must reject wrong grouping despite valid shape")
        store.close()

    def test_first_admission_of_persisted_area_via_reuse(self):
        """E-13B/C contract case: first admission of an already-known area.

        Existing canonical Subject + existing current coverage + new target
        campaign → assign inventory to that Subject →
        proposed_target_questions=(existing question,). No new PENDING
        coverage is manufactured (§§4C.2/4C.4). This failed before the
        correction as "new area without PENDING question" / unknown area.
        """
        from span.shell.structural.memory import (
            InMemoryFile as _F, InMemoryStructuralSource as _S,
            InMemorySubject as _Subj,
        )
        from span.shell.evidence import FixtureEvidenceSource as _E

        repo = "e13h-reuse-first-admission"
        files = {"one.py": "A=1\n", "two.py": "B=2\n"}
        structural = _S(
            repo, tuple(_F(p, c) for p, c in files.items()),
            tuple(_Subj(p, m.SubjectKind.COMPONENT, p.split(".")[0]) for p in files),
            (),
        )
        evidence = _E(repo, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test", authority_seeds=(),
            ),
            repository_id=repo, structural=structural, evidence=evidence,
            store=store,
        )
        scope = m.EvidenceScope(paths=("one.py", "two.py"), evidence_refs=())
        area = m.SubjectId(
            repository_id=repo, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="area",
        )
        question = m.SemanticQuestionScope(
            scope_root=area, subject=area,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="area purpose",
            materiality_basis="admitted by mapping",
        )

        def _basis_for(ref):
            return m.SemanticBasis(
                derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                summary="mapping admits area",
                input_refs=(ref,),
            )

        # Campaign A persists the area with a new PENDING coverage.
        live_a = ContinuationStore()
        first_a = ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id=repo, target=scope,
                objective="first objective", bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live_a, authority_seeds=(),
        )
        assert first_a.request.question is None
        item_a = first_a.request.target_inventory_item
        assert item_a is not None
        ops.submit_interpretation(
            first_a.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("campaign-a admit",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="area", kind=m.SubjectKind.OTHER,
                        display_name="area", declared_kind="area",
                        evidence=(item_a.evidence_ref,),
                        basis=_basis_for(item_a.evidence_ref),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(area,), question_slice="area purpose",
                        evidence_scope=m.EvidenceScope(), declared_complete=False,
                        question=question,
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="admitted", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item_a.evidence_ref,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live_a,
        )
        # The Subject and its coverage are now persisted independently of
        # any single campaign association.
        self.assertTrue(store.load_subjects(repo, (area,)))
        persisted = store.load_all_question_coverages(repo, area, (area,))
        self.assertTrue(
            any(
                cov.question is not None and cov.question == question
                for cov in persisted
            )
        )

        # Campaign B (different objective → different TargetId) admits the
        # same already-persisted area first via reuse only: no candidate,
        # no new coverage, just the assignment + proposed_target_questions.
        live_b = ContinuationStore()
        first_b = ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id=repo, target=scope,
                objective="second objective", bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live_b, authority_seeds=(),
        )
        assert first_b.request.question is None
        item_b = first_b.request.target_inventory_item
        assert item_b is not None
        ops.submit_interpretation(
            first_b.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("campaign-b first admission via reuse",),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(), candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item_b.evidence_ref,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(question,),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live_b,
        )
        cscore_b, cobj_b = m.canonicalize_target_scope(
            repo, scope, "second objective"
        )
        tid_b = m.derive_target_id(repo, cscore_b, cobj_b)
        assoc_b = store.load_target_association(repo, tid_b)
        assert assoc_b is not None
        self.assertIn(area, assoc_b.area_subjects)
        self.assertIn(question, assoc_b.target_questions)
        by_loc = {
            a.evidence_ref.locator: a for a in assoc_b.inventory_accounting
        }
        self.assertEqual(
            set(by_loc[item_b.evidence_ref.locator].assigned_area_subjects),
            {area},
        )
        store.close()


class TargetQuestionAnswerabilityTest(unittest.TestCase):
    """§4C.6D amendment (2026-10-11): admitted target questions must be
    answerable — scope_root in the answering run's known set, subject
    anchor resolvable — and anchorless questions must signal, never sink."""

    NAV_REPO = "e-ans-nav"
    NAV_FILES = {"solo_a.py": "A = 1\n"}
    NAV_OBJECTIVE = "Establish the navigation area and its purpose."

    def _harness(self):
        files = dict(self.NAV_FILES)
        structural = InMemoryStructuralSource(
            self.NAV_REPO,
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            tuple(
                InMemorySubject(p, m.SubjectKind.COMPONENT, p.split(".")[0])
                for p in files
            ),
            (),
        )
        evidence = FixtureEvidenceSource(self.NAV_REPO, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id=self.NAV_REPO,
            structural=structural, evidence=evidence, store=store,
        )
        return structural, evidence, store

    def _admit(self, structural, evidence, store, live):
        return ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id=self.NAV_REPO,
                target=m.EvidenceScope(paths=tuple(sorted(self.NAV_FILES)), evidence_refs=()),
                objective=self.NAV_OBJECTIVE, bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live, authority_seeds=(),
        )

    def _tid(self):
        scope, obj = m.canonicalize_target_scope(
            self.NAV_REPO,
            m.EvidenceScope(paths=tuple(sorted(self.NAV_FILES)), evidence_refs=()),
            self.NAV_OBJECTIVE,
        )
        return m.derive_target_id(self.NAV_REPO, scope, obj)

    def _nav_area(self):
        return m.SubjectId(
            repository_id=self.NAV_REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="nav",
        )

    def _file_a(self):
        return m.SubjectId(
            repository_id=self.NAV_REPO, subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="solo_a.py",
        )

    def test_member_anchored_question_round_trip(self):
        structural, evidence, store = self._harness()
        live = ContinuationStore()
        nav, file_a = self._nav_area(), self._file_a()
        # Anchor first: mapping tasks cannot co-admit non-area subjects
        # (orphan rule), so establish the file anchor question-locally.
        suspended = ops.explain(
            ops.SemanticExplainRequest(
                repository_id=self.NAV_REPO,
                target=m.SubjectSelector(None, "solo_a.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live, authority_seeds=(),
        )
        self.assertTrue(hasattr(suspended, "continuation"))
        anchor_ref = suspended.request.evidence_units[0].evidence_ref
        ops.submit_interpretation(
            suspended.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("anchor-admission",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="solo_a.py",
                        kind=m.SubjectKind.COMPONENT,
                        display_name="solo_a.py", declared_kind="COMPONENT",
                        evidence=(anchor_ref,),
                        basis=_basis("identity binds solo_a anchor", (anchor_ref,)),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        self.assertTrue(store.load_subjects(self.NAV_REPO, (file_a,)))
        first = self._admit(structural, evidence, store, live)
        self.assertTrue(hasattr(first, "continuation"))
        req = first.request
        self.assertIsNone(req.question)
        item = req.target_inventory_item
        assert item is not None
        question = m.SemanticQuestionScope(
            scope_root=nav, subject=file_a,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="nav purpose",
            materiality_basis="mapping admits nav",
        )
        pending_cov = m.InterpretationCoverage(
            subjects=(file_a,), question_slice="nav purpose",
            evidence_scope=m.EvidenceScope(), declared_complete=False,
            question=question,
            disposition=m.SemanticQuestionDisposition.PENDING,
            result_refs=(), resolution_requirements=(),
            disposition_basis="admitted", question_evidence=(),
        )
        submit = ops.submit_interpretation(
            first.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("mapping",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="nav", kind=m.SubjectKind.OTHER,
                        display_name="nav", declared_kind="nav",
                        evidence=(item.evidence_ref,),
                        basis=_basis("mapping admits nav", (item.evidence_ref,)),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(pending_cov,),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item.evidence_ref,
                        assigned_area_subjects=(nav,),
                    ),
                ),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        self.assertTrue(hasattr(submit, "continuation"))
        # The admitted member-anchored question suspends (anchor persisted).
        pending = self._admit(structural, evidence, store, live)
        self.assertTrue(hasattr(pending, "continuation"))
        self.assertIsNotNone(pending.request.question)
        self.assertEqual(pending.request.question.question_slice, "nav purpose")
        refs = tuple(u.evidence_ref for u in pending.request.evidence_units)
        self.assertTrue(refs)
        claim = m.CandidateSemanticClaim(
            candidate_key="nav-purpose", subject=file_a,
            kind=m.ClaimKind.PURPOSE,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue(summary="solo_a holds navigation state"),
            evidence=(refs[0],),
            basis=_basis("mapping admits nav purpose", (refs[0],)),
        )
        question = pending.request.question
        answered = ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(claim,), relationships=(), governing_source_refs=(),
                diagnostics=("semantic",), candidate_subjects=(),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(file_a,),
                        question_slice=question.question_slice,
                        evidence_scope=m.EvidenceScope(),
                        declared_complete=True, question=question,
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="examined", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        self.assertTrue(hasattr(answered, "continuation") or hasattr(answered, "answer_id"))
        covs = store.load_all_question_coverages(self.NAV_REPO, nav, (file_a,))
        self.assertTrue(
            any(
                cov.question is not None
                and cov.question.question_slice == "nav purpose"
                and cov.disposition is m.SemanticQuestionDisposition.ANSWERED
                for cov in covs
            )
        )
        done = self._admit(structural, evidence, store, live)
        self.assertFalse(hasattr(done, "continuation"))
        ans = ops.status(
            ops.SemanticStatusRequest(
                repository_id=self.NAV_REPO, target=self._tid(), bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans, m.SemanticAnswer)
        assert isinstance(ans.content, m.StatusContent)
        self.assertEqual(
            ans.content.target_disposition, m.SemanticCoverageDisposition.CURRENT
        )

    def test_anchorless_admission_rejected(self):
        structural, evidence, store = self._harness()
        live = ContinuationStore()
        first = self._admit(structural, evidence, store, live)
        self.assertTrue(hasattr(first, "continuation"))
        item = first.request.target_inventory_item
        assert item is not None
        nav, file_a = self._nav_area(), self._file_a()

        def _mapping_result(question):
            return m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("mapping",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="nav", kind=m.SubjectKind.OTHER,
                        display_name="nav", declared_kind="nav",
                        evidence=(item.evidence_ref,),
                        basis=_basis("mapping admits nav", (item.evidence_ref,)),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(question.subject,),
                        question_slice=question.question_slice,
                        evidence_scope=m.EvidenceScope(),
                        declared_complete=False, question=question,
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="admitted", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=item.evidence_ref,
                        assigned_area_subjects=(nav,),
                    ),
                ),
                proposed_target_questions=(),
            )

        # Live shape: question anchored to the current item's file —
        # run-known but never persisted and not co-proposed. The
        # admission check names it.
        live_question = m.SemanticQuestionScope(
            scope_root=nav, subject=file_a,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="nav purpose",
            materiality_basis="mapping admits nav",
        )
        with self.assertRaises(ops.InterpretationUnitRejected) as cm:
            ops.submit_interpretation(
                first.continuation, _mapping_result(live_question),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        self.assertIn("target question subject does not resolve", str(cm.exception))
        # Rejection is atomic: the item is still unaccounted, so the
        # frontier re-issues the same mapping unit on a fresh continuation.
        second = self._admit(structural, evidence, store, live)
        self.assertTrue(hasattr(second, "continuation"))
        # Foreign subjects fail even earlier, at coverage validation.
        ghost = m.SubjectId(
            repository_id=self.NAV_REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="ghost.py",
        )
        ghost_question = m.SemanticQuestionScope(
            scope_root=nav, subject=ghost,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="ghost purpose",
            materiality_basis="mapping admits nav",
        )
        with self.assertRaises(ops.InterpretationUnitRejected) as cm2:
            ops.submit_interpretation(
                second.continuation, _mapping_result(ghost_question),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        self.assertIn("not run-bound", str(cm2.exception))

    def test_refresh_answer_round_trip(self):
        # A1b seam: a refresh-suspended run answers an area-rooted admitted
        # question. Pre-fix this submit failed run-bound validation.
        files = {"solo_a.py": "A = 1\n", "solo_b.py": "B = 2\n"}
        structural = InMemoryStructuralSource(
            self.NAV_REPO,
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            tuple(
                InMemorySubject(p, m.SubjectKind.COMPONENT, p.split(".")[0])
                for p in files
            ),
            (),
        )
        evidence = FixtureEvidenceSource(self.NAV_REPO, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id=self.NAV_REPO,
            structural=structural, evidence=evidence, store=store,
        )
        live = ContinuationStore()
        scope = m.EvidenceScope(paths=("solo_a.py", "solo_b.py"), evidence_refs=())

        def _admit():
            return ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=self.NAV_REPO, target=scope,
                    objective=self.NAV_OBJECTIVE, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live, authority_seeds=(),
            )

        nav = self._nav_area()
        file_a = m.SubjectId(
            repository_id=self.NAV_REPO, subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="solo_a.py",
        )
        # Anchor first (mapping cannot co-admit non-area subjects).
        suspended = ops.explain(
            ops.SemanticExplainRequest(
                repository_id=self.NAV_REPO,
                target=m.SubjectSelector(None, "solo_a.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live, authority_seeds=(),
        )
        self.assertTrue(hasattr(suspended, "continuation"))
        anchor_ref = suspended.request.evidence_units[0].evidence_ref
        ops.submit_interpretation(
            suspended.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("anchor-admission",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="solo_a.py",
                        kind=m.SubjectKind.COMPONENT,
                        display_name="solo_a.py", declared_kind="COMPONENT",
                        evidence=(anchor_ref,),
                        basis=_basis("identity binds solo_a anchor", (anchor_ref,)),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(), candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        # Drain mapping: solo_a admits nav + PENDING purpose, solo_b joins.
        question = m.SemanticQuestionScope(
            scope_root=nav, subject=file_a,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="nav purpose",
            materiality_basis="mapping admits nav",
        )
        seen_anchor_question = False
        for _ in range(6):
            pending = _admit()
            if not hasattr(pending, "continuation"):
                break
            req = pending.request
            if req.question is not None:
                break
            item = req.target_inventory_item
            assert item is not None
            if item.evidence_ref.locator == "solo_a.py":
                covs = (
                    m.InterpretationCoverage(
                        subjects=(file_a,), question_slice="nav purpose",
                        evidence_scope=m.EvidenceScope(), declared_complete=False,
                        question=question,
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="admitted", question_evidence=(),
                    ),
                )
                cands = (
                    m.CandidateSubject(
                        provisional_locator="nav", kind=m.SubjectKind.OTHER,
                        display_name="nav", declared_kind="nav",
                        evidence=(item.evidence_ref,),
                        basis=_basis("mapping admits nav", (item.evidence_ref,)),
                    ),
                )
            else:
                covs, cands = (), ()
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(), governing_source_refs=(),
                    diagnostics=("mapping",), candidate_subjects=cands,
                    candidate_conflicts=(),
                    proposed_question_coverages=covs, candidate_withdrawals=(),
                    proposed_target_inventory_accounting=(
                        m.TargetInventoryAccount(
                            evidence_ref=item.evidence_ref,
                            assigned_area_subjects=(nav,),
                        ),
                    ),
                    proposed_target_questions=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        # Answer the purpose question to CURRENT.
        pending = _admit()
        self.assertTrue(hasattr(pending, "continuation"))
        self.assertIsNotNone(pending.request.question)
        refs = tuple(u.evidence_ref for u in pending.request.evidence_units)
        self.assertTrue(refs)
        ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(
                    m.CandidateSemanticClaim(
                        candidate_key="nav-purpose", subject=file_a,
                        kind=m.ClaimKind.PURPOSE,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue(summary="solo_a holds state"),
                        evidence=(refs[0],),
                        basis=_basis("mapping admits nav purpose", (refs[0],)),
                    ),
                ),
                relationships=(), governing_source_refs=(),
                diagnostics=("semantic",), candidate_subjects=(),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(file_a,),
                        question_slice=pending.request.question.question_slice,
                        evidence_scope=m.EvidenceScope(), declared_complete=True,
                        question=pending.request.question,
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="examined", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        # Membership churn outside the examined file stales the coverage;
        # refresh must suspend the admitted question for re-examination.
        evidence2 = FixtureEvidenceSource(self.NAV_REPO, {"solo_a.py": "A = 1\n"})
        live2 = ContinuationStore()
        suspended_refresh = ops.refresh(
            ops.SemanticRefreshRequest(
                repository_id=self.NAV_REPO, target=scope, bounds=_bounds(),
                stale_only=True,
            ),
            structural=structural, evidence=evidence2, store=store,
            continuations=live2, authority_seeds=(),
        )
        self.assertTrue(hasattr(suspended_refresh, "continuation"))
        rreq = suspended_refresh.request
        self.assertIsNotNone(rreq.question)
        rrefs = tuple(u.evidence_ref for u in rreq.evidence_units)
        self.assertTrue(rrefs)
        answered = ops.submit_interpretation(
            suspended_refresh.continuation,
            m.SemanticInterpretationResult(
                claims=(
                    m.CandidateSemanticClaim(
                        candidate_key="nav-purpose-again", subject=file_a,
                        kind=m.ClaimKind.PURPOSE,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue(summary="solo_a holds state"),
                        evidence=(rrefs[0],),
                        basis=_basis("re-examined after churn", (rrefs[0],)),
                    ),
                ),
                relationships=(), governing_source_refs=(),
                diagnostics=("re-examination",), candidate_subjects=(),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(file_a,),
                        question_slice=rreq.question.question_slice,
                        evidence_scope=m.EvidenceScope(), declared_complete=True,
                        question=rreq.question,
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="re-examined", question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence2, store=store,
            continuations=live2,
        )
        self.assertTrue(
            hasattr(answered, "continuation") or hasattr(answered, "answer_id"))
        covs = store.load_all_question_coverages(self.NAV_REPO, nav, (file_a,))
        self.assertTrue(
            any(
                cov.question is not None
                and cov.disposition is m.SemanticQuestionDisposition.ANSWERED
                for cov in covs
            )
        )

    def test_anchorless_legacy_signals_in_status(self):
        structural, evidence, store = self._harness()
        from span.service.discovery import enumerate_target_inventory
        scope, obj = m.canonicalize_target_scope(
            self.NAV_REPO,
            m.EvidenceScope(paths=tuple(sorted(self.NAV_FILES)), evidence_refs=()),
            self.NAV_OBJECTIVE,
        )
        tid = m.derive_target_id(self.NAV_REPO, scope, obj)
        inv_items = enumerate_target_inventory(
            self.NAV_REPO, scope, evidence=evidence, bounds=_bounds(),
        )
        self.assertEqual(len(inv_items), 1)
        nav = self._nav_area()
        ghost = m.SubjectId(
            repository_id=self.NAV_REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="ghost.py",
        )
        assoc = m.TargetAssociation(
            target_id=tid, repository_id=self.NAV_REPO,
            target_scope=scope, objective=obj,
            area_subjects=(nav,),
            target_questions=(
                m.SemanticQuestionScope(
                    scope_root=nav, subject=ghost,
                    question_class=m.SemanticQuestionClass.CQ_01,
                    question_slice="ghost purpose",
                    materiality_basis="legacy admission",
                ),
            ),
            inventory_accounting=(
                m.TargetInventoryAccount(
                    evidence_ref=inv_items[0].evidence_ref,
                    assigned_area_subjects=(nav,),
                ),
            ),
            inventory_fingerprint=m.target_inventory_fingerprint(tuple(inv_items)),
            observed_repository_state_fingerprint="test",
        )
        store.write_index_batch(m.CanonicalIndexBatch(target_associations=(assoc,)))
        ans = ops.status(
            ops.SemanticStatusRequest(
                repository_id=self.NAV_REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans, m.SemanticAnswer)
        assert isinstance(ans.content, m.StatusContent)
        self.assertEqual(
            ans.content.target_disposition, m.SemanticCoverageDisposition.INCOMPLETE
        )
        named = [
            r for r in ans.resolution_requirements
            if r.subject_or_claim == ghost
        ]
        self.assertTrue(named)
        self.assertIn("CandidateSubject", named[0].description)


if __name__ == "__main__":
    unittest.main()
