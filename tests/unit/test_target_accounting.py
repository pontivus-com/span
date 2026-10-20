"""Addendum E E-13: whole-target accounting and worklist-first resume.

Two binding behaviors with no new store, carrier, or writer:

1. A restart (fresh continuations) re-admitting an exact target resumes the
   admitted PENDING worklist instead of re-asking an OPEN audit.
2. Exact-target status carries a typed frontier report with one explicit
   disposition per target candidate (UNASSESSED where nothing was adopted).
"""

import unittest

from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "target-acct-svc"

FILES = {
    "README.md": "# target-acct-svc\n\nTracks balances.\n",
    "src/postings.py": "POSTING = 1\n",
    "src/inventory.py": "STOCK = {}\n",
}

TARGET_PATHS = ("src/postings.py", "src/inventory.py")
OBJECTIVE = "Establish reusable memory for the postings scope."
FOLLOW_SLICE = "Establish the postings root purpose from direct evidence."



def _fill_batch(pending, accounts):
    """S5/J-6 test helper: account for every bound inventory item.

    A mapping result must contain exactly one candidate per bound item;
    items the test does not exercise are recorded as unresolved mapping
    requirements. No-op for an empty accounts tuple (non-mapping units).
    """
    accounts = tuple(accounts)
    if not accounts:
        return accounts
    have = {a.evidence_id.value for a in accounts}
    out = list(accounts)
    for it in pending.request.target_inventory_items:
        eid = it.evidence_ref.evidence_id.value
        if eid in have:
            continue
        out.append(m.CandidateTargetInventoryAccount(
            evidence_id=it.evidence_ref.evidence_id,
            resolution_requirements=(m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=None,
                description="not examined in this test",
                supporting_context=(),
            ),),
        ))
    return tuple(out)

def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        (
            InMemorySubject(
                "src/postings.py", m.SubjectKind.COMPONENT, "postings"),
            InMemorySubject(
                "src/inventory.py", m.SubjectKind.COMPONENT, "inventory"),
        ),
        (),
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


def _admit(structural, evidence, store, continuations,
           paths=TARGET_PATHS):
    return ops.initialize_target(
        ops.SemanticInitializeTargetRequest(
            repository_id=REPO,
            target=m.EvidenceScope(paths=paths, evidence_refs=()),
            objective=OBJECTIVE,
            bounds=_bounds(),
        ),
        structural=structural, evidence=evidence, store=store,
        continuations=continuations, authority_seeds=(),
    )


def _submit_audit_open(pending, structural, evidence, store, continuations):
    req = pending.request
    root = req.subjects[0].subject_id
    refs = tuple(u.evidence_ref for u in req.evidence_units)
    assert refs, "audit unit must carry evidence"
    open_cov = m.InterpretationCoverage(
        subjects=(root,),
        question_slice=req.question.question_slice,
        evidence_scope=m.EvidenceScope(paths=TARGET_PATHS,
                                       evidence_refs=refs),
        declared_complete=False,
        question=req.question,
        disposition=m.SemanticQuestionDisposition.OPEN,
        result_refs=(),
        resolution_requirements=(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=root,
                description="no governing source in unit evidence",
                supporting_context=(),
            ),
        ),
        disposition_basis="test audit OPEN with follow-up",
        question_evidence=(),
    )
    follow_q = m.SemanticQuestionScope(
        scope_root=root, subject=root,
        question_class=m.SemanticQuestionClass.CQ_01,
        question_slice=FOLLOW_SLICE,
        materiality_basis="admitted by the audit as material; unexamined",
    )
    follow_cov = m.InterpretationCoverage(
        subjects=(root,),
        question_slice=FOLLOW_SLICE,
        evidence_scope=m.EvidenceScope(),
        declared_complete=False,
        question=follow_q,
        disposition=m.SemanticQuestionDisposition.PENDING,
        result_refs=(),
        resolution_requirements=(),
        disposition_basis="admitted by audit; awaits examination",
        question_evidence=(),
    )
    return ops.submit_interpretation(
        pending.continuation,
        m.SemanticInterpretationResult(
            claims=(), relationships=(), governing_source_refs=(),
            diagnostics=("test audit",),
            candidate_subjects=(), candidate_conflicts=(),
            proposed_question_coverages=(open_cov, follow_cov),
            candidate_withdrawals=(),
        ),
        structural=structural, evidence=evidence, store=store,
        continuations=continuations,
    )


class TargetAccountingTest(unittest.TestCase):
    def test_restart_resumes_admitted_pending(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        solo = ("src/postings.py",)
        first = _admit(structural, evidence, store, live, paths=solo)
        self.assertTrue(hasattr(first, "continuation"))
        self.assertIsNone(first.request.question)
        item = first.request.target_inventory_items[0]
        self.assertIsNotNone(item)
        assert item is not None
        area = m.SubjectId(
            repository_id=REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="postings-area",
        )
        q = m.SemanticQuestionScope(
            scope_root=area, subject=area,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice=FOLLOW_SLICE,
            materiality_basis="admitted by mapping; unexamined",
        )
        pend = m.InterpretationCoverage(
            subjects=(area,), question_slice=FOLLOW_SLICE,
            evidence_scope=m.EvidenceScope(), declared_complete=False,
            question=q, disposition=m.SemanticQuestionDisposition.PENDING,
            result_refs=(), resolution_requirements=(),
            disposition_basis="admitted by mapping", question_evidence=(),
        )
        ops.submit_interpretation(
            first.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("mapping",),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="postings-area",
                        kind=m.SubjectKind.OTHER,
                        display_name="postings-area",
                        declared_kind="postings-area",
                        evidence=(item.evidence_ref,),
                        basis=m.SemanticBasis(
                            derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                            summary="mapping admits postings area",
                            input_refs=(item.evidence_ref,),
                        ),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(pend,),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=_fill_batch(first, (
                    m.CandidateTargetInventoryAccount(
                         evidence_id=item.evidence_ref.evidence_id,
                        assigned_area_subjects=(area,),
                    ),
                )),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=live,
        )
        scope, obj = m.canonicalize_target_scope(
            REPO, m.EvidenceScope(paths=solo, evidence_refs=()), OBJECTIVE)
        tid = m.derive_target_id(REPO, scope, obj)
        assoc = store.load_target_association(REPO, tid)
        self.assertIsNotNone(assoc)
        assert assoc is not None
        self.assertEqual(len(assoc.inventory_accounting), 1)
        self.assertIn(area, assoc.area_subjects)

    def test_exact_target_status_carries_frontier_report(self):
        # E-13B mapping drains inventory; status(TargetId) reports INCOMPLETE
        # until admitted questions terminate.
        structural, evidence, store = _harness()
        live = ContinuationStore()
        area = m.SubjectId(
            repository_id=REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator="postings-area",
        )
        for _ in range(1):
            pending = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO,
                    target=m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=()),
                    objective=OBJECTIVE, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live, authority_seeds=(),
            )
            if not hasattr(pending, "continuation"):
                break
            assert pending.request.question is None
            item = pending.request.target_inventory_items[0]
            assert item is not None
            q = m.SemanticQuestionScope(
                scope_root=area, subject=area,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice=FOLLOW_SLICE,
                materiality_basis="admitted by mapping; unexamined",
            )
            pend = m.InterpretationCoverage(
                subjects=(area,), question_slice=FOLLOW_SLICE,
                evidence_scope=m.EvidenceScope(), declared_complete=False,
                question=q, disposition=m.SemanticQuestionDisposition.PENDING,
                result_refs=(), resolution_requirements=(),
                disposition_basis="admitted by mapping", question_evidence=(),
            )
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(), governing_source_refs=(),
                    diagnostics=("mapping",),
                    candidate_subjects=(
                        m.CandidateSubject(
                            provisional_locator="postings-area",
                            kind=m.SubjectKind.OTHER,
                            display_name="postings-area",
                            declared_kind="postings-area",
                            evidence=(item.evidence_ref,),
                            basis=m.SemanticBasis(
                                derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                                summary="mapping admits postings area",
                                input_refs=(item.evidence_ref,),
                            ),
                        ),
                    ),
                    candidate_conflicts=(),
                    proposed_question_coverages=(pend,),
                    candidate_withdrawals=(),
                    proposed_target_inventory_accounting=_fill_batch(pending, (
                        m.CandidateTargetInventoryAccount(
                             evidence_id=item.evidence_ref.evidence_id,
                            assigned_area_subjects=(area,),
                        ),
                    )),
                    proposed_target_questions=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
        scope, obj = m.canonicalize_target_scope(
            REPO, m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=()), OBJECTIVE)
        tid = m.derive_target_id(REPO, scope, obj)
        assoc = store.load_target_association(REPO, tid)
        self.assertIsNotNone(assoc)
        assert assoc is not None
        self.assertEqual(len(assoc.inventory_accounting), len(TARGET_PATHS))
        ans = ops.status(
            ops.SemanticStatusRequest(repository_id=REPO, target=tid, bounds=_bounds()),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(), authority_seeds=(),
        )
        assert isinstance(ans, m.SemanticAnswer)
        assert isinstance(ans.content, m.StatusContent)
        self.assertEqual(
            ans.content.target_disposition, m.SemanticCoverageDisposition.INCOMPLETE)


def _unresolved_account(item):
    return m.CandidateTargetInventoryAccount(
        evidence_id=item.evidence_ref.evidence_id,
        resolution_requirements=(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=None,
                description="not examined in this test",
                supporting_context=(),
            ),
        ),
    )


def _target_id():
    scope, obj = m.canonicalize_target_scope(
        REPO, m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=()),
        OBJECTIVE,
    )
    return m.derive_target_id(REPO, scope, obj)


class MappingBatchIdentityTest(unittest.TestCase):
    """SPMCP-04: mapping batches correlate by stable EvidenceId.

    Submission order is irrelevant; each rejection names the exact bound
    member by EvidenceId, and the whole unit stays atomic with a live
    continuation.
    """

    def test_batch_accounts_by_evidence_id_regardless_of_order(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        try:
            pending = _admit(structural, evidence, store, live)
            self.assertEqual(len(pending.request.target_inventory_items), 2)
            reversed_items = tuple(
                reversed(pending.request.target_inventory_items)
            )
            ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(), governing_source_refs=(),
                    diagnostics=("mapping in reverse order",),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(),
                    candidate_withdrawals=(),
                    proposed_target_inventory_accounting=tuple(
                        _unresolved_account(item) for item in reversed_items
                    ),
                    proposed_target_questions=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live,
            )
            assoc = store.load_target_association(REPO, _target_id())
            assert assoc is not None
            self.assertEqual(
                {acc.evidence_ref.evidence_id.value
                 for acc in assoc.inventory_accounting},
                {item.evidence_ref.evidence_id.value
                 for item in pending.request.target_inventory_items},
            )
        finally:
            store.close()

    def test_missing_bound_member_is_named_and_atomic(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        try:
            pending = _admit(structural, evidence, store, live)
            items = pending.request.target_inventory_items
            self.assertEqual(len(items), 2)
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(), relationships=(), governing_source_refs=(),
                        diagnostics=("partial mapping",),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(),
                        candidate_withdrawals=(),
                        proposed_target_inventory_accounting=(
                            _unresolved_account(items[0]),
                        ),
                        proposed_target_questions=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=live,
                )
            message = str(ctx.exception)
            missing = items[1].evidence_ref.evidence_id.value
            self.assertIn(missing, message)
            self.assertIn("bound mapping item has no accounting candidate",
                          message)
            self.assertIn("bound_items[1]", message)
            # Atomic rejection: no accounting committed, continuation live.
            assoc = store.load_target_association(REPO, _target_id())
            assert assoc is not None
            self.assertEqual(assoc.inventory_accounting, ())
            self.assertEqual(len(live), 1)
        finally:
            store.close()

    def test_unbound_account_is_named_and_atomic(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        try:
            from span.service.discovery import enumerate_target_inventory

            bounds = _bounds(max_evidence_units=1)
            pending = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO,
                    target=m.EvidenceScope(
                        paths=TARGET_PATHS, evidence_refs=()
                    ),
                    objective=OBJECTIVE,
                    bounds=bounds,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=live, authority_seeds=(),
            )
            self.assertEqual(len(pending.request.target_inventory_items), 1)
            inventory = enumerate_target_inventory(
                REPO, m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=()),
                evidence=evidence, bounds=_bounds(),
            )
            bound_id = (
                pending.request.target_inventory_items[0]
                .evidence_ref.evidence_id.value
            )
            extra = next(
                item for item in inventory
                if item.evidence_ref.evidence_id.value != bound_id
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(), relationships=(), governing_source_refs=(),
                        diagnostics=("extra mapping",),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(),
                        candidate_withdrawals=(),
                        proposed_target_inventory_accounting=(
                            _unresolved_account(
                                pending.request.target_inventory_items[0]
                            ),
                            _unresolved_account(extra),
                        ),
                        proposed_target_questions=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=live,
                )
            message = str(ctx.exception)
            self.assertIn(extra.evidence_ref.evidence_id.value, message)
            self.assertIn("outside the bound mapping batch", message)
            self.assertIn("target_accounts[1]", message)
            assoc = store.load_target_association(REPO, _target_id())
            assert assoc is not None
            self.assertEqual(assoc.inventory_accounting, ())
            self.assertEqual(len(live), 1)
        finally:
            store.close()

    def test_duplicate_account_is_named_and_atomic(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        try:
            pending = _admit(structural, evidence, store, live)
            items = pending.request.target_inventory_items
            duplicated = (
                _unresolved_account(items[0]),
                _unresolved_account(items[0]),
                _unresolved_account(items[1]),
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(), relationships=(), governing_source_refs=(),
                        diagnostics=("duplicate mapping",),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(),
                        candidate_withdrawals=(),
                        proposed_target_inventory_accounting=duplicated,
                        proposed_target_questions=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=live,
                )
            message = str(ctx.exception)
            eid = items[0].evidence_ref.evidence_id.value
            self.assertIn(f"duplicate target account: {eid}", message)
            self.assertIn("target_accounts[1]", message)
            assoc = store.load_target_association(REPO, _target_id())
            assert assoc is not None
            self.assertEqual(assoc.inventory_accounting, ())
            self.assertEqual(len(live), 1)
        finally:
            store.close()


class ArtifactSnapshotTest(unittest.TestCase):
    def test_snapshot_is_read_only_census(self):
        import pathlib
        import tempfile

        from span.shell.structural.graft import artifact_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            graph = root / "graft" / ".graph"
            graph.mkdir(parents=True)
            (graph / "wiring.json").write_text('{"nodes": []}')
            (root / "graft" / "a.md").write_text("# a\n")
            (root / "graft" / "INDEX.md").write_text("# index\n")
            before = sorted(p.name for p in root.rglob("*"))
            snap = artifact_snapshot(root)
            after = sorted(p.name for p in root.rglob("*"))
        self.assertEqual(before, after)
        self.assertTrue(snap["wiring"]["present"])
        self.assertEqual(snap["markdown_cards"], 2)
        self.assertTrue(snap["index_md"])

    def test_snapshot_missing_tree(self):
        import pathlib
        import tempfile

        from span.shell.structural.graft import artifact_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            snap = artifact_snapshot(pathlib.Path(tmp) / "absent")
        self.assertFalse(snap["wiring"]["present"])
        self.assertEqual(snap["markdown_cards"], 0)
        self.assertFalse(snap["index_md"])
