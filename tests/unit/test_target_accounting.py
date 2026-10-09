"""Addendum E E-13: whole-target accounting and worklist-first resume.

Two binding behaviors with no new store, carrier, or writer:

1. A restart (fresh continuations) re-admitting an exact target resumes the
   admitted PENDING worklist instead of re-asking an OPEN audit.
2. Exact-target status carries a typed frontier report with one explicit
   disposition per target candidate (UNASSESSED where nothing was adopted).
"""

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


def _bounds():
    return m.QueryBounds(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )


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
        audit_slice = first.request.question.question_slice
        _submit_audit_open(first, structural, evidence, store, live)
        # Restart: fresh continuations, same store. The admitted PENDING
        # follow-up must surface, not a repeated audit.
        resumed = _admit(structural, evidence, store, ContinuationStore(),
                         paths=solo)
        self.assertTrue(hasattr(resumed, "continuation"))
        self.assertEqual(
            resumed.request.question.question_slice, FOLLOW_SLICE)
        self.assertNotEqual(
            resumed.request.question.question_slice, audit_slice)

    def test_exact_target_status_carries_frontier_report(self):
        structural, evidence, store = _harness()
        live = ContinuationStore()
        first = _admit(structural, evidence, store, live)
        _submit_audit_open(first, structural, evidence, store, live)
        target = m.EvidenceScope(paths=TARGET_PATHS, evidence_refs=())

        def _status(continuations):
            return ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=target, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations, authority_seeds=(),
            )

        # The untouched anchor suspends first (read path never invents
        # coverage); examining it as OPEN lets the frontier report appear.
        st_live = ContinuationStore()
        suspended = _status(st_live)
        self.assertTrue(hasattr(suspended, "continuation"))
        sreq = suspended.request
        srefs = tuple(u.evidence_ref for u in sreq.evidence_units)
        ops.submit_interpretation(
            suspended.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=("test status OPEN",),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(sreq.subjects[0].subject_id,),
                        question_slice=sreq.question.question_slice,
                        evidence_scope=m.EvidenceScope(
                            paths=TARGET_PATHS, evidence_refs=srefs),
                        declared_complete=False,
                        question=sreq.question,
                        disposition=(
                            m.SemanticQuestionDisposition.OPEN),
                        result_refs=(),
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=(m.ResolutionKind
                                      .MISSING_SEMANTIC_COVERAGE),
                                subject_or_claim=(
                                    sreq.subjects[0].subject_id),
                                description=(
                                    "status scope not yet examined"),
                                supporting_context=(),
                            ),
                        ),
                        disposition_basis="test OPEN",
                        question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=st_live,
        )
        answer = _status(ContinuationStore())
        self.assertEqual(type(answer).__name__, "SemanticAnswer")
        report = answer.content.coverage_report
        self.assertIsNotNone(report)
        by_locator = {
            entry.subject.canonical_locator: entry
            for entry in report.entries
        }
        # Both structural candidates are accounted for with an explicit
        # disposition; nothing is silently absent and nothing claims
        # CURRENT while OPEN work remains.
        self.assertEqual(set(by_locator), set(TARGET_PATHS))
        for locator, entry in by_locator.items():
            self.assertEqual(
                entry.disposition,
                m.SemanticCoverageDisposition.INCOMPLETE,
                locator)
        self.assertTrue(any(
            entry.resolution_requirements for entry in by_locator.values()))


if __name__ == "__main__":
    unittest.main()


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
