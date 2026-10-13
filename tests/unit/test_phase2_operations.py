"""Phase 2 operation tests (plan §7 exchange, §6 discovery, §8 reuse,
§9 refresh, §11.1 init, §11.12 submit).

All deterministic; the FixtureAgent stands in for the invoking agent.
"""

import datetime
import pathlib
import unittest

from span.core import model as m
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service as ops
from span.service.discovery import _inventory_snapshot, _read_units_within_bytes
from span.service.resolution import _resolve_query_subject
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


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose-main",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        value=m.PurposeValue("does things", ()),
        evidence=(_ref("README.md"), _ref("src/main.py")),
        candidate_authority=m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=_ref("README.md"),
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span="Does things",
                status_section="README.md",
                applicability_section=None,
            ),
        ),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the service purpose",
        ),
    )


def _agent(complete_questions=False):
    return FixtureAgent(
        {"src/main.py": FixtureCandidates((_candidate(),), ())},
        complete_questions=complete_questions,
    )


def _state():
    return m.RepositoryState(
        repository_id="repo-1", revision_id="r1", dirty=False,
        state_fingerprint="fp",
        observed_at=datetime.datetime(
            2026, 1, 1, tzinfo=datetime.timezone.utc
        ),
    )


def _bare_request():
    return m.SemanticInterpretationRequest(
        repository_id="repo-1",
        subjects=(m.Subject(_sid(), "main", None),),
        evidence_units=(),
        structural_observations=(),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(_sid(),),
        brief=m.TaskBrief(),
        bounds=_bounds(),
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


def _explain_request():
    return ops.SemanticExplainRequest(
        repository_id="repo-1",
        target=m.SubjectSelector(None, "src/main.py", (), None),
        bounds=_bounds(),
    )


def _run_exchange(explain_request, structural, evidence, store, agent,
                  seeds=(), continuations=None):
    """Drive one full suspend→perform→submit cycle; returns the answer."""
    continuations = continuations or ContinuationStore()
    pending = ops.explain(
        explain_request, structural=structural, evidence=evidence,
        store=store, continuations=continuations, authority_seeds=seeds,
    )
    assert isinstance(pending, PendingInterpretation), type(pending)
    result = agent.perform(pending.request)
    return ops.submit_interpretation(
        pending.continuation, result, structural=structural,
        evidence=evidence, store=store, continuations=continuations,
    )


class ExchangeTest(unittest.TestCase):
    def test_suspend_then_submit_answers(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertTrue(pending.continuation)
            self.assertEqual(len(continuations), 1)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
            self.assertEqual(len(continuations), 0)
        finally:
            store.close()

    def test_unknown_continuation_unavailable(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    "cont-999",
                    m.SemanticInterpretationResult((), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_expired_continuation_abandoned(self):
        now = [datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]
        store_harness = _harness()
        structural, evidence, store = store_harness
        try:
            continuations = ContinuationStore(
                ttl_seconds=60, now=lambda: now[0]
            )
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            now[0] += datetime.timedelta(hours=1)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation,
                    _agent().perform(pending.request),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_reissue_once_then_abandoned(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            self.assertIsInstance(reissued, PendingInterpretation)
            self.assertNotEqual(
                reissued.continuation, pending.continuation
            )
            self.assertEqual(
                reissued.request, pending.request
            )
            with self.assertRaises(InterpretationIngressFailure):
                ops.reissue_interpretation(
                    reissued.continuation, continuations=continuations
                )
            with self.assertRaises(InterpretationUnavailable):
                ops.reissue_interpretation(
                    "cont-999", continuations=continuations
                )
        finally:
            store.close()

    def test_reissued_continuation_submits_normally(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            reissued = ops.reissue_interpretation(
                pending.continuation, continuations=continuations
            )
            answer = ops.submit_interpretation(
                reissued.continuation, _agent().perform(reissued.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(answer.content.claims), 1)
        finally:
            store.close()

    def test_naive_clock_abandons(self):
        from span.shell.agent_exchange.continuations import SuspendedOperation

        naive = ContinuationStore(
            now=lambda: datetime.datetime(2026, 1, 1)
        )
        token = naive.pend(
            SuspendedOperation(
                op="explain", repository_id="repo-1",
                subject=m.Subject(_sid(), "main", None),
                request=_bare_request(),
                bounds=_bounds(),
                state=_state(),
            )
        )
        self.assertIsNone(naive.claim(token))

    def test_validation_failure_rejects_without_reissue(self):
        """Addendum H §4: validation rejection retains the live
        continuation (no reissue); a corrected resubmission under the
        same continuation then persists exactly once."""
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            pending = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            bad = m.CandidateSemanticClaim(
                subject=_sid(), kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("ghost", ()),
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id="repo-1",
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION
                ),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation,
                    m.SemanticInterpretationResult((bad,), (), (), ()),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            # Continuation retained; nothing persisted.
            self.assertEqual(len(continuations), 1)
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
            # Corrected resubmission under the same continuation persists.
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertEqual(len(continuations), 0)
            with self.assertRaises(InterpretationUnavailable):
                ops.submit_interpretation(
                    pending.continuation, _agent().perform(pending.request),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_submitted_overflow_rejected(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            request = ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(max_candidate_claims=1),
            )
            pending = ops.explain(
                request, structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            overflow = m.SemanticInterpretationResult(
                tuple(
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
                        value=m.PurposeValue(f"s-{n}", ()),
                        evidence=(_ref("README.md"),),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    )
                    for n in range(3)
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, overflow,
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()


class DiscoveryTest(unittest.TestCase):
    def test_discovery_finds_identity_anchored_evidence(self):
        structural, evidence, store = _harness()
        try:
            subject = m.Subject(_sid(), "main", None)
            state = structural.repository_state("repo-1")
            selection = ops.discover_evidence(
                "repo-1", subject, structural=structural, evidence=evidence,
                bounds=_bounds(), state=state,
                authority_seeds=(_ref("README.md"),),
            )
            locators = {r.locator for r in selection.selected_refs}
            self.assertTrue({"README.md", "src/main.py"} <= locators)
        finally:
            store.close()


class ReuseTest(unittest.TestCase):
    def test_second_query_answers_without_suspension(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            seeds = (_ref("README.md"),)
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(complete_questions=True), seeds, continuations,
            )
            second = ops.explain(
                _explain_request(), structural=structural, evidence=evidence,
                store=store, continuations=continuations,
                authority_seeds=seeds,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(
                [c.claim_id for c in answer.content.claims],
                [c.claim_id for c in second.content.claims],
            )
        finally:
            store.close()


class RefreshExchangeTest(unittest.TestCase):
    def _indexed(self, continuations=None):
        structural, evidence, store = _harness()
        continuations = continuations or ContinuationStore()
        answer = _run_exchange(
            _explain_request(), structural, evidence, store,
            _agent(), (_ref("README.md"),), continuations,
        )
        return structural, evidence, store, continuations, answer

    def test_nothing_stale_answers_directly(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            observed = fingerprint_content(FILES["src/main.py"])
            # G-15: drain admitted pendings first (refresh now resumes
            # them in order); the all-clear path must then answer
            # directly with nothing outstanding.
            for _ in range(4):
                pending = [
                    cov for cov in store.load_all_question_coverages(
                        "repo-1", None, (_sid(),),
                    )
                    if cov.disposition
                    is m.SemanticQuestionDisposition.PENDING
                    and cov.question is not None
                ]
                if not pending:
                    break
                unit = ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id="repo-1",
                        target=m.SubjectSelector(
                            None, "src/main.py", (), None,
                        ),
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                    authority_seeds=(_ref("README.md"),),
                )
                self.assertIsInstance(unit, PendingInterpretation)
                ops.submit_interpretation(
                    unit.continuation,
                    m.SemanticInterpretationResult(
                        claims=(), relationships=(),
                        governing_source_refs=(), diagnostics=(),
                        candidate_subjects=(), candidate_conflicts=(),
                        proposed_question_coverages=(
                            m.InterpretationCoverage(
                                subjects=(unit.request.question.subject,),
                                question_slice=(
                                    unit.request.question.question_slice
                                ),
                                evidence_scope=m.EvidenceScope(),
                                declared_complete=False,
                                question=unit.request.question,
                                disposition=(
                                    m.SemanticQuestionDisposition
                                    .NOT_APPLICABLE
                                ),
                                result_refs=(), resolution_requirements=(),
                                disposition_basis="drain test",
                                question_evidence=(
                                    m.QuestionEvidenceObservation(
                                        evidence_ref=_ref("src/main.py"),
                                        observed_fingerprint=observed,
                                    ),
                                )),
                        ),
                        candidate_withdrawals=(),
                        proposed_target_inventory_accounting=(),
                        proposed_target_questions=(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
            answer = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            self.assertTrue(answer.content.freshness_items)
        finally:
            store.close()

    def test_stale_suspends_then_resumes_current(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation, _agent().perform(pending.request),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            content = answer.content
            self.assertIsInstance(content, m.StatusContent)
            self.assertTrue(content.changed_dependencies)
            self.assertEqual(
                content.refresh_scope,
                m.EvidenceScope(paths=("src/main.py",), evidence_refs=()),
            )
        finally:
            store.close()

    def test_failed_unit_preserved_as_stale(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            changed = dict(FILES)
            changed["src/main.py"] = "VALUE = 2\n"
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            pending = ops.refresh(
                ops.SemanticRefreshRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence_v2, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            bad = m.SemanticInterpretationResult(
                (
                    m.CandidateSemanticClaim(
                        subject=_sid(), kind=m.ClaimKind.PURPOSE,
                        value=m.PurposeValue("ghost", ()),
                        evidence=(
                            m.EvidenceRef(
                                evidence_id=m.EvidenceId("ev-ghost"),
                                repository_id="repo-1",
                                source_kind=(
                                    m.EvidenceSourceKind.SOURCE_CODE
                                ),
                                locator="ghost.py",
                            ),
                        ),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION
                        ),
                    ),
                ),
                (), (), (),
            )
            from span.core.validation import InterpretationUnitRejected

            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, bad,
                    structural=structural, evidence=evidence_v2, store=store,
                    continuations=continuations,
                )
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertTrue(page.items)
        finally:
            store.close()

    def test_none_target_rejected(self):
        structural, evidence, store, continuations, _ = self._indexed()
        try:
            with self.assertRaises(ops.RefreshScopeError):
                ops.refresh(
                    ops.SemanticRefreshRequest(
                        repository_id="repo-1", target=None, bounds=_bounds()
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=continuations,
                )
        finally:
            store.close()

    def test_dirty_tree_uses_content_fingerprints(self):
        files = dict(FILES)
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            SUBJECTS,
            revision="r-dirty",
            dirty=True,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
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
        try:
            continuations = ContinuationStore()
            answer = _run_exchange(
                _explain_request(), structural, evidence, store,
                _agent(), (_ref("README.md"),), continuations,
            )
            for claim in answer.content.claims:
                self.assertIs(
                    claim.freshness.state, m.FreshnessState.CURRENT
                )
        finally:
            store.close()


class InitializeTest(unittest.TestCase):
    def test_init_returns_ready_without_interpretation(self):
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                    authority_seeds=(_ref("README.md"),),
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
            )
            self.assertEqual(result.repository_id, "repo-1")
            self.assertIs(
                result.readiness, m.RepositoryReadiness.READY
            )
            self.assertEqual(result.structural_source_status, "ready")
            self.assertTrue(
                result.evidence_inventory_status.startswith("ready:")
            )
            self.assertTrue(
                result.semantic_store_status.startswith("ready:schema-")
            )
            self.assertEqual(result.warnings, ())
            page = store.load_claims("repo-1", (_sid(),), (), _bounds())
            self.assertEqual(page.items, ())
        finally:
            store.close()

    def test_init_signature_has_no_interpretation_input(self):
        import inspect

        params = inspect.signature(ops.initialize_repository).parameters
        self.assertNotIn("interpreter", params)
        self.assertNotIn("agent", params)
        fields = (
            ops.SemanticInitializeRepositoryRequest.__dataclass_fields__
        )
        self.assertNotIn("semantic_provider_config", fields)

    def test_init_rejects_empty_locator(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(ValueError):
                ops.initialize_repository(
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator="",
                        structural_provider_config="x",
                    ),
                    repository_id="repo-1",
                    structural=structural,
                    evidence=evidence,
                    store=store,
                )
        finally:
            store.close()

    def test_init_ready_despite_truncation(self):
        """Bounded inventory never degrades operational readiness.

        Plan §4.8/I-31 (Q34): readiness answers whether the repository
        can service operations. Truncation is boundedness, reported in
        evidence_inventory_status + warnings — consistent with the
        HOOK_FAST path, which reports READY once initialized.
        """
        structural, evidence, store = _harness()
        try:
            result = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="/tmp/svc",
                    structural_provider_config="memory:spec",
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=_bounds(max_evidence_units=1),
            )
            self.assertIs(
                result.readiness, m.RepositoryReadiness.READY
            )
            self.assertTrue(result.warnings)
            self.assertTrue(
                result.evidence_inventory_status.startswith(
                    "degraded:truncated-at-"
                )
            )
        finally:
            store.close()


class InventorySnapshotTest(unittest.TestCase):
    """Membership-only snapshots match the paged inventory walk.

    `_inventory_snapshot` must produce the identical membership
    fingerprint as paging through `inventory_evidence`, while hashing
    only requested seed locators (§8.5/MI-07 unchanged, one metadata
    walk instead of one full re-hash per page).
    """

    def _paged_ids(self, evidence, bounds):
        ids = []
        token = None
        while True:
            page = evidence.inventory_evidence(
                "repo-1", m.EvidenceScope(paths=(), evidence_refs=()),
                bounds, token,
            )
            ids.extend(
                item.evidence_ref.evidence_id.value
                for item in page.items
            )
            token = page.bound_info.continuation_token
            if token is None:
                break
        return ids

    def test_fixture_snapshot_matches_paged_walk(self):
        import hashlib

        evidence = FixtureEvidenceSource("repo-1", dict(FILES))
        bounds = _bounds(max_evidence_units=1)
        expected = hashlib.sha256(
            repr(sorted(self._paged_ids(evidence, bounds))).encode()
        ).hexdigest()
        membership, seed_map = _inventory_snapshot(
            "repo-1",
            evidence=evidence,
            seeds=(("README.md", "ev-README.md"),
                   ("nope.md", "ev-nope.md")),
        )
        self.assertEqual(membership, expected)
        self.assertEqual(
            seed_map["ev-README.md"],
            fingerprint_content(FILES["README.md"]),
        )
        self.assertEqual(seed_map["ev-nope.md"], "")

    def test_filesystem_snapshot_matches_paged_walk(self):
        import hashlib
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "a.py").write_text("A = 1\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.md").write_text("# b\n", encoding="utf-8")
            evidence = FilesystemEvidenceSource("repo-1", root)
            bounds = _bounds(max_evidence_units=1)
            expected = hashlib.sha256(
                repr(sorted(self._paged_ids(evidence, bounds))).encode()
            ).hexdigest()
            membership, seed_map = _inventory_snapshot(
                "repo-1",
                evidence=evidence,
                seeds=(("a.py", "ev-a.py"),),
            )
            self.assertEqual(membership, expected)
            self.assertTrue(seed_map["ev-a.py"])


class BoundedEvidenceReadTest(unittest.TestCase):
    """Byte-budget reads trim the selection instead of failing it.

    Discovery counts units; §8.4 bytes are enforced by keeping refs
    that fit (§6.2 bounded set) — never by widening bounds, never by
    failing a unit the agent could have answered partially.
    """

    def _ref(self, locator):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{locator}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, locator,
        )

    def test_keeps_fitting_prefix(self):
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "small.py").write_text("A = 1\n", encoding="utf-8")
            (root / "big.py").write_text(
                "X = '" + "y" * 200 + "'\n", encoding="utf-8"
            )
            evidence = FilesystemEvidenceSource("repo-1", root)
            units = _read_units_within_bytes(
                evidence,
                (self._ref("small.py"), self._ref("big.py")),
                _bounds(max_evidence_units=24, max_evidence_bytes=100),
            )
            self.assertEqual(
                [u.evidence_ref.locator for u in units], ["small.py"]
            )

    def test_fail_closed_when_nothing_fits(self):
        import tempfile

        from span.shell.filesystem_evidence import (
            FilesystemEvidenceSource,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "big.py").write_text(
                "X = '" + "y" * 200 + "'\n", encoding="utf-8"
            )
            evidence = FilesystemEvidenceSource("repo-1", root)
            with self.assertRaises(ValueError):
                _read_units_within_bytes(
                    evidence, (self._ref("big.py"),),
                    _bounds(max_evidence_units=24, max_evidence_bytes=10),
                )


class StoreResolutionTest(unittest.TestCase):
    """Addendum A, F1: registered subjects resolve at query time.

    Structural resolution stays first; an exact identity the index
    cannot resolve falls back to the stored record. Ambiguity is never
    overridden and name-only queries never reach the store.
    """

    def _empty_structural(self):
        return InMemoryStructuralSource("repo-1", (), ())

    def _store_with_workflow(self):
        from span.shell.sqlite_store import SqliteSemanticStore

        store = SqliteSemanticStore(":memory:")
        sid = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.SUBSYSTEM,
            canonical_locator="workflows/tta",
        )
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=(m.Subject(sid, "tta workflow", None),),
            )
        )
        return store, sid

    def test_store_subject_resolves_by_exact_id(self):
        structural = self._empty_structural()
        store, sid = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(sid, None, (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED
            )
            candidate = resolution.candidates[0]
            self.assertEqual(
                candidate.subject.subject_id.canonical_locator,
                "workflows/tta",
            )
            self.assertIs(
                candidate.rank_basis, m.CandidateRankBasis.EXACT_LOCATOR
            )
        finally:
            store.close()

    def test_store_subject_served_by_explain(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        structural = self._empty_structural()
        evidence = FixtureEvidenceSource("repo-1", {})
        store, sid = self._store_with_workflow()
        try:
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
            from span.shell.agent_exchange.continuations import (
                ContinuationStore,
            )

            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(sid, None, (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            # Reaches the subject (suspends for interpretation) instead
            # of answering NOT_FOUND.
            from span.ports.interpretation import PendingInterpretation

            self.assertIsInstance(pending, PendingInterpretation)
        finally:
            store.close()

    def test_ambiguous_identity_never_overridden(self):
        structural = InMemoryStructuralSource(
            "repo-1",
            (InMemoryFile("a.py", "x\n"), InMemoryFile("b.py", "x\n")),
            (
                InMemorySubject("a.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
                InMemorySubject("b.py#dup", m.SubjectKind.CODE_SYMBOL, "dup"),
            ),
        )
        store, _ = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "dup", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.AMBIGUOUS
            )
        finally:
            store.close()

    def test_name_only_query_never_reaches_store(self):
        structural = self._empty_structural()
        store, _ = self._store_with_workflow()
        try:
            resolution = _resolve_query_subject(
                "repo-1",
                m.SubjectSelector(None, "workflows/tta", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(
                resolution.ambiguity, m.ResolutionAmbiguity.NOT_FOUND
            )
        finally:
            store.close()


class CrossUnitCitationTest(unittest.TestCase):
    """Addendum H §5: citations resolve against the canonical provider.

    A later unit may cite evidence established by an earlier unit;
    changed bytes admit the current observation (old rows keep old
    fingerprints and go stale through existing freshness) and unknown
    ids stay unknown.
    """

    FILES2 = {"a.py": "ALPHA = 1\n", "b.py": "BETA = 2\n"}

    def _harness2(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        files = dict(self.FILES2)
        subjects = (
            InMemorySubject("a.py", m.SubjectKind.COMPONENT, "aaa"),
            InMemorySubject("b.py", m.SubjectKind.COMPONENT, "bbb"),
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            subjects,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
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

    def _ref(self, path, fingerprint):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{path}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, path,
            revision_or_fingerprint=fingerprint,
        )

    def _claim_for(self, locator, ref):
        return m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator=locator,
            ),
            kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue(f"{locator} serves its module", ()),
            evidence=(ref,),
            candidate_authority=None,
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "test"
            ),
        )

    def _submit_for(self, locator, result, structural, evidence, store):
        from span.shell.agent_exchange.continuations import (
            ContinuationStore,
        )

        continuations = ContinuationStore()
        pending = ops.explain(
            ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        from span.ports.interpretation import PendingInterpretation

        self.assertIsInstance(pending, PendingInterpretation)
        return ops.submit_interpretation(
            pending.continuation, result, structural=structural,
            evidence=evidence, store=store,
            continuations=continuations,
        ), pending

    def test_cross_unit_citation_accepted_when_bytes_current(self):
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            first, _ = self._submit_for(
                "a.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "a.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(first, m.SemanticAnswer)
            # Second unit cites a.py although its own task units cover
            # only b.py: established bytes admit the citation.
            second, _ = self._submit_for(
                "b.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "b.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(second.content.claims), 1)
        finally:
            store.close()

    def test_cross_unit_citation_admitted_when_bytes_changed(self):
        """Addendum H §5: changed source bytes admit a new current
        interpretation; the new dependency row carries the current
        fingerprint while the old row keeps its original observation."""
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            self._submit_for(
                "a.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "a.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            evidence._files["a.py"] = "ALPHA = 99\n"
            current_fp = fingerprint_content("ALPHA = 99\n")
            second, _ = self._submit_for(
                "b.py",
                m.SemanticInterpretationResult(
                    claims=(
                        self._claim_for(
                            "b.py",
                            self._ref("a.py", fingerprint_content("ALPHA = 1\n")),
                        ),
                    ),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                ),
                structural, evidence, store,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(second.content.claims), 1)
            persisted_ref = second.content.claims[0].evidence[0]
            self.assertEqual(persisted_ref.evidence_id.value, "ev-a.py")
            self.assertEqual(persisted_ref.locator, "a.py")
            self.assertEqual(
                persisted_ref.revision_or_fingerprint, current_fp
            )
            deps = store.load_evidence_dependencies(
                "repo-1",
                (m.ClaimRef(id=second.content.claims[0].claim_id),),
            )
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0].observed_fingerprint, current_fp)
        finally:
            store.close()

    def test_unknown_evidence_still_rejected(self):
        structural, evidence, store = self._harness2()
        try:
            with self.assertRaises(ops.InterpretationUnitRejected) as cm:
                self._submit_for(
                    "b.py",
                    m.SemanticInterpretationResult(
                        claims=(
                            self._claim_for(
                                "b.py", self._ref("ghost.py", "fp"),
                            ),
                        ),
                        relationships=(),
                        governing_source_refs=(),
                        diagnostics=(),
                        candidate_subjects=(),
                        candidate_conflicts=(),
                    ),
                    structural, evidence, store,
                )
            self.assertIn("ev-ghost.py", str(cm.exception))
        finally:
            store.close()


class SemanticOutcomeTest(unittest.TestCase):
    """Workflow questions get synthesized, served answers (F1+F2 end to end).

    Two per-file claims established in two units, a registered workflow
    subject, then a synthesis claim citing both files' established
    evidence — served back by exact locator with the synthesized content
    intact and trust honestly unestablished (no authority seeds).
    """

    FILES2 = {"a.py": "ALPHA = 1\n", "b.py": "BETA = 2\n"}
    SUMMARY = (
        "Alpha input configured with beta threshold."
    )

    def _harness2(self):
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.sqlite_store import SqliteSemanticStore

        files = dict(self.FILES2)
        subjects = (
            InMemorySubject("a.py", m.SubjectKind.COMPONENT, "aaa"),
            InMemorySubject("b.py", m.SubjectKind.COMPONENT, "bbb"),
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            subjects,
        )
        evidence = FixtureEvidenceSource("repo-1", files)
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

    def _ref(self, path, fingerprint):
        return m.EvidenceRef(
            m.EvidenceId(f"ev-{path}"), "repo-1",
            m.EvidenceSourceKind.SOURCE_CODE, path,
            revision_or_fingerprint=fingerprint,
        )

    def _exchange(
        self, locator, result, structural, evidence, store,
        complete=False,
    ):
        from span.shell.agent_exchange.continuations import (
            ContinuationStore,
        )
        from span.ports.interpretation import PendingInterpretation

        continuations = ContinuationStore()
        pending = ops.explain(
            ops.SemanticExplainRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=continuations,
        )
        self.assertIsInstance(pending, PendingInterpretation)
        if complete:
            # Addendum C C-05 cutover: explicit ANSWERED completion
            # intent for the bound question; the service derives refs.
            question = pending.request.question
            result = m.SemanticInterpretationResult(
                claims=result.claims,
                relationships=result.relationships,
                governing_source_refs=result.governing_source_refs,
                diagnostics=result.diagnostics,
                candidate_subjects=result.candidate_subjects,
                candidate_conflicts=result.candidate_conflicts,
                proposed_question_coverages=(
                    m.InterpretationCoverage(
                        subjects=(question.subject,),
                        question_slice=question.question_slice,
                        evidence_scope=m.EvidenceScope(
                            paths=(), evidence_refs=()
                        ),
                        declared_complete=True,
                        question=question,
                        disposition=(
                            m.SemanticQuestionDisposition.ANSWERED
                        ),
                        result_refs=(),
                        resolution_requirements=(),
                        disposition_basis="test explicit completion",
                        question_evidence=(),
                    ),
                ),
                candidate_withdrawals=result.candidate_withdrawals,
            )
        return ops.submit_interpretation(
            pending.continuation, result, structural=structural,
            evidence=evidence, store=store,
            continuations=continuations,
        )

    def _purpose(self, locator, ref):
        return m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator=locator,
            ),
            kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue(f"{locator} serves its module", ()),
            evidence=(ref,),
            candidate_authority=None,
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "test"
            ),
        )

    def _result(self, claims, subjects=()):
        return m.SemanticInterpretationResult(
            claims=tuple(claims),
            relationships=(),
            governing_source_refs=(),
            diagnostics=(),
            candidate_subjects=tuple(subjects),
            candidate_conflicts=(),
        )

    def test_workflow_synthesis_served_with_content(self):
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store = self._harness2()
        try:
            fp_a = fingerprint_content("ALPHA = 1\n")
            fp_b = fingerprint_content("BETA = 2\n")
            self._exchange(
                "a.py",
                self._result(
                    (self._purpose("a.py", self._ref("a.py", fp_a)),)
                ),
                structural, evidence, store,
                complete=True,
            )
            workflow = m.CandidateSubject(
                provisional_locator="workflows/tta",
                kind=m.SubjectKind.SUBSYSTEM,
                display_name="tta workflow",
                declared_kind=None,
                evidence=(self._ref("b.py", fp_b),),
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "workflow owns both modules",
                ),
            )
            self._exchange(
                "b.py",
                self._result(
                    (self._purpose("b.py", self._ref("b.py", fp_b)),),
                    (workflow,),
                ),
                structural, evidence, store,
                complete=True,
            )
            synthesis = m.CandidateSemanticClaim(
                candidate_key="purpose",
                subject=m.SubjectId(
                    repository_id="repo-1",
                    subject_kind=m.SubjectKind.SUBSYSTEM,
                    canonical_locator="workflows/tta",
                ),
                kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue(self.SUMMARY, ()),
                evidence=(
                    self._ref("a.py", fp_a), self._ref("b.py", fp_b),
                ),
                candidate_authority=None,
                basis=m.SemanticBasis(
                    m.DerivationKind.SEMANTIC_INTERPRETATION,
                    "both module purposes combined",
                ),
            )
            from span.shell.agent_exchange.continuations import (
                ContinuationStore,
            )
            from span.ports.interpretation import PendingInterpretation

            continuations = ContinuationStore()
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        m.SubjectId(
                            repository_id="repo-1",
                            subject_kind=m.SubjectKind.SUBSYSTEM,
                            canonical_locator="workflows/tta",
                        ),
                        None, (), None,
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(synthesis,),
                    relationships=(),
                    governing_source_refs=(),
                    diagnostics=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    proposed_question_coverages=(
                        m.InterpretationCoverage(
                            subjects=(
                                pending.request.question.subject,
                            ),
                            question_slice=(
                                pending.request.question.question_slice
                            ),
                            evidence_scope=m.EvidenceScope(
                                paths=(), evidence_refs=()
                            ),
                            declared_complete=True,
                            question=pending.request.question,
                            disposition=(
                                m.SemanticQuestionDisposition.ANSWERED
                            ),
                            result_refs=(),
                            resolution_requirements=(),
                            disposition_basis="test explicit completion",
                            question_evidence=(),
                        ),
                    ),
                    candidate_withdrawals=(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            (served,) = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        m.SubjectId(
                            repository_id="repo-1",
                            subject_kind=m.SubjectKind.SUBSYSTEM,
                            canonical_locator="workflows/tta",
                        ),
                        None, (), None,
                    ),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            ).content.claims
            self.assertEqual(served.value.summary, self.SUMMARY)
            self.assertEqual(
                {r.locator for r in served.evidence},
                {"a.py", "b.py"},
            )
            self.assertIs(served.trust, m.TrustState.UNRESOLVED)
            self.assertIs(
                served.freshness.state, m.FreshnessState.CURRENT
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
