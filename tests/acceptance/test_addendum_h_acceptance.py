"""Addendum H acceptance (friction-resolution R0–R6 proving tests).

Pins the corrective contracts at the service/store boundary through the
same call paths the MCP adapter uses: recoverable continuation
ownership, provider-backed admission with normalization, one-question
correction binding, pre-call repository discovery data, and read-only
target counts. All deterministic; no model invocation.
"""

import datetime
import os
import tempfile
import threading
import unittest

from span.core import model as m
from span.core.validation import InterpretationUnitRejected
from span.ports.interpretation import (
    InterpretationUnavailable,
    PendingInterpretation,
)
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

REPO = "h-svc"

FILES = {
    "src/seed.py": "VALUE = 1\n",
    "src/other.py": "OTHER = 2\n",
}


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _sid(locator="src/seed.py"):
    return m.SubjectId(
        repository_id=REPO, subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator=locator,
    )


def _ref(path, fingerprint=None, span=None):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=(
            fingerprint if fingerprint is not None
            else fingerprint_content(FILES[path])
        ),
        section_or_span=span,
    )


def _fixture_sources(files=None):
    files = dict(FILES) if files is None else files
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in files.items()),
        tuple(
            InMemorySubject(p, m.SubjectKind.COMPONENT, p.split("/")[-1])
            for p in files
        ),
        (),
    )
    evidence = FixtureEvidenceSource(REPO, dict(files))
    return structural, evidence


def _harness(files=None):
    files = dict(FILES) if files is None else files
    structural, evidence = _fixture_sources(files)
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


def _answer_current(request):
    q = request.question
    return m.InterpretationCoverage(
        subjects=(q.subject,),
        question_slice=q.question_slice,
        evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
        declared_complete=True,
        question=q,
        disposition=m.SemanticQuestionDisposition.ANSWERED,
        result_refs=(),
        resolution_requirements=(),
        disposition_basis="test explicit completion",
        question_evidence=(),
    )


def _purpose_claim(summary="Sorts seeds"):
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue(summary, ()),
        evidence=(_ref("src/seed.py"),),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "seed module states the seed purpose",
        ),
    )


def _suspend(structural, evidence, store, continuations):
    current = ops.explain(
        ops.SemanticExplainRequest(
            repository_id=REPO,
            target=m.SubjectSelector(None, "src/seed.py", (), None),
            bounds=_bounds(),
        ),
        structural=structural, evidence=evidence, store=store,
        continuations=continuations,
    )
    assert isinstance(current, PendingInterpretation), type(current)
    return current


def _crash_during_commit(db_path):
    """Run one submit in a child that dies at SQLite's commit boundary."""
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        tuple(
            InMemorySubject(p, m.SubjectKind.COMPONENT, p.split("/")[-1])
            for p in FILES
        ),
        (),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(db_path)
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural, evidence=evidence, store=store,
    )
    continuations = ContinuationStore()
    pending = _suspend(structural, evidence, store, continuations)

    def kill_at_commit(statement):
        if statement.strip().upper().startswith("COMMIT"):
            os._exit(86)

    store._db.set_trace_callback(kill_at_commit)
    ops.submit_interpretation(
        pending.continuation,
        m.SemanticInterpretationResult(
            claims=(_purpose_claim(),), relationships=(),
            candidate_subjects=(), candidate_conflicts=(),
            proposed_question_coverages=(_answer_current(pending.request),),
            candidate_withdrawals=(),
        ),
        structural=structural, evidence=evidence, store=store,
        continuations=continuations,
    )
    raise AssertionError("the child must terminate at the SQLite commit")


def _recover_after_commit_crash(db_path):
    structural, evidence = _fixture_sources()
    store = SqliteSemanticStore(db_path)
    continuations = ContinuationStore()
    try:
        fresh = ops.explain(
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/seed.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        if isinstance(fresh, PendingInterpretation):
            fresh = ops.submit_interpretation(
                fresh.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(fresh.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
        page = store.load_claims(REPO, (_sid(),), (), _bounds())
        coverages = store.load_question_coverages(
            REPO, _sid(), (_sid(),), _bounds()
        )
        return fresh, page, coverages
    finally:
        store.close()


class ContinuationOwnershipTest(unittest.TestCase):
    """H §4/R1: single-flight acquire, replay rejection, expiry re-entry."""

    def test_concurrent_acquire_single_winner(self):
        from span.shell.agent_exchange.continuations import SuspendedOperation

        continuations = ContinuationStore()
        token = continuations.pend(
            SuspendedOperation(
                op="explain", repository_id=REPO,
                subject=m.Subject(_sid(), "seed", None),
                request=m.SemanticInterpretationRequest(
                    repository_id=REPO,
                    subjects=(m.Subject(_sid(), "seed", None),),
                    evidence_units=(),
                    structural_observations=(),
                    allowed_claim_kinds=tuple(m.ClaimKind),
                    allowed_relationship_kinds=tuple(m.RelationshipKind),
                    identity_bindings=(_sid(),),
                    brief=m.TaskBrief(),
                    bounds=_bounds(),
                ),
                bounds=_bounds(),
                state=m.RepositoryState(
                    repository_id=REPO, revision_id="r1", dirty=False,
                    state_fingerprint="fp",
                    observed_at=datetime.datetime(
                        2026, 1, 1, tzinfo=datetime.timezone.utc
                    ),
                ),
            )
        )
        barrier = threading.Barrier(2)
        results = []

        def attempt():
            barrier.wait()
            results.append(continuations.acquire(token))

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(1 for r in results if r is not None), 1)
        self.assertEqual(len(continuations), 1)
        continuations.release(token)
        self.assertIsNotNone(continuations.acquire(token))

    def test_replay_after_success_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(pending.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            page = store.load_claims(REPO, (_sid(),), (), _bounds())
            self.assertEqual(len(page.items), 1)
        finally:
            store.close()

    def test_reissue_loses_to_inflight_submit(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            owned = continuations.acquire(pending.continuation)
            self.assertIsNotNone(owned)
            # A concurrent reissue must not steal submit's token.
            with self.assertRaises(InterpretationUnavailable):
                ops.reissue_interpretation(
                    pending.continuation, continuations=continuations
                )
            continuations.release(pending.continuation)
            # After release, reissue succeeds and consumes the old token.
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            self.assertIsInstance(reissued, PendingInterpretation)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_expired_entries_reaped_on_next_operation(self):
        from span.shell.agent_exchange.continuations import SuspendedOperation

        now = [datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]
        store = ContinuationStore(ttl_seconds=60, now=lambda: now[0])

        def _record():
            return SuspendedOperation(
                op="explain", repository_id=REPO,
                subject=m.Subject(_sid(), "seed", None),
                request=m.SemanticInterpretationRequest(
                    repository_id=REPO,
                    subjects=(m.Subject(_sid(), "seed", None),),
                    evidence_units=(),
                    structural_observations=(),
                    allowed_claim_kinds=tuple(m.ClaimKind),
                    allowed_relationship_kinds=tuple(m.RelationshipKind),
                    identity_bindings=(_sid(),),
                    brief=m.TaskBrief(),
                    bounds=_bounds(),
                ),
                bounds=_bounds(),
                state=m.RepositoryState(
                    repository_id=REPO, revision_id="r1", dirty=False,
                    state_fingerprint="fp",
                    observed_at=datetime.datetime(
                        2026, 1, 1, tzinfo=datetime.timezone.utc
                    ),
                ),
            )

        first = store.pend(_record())
        self.assertEqual(len(store), 1)
        now[0] += datetime.timedelta(seconds=61)
        second = store.pend(_record())
        # The expired abandoned entry is actually removed, not skipped.
        self.assertEqual(len(store), 1)
        self.assertIsNone(store.peek(first))
        self.assertIsNone(store.acquire(first))
        self.assertIsNotNone(store.peek(second))

    def test_expired_token_reenters_via_original_operation(self):
        now = [datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore(
                ttl_seconds=60, now=lambda: now[0]
            )
            pending = _suspend(structural, evidence, store, continuations)
            now[0] += datetime.timedelta(seconds=61)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            # Recovery is the idempotent original operation, not reissue.
            again = _suspend(structural, evidence, store, continuations)
            self.assertIsInstance(again, PendingInterpretation)
        finally:
            store.close()

    def test_persistence_failure_retries_same_continuation(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            result = m.SemanticInterpretationResult(
                claims=(_purpose_claim(),), relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(
                    _answer_current(pending.request),
                ),
                candidate_withdrawals=(),
            )
            original = store.write_index_batch
            calls = {"n": 0}

            def flaky(batch):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("injected store failure")
                return original(batch)

            store.write_index_batch = flaky
            try:
                with self.assertRaises(RuntimeError):
                    ops.submit_interpretation(
                        pending.continuation, result,
                        structural=structural, evidence=evidence,
                        store=store, continuations=continuations,
                    )
            finally:
                store.write_index_batch = original
            self.assertEqual(len(continuations), 1)
            page = store.load_claims(REPO, (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
            answer = ops.submit_interpretation(
                pending.continuation, result,
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()

    def test_postcommit_failure_recovers_via_reissue(self):
        import span.service.exchange as exchange_mod

        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            original = exchange_mod._compose_explain_answer
            calls = {"n": 0}

            def flaky(*args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("injected post-commit failure")
                return original(*args, **kwargs)

            exchange_mod._compose_explain_answer = flaky
            try:
                with self.assertRaises(RuntimeError):
                    ops.submit_interpretation(
                        pending.continuation,
                        m.SemanticInterpretationResult(
                            claims=(_purpose_claim(),), relationships=(),
                            candidate_subjects=(), candidate_conflicts=(),
                            proposed_question_coverages=(
                                _answer_current(pending.request),
                            ),
                            candidate_withdrawals=(),
                        ),
                        structural=structural, evidence=evidence,
                        store=store, continuations=continuations,
                    )
            finally:
                exchange_mod._compose_explain_answer = original
            # Token consumed; semantic state committed exactly once.
            self.assertEqual(len(continuations), 0)
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()


class EvidenceProvenanceTest(unittest.TestCase):
    """H §5/R2: fabricated spans strip; fingerprints come from the provider."""

    def test_fabricated_nested_provenance_rejected(self):
        """Nested `EvidenceRef`s (basis input refs, requirement
        supporting context, precedence overrides) go through the same
        provider admission: unknown nested ids reject with the token
        retained."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            forged_nested = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-ghost-nested"),
                repository_id=REPO,
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="ghost-nested.py",
            )
            claim = _purpose_claim()
            claim = claim.__class__(
                candidate_key=claim.candidate_key,
                subject=claim.subject,
                kind=claim.kind,
                value=claim.value,
                assertion_nature=claim.assertion_nature,
                evidence=claim.evidence,
                candidate_authority=claim.candidate_authority,
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "seed module states the seed purpose",
                    (forged_nested,),
                ),
            )
            with self.assertRaises(InterpretationUnitRejected) as cm:
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(claim,), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            self.assertIn("ev-ghost-nested", str(cm.exception))
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()

    def test_valid_nested_provenance_normalized_on_persist(self):
        """Valid nested refs persist in canonical form: current
        observation fingerprint, fabricated spans stripped."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            nested = _ref(
                "src/other.py", fingerprint="0" * 64,
                span="made-up-nested-span",
            )
            claim = _purpose_claim()
            claim = claim.__class__(
                candidate_key=claim.candidate_key,
                subject=claim.subject,
                kind=claim.kind,
                value=claim.value,
                assertion_nature=claim.assertion_nature,
                evidence=claim.evidence,
                candidate_authority=claim.candidate_authority,
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "seed and other modules state the seed purpose",
                    (nested,),
                ),
            )
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(claim,), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(pending.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            persisted_basis = answer.content.claims[0].basis
            nested_refs = [
                ref for ref in persisted_basis.input_refs
                if isinstance(ref, m.EvidenceRef)
            ]
            self.assertEqual(len(nested_refs), 1)
            self.assertEqual(nested_refs[0].locator, "src/other.py")
            self.assertIsNone(nested_refs[0].section_or_span)
            self.assertEqual(
                nested_refs[0].revision_or_fingerprint,
                fingerprint_content(FILES["src/other.py"]),
            )
        finally:
            store.close()

    def test_fabricated_span_stripped_not_persisted(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            stale_fp = "0" * 64
            forged = _purpose_claim()
            forged = forged.__class__(
                candidate_key=forged.candidate_key,
                subject=forged.subject,
                kind=forged.kind,
                value=forged.value,
                assertion_nature=forged.assertion_nature,
                evidence=(
                    _ref(
                        "src/seed.py", fingerprint=stale_fp,
                        span="completely-made-up-location",
                    ),
                ),
                candidate_authority=forged.candidate_authority,
                basis=forged.basis,
            )
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(forged,), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(pending.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            persisted = answer.content.claims[0].evidence[0]
            self.assertEqual(persisted.evidence_id.value, "ev-src/seed.py")
            self.assertEqual(persisted.locator, "src/seed.py")
            self.assertIsNone(persisted.section_or_span)
            self.assertEqual(
                persisted.revision_or_fingerprint,
                fingerprint_content(FILES["src/seed.py"]),
            )
            deps = store.load_evidence_dependencies(
                REPO, (m.ClaimRef(id=answer.content.claims[0].claim_id),)
            )
            self.assertEqual(len(deps), 1)
            self.assertIsNone(deps[0].evidence_ref.section_or_span)
            self.assertEqual(
                deps[0].observed_fingerprint,
                fingerprint_content(FILES["src/seed.py"]),
            )
        finally:
            store.close()


class CorrectionBindingTest(unittest.TestCase):
    """H §6/R4: one fallback unit corrects exactly one persisted question."""

    def _establish(self, structural, evidence, store, continuations):
        pending = _suspend(structural, evidence, store, continuations)
        answer = ops.submit_interpretation(
            pending.continuation,
            m.SemanticInterpretationResult(
                claims=(_purpose_claim("Sorts seeds"),), relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(
                    _answer_current(pending.request),
                ),
                candidate_withdrawals=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(answer, m.SemanticAnswer)
        return pending.request.question, answer.content.claims[0]

    def _challenge(self, structural, evidence, store, continuations):
        challenged = ops.refresh(
            ops.SemanticRefreshRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/seed.py", (), None),
                bounds=_bounds(),
                stale_only=False,
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(challenged, PendingInterpretation)
        return challenged

    @staticmethod
    def _coverage(scope):
        return m.InterpretationCoverage(
            subjects=(scope.subject,),
            question_slice=scope.question_slice,
            evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
            declared_complete=True,
            question=scope,
            disposition=m.SemanticQuestionDisposition.ANSWERED,
            result_refs=(),
            resolution_requirements=(),
            disposition_basis="test correction identity",
            question_evidence=(),
        )

    def test_same_slice_different_subject_is_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, _ = self._establish(
                structural, evidence, store, continuations
            )
            challenged = self._challenge(
                structural, evidence, store, continuations
            )
            wrong = m.SemanticQuestionScope(
                scope_root=original_scope.scope_root,
                subject=_sid("src/other.py"),
                question_class=original_scope.question_class,
                question_slice=original_scope.question_slice,
                materiality_basis=original_scope.materiality_basis,
            )
            self._assert_rejected(original_scope, wrong, challenged,
                                  structural, evidence, store, continuations)
        finally:
            store.close()

    def test_same_subject_and_slice_different_class_is_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, _ = self._establish(
                structural, evidence, store, continuations
            )
            challenged = self._challenge(
                structural, evidence, store, continuations
            )
            wrong = m.SemanticQuestionScope(
                scope_root=original_scope.scope_root,
                subject=original_scope.subject,
                question_class=m.SemanticQuestionClass.CQ_09,
                question_slice=original_scope.question_slice,
                materiality_basis=original_scope.materiality_basis,
            )
            self._assert_rejected(original_scope, wrong, challenged,
                                  structural, evidence, store, continuations)
        finally:
            store.close()

    def test_same_subject_and_class_different_scope_root_is_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, _ = self._establish(
                structural, evidence, store, continuations
            )
            challenged = self._challenge(
                structural, evidence, store, continuations
            )
            wrong = m.SemanticQuestionScope(
                scope_root=_sid("src/other.py"),
                subject=original_scope.subject,
                question_class=original_scope.question_class,
                question_slice=original_scope.question_slice,
                materiality_basis=original_scope.materiality_basis,
            )
            self._assert_rejected(original_scope, wrong, challenged,
                                  structural, evidence, store, continuations)
        finally:
            store.close()

    def _assert_rejected(
        self, original_scope, wrong, challenged, structural, evidence,
        store, continuations,
    ):
        with self.assertRaises(InterpretationUnitRejected) as cm:
            ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim(),), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(self._coverage(wrong),),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
        message = str(cm.exception)
        self.assertIn(
            "correction question is not an exact persisted "
            "SemanticQuestionScope",
            message,
        )
        self.assertIn("scope_root.repository_id=", message)
        self.assertIn("subject.canonical_locator=", message)
        self.assertIn("question_class=", message)
        self.assertIn("question_slice=", message)
        corrected = ops.submit_interpretation(
            challenged.continuation,
            m.SemanticInterpretationResult(
                claims=(_purpose_claim("Sorts seeds reliably"),),
                relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(
                    self._coverage(original_scope),
                ),
                candidate_withdrawals=(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(corrected, m.SemanticAnswer)

    def test_unchanged_source_correction_preserves_question(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, old_claim = self._establish(
                structural, evidence, store, continuations
            )
            challenged = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                    stale_only=False,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(challenged, PendingInterpretation)
            self.assertTrue(
                any(
                    "Correction mode" in rule
                    for rule in challenged.request.brief.submission_rules
                )
            )
            seed_ref = challenged.request.evidence_units[0].evidence_ref
            nominated = m.InterpretationCoverage(
                subjects=(_sid(),),
                question_slice=original_scope.question_slice,
                evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
                declared_complete=True,
                question=original_scope,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(),
                resolution_requirements=(),
                disposition_basis="corrected reading",
                question_evidence=(),
            )
            corrected = ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim("Sorts seeds reliably"),),
                    relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(nominated,),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=m.ClaimRef(id=old_claim.claim_id),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "purpose disproven by inspection",
                            ),
                            evidence=(seed_ref,),
                        ),
                    ),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(corrected, m.SemanticAnswer)
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(
                answer.content.claims[0].value.summary,
                "Sorts seeds reliably",
            )
            with self.assertRaises(ValueError):
                store.load_by_refs(REPO, (m.ClaimRef(id=old_claim.claim_id),))
        finally:
            store.close()

    def test_unchanged_source_correction_persists_no_fallback_coverage(self):
        """Addendum H §6: a successful correction leaves no synthetic
        fallback question behind. After the unit commits, the original
        question identity persists exactly once as ANSWERED, no extra
        CQ-09/fallback coverage exists, and subject status carries no
        artificial pending count."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, _ = self._establish(
                structural, evidence, store, continuations
            )
            challenged = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                    stale_only=False,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(challenged, PendingInterpretation)
            fallback = challenged.request.question
            self.assertIsNotNone(fallback)
            self.assertNotEqual(fallback, original_scope)
            self.assertIs(
                fallback.question_class, m.SemanticQuestionClass.CQ_09
            )
            corrected = ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim("Sorts seeds reliably"),),
                    relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice=original_scope.question_slice,
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=True,
                            question=original_scope,
                            disposition=(
                                m.SemanticQuestionDisposition.ANSWERED
                            ),
                            result_refs=(),
                            resolution_requirements=(),
                            disposition_basis="corrected reading",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(corrected, m.SemanticAnswer)
            rows = store.load_all_question_coverages(
                REPO, None, (_sid(),)
            )
            original_rows = [
                cov for cov in rows
                if cov.question is not None and cov.question == original_scope
            ]
            self.assertEqual(len(original_rows), 1)
            self.assertIs(
                original_rows[0].disposition,
                m.SemanticQuestionDisposition.ANSWERED,
            )
            extras = [
                cov for cov in rows
                if cov.question is not None and cov.question != original_scope
            ]
            self.assertEqual(extras, [])
            status = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(status, m.SemanticAnswer)
            pending_views = [
                view for view in status.content.question_coverage
                if view.effective_disposition
                is m.SemanticQuestionDisposition.PENDING
            ]
            self.assertEqual(pending_views, [])
        finally:
            store.close()

    def test_two_question_correction_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            original_scope, _ = self._establish(
                structural, evidence, store, continuations
            )
            challenged = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                    stale_only=False,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(challenged, PendingInterpretation)
            other_scope = m.SemanticQuestionScope(
                scope_root=original_scope.scope_root,
                subject=original_scope.subject,
                question_class=original_scope.question_class,
                question_slice="a different slice",
                materiality_basis="test material",
            )

            def _coverage(scope):
                return m.InterpretationCoverage(
                    subjects=(_sid(),),
                    question_slice=scope.question_slice,
                    evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
                    declared_complete=True,
                    question=scope,
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=(),
                    resolution_requirements=(),
                    disposition_basis="test",
                    question_evidence=(),
                )

            with self.assertRaises(InterpretationUnitRejected) as cm:
                ops.submit_interpretation(
                    challenged.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _coverage(original_scope),
                            _coverage(other_scope),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            self.assertIn(
                "refresh correction admits exactly one persisted original "
                "question per unit",
                str(cm.exception),
            )
            self.assertIn(
                "scope_root.canonical_locator=src/seed.py",
                str(cm.exception),
            )
            # The rejected correction retains the live continuation: a
            # corrected single-question submission succeeds on it.
            answer = ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim("Sorts seeds reliably"),),
                    relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _coverage(original_scope),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
        finally:
            store.close()


class TargetCountsTest(unittest.TestCase):
    """H §7/R5: single status answer carries snapshot counts."""

    def test_overbounds_plus_stale_reports_unverifiable(self):
        """Governing precedence UNVERIFIABLE → STALE: an over-bounds
        campaign with drifted membership reports UNVERIFIABLE (with
        `None` counts), not STALE."""
        structural, evidence, store = _harness()
        try:
            scope = m.EvidenceScope(paths=("src",), evidence_refs=())
            canonical_scope, canonical_objective = (
                m.canonicalize_target_scope(
                    REPO, scope, "Establish seed areas."
                )
            )
            target_id = m.derive_target_id(
                REPO, canonical_scope, canonical_objective
            )
            area = _sid()
            assoc = m.TargetAssociation(
                target_id=target_id,
                repository_id=REPO,
                target_scope=canonical_scope,
                objective=canonical_objective,
                area_subjects=(area,),
                target_questions=(),
                inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=_ref("src/seed.py"),
                        assigned_area_subjects=(area,),
                    ),
                    m.TargetInventoryAccount(
                        evidence_ref=_ref("src/other.py"),
                        assigned_area_subjects=(area,),
                    ),
                ),
                inventory_fingerprint="drifted-membership",
                observed_repository_state_fingerprint="fp",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(assoc,))
            )
            over = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=target_id,
                    bounds=_bounds(max_results=1),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(over, m.SemanticAnswer)
            self.assertIs(
                over.content.target_disposition,
                m.SemanticCoverageDisposition.UNVERIFIABLE,
            )
            self.assertIsNone(over.content.target_total_count)
            self.assertIsNone(over.content.target_accounted_count)
            self.assertIsNone(over.content.target_unaccounted_count)
            # Control: roomy bounds still observe the membership drift
            # as STALE, with counts from the current enumeration.
            roomy = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=target_id,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(roomy, m.SemanticAnswer)
            self.assertIs(
                roomy.content.target_disposition,
                m.SemanticCoverageDisposition.STALE,
            )
            self.assertEqual(roomy.content.target_total_count, 2)
            self.assertEqual(roomy.content.target_accounted_count, 2)
            self.assertEqual(roomy.content.target_unaccounted_count, 0)
        finally:
            store.close()

    def test_stale_membership_carries_drift_requirement(self):
        """Workflow-issues §6: membership STALE keeps counts and explains
        that STALE means membership drift, not stale semantic claims."""
        structural, evidence, store = _harness()
        try:
            scope = m.EvidenceScope(paths=("src",), evidence_refs=())
            canonical_scope, canonical_objective = (
                m.canonicalize_target_scope(
                    REPO, scope, "Establish seed areas."
                )
            )
            target_id = m.derive_target_id(
                REPO, canonical_scope, canonical_objective
            )
            area = _sid()
            assoc = m.TargetAssociation(
                target_id=target_id,
                repository_id=REPO,
                target_scope=canonical_scope,
                objective=canonical_objective,
                area_subjects=(area,),
                target_questions=(),
                inventory_accounting=(
                    m.TargetInventoryAccount(
                        evidence_ref=_ref("src/seed.py"),
                        assigned_area_subjects=(area,),
                    ),
                    m.TargetInventoryAccount(
                        evidence_ref=_ref("src/other.py"),
                        assigned_area_subjects=(area,),
                    ),
                ),
                inventory_fingerprint="drifted-membership",
                observed_repository_state_fingerprint="fp",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(assoc,))
            )
            answer = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=target_id,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertIs(
                answer.content.target_disposition,
                m.SemanticCoverageDisposition.STALE,
            )
            self.assertEqual(answer.content.target_total_count, 2)
            self.assertEqual(answer.content.target_accounted_count, 2)
            self.assertEqual(answer.content.target_unaccounted_count, 0)
            self.assertTrue(
                any(
                    "membership changed since campaign establishment"
                    in requirement.description
                    for requirement in answer.resolution_requirements
                ),
                [
                    requirement.description
                    for requirement in answer.resolution_requirements
                ],
            )
        finally:
            store.close()

    def test_target_status_carries_counts(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            scope = m.EvidenceScope(paths=("src",), evidence_refs=())
            objective = "Establish seed areas."
            pending = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=REPO, target=scope,
                    objective=objective, bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            canonical_scope, canonical_objective = m.canonicalize_target_scope(
                REPO, scope, objective
            )
            target_id = m.derive_target_id(
                REPO, canonical_scope, canonical_objective
            )
            answer = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO, target=target_id,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            content = answer.content
            self.assertIs(
                content.target_disposition,
                m.SemanticCoverageDisposition.INCOMPLETE,
            )
            self.assertEqual(content.target_total_count, 2)
            self.assertEqual(content.target_accounted_count, 0)
            self.assertEqual(content.target_unaccounted_count, 2)
        finally:
            store.close()


def _suspend_for(structural, evidence, store, continuations, locator):
    current = ops.explain(
        ops.SemanticExplainRequest(
            repository_id=REPO,
            target=m.SubjectSelector(None, locator, (), None),
            bounds=_bounds(),
        ),
        structural=structural, evidence=evidence, store=store,
        continuations=continuations,
    )
    assert isinstance(current, PendingInterpretation), type(current)
    return current


class UnsupportedChallengeTest(unittest.TestCase):
    """H §6/R4.5: an unsupported challenge keeps the existing claim with
    visible unresolved state; nothing is blindly replaced."""

    def test_open_challenge_preserves_existing_claim(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend(structural, evidence, store, continuations)
            original_scope = pending.request.question
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_purpose_claim("Sorts seeds"),), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(pending.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            old_id = answer.content.claims[0].claim_id
            challenged = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                    stale_only=False,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(challenged, PendingInterpretation)
            kept = ops.submit_interpretation(
                challenged.continuation,
                m.SemanticInterpretationResult(
                    claims=(), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice=original_scope.question_slice,
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=False,
                            question=original_scope,
                            disposition=(
                                m.SemanticQuestionDisposition.OPEN
                            ),
                            result_refs=(),
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=(
                                        m.ResolutionKind
                                        .MISSING_SEMANTIC_COVERAGE
                                    ),
                                    subject_or_claim=_sid(),
                                    description=(
                                        "challenge lacks supporting evidence"
                                    ),
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis="unsupported challenge",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(kept, m.SemanticAnswer)
            answer = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/seed.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(
                answer.content.claims[0].value.summary, "Sorts seeds"
            )
            store.load_by_refs(REPO, (m.ClaimRef(id=old_id),))
        finally:
            store.close()


class CommitBoundaryRecoveryTest(unittest.TestCase):
    """A process loss at SQLite COMMIT converges on original re-entry."""

    def test_crash_during_commit_reissues_original_operation(self):
        import multiprocessing
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "h-commit.db")
            context = multiprocessing.get_context("spawn")
            process = context.Process(
                target=_crash_during_commit, args=(db,)
            )
            process.start()
            process.join(30)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 86)
            fresh, page, coverages = _recover_after_commit_crash(db)
            self.assertIsInstance(fresh, m.SemanticAnswer)
            self.assertEqual(len(page.items), 1)
            self.assertEqual(len(coverages), 1)
            self.assertEqual(len(coverages[0].result_refs), 1)


class CrashRecoveryTest(unittest.TestCase):
    """H §4/R1: a lost continuation (crashed process) converges via
    idempotent re-issue of the original operation — no duplicates."""

    def test_crash_after_commit_converges_without_duplicates(self):
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "h.db")
            structural, evidence, store = _harness()
            store.close()
            store = SqliteSemanticStore(db)
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    structural_provider_config="memory:test",
                    authority_seeds=(),
                ),
                repository_id=REPO,
                structural=structural, evidence=evidence, store=store,
            )
            try:
                continuations = ContinuationStore()
                pending = _suspend(structural, evidence, store, continuations)
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim(),), relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
                # Crash: continuations and store handles are lost.
                del continuations
                store.close()
                store = SqliteSemanticStore(db)
                answer = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(
                            None, "src/seed.py", (), None
                        ),
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(answer, m.SemanticAnswer)
                self.assertEqual(len(answer.content.claims), 1)
                page = store.load_claims(REPO, (_sid(),), (), _bounds())
                self.assertEqual(len(page.items), 1)
            finally:
                store.close()


class QuestionEvidenceUnionTest(unittest.TestCase):
    """H §5/A3: derived ANSWERED question evidence carries admitted
    out-of-task citations with current fingerprints."""

    def test_answered_coverage_includes_admitted_evidence(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = _suspend_for(
                structural, evidence, store, continuations, "src/other.py"
            )
            other_sid = _sid("src/other.py")
            claim = m.CandidateSemanticClaim(
                candidate_key="purpose-other",
                subject=other_sid, kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("Other module", ()),
                evidence=(_ref("src/seed.py"),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "seed module backs the other module",
                ),
            )
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(claim,), relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    proposed_question_coverages=(
                        _answer_current(pending.request),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            bound = pending.request.question
            coverages = store.load_question_coverages(
                REPO, bound.scope_root, (bound.subject,), _bounds()
            )
            match = next(
                cov for cov in coverages if cov.question == bound
            )
            observed = {
                obs.evidence_ref.evidence_id.value: obs.observed_fingerprint
                for obs in match.question_evidence
            }
            self.assertIn("ev-src/seed.py", observed)
            self.assertEqual(
                observed["ev-src/seed.py"],
                fingerprint_content(FILES["src/seed.py"]),
            )
        finally:
            store.close()


class FreshSessionTest(unittest.TestCase):
    """H §6/R6: corrected semantics with provenance survive a fresh
    session on the same durable store."""

    def test_corrected_semantics_retrievable_after_reopen(self):
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            db = str(pathlib.Path(tmp) / "h2.db")
            structural, evidence, store = _harness()
            store.close()
            store = SqliteSemanticStore(db)
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    structural_provider_config="memory:test",
                    authority_seeds=(),
                ),
                repository_id=REPO,
                structural=structural, evidence=evidence, store=store,
            )
            try:
                continuations = ContinuationStore()
                pending = _suspend(structural, evidence, store, continuations)
                original_scope = pending.request.question
                first = ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim("Sorts seeds"),),
                        relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            _answer_current(pending.request),
                        ),
                        candidate_withdrawals=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
                old_id = first.content.claims[0].claim_id
                challenged = ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(
                            None, "src/seed.py", (), None
                        ),
                        bounds=_bounds(),
                        stale_only=False,
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
                seed_ref = challenged.request.evidence_units[0].evidence_ref
                ops.submit_interpretation(
                    challenged.continuation,
                    m.SemanticInterpretationResult(
                        claims=(_purpose_claim("Sorts seeds reliably"),),
                        relationships=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            m.InterpretationCoverage(
                                subjects=(_sid(),),
                                question_slice=(
                                    original_scope.question_slice
                                ),
                                evidence_scope=m.EvidenceScope(
                                    paths=(), evidence_refs=()
                                ),
                                declared_complete=True,
                                question=original_scope,
                                disposition=(
                                    m.SemanticQuestionDisposition.ANSWERED
                                ),
                                result_refs=(),
                                resolution_requirements=(),
                                disposition_basis="corrected reading",
                                question_evidence=(),
                            ),
                        ),
                        candidate_withdrawals=(
                            m.CandidateSemanticWithdrawal(
                                target=m.ClaimRef(id=old_id),
                                basis=m.SemanticBasis(
                                    m.DerivationKind
                                    .SEMANTIC_INTERPRETATION,
                                    "purpose disproven by inspection",
                                ),
                                evidence=(seed_ref,),
                            ),
                        ),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
                store.close()
                store = SqliteSemanticStore(db)
                fresh = ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id=REPO,
                        target=m.SubjectSelector(
                            None, "src/seed.py", (), None
                        ),
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(fresh, m.SemanticAnswer)
                self.assertEqual(
                    fresh.content.claims[0].value.summary,
                    "Sorts seeds reliably",
                )
                deps = store.load_evidence_dependencies(
                    REPO, (m.ClaimRef(id=fresh.content.claims[0].claim_id),)
                )
                self.assertEqual(len(deps), 1)
                self.assertEqual(deps[0].evidence_ref.locator, "src/seed.py")
                self.assertEqual(
                    deps[0].observed_fingerprint,
                    fingerprint_content(FILES["src/seed.py"]),
                )
            finally:
                store.close()


class DocumentMappingTest(unittest.TestCase):
    """Workflow-issues §5: documentation members with no indexed subject
    map to real admitted areas, never to a synthetic fallback."""

    DOC_FILES = {
        "src/app.py": "APP = 1\n",
        "docs/contract.md": "# Contract\n",
        "docs/notes.md": "# Notes\n",
    }

    def _doc_harness(self):
        files = dict(self.DOC_FILES)
        structural = InMemoryStructuralSource(
            REPO,
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            (
                InMemorySubject(
                    "src/app.py", m.SubjectKind.COMPONENT, "app.py"
                ),
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

    def _doc_area(self):
        return m.SubjectId(
            repository_id=REPO, subject_kind=m.SubjectKind.DOCUMENT,
            canonical_locator="docs/contract.md",
        )

    def _doc_question(self):
        area = self._doc_area()
        return m.SemanticQuestionScope(
            scope_root=area, subject=area,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="contract purpose",
            materiality_basis="mapping admits contract",
        )

    def _doc_scope(self):
        return m.EvidenceScope(
            paths=(
                "src/app.py", "docs/contract.md", "docs/notes.md",
            ),
            evidence_refs=(),
        )

    def _start_doc_campaign(self, structural, evidence, store,
                            continuations):
        pending = ops.initialize_target(
            ops.SemanticInitializeTargetRequest(
                repository_id=REPO, target=self._doc_scope(),
                objective="document mapping probe", bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(pending, PendingInterpretation)
        return pending

    def _map_current_item(self, structural, evidence, store,
                          continuations, pending):
        area = self._doc_area()
        item = pending.request.target_inventory_items[0]
        loc = item.evidence_ref.locator
        if loc == "docs/contract.md":
            result = m.SemanticInterpretationResult(
                claims=(), relationships=(),
                candidate_subjects=(
                    m.CandidateSubject(
                        provisional_locator="docs/contract.md",
                        kind=m.SubjectKind.DOCUMENT,
                        display_name="contract",
                        evidence=(item.evidence_ref,),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION,
                            "contract readme is a coherent area",
                        ),
                    ),
                ),
                candidate_conflicts=(),
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(area,),
                        question_slice="contract purpose",
                        evidence_scope=m.EvidenceScope(
                            paths=(), evidence_refs=()
                        ),
                        declared_complete=False,
                        question=self._doc_question(),
                        disposition=(
                            m.SemanticQuestionDisposition.PENDING
                        ),
                        result_refs=(),
                        resolution_requirements=(),
                        disposition_basis="admitted on mapping",
                        question_evidence=(),
                    ),
                ),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.CandidateTargetInventoryAccount(
                         evidence_id=item.evidence_ref.evidence_id,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(),
            )
        elif loc == "docs/notes.md":
            result = m.SemanticInterpretationResult(
                claims=(), relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.CandidateTargetInventoryAccount(
                         evidence_id=item.evidence_ref.evidence_id,
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=(
                                    m.ResolutionKind
                                    .MISSING_SEMANTIC_COVERAGE
                                ),
                                subject_or_claim=None,
                                description="notes need owner triage",
                                supporting_context=(),
                            ),
                        ),
                    ),
                ),
                proposed_target_questions=(),
            )
        else:
            result = m.SemanticInterpretationResult(
                claims=(), relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.CandidateTargetInventoryAccount(
                         evidence_id=item.evidence_ref.evidence_id,
                        assigned_area_subjects=(area,),
                    ),
                ),
                proposed_target_questions=(),
            )
        from dataclasses import replace as _dc_replace

        if result.proposed_target_inventory_accounting:
            # S5/J-6: one unit accounts for the whole bound batch.
            result = _dc_replace(
                result,
                proposed_target_inventory_accounting=_fill_batch(
                    pending, result.proposed_target_inventory_accounting
                ),
            )
        return ops.submit_interpretation(
            pending.continuation, result,
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )

    def _drain_doc_campaign(self, structural, evidence, store,
                            continuations):
        pending = self._start_doc_campaign(
            structural, evidence, store, continuations
        )
        for _ in range(6):
            self.assertIsInstance(pending, PendingInterpretation)
            if pending.request.question is not None:
                return pending
            pending = self._map_current_item(
                structural, evidence, store, continuations, pending
            )
        self.fail("mapping frontier did not reach a semantic question")

    def _synthetic_sid(self, locator):
        return m.SubjectId(
            repository_id=REPO, subject_kind=m.SubjectKind.OTHER,
            canonical_locator=locator,
        )

    def test_partial_mapping_batch_named_and_atomic(self):
        """SPMCP-04/H: a partial batch rejects by EvidenceId, writes no
        accounting, and leaves the continuation live for correction."""
        structural, evidence, store = self._doc_harness()
        try:
            continuations = ContinuationStore()
            pending = self._start_doc_campaign(
                structural, evidence, store, continuations
            )
            items = pending.request.target_inventory_items
            self.assertEqual(len(items), 3)
            partial = m.SemanticInterpretationResult(
                claims=(), relationships=(),
                candidate_subjects=(), candidate_conflicts=(),
                proposed_question_coverages=(),
                candidate_withdrawals=(),
                proposed_target_inventory_accounting=(
                    m.CandidateTargetInventoryAccount(
                        evidence_id=items[0].evidence_ref.evidence_id,
                        resolution_requirements=(
                            m.ResolutionRequirement(
                                kind=(
                                    m.ResolutionKind
                                    .MISSING_SEMANTIC_COVERAGE
                                ),
                                subject_or_claim=None,
                                description="not examined in this test",
                                supporting_context=(),
                            ),
                        ),
                    ),
                ),
                proposed_target_questions=(),
            )
            with self.assertRaises(InterpretationUnitRejected) as ctx:
                ops.submit_interpretation(
                    pending.continuation, partial,
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            message = str(ctx.exception)
            for item in items[1:]:
                self.assertIn(item.evidence_ref.evidence_id.value, message)
            self.assertIn(
                "bound mapping item has no accounting candidate", message
            )
            assoc = store.load_target_association(
                REPO, pending.request.target_id
            )
            assert assoc is not None
            self.assertEqual(assoc.inventory_accounting, ())
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()

    def test_subject_null_document_admits_real_area(self):
        structural, evidence, store = self._doc_harness()
        try:
            continuations = ContinuationStore()
            members = ops.locate(
                ops.SemanticStructuralLocateRequest(
                    repository_id=REPO,
                    mode=m.StructuralLocateMode.TARGET_MEMBERS,
                    bounds=_bounds(),
                    target=m.EvidenceScope(
                        paths=("docs",), evidence_refs=()
                    ),
                ),
                structural=structural, evidence=evidence, store=store,
            )
            by_loc = {
                entry.evidence_ref.locator: entry
                for entry in members.entries
            }
            self.assertIsNone(by_loc["docs/contract.md"].subject)
            pending = self._drain_doc_campaign(
                structural, evidence, store, continuations
            )
            self.assertIsNotNone(pending.request.question)
            self.assertEqual(
                pending.request.question.scope_root, self._doc_area()
            )
            assoc = store.load_target_association(
                REPO, pending.request.target_id
            )
            self.assertIn(self._doc_area(), assoc.area_subjects)
            self.assertFalse(
                store.load_subjects(
                    REPO, (self._synthetic_sid("docs/contract.md"),)
                )
            )
            self.assertFalse(
                store.load_subjects(
                    REPO, (self._synthetic_sid("cdg-workflow-area"),)
                )
            )
        finally:
            store.close()

    def test_subject_null_mapping_task_explains_null(self):
        from span.service.interpretation import (
            prepare_interpretation_task,
        )

        structural, evidence, store = self._doc_harness()
        try:
            state = structural.repository_state(REPO)
            anchor = m.Subject(
                subject_id=self._synthetic_sid("docs/contract.md"),
                display_name="docs/contract.md",
                declared_kind="docs/contract.md",
            )
            item = m.EvidenceInventoryItem(
                evidence_ref=m.EvidenceRef(
                    evidence_id=m.EvidenceId(
                        "ev-docs/contract.md"
                    ),
                    repository_id=REPO,
                    source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                    locator="docs/contract.md",
                    revision_or_fingerprint=fingerprint_content(
                        self.DOC_FILES["docs/contract.md"]
                    ),
                    section_or_span=None,
                ),
                content_fingerprint=fingerprint_content(
                    self.DOC_FILES["docs/contract.md"]
                ),
            )
            task = prepare_interpretation_task(
                REPO, anchor,
                structural=structural, evidence=evidence,
                bounds=_bounds(), state=state, store=store,
                target_scope=m.EvidenceScope(
                    paths=("docs/contract.md",), evidence_refs=()
                ),
                target_inventory_items=(item,), mapping_mode=True,
            )
            text = " ".join(
                task.request.brief.scope_boundaries
                + task.request.brief.submission_rules
            )
            self.assertIn("subject: null", text)
            self.assertIn("service-owned PENDING CQ-01 seed", text)
            self.assertNotIn(
                "requires at least one target question", text
            )
        finally:
            store.close()


def _fill_batch(pending, accounts):
    """S5/J-6 test helper: account for every bound inventory item."""
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


if __name__ == "__main__":
    unittest.main()
