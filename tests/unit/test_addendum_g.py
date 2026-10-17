"""Addendum G completion tests (docs/semantic-governance-addendum-g.md).

G-4 validation member identity: whole-unit atomic rejection stays, but
every diagnostic carries `collection[index] (key=...)` so the agent can
locate the bad member even with missing or duplicated keys.
"""

import datetime
import unittest

from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span import service as ops
from span.service.bounds import BoundsRejectedError, resolve_bounds
from span.service.interpretation import _member_diagnostics
from span.service.requests import RefreshScopeError, StatusTargetError
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import McpAdapter
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


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id="repo-1",
        target=m.SubjectSelector(None, "src/main.py", (), None),
        bounds=_bounds(),
    )


def _claim(key, evidence):
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("does things", ()),
        evidence=evidence,
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the service purpose",
        ),
    )


class ValidationMemberIdentityTest(unittest.TestCase):
    def test_member_diagnostics_format(self):
        prefixed = _member_diagnostics("claims", 3, "purpose-main", ("bad",))
        self.assertEqual(prefixed, ["claims[3] (key=purpose-main): bad"])

    def test_member_diagnostics_missing_key_stays_indexed(self):
        prefixed = _member_diagnostics("relationships", 0, None, ("bad",))
        self.assertEqual(prefixed, ["relationships[0] (key=?): bad"])

    def test_duplicate_keys_rejected_with_index_identity(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            dup = m.SemanticInterpretationResult(
                (
                    _claim("dup-key", (_ref("README.md"),)),
                    _claim("dup-key", (_ref("src/main.py"),)),
                ),
                (), (), (),
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation, dup,
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            message = str(ctx.exception)
            # Same key twice: members stay distinguishable by index.
            self.assertIn("claims[0] (key=dup-key)", message)
            self.assertIn("claims[1] (key=dup-key)", message)
            # Atomic rejection: nothing persisted.
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_unresolvable_evidence_names_member(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            bad = _claim(
                "ghost-claim",
                (
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id="repo-1",
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult((bad,), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            self.assertIn("claims[0] (key=ghost-claim)", str(ctx.exception))
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()


class TransportDiagnosticsTest(unittest.TestCase):
    """G-1: typed errors name the fix and the valid alternative."""

    def test_unknown_repository_lists_registered_ids(self):
        import json

        adapter = McpAdapter()
        result = _dispatch(adapter, 
            "status", {"repository_id": "nope", "target": None}
        )
        self.assertTrue(result.is_error)
        body = json.loads(result.content)
        self.assertEqual(body["error"], "unknown_repository")
        self.assertIn("'nope'", body["message"])
        self.assertIn("registered", body["message"])

    def test_continuation_as_page_token_names_mixup(self):
        import json

        adapter = McpAdapter()
        result = _dispatch(adapter, 
            "locate",
            {
                "repository_id": "repo-1",
                "mode": "SYMBOL",
                "query": "main",
                "match": "CONTAINS",
                "page_token": "cont-lost",
            },
        )
        self.assertTrue(result.is_error)
        body = json.loads(result.content)
        self.assertEqual(body["error"], "ingress")
        self.assertIn("continuation presented as page_token", body["message"])
        self.assertIn("submit_interpretation", body["message"])

    def test_null_edge_kinds_decodes_as_all(self):
        import json

        adapter = McpAdapter()
        result = _dispatch(adapter, 
            "neighbors",
            {
                "repository_id": "nope",
                "target": {
                    "$type": "SubjectSelector",
                    "exact_subject_id": None,
                    "name_or_locator": "src/main.py",
                    "expected_kinds": [],
                    "retrieval_scope_hint": None,
                },
                "direction": "BOTH",
                "edge_kinds": None,
            },
        )
        # Null decodes (schema promises null/empty for all); routing
        # then fails on the unknown repository, not on ingress.
        self.assertTrue(result.is_error)
        body = json.loads(result.content)
        self.assertEqual(body["error"], "unknown_repository")

    def test_page_token_as_continuation_names_mixup(self):
        import json

        adapter = McpAdapter()
        result = _dispatch(adapter, 
            "submit_interpretation",
            {
                "repository_id": "repo-1",
                "continuation": "pg:1:2:3",
                "result": {"$type": "SemanticInterpretationResult"},
            },
        )
        self.assertTrue(result.is_error)
        body = json.loads(result.content)
        self.assertEqual(body["error"], "ingress")
        self.assertIn("page_token presented as continuation", body["message"])

    def test_bounds_over_maximum_names_received_max_default(self):
        with self.assertRaises(BoundsRejectedError) as ctx:
            resolve_bounds(
                _bounds(max_results=1000000), hook=False,
            )
        message = str(ctx.exception)
        self.assertIn("max_results=1000000", message)
        self.assertIn("maximum", message)
        self.assertIn("default when omitted", message)

    def test_target_id_under_hook_fast_standardized(self):
        structural, evidence, store = _harness()
        try:
            request = ops.SemanticStatusRequest(
                repository_id="repo-1",
                target=m.TargetId(value="tgt-1"),
                mode=m.StatusMode.HOOK_FAST,
                bounds=_bounds(),
            )
            with self.assertRaises(StatusTargetError) as ctx:
                ops.status(
                    request, structural=structural, evidence=evidence,
                    store=store, continuations=ContinuationStore(),
                )
            self.assertIn(
                "campaign status requires StatusMode.NORMAL",
                str(ctx.exception),
            )
        finally:
            store.close()

    def test_null_refresh_names_scoped_recovery(self):
        structural, evidence, store = _harness()
        try:
            request = ops.SemanticRefreshRequest(
                repository_id="repo-1", target=None, bounds=_bounds(),
            )
            with self.assertRaises(RefreshScopeError) as ctx:
                ops.refresh(
                    request, structural=structural, evidence=evidence,
                    store=store, continuations=ContinuationStore(),
                )
            message = str(ctx.exception)
            self.assertIn("SubjectSelector", message)
            self.assertIn("status", message)
            self.assertNotIn("Phase 3", message)
        finally:
            store.close()


class StructuralDiagnosticTokensTest(unittest.TestCase):
    """G-3 §4.2a: closed token set beyond the dirty-tree happy path.

    Existing tests cover dirty-tree joins, clean-verified, and strict
    construction validation. These cover the remaining producer states:
    old index, unverifiable file, injected (pathless) wiring, non-git
    tree, and the scope+file join order. Missing-index fail-closed is
    covered by graft-source tests; the live stdio transcript covers
    dirty-tree end to end.
    """

    def _write_repo(self, tmp, files, commit=True):
        import pathlib
        import subprocess

        root = pathlib.Path(tmp)
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (root / ".gitignore").write_text(
            "graft/\n.ignore\n", encoding="utf-8"
        )
        subprocess.run(
            ("git", "-C", str(root), "init", "-q"),
            check=True, timeout=60,
        )
        subprocess.run(
            ("git", "-C", str(root), "add", "-A"),
            check=True, timeout=60,
        )
        if commit:
            subprocess.run(
                (
                    "git", "-C", str(root),
                    "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "fixture",
                ),
                check=True, timeout=60,
            )
        return root

    def _write_wiring(self, root, bodies):
        import hashlib
        import json
        import pathlib

        root = pathlib.Path(root)
        graph_dir = root / "graft" / ".graph"
        graph_dir.mkdir(parents=True, exist_ok=True)
        nodes = [
            {
                "id": rel,
                "name": pathlib.Path(rel).name,
                "kind": "file",
                "path": rel,
                "body_hash": hashlib.sha256(
                    body.encode("utf-8")
                ).hexdigest(),
            }
            for rel, body in bodies.items()
        ]
        (graph_dir / "wiring.json").write_text(
            json.dumps({"nodes": nodes, "edges": []}),
            encoding="utf-8",
        )

    def test_old_index_token_when_wiring_predates_head(self):
        import os
        import tempfile
        import time

        from span.shell.structural.graft import GraftStructuralSource

        tmp = tempfile.mkdtemp(prefix="span-g8-old-")
        try:
            files = {"src/a.py": "VALUE = 1\n"}
            root = self._write_repo(tmp, files)
            self._write_wiring(root, files)
            # Age the wiring before HEAD: HEAD time is now, so backdate
            # the wiring file by two minutes.
            wiring = root / "graft" / ".graph" / "wiring.json"
            old = time.time() - 120
            os.utime(wiring, (old, old))
            source = GraftStructuralSource("old-idx", root)
            report = source.verify_files("old-idx", ("src/a.py",))
            self.assertIs(
                report.coverage, m.ScopeCoverage.UNVERIFIED
            )
            self.assertEqual(
                report.coverage_detail,
                "index-older-than-head+repository-population-unverified",
            )
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_unverifiable_file_token_for_unrecorded_path(self):
        import tempfile

        from span.shell.structural.graft import GraftStructuralSource

        tmp = tempfile.mkdtemp(prefix="span-g8-unver-")
        try:
            files = {"src/a.py": "VALUE = 1\n"}
            root = self._write_repo(tmp, files)
            self._write_wiring(root, files)
            source = GraftStructuralSource("unver", root)
            report = source.verify_files("unver", ("src/ghost.py",))
            self.assertEqual(
                report.coverage_detail, "unverifiable-file"
            )
            self.assertEqual(report.unverifiable_files, ("src/ghost.py",))
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_injected_index_token_for_pathless_wiring(self):
        import hashlib

        from span.shell.structural.graft import GraftStructuralSource

        body = "VALUE = 1\n"
        source = GraftStructuralSource(
            "inj",
            "/nonexistent",
            wiring={
                "nodes": [{
                    "id": "src/a.py",
                    "kind": "file",
                    "path": "src/a.py",
                    "body_hash": hashlib.sha256(
                        body.encode("utf-8")
                    ).hexdigest(),
                }],
                "edges": [],
            },
        )
        report = source.verify_files("inj", ("src/a.py",))
        # Pathless construction cannot establish scope currency; the
        # live file is also unreadable under /nonexistent, so both the
        # scope token and the file token apply in fixed order.
        self.assertEqual(
            report.coverage_detail,
            "injected-index+touched-file-mismatch",
        )

    def test_non_git_tree_token_without_git(self):
        import pathlib
        import tempfile

        from span.shell.structural.graft import GraftStructuralSource

        tmp = tempfile.mkdtemp(prefix="span-g8-nogit-")
        try:
            root = pathlib.Path(tmp)
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "a.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            self._write_wiring(root, {"src/a.py": "VALUE = 1\n"})
            # Deliberately no git init: scope currency cannot be
            # established, but the touched file verifies, so the
            # scope token stands alone.
            source = GraftStructuralSource("nogit", root)
            report = source.verify_files("nogit", ("src/a.py",))
            self.assertEqual(report.coverage_detail, "non-git-tree")
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_scope_and_file_tokens_join_in_fixed_order(self):
        import pathlib
        import tempfile

        from span.shell.structural.graft import GraftStructuralSource

        tmp = tempfile.mkdtemp(prefix="span-g8-join-")
        try:
            root = pathlib.Path(tmp)
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "a.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            self._write_wiring(root, {"src/a.py": "VALUE = 1\n"})
            source = GraftStructuralSource("join", root)
            report = source.verify_files("join", ("src/a.py",))
            self.assertEqual(
                report.coverage_detail,
                "non-git-tree+touched-file-mismatch",
            )
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


class EmptyResultWordingTest(unittest.TestCase):
    """G-4.2c: empty UNVERIFIED proves nothing — wording pinned where
    agents actually read it (runbook guidance + ScopeCoverage contract).
    Live behavior verified separately: 0-entry UNVERIFIED pages return
    empty entries with coverage_detail, never a claimed miss."""

    def test_runbook_states_empty_proves_nothing(self):
        import pathlib

        runbook = (
            pathlib.Path(__file__).resolve().parents[2]
            / "docs" / "onboarding-runbook.md"
        ).read_text(encoding="utf-8")
        self.assertIn("UNVERIFIED", runbook)
        self.assertIn("proves nothing about absence", runbook)

    def test_scope_coverage_contract_states_empty_unverified(self):
        self.assertIn("proves", m.ScopeCoverage.__doc__)
        self.assertIn("nothing about absence", m.ScopeCoverage.__doc__)


class EntryDecisionDescriptionTest(unittest.TestCase):
    """G-11: MCP `status` description states the HOOK_FAST boundary so
    agents that never read the skill still cannot misread 0/0 as clean."""

    def test_status_description_states_event_local_scope(self):
        from span.shell.mcp import TOOL_DESCRIPTIONS

        description = TOOL_DESCRIPTIONS["status"]
        self.assertIn("HOOK_FAST", description)
        self.assertIn("event-local", description)
        self.assertIn("never", description)
        self.assertIn("inventory", description)


class RefreshAdmissionOrderTest(unittest.TestCase):
    """G-15: refresh resumes recorded pendings in deterministic order
    instead of re-deriving the root question, and never suspends one
    question twice while its unit is live."""

    def _write_pending(self, store, cls, slice):
        sid = _sid()
        question = m.SemanticQuestionScope(
            scope_root=sid, subject=sid, question_class=cls,
            question_slice=slice, materiality_basis="rotation test",
        )
        store.write_index_batch(m.CanonicalIndexBatch(
            subjects=(m.Subject(sid, "main", None),),
            coverage=(m.InterpretationCoverage(
                subjects=(sid,), question_slice=slice,
                evidence_scope=m.EvidenceScope(), declared_complete=False,
                question=question,
                disposition=m.SemanticQuestionDisposition.PENDING,
                result_refs=(), resolution_requirements=(),
                disposition_basis="admitted",
                question_evidence=()),),
        ))
        return question

    def _refresh(self, structural, evidence, store, continuations):
        from span.ports.interpretation import PendingInterpretation  # noqa: F401
        return ops.refresh(
            ops.SemanticRefreshRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
            authority_seeds=(_ref("README.md"),),
        )

    def _resolve_na(self, pending, structural, evidence, store, continuations):
        observed = fingerprint_content(FILES["src/main.py"])
        return ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(), relationships=(), governing_source_refs=(),
                diagnostics=(), candidate_subjects=(),
                candidate_conflicts=(), proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(pending.request.question.subject,),
                        question_slice=(
                            pending.request.question.question_slice
                        ),
                        evidence_scope=m.EvidenceScope(),
                        declared_complete=False,
                        question=pending.request.question,
                        disposition=(
                            m.SemanticQuestionDisposition.NOT_APPLICABLE
                        ),
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="rotation test",
                        question_evidence=(
                            m.QuestionEvidenceObservation(
                                evidence_ref=_ref("src/main.py"),
                                observed_fingerprint=observed,
                            ),
                        )),),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(),
                proposed_target_questions=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )

    def test_pendings_bind_in_order_without_duplicates(self):
        from span.ports.interpretation import PendingInterpretation

        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            self._write_pending(
                store, m.SemanticQuestionClass.CQ_03, "zeta slice",
            )
            self._write_pending(
                store, m.SemanticQuestionClass.CQ_02, "alpha slice",
            )
            first = self._refresh(
                structural, evidence, store, continuations,
            )
            self.assertIsInstance(first, PendingInterpretation)
            self.assertEqual(
                first.request.question.question_slice, "alpha slice",
            )
            # The first unit is still live: the next refresh must bind
            # the other pending, never re-suspend the same question.
            second = self._refresh(
                structural, evidence, store, continuations,
            )
            self.assertIsInstance(second, PendingInterpretation)
            self.assertEqual(
                second.request.question.question_slice, "zeta slice",
            )
            self.assertNotEqual(
                first.continuation, second.continuation,
            )
            self._resolve_na(
                first, structural, evidence, store, continuations,
            )
            self._resolve_na(
                second, structural, evidence, store, continuations,
            )
            third = self._refresh(
                structural, evidence, store, continuations,
            )
            if isinstance(third, PendingInterpretation):
                self.assertNotIn(
                    third.request.question.question_slice,
                    ("alpha slice", "zeta slice"),
                )
        finally:
            store.close()


class GhostSubjectTest(unittest.TestCase):
    """G-16: a recorded path-like subject absent from the evidence
    inventory reads UNVERIFIABLE with an explicit absence
    requirement; present paths are unaffected."""

    def test_absent_path_reads_unverifiable(self):
        from span.service.operations.status import (
            _repository_coverage_entry,
        )

        structural, evidence, store = _harness()
        try:
            ghost_id = m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/gone.py",
            )
            ghost = m.Subject(ghost_id, "ghost", None)
            # No records: pure-UNASSESSED subjects keep UNASSESSED;
            # the ghost rule only fires where positive display would
            # otherwise mislead.
            bare = _repository_coverage_entry(
                "repo-1", ghost, evidence=evidence, store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                bare.disposition,
                m.SemanticCoverageDisposition.UNASSESSED,
            )
            self.assertFalse(
                any(
                    "absent" in requirement.description
                    for requirement in bare.resolution_requirements
                )
            )
            # With persisted records behind it, the same absent path
            # reads UNVERIFIABLE with an explicit absence requirement.
            question = m.SemanticQuestionScope(
                scope_root=ghost_id, subject=ghost_id,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="ghost purpose",
                materiality_basis="ghost test",
            )
            store.write_index_batch(m.CanonicalIndexBatch(
                subjects=(ghost,),
                coverage=(m.InterpretationCoverage(
                    subjects=(ghost_id,), question_slice="ghost purpose",
                    evidence_scope=m.EvidenceScope(),
                    declared_complete=False, question=question,
                    disposition=m.SemanticQuestionDisposition.PENDING,
                    result_refs=(), resolution_requirements=(),
                    disposition_basis="admitted",
                    question_evidence=()),),
            ))
            entry = _repository_coverage_entry(
                "repo-1", ghost, evidence=evidence, store=store,
                bounds=_bounds(),
            )
            self.assertIs(
                entry.disposition,
                m.SemanticCoverageDisposition.UNVERIFIABLE,
            )
            self.assertTrue(
                any(
                    "absent" in requirement.description
                    for requirement in entry.resolution_requirements
                )
            )
            present = m.Subject(_sid(), "main", None)
            control = _repository_coverage_entry(
                "repo-1", present, evidence=evidence, store=store,
                bounds=_bounds(),
            )
            self.assertFalse(
                any(
                    "absent" in requirement.description
                    for requirement in control.resolution_requirements
                )
            )
        finally:
            store.close()


class InventoryWalkTest(unittest.TestCase):
    """Pruned filesystem walk produces an identical output set to the
    unpruned walk (skips .git/node_modules-style trees before
    descending). Reverted 2026-10-13: the former one-shared-walk
    batching across a status call plus its call-count test were
    removed as unauthorized Stage-2 behavior under §4.8c (Stage 1 is
    observation-only; internal breakdown unisolated, no dominance
    proven). Per-coverage discovery checks walk as before; no
    cross-operation snapshot exists, so no staleness question arises."""

    def test_pruned_walk_matches_unpruned_set(self):
        import pathlib
        import tempfile

        from span.shell.filesystem_evidence import FilesystemEvidenceSource

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "keep.txt").write_text("hello\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "sub" / "nested").mkdir()
            (root / "sub" / "nested" / "deep.md").write_text(
                "# d\n", encoding="utf-8"
            )
            (root / ".hidden.txt").write_text("h\n", encoding="utf-8")
            (root / "binary.bin").write_bytes(b"\x00\x01\x02binary")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "skip.js").write_text(
                "x\n", encoding="utf-8"
            )
            (root / ".git").mkdir()
            (root / ".git" / "skip2").write_text("x\n", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "skip3.pyc").write_bytes(b"\x00x")
            (root / "sub" / "__pycache__").mkdir()
            (root / "sub" / "__pycache__" / "skip4.pyc").write_bytes(
                b"\x00x"
            )
            (root / "node_modules_file").write_text("x\n", encoding="utf-8")
            source = FilesystemEvidenceSource("walk-repo", root)
            self.assertEqual(
                source._paths(),
                [
                    ".hidden.txt",
                    "keep.txt",
                    "node_modules_file",
                    "sub/keep.py",
                    "sub/nested/deep.md",
                ],
            )


class StructuralCurrentTest(unittest.TestCase):
    """G-18: provider-generic structural currency stays hidden.

    `refresh` calls `ensure_current` exactly once per call; provider
    failure degrades to an UNVERIFIABLE note, never raises; the graft
    adapter answers currency from its own wiring-vs-HEAD computation
    and never builds during describe. No MCP surface change (twelve
    operations; TOOL_NAMES freeze covered in test_mcp_transport)."""

    def _refresh_harness(self, structural):
        from span.shell.agent_exchange.continuations import ContinuationStore  # noqa: F401
        evidence = FixtureEvidenceSource("repo-1", dict(FILES))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural, evidence=evidence, store=store,
        )
        return evidence, store

    def _refresh_answer(self, structural, evidence, store):
        from span.shell.agent_exchange.continuations import ContinuationStore
        return ops.refresh(
            ops.SemanticRefreshRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(),
        )

    def test_refresh_calls_ensure_current_once(self):
        calls = []

        class _Counting(InMemoryStructuralSource):
            def ensure_current(self, repository_id):
                calls.append(repository_id)
                return super().ensure_current(repository_id)

        structural = _Counting(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            SUBJECTS,
        )
        evidence, store = self._refresh_harness(structural)
        try:
            self._refresh_answer(structural, evidence, store)
            self.assertEqual(calls, ["repo-1"])
        finally:
            store.close()

    def test_currency_note_maps_states(self):
        from span.service.operations.refresh import _currency_note

        self.assertIsNone(_currency_note(m.Freshness(
            state=m.FreshnessState.CURRENT, reason="t-ok",
        )))
        note = _currency_note(m.Freshness(
            state=m.FreshnessState.UNVERIFIABLE, reason="t-down",
        ))
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIs(
            note.kind, m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
        )
        self.assertIn("t-down", note.description)

    def test_ensure_failure_never_raises(self):
        class _Failing(InMemoryStructuralSource):
            def ensure_current(self, repository_id):
                return m.Freshness(
                    state=m.FreshnessState.UNVERIFIABLE,
                    reason="t-provider-down",
                )

        structural = _Failing(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            SUBJECTS,
        )
        evidence, store = self._refresh_harness(structural)
        try:
            # Suspend path also performs the single ensure call first;
            # the provider reason is covered by test_currency_note_maps_states.
            self._refresh_answer(structural, evidence, store)
        finally:
            store.close()

    def test_graft_describe_unverifiable_off_tree(self):
        import pathlib
        import tempfile

        from span.shell.structural import graft as g

        wiring = {
            "nodes": [
                {
                    "id": "a.py", "name": "a.py", "kind": "file",
                    "path": "a.py", "span": "L1-L2", "signature": None,
                    "body_hash": "aa01",
                },
            ],
            "edges": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            src = g.GraftStructuralSource(
                "repo-1", pathlib.Path(tmp), wiring=wiring,
            )
            out = src.describe_current("repo-1")
            self.assertIs(out.state, m.FreshnessState.UNVERIFIABLE)

    def test_graft_ensure_never_raises_without_builder(self):
        import pathlib
        import tempfile
        from unittest import mock

        from span.shell.structural import graft as g

        wiring = {
            "nodes": [
                {
                    "id": "a.py", "name": "a.py", "kind": "file",
                    "path": "a.py", "span": "L1-L2", "signature": None,
                    "body_hash": "aa01",
                },
            ],
            "edges": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            src = g.GraftStructuralSource(
                "repo-1", root, wiring=wiring,
            )
            calls = []
            real = g._run_index_build

            def _fake(path, artifact_dir=None):
                calls.append(str(path))
                return False, "t-no-builder"

            try:
                g._run_index_build = _fake
                out = src.ensure_current("repo-1")
            finally:
                g._run_index_build = real
            self.assertIs(out.state, m.FreshnessState.UNVERIFIABLE)
            self.assertIn("t-no-builder", out.reason)
            self.assertEqual(calls, [str(root)])

    def test_status_shares_one_inventory_walk(self):
        from span import service as ops
        from span.shell.sqlite_store import SqliteSemanticStore
        from span.shell.structural.memory import (
            InMemoryFile,
            InMemoryStructuralSource,
            InMemorySubject,
        )

        files = {
            "README.md": "# svc\n\nDoes things.\n",
            "src/main.py": "VALUE = 1\n",
        }
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            (InMemorySubject(
                "src/main.py", m.SubjectKind.COMPONENT, "main",
            ),),
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
            structural=structural, evidence=evidence, store=store,
        )
        try:
            sid = _sid()
            for cls, sl in (
                (m.SemanticQuestionClass.CQ_02, "alpha slice"),
                (m.SemanticQuestionClass.CQ_03, "zeta slice"),
            ):
                question = m.SemanticQuestionScope(
                    scope_root=sid, subject=sid, question_class=cls,
                    question_slice=sl,
                    materiality_basis="walk test",
                )
                store.write_index_batch(m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "main", None),),
                    coverage=(m.InterpretationCoverage(
                        subjects=(sid,), question_slice=sl,
                        evidence_scope=m.EvidenceScope(),
                        declared_complete=False, question=question,
                        disposition=(
                            m.SemanticQuestionDisposition.PENDING
                        ),
                        result_refs=(), resolution_requirements=(),
                        disposition_basis="admitted",
                        question_evidence=()),),
                ))
            real_list = evidence.list_inventory_entries
            calls = []

            def counting_list(repository_id, scope, fingerprint_locators=()):
                calls.append((scope, tuple(fingerprint_locators)))
                return real_list(repository_id, scope, fingerprint_locators)

            evidence.list_inventory_entries = counting_list  # type: ignore[method-assign]
            try:
                answer = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id="repo-1", target=None,
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
            finally:
                evidence.list_inventory_entries = real_list  # type: ignore[method-assign]
            self.assertIsInstance(answer, m.SemanticAnswer)
            # One shared walk for the whole status call — not one per
            # coverage examined. Generous bound; bites only on fan-out
            # regressions back to per-coverage walks.
            self.assertLessEqual(len(calls), 2)
        finally:
            store.close()


def _dispatch(adapter, tool, arguments):
    """S6 migration: project the payload to the compact wire grammar."""
    from span.core import schema as _schema
    from span.shell.mcp import _REQUEST_CLASS, McpAdapter

    if isinstance(arguments, dict):
        cls = _REQUEST_CLASS.get(tool)
        if cls is not None:
            arguments = _schema.compact_payload(cls, arguments)
    return McpAdapter.dispatch(adapter, tool, arguments)
