"""MCP transport tests (plan Phase 4.2–4.5).

Transport only: schema/contract sync, strict ingress, thin dispatch,
the submit union over the wire, and SDK server construction. No
semantic rule may live in transport — the schema-sync test pins the
mechanical projection, and the skill tests pin non-authority.
"""

import dataclasses
import json
import pathlib
import unittest

from span.core import model as m
from span.core import schema as _schema
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.bounds import resolve_bounds
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    McpAdapter,
    ServiceContext,
    _REQUEST_CLASS,
    encode_result,
)
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

try:
    import mcp.server  # noqa: F401

    _HAS_MCP_SDK = True
except Exception:
    _HAS_MCP_SDK = False


def _decision(coverage):
    """Test-only: express an authored coverage as the compact decision."""
    return m.SemanticQuestionDecision(
        disposition=coverage.disposition,
        evidence_scope=coverage.evidence_scope,
        resolution_requirements=coverage.resolution_requirements,
        disposition_basis=coverage.disposition_basis,
    )


REPO = "mcp-svc"

FILES = {
    "README.md": "# mcp-svc\n\nServes tools.\n",
    "src/tools.py": "run = True\n",
}


def _sid():
    return m.SubjectId(
        repository_id=REPO,
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator="src/tools.py",
    )


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=(
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(".md")
            else m.EvidenceSourceKind.SOURCE_CODE
        ),
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid(),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("serves tools", ()),
        evidence=(_ref("README.md"),),
        candidate_authority=m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=_ref("README.md"),
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span="Serves tools",
                status_section="README.md",
                applicability_section=None,
            ),
        ),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "README states the tool purpose",
        ),
    )


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        (InMemorySubject("src/tools.py", m.SubjectKind.COMPONENT, "t"),),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
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
    agent = FixtureAgent({"src/tools.py": FixtureCandidates((_candidate(),), ())})
    adapter = McpAdapter(
        contexts={
            REPO: ServiceContext(
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
                authority_seeds=(),
            )
        }
    )
    return adapter, agent


def _selector_args(locator="src/tools.py"):
    selector = m.SubjectSelector(
        exact_subject_id=None,
        name_or_locator=locator,
        expected_kinds=(),
        retrieval_scope_hint=None,
    )
    return m.to_canonical(selector)


class SchemaSyncTest(unittest.TestCase):
    """Tool schemas stay a mechanical projection of the contracts."""

    def test_eleven_canonical_tools(self):
        self.assertEqual(
            TOOL_NAMES,
            (
                "initialize_repository",
                "initialize_target",
                "explain",
                "impact",
                "trace",
                "authority",
                "status",
                "refresh",
                "submit_interpretation",
                "locate",
                "neighbors",
            ),
        )
        self.assertEqual(set(TOOL_SCHEMAS), set(TOOL_NAMES))

    def test_required_matches_contract(self):
        classes = {
            "explain": ops.SemanticExplainRequest,
            "impact": ops.SemanticImpactRequest,
            "trace": ops.SemanticTraceRequest,
            "authority": ops.SemanticAuthorityRequest,
            "status": ops.SemanticStatusRequest,
            "refresh": ops.SemanticRefreshRequest,
            "locate": ops.SemanticStructuralLocateRequest,
            "neighbors": ops.SemanticStructuralNeighborsRequest,
        }
        for tool, cls in classes.items():
            with self.subTest(tool=tool):
                fields = dataclasses.fields(cls)
                names = {f.name for f in fields}
                # Required dataclass fields except bounds (plan §5.1
                # defaults omitted bounds at the boundary).
                required = {
                    f.name
                    for f in fields
                    if f.default is dataclasses.MISSING
                    and f.default_factory is dataclasses.MISSING
                } - {"bounds"}
                schema = TOOL_SCHEMAS[tool]
                self.assertEqual(set(schema["required"]), required, tool)
                self.assertTrue(set(schema["properties"]) >= names, tool)

    def test_nullable_targets_advertise_null(self):
        # J-8/S6.2: a single-dataclass (or X|None) position forbids the
        # tag; a nullable contract target advertises an explicit null
        # alternative, and a non-null target does not. Refresh's target
        # is required (Addendum L §13): no impossible null is advertised.
        for tool in ("status", "locate"):
            with self.subTest(tool=tool):
                target_schema = TOOL_SCHEMAS[tool]["properties"]["target"]
                alternatives = target_schema.get("anyOf", [])
                self.assertTrue(
                    any(a == {"type": "null"} for a in alternatives),
                    target_schema,
                )
        refresh_schema = TOOL_SCHEMAS["refresh"]["properties"]["target"]
        self.assertFalse(
            any(
                branch == {"type": "null"} for branch in refresh_schema.get("anyOf", [])
            ),
            refresh_schema,
        )
        for tool in (
            "explain",
            "impact",
            "trace",
            "authority",
            "initialize_target",
            "neighbors",
        ):
            with self.subTest(tool=tool):
                target_schema = TOOL_SCHEMAS[tool]["properties"]["target"]
                alternatives = target_schema.get("anyOf", [])
                self.assertFalse(
                    any(a.get("type") == "null" for a in alternatives),
                    target_schema,
                )

    def test_submit_and_init_shapes(self):
        submit = TOOL_SCHEMAS["submit_interpretation"]
        self.assertEqual(
            set(submit["required"]),
            {"continuation", "result", "repository_id"},
        )
        init = TOOL_SCHEMAS["initialize_repository"]
        self.assertEqual(
            set(init["required"]),
            {"repository_locator"},
        )
        self.assertNotIn("structural_provider_config", init["properties"])
        impact = TOOL_SCHEMAS["impact"]
        self.assertNotIn("change_description", impact["required"])
        trace = TOOL_SCHEMAS["trace"]
        self.assertNotIn("relationship_filter", trace["required"])
        self.assertNotIn("boundary_only", trace["required"])


class IngressTest(unittest.TestCase):
    def test_decode_explain(self):
        request = _decode_request(
            "explain",
            {
                "repository_id": REPO,
                "target": _selector_args(),
            },
        )
        self.assertIsInstance(request, ops.SemanticExplainRequest)
        # S6.3: omitted bounds decode to None; the service resolves the
        # default via resolve_bounds() at operation entry.
        self.assertIsNone(request.bounds)
        self.assertEqual(
            resolve_bounds(request.bounds, hook=False),
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
        )

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            _decode_request(
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                    "bogus": 1,
                },
            )

    def test_unknown_enum_rejected(self):
        args = {
            "repository_id": REPO,
            "target": _selector_args(),
            "direction": "SIDEWAYS",
            "relationship_filter": None,
            "boundary_only": False,
        }
        with self.assertRaises(ValueError):
            _decode_request("trace", args)

    def test_missing_required_rejected(self):
        with self.assertRaises(ValueError):
            _decode_request("explain", {"repository_id": REPO})

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ValueError):
            _decode_request("span_nope", {})


class DispatchTest(unittest.TestCase):
    def test_initialize_target_advances_complete_boundary(self):
        adapter, agent = _harness()
        try:
            pending = _dispatch(
                adapter,
                "initialize_target",
                {
                    "repository_id": REPO,
                    "target": m.to_canonical(
                        m.EvidenceScope(paths=("src/tools.py",), evidence_refs=())
                    ),
                    "objective": "Understand the tool boundary and its use.",
                },
            )
            self.assertFalse(pending.is_error)
            envelope = json.loads(pending.content)
            self.assertEqual(envelope["$type"], "PendingInterpretation")
            task = _schema.from_wire(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            wire_brief = envelope["request"]["brief"]
            self.assertNotIn("open_handling", wire_brief)
            self.assertTrue(
                set(m.TASK_BRIEF_SUBMISSION_RULES).isdisjoint(
                    wire_brief.get("submission_rules", [])
                )
            )
            self.assertEqual(task.target_scope.paths, ("src/tools.py",))
            self.assertIn(
                "target path: src/tools.py",
                task.brief.scope_boundaries,
            )
            self.assertIn(
                "Understand the tool boundary",
                task.brief.objective,
            )
            # E-13B mapping task carries TargetId + item with question=None.
            self.assertIsNone(task.question)
            self.assertIsNotNone(task.target_id)
            self.assertIsNotNone(task.target_inventory_items[0])
            assert task.target_inventory_items[0] is not None
            item_ref = task.target_inventory_items[0].evidence_ref
            area = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.OTHER,
                canonical_locator="tools-area",
            )
            map_q = m.SemanticQuestionScope(
                scope_root=area,
                subject=area,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="tools purpose",
                materiality_basis="mapping admits tools",
            )
            map_cov = m.InterpretationCoverage(
                subjects=(area,),
                question_slice="tools purpose",
                evidence_scope=m.EvidenceScope(),
                declared_complete=False,
                question=map_q,
                disposition=m.SemanticQuestionDisposition.PENDING,
                result_refs=(),
                resolution_requirements=(),
                disposition_basis="admitted",
                question_evidence=(),
            )
            answered = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "result": m.to_canonical(
                        m.SemanticInterpretationResult(
                            claims=(),
                            relationships=(),
                            governing_source_refs=(),
                            diagnostics=("mapping",),
                            candidate_subjects=(
                                m.CandidateSubject(
                                    provisional_locator="tools-area",
                                    kind=m.SubjectKind.OTHER,
                                    display_name="tools-area",
                                    declared_kind="tools-area",
                                    evidence=(item_ref,),
                                    basis=m.SemanticBasis(
                                        derivation=m.DerivationKind.SEMANTIC_INTERPRETATION,
                                        summary="mapping admits tools",
                                        input_refs=(item_ref,),
                                    ),
                                ),
                            ),
                            candidate_conflicts=(),
                            proposed_questions=(
                                m.ProposedSemanticQuestion(
                                    map_cov.question, _decision(map_cov)
                                ),
                            ),
                            candidate_withdrawals=(),
                            proposed_target_inventory_accounting=(
                                m.CandidateTargetInventoryAccount(
                                    evidence_id=item_ref.evidence_id,
                                    assigned_area_subjects=(area,),
                                ),
                            ),
                            proposed_target_questions=(),
                        )
                    ),
                    "repository_id": REPO,
                },
            )
            self.assertFalse(answered.is_error)
            answer = json.loads(answered.content)
            # Mapping drained for the single file; semantic PENDING follows.
            self.assertEqual(answer["$type"], "PendingInterpretation")
        finally:
            adapter.contexts[REPO].store.close()

    def test_mapping_batch_rejection_names_evidence_id(self):
        """SPMCP-04: an account outside the bound batch rejects by stable
        EvidenceId over the wire and leaves the continuation usable."""
        adapter, agent = _harness()
        try:
            pending = _dispatch(
                adapter,
                "initialize_target",
                {
                    "repository_id": REPO,
                    "target": m.to_canonical(
                        m.EvidenceScope(paths=("src/tools.py",), evidence_refs=())
                    ),
                    "objective": "Understand the tool boundary and its use.",
                },
            )
            self.assertFalse(pending.is_error)
            envelope = json.loads(pending.content)
            task = _schema.from_wire(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            item_ref = task.target_inventory_items[0].evidence_ref

            def _unresolved(evidence_id):
                return m.CandidateTargetInventoryAccount(
                    evidence_id=evidence_id,
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=(m.ResolutionKind.MISSING_SEMANTIC_COVERAGE),
                            subject_or_claim=None,
                            description="not examined in this test",
                            supporting_context=(),
                        ),
                    ),
                )

            def _submit(account):
                return _dispatch(
                    adapter,
                    "submit_interpretation",
                    {
                        "continuation": envelope["continuation"],
                        "result": m.to_canonical(
                            m.SemanticInterpretationResult(
                                claims=(),
                                relationships=(),
                                governing_source_refs=(),
                                diagnostics=("mapping",),
                                candidate_subjects=(),
                                candidate_conflicts=(),
                                candidate_withdrawals=(),
                                proposed_target_inventory_accounting=(account,),
                                proposed_target_questions=(),
                            )
                        ),
                        "repository_id": REPO,
                    },
                )

            failed = _submit(_unresolved(m.EvidenceId("ev-not-bound")))
            self.assertTrue(failed.is_error)
            payload = json.loads(failed.content)
            self.assertEqual(payload["error"], "validation")
            self.assertIn("ev-not-bound", payload["message"])
            self.assertIn("outside the bound mapping batch", payload["message"])

            corrected = _submit(_unresolved(item_ref.evidence_id))
            self.assertFalse(corrected.is_error)
        finally:
            adapter.contexts[REPO].store.close()

    def test_explain_suspend_then_submit_over_wire(self):
        adapter, agent = _harness()
        try:
            pending = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            self.assertFalse(pending.is_error)
            envelope = json.loads(pending.content)
            self.assertEqual(envelope["$type"], "PendingInterpretation")
            task = _schema.from_wire(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            result = agent.perform(task)
            answered = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "result": m.to_canonical(result),
                    "repository_id": REPO,
                },
            )
            self.assertFalse(answered.is_error)
            answer = json.loads(answered.content)
            self.assertEqual(answer["$type"], "SemanticAnswer")
            self.assertEqual(answer["intent"], "EXPLAIN")
            self.assertTrue(answer["content"]["claims"])
            # Refs resolve inside the answer (I-36 over the wire).
            carried = {c["claim_id"]["value"] for c in answer["content"]["claims"]}
            for conflict in answer["content"]["conflicts"]:
                for side in ("left", "right"):
                    self.assertIn(conflict[side]["id"]["value"], carried)
        finally:
            adapter.contexts[REPO].store.close()

    def test_status_hook_fast_notice_shape(self):
        adapter, _ = _harness()
        try:
            notice = _dispatch(
                adapter,
                "status",
                {
                    "repository_id": REPO,
                    "target": None,
                    "mode": "HOOK_FAST",
                },
            )
            self.assertFalse(notice.is_error)
            body = json.loads(notice.content)
            self.assertEqual(body["$type"], "HookStatusNotice")
        finally:
            adapter.contexts[REPO].store.close()

    def test_status_normal_exposes_repository_coverage_report(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "status",
                {
                    "repository_id": REPO,
                    "target": None,
                    "mode": "NORMAL",
                },
            )
            self.assertFalse(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["$type"], "SemanticAnswer")
            self.assertEqual(body["intent"], "STATUS")
            report = body["content"]["coverage_report"]
            self.assertEqual(report["$type"], "RepositoryCoverageReport")
            self.assertEqual(report["repository"]["persisted_subject_count"], 0)
            self.assertEqual(report["page"]["entries"], [])
            # Derived counts are properties, not wire fields.
            self.assertNotIn("returned_subject_count", report["page"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_unknown_tool_is_typed_error(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(adapter, "span_nope", {})
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unknown_tool")
        finally:
            adapter.contexts[REPO].store.close()

    def test_bad_continuation_is_unavailable(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": "cont-999",
                    "result": m.to_canonical(m.SemanticInterpretationResult()),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unavailable")
        finally:
            adapter.contexts[REPO].store.close()

    def test_unavailable_names_recovery(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": "cont-999",
                    "result": m.to_canonical(m.SemanticInterpretationResult()),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unavailable")
            self.assertIn("Re-run the original operation", body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_validation_names_same_continuation_resubmit(self):
        adapter, _ = _harness()
        try:
            pending = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            continuation = envelope["continuation"]
            result = m.SemanticInterpretationResult(
                claims=(
                    m.CandidateSemanticClaim(
                        candidate_key="stray",
                        subject=m.SubjectId(
                            repository_id=REPO,
                            subject_kind=m.SubjectKind.OTHER,
                            canonical_locator="nope",
                        ),
                        kind=m.ClaimKind.PURPOSE,
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        value=m.PurposeValue("stray", ()),
                        evidence=(_ref("src/tools.py"),),
                        basis=m.SemanticBasis(
                            m.DerivationKind.SEMANTIC_INTERPRETATION,
                            "stray basis",
                        ),
                    ),
                ),
                relationships=(),
                candidate_subjects=(),
                candidate_conflicts=(),
                candidate_withdrawals=(),
            )
            rejected = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": continuation,
                    "result": m.to_canonical(result),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(rejected.is_error)
            body = json.loads(rejected.content)
            self.assertEqual(body["error"], "validation")
            self.assertIn("resubmit using the same continuation", body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_correction_validation_names_exact_question_identity(self):
        """SPMCP-02: a wrong correction question is a validation error
        naming the complete canonical identity, and the same live
        continuation accepts the corrected submission."""
        from span.ports.interpretation import PendingInterpretation

        adapter, _ = _harness()
        context = adapter.contexts[REPO]
        try:
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(
                        exact_subject_id=None,
                        name_or_locator="src/tools.py",
                        expected_kinds=(),
                        retrieval_scope_hint=None,
                    ),
                    bounds=DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
                ),
                structural=context.structural,
                evidence=context.evidence,
                store=context.store,
                continuations=context.continuations,
            )
            self.assertIsInstance(pending, PendingInterpretation)
            original_scope = pending.request.question
            coverage = m.InterpretationCoverage(
                subjects=(original_scope.subject,),
                question_slice=original_scope.question_slice,
                evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
                declared_complete=True,
                question=original_scope,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(),
                resolution_requirements=(),
                disposition_basis="transport correction test",
                question_evidence=(),
            )
            answered = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(_candidate(),),
                    relationships=(),
                    candidate_subjects=(),
                    candidate_conflicts=(),
                    question_decision=_decision(coverage),
                    candidate_withdrawals=(),
                ),
                structural=context.structural,
                evidence=context.evidence,
                store=context.store,
                continuations=context.continuations,
            )
            self.assertIsInstance(answered, m.SemanticAnswer)
            challenged = _dispatch(
                adapter,
                "refresh",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                    "stale_only": False,
                },
            )
            self.assertFalse(challenged.is_error)
            envelope = json.loads(challenged.content)
            wrong = m.SemanticQuestionScope(
                scope_root=original_scope.scope_root,
                subject=original_scope.subject,
                question_class=m.SemanticQuestionClass.CQ_09,
                question_slice=original_scope.question_slice,
                materiality_basis=original_scope.materiality_basis,
            )
            wrong_coverage = m.InterpretationCoverage(
                subjects=(wrong.subject,),
                question_slice=wrong.question_slice,
                evidence_scope=m.EvidenceScope(paths=(), evidence_refs=()),
                declared_complete=True,
                question=wrong,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(),
                resolution_requirements=(),
                disposition_basis="transport correction test",
                question_evidence=(),
            )
            rejected = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "result": m.to_canonical(
                        m.SemanticInterpretationResult(
                            claims=(_candidate(),),
                            relationships=(),
                            candidate_subjects=(),
                            candidate_conflicts=(),
                            proposed_questions=(
                                m.ProposedSemanticQuestion(
                                    wrong, _decision(wrong_coverage)
                                ),
                            ),
                            candidate_withdrawals=(),
                        )
                    ),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(rejected.is_error)
            body = json.loads(rejected.content)
            self.assertEqual(body["error"], "validation")
            self.assertIn(
                "correction question is not an exact persisted "
                "SemanticQuestionScope",
                body["message"],
            )
            self.assertIn(f"scope_root.repository_id={REPO}", body["message"])
            self.assertIn(
                "subject.canonical_locator=src/tools.py",
                body["message"],
            )
            self.assertIn("question_class=CQ_09", body["message"])
        finally:
            context.store.close()

    def test_malformed_submit_preserves_continuation(self):
        """Invalid submissions never consume the continuation (G-04).

        A malformed typed result over MCP fails ingress; the same
        continuation then accepts the corrected result — recovery
        without reissue, without laundering.
        """
        adapter, agent = _harness()
        try:
            pending = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            continuation = envelope["continuation"]
            task = _schema.from_wire(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            good = m.to_canonical(agent.perform(task))
            bad = dict(good)
            bad["claims"] = [
                dict(
                    claim,
                    kind="NOT_A_KIND",
                )
                for claim in bad["claims"]
            ]
            rejected = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": continuation,
                    "result": bad,
                    "repository_id": REPO,
                },
            )
            self.assertTrue(rejected.is_error)
            self.assertEqual(json.loads(rejected.content)["error"], "ingress")
            recovered = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": continuation,
                    "result": good,
                    "repository_id": REPO,
                },
            )
            self.assertFalse(recovered.is_error)
            answer = json.loads(recovered.content)
            self.assertEqual(answer["$type"], "SemanticAnswer")
        finally:
            adapter.contexts[REPO].store.close()

    def test_unknown_repository_is_typed_error(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": "nope",
                    "target": _selector_args(),
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unknown_repository")
            self.assertIn(REPO, body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_page_token_as_continuation_names_both_mechanisms(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": "pg:0",
                    "result": m.to_canonical(m.SemanticInterpretationResult()),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "ingress")
            self.assertIn("page token", body["message"])
            self.assertIn("continuation", body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_continuation_as_page_token_names_both_mechanisms(self):
        adapter, _ = _harness()
        try:
            result = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                    "page_token": "cont-1",
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "ingress")
            self.assertIn("page token", body["message"])
            self.assertIn("continuation", body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_failed_submit_leaves_no_partial_state(self):
        """Validation failure persists nothing (addendum A, F7).

        A unit with one valid and one invalid candidate rejects as a
        whole; the valid candidate must not leak into the store.
        """
        adapter, agent = _harness()
        try:
            pending = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            task = _schema.from_wire(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            good = agent.perform(task)
            bad_claim = dataclasses.replace(
                good.claims[0],
                candidate_key="bad",
                evidence=(
                    m.EvidenceRef(
                        evidence_id=m.EvidenceId("ev-ghost"),
                        repository_id=REPO,
                        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                        locator="ghost.py",
                    ),
                ),
                candidate_authority=None,
            )
            result = m.SemanticInterpretationResult(
                claims=(good.claims[0], bad_claim),
                relationships=(),
                governing_source_refs=(),
                diagnostics=(),
                candidate_subjects=(),
                candidate_conflicts=(),
            )
            rejected = _dispatch(
                adapter,
                "submit_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "result": m.to_canonical(result),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(rejected.is_error)
            body = json.loads(rejected.content)
            self.assertEqual(body["error"], "validation")
            self.assertIn("claims[1]", body["message"])
            store = adapter.contexts[REPO].store
            page = store.load_claims(
                REPO,
                (_sid(),),
                (),
                DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            )
            self.assertEqual(page.items, ())
            self.assertEqual(store.load_subjects(REPO, (_sid(),)), ())
        finally:
            adapter.contexts[REPO].store.close()

    def test_encode_result_is_deterministic(self):
        first = encode_result(m.SemanticInterpretationResult())
        self.assertEqual(first, encode_result(m.SemanticInterpretationResult()))
        json.loads(first)

    def test_graft_edge_population_is_unverified_when_index_predates_head(self):
        import hashlib
        import os
        import pathlib
        import subprocess
        import tempfile

        from span.shell.structural.graft import GraftStructuralSource

        with tempfile.TemporaryDirectory(prefix="span-mcp-graft-") as tmp:
            root = pathlib.Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("import b\n", encoding="utf-8")
            (root / "src" / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
            graph = root / "structural" / REPO / ".graph"
            graph.mkdir(parents=True)
            (root / ".gitignore").write_text("graft/\n", encoding="utf-8")
            wiring = {
                "nodes": [
                    {
                        "id": path,
                        "name": pathlib.Path(path).name,
                        "kind": "file",
                        "path": path,
                        "body_hash": hashlib.sha256(
                            (root / path).read_bytes()
                        ).hexdigest(),
                    }
                    for path in ("src/a.py", "src/b.py")
                ],
                "edges": [
                    {
                        "source": "src/a.py",
                        "target": "src/b.py",
                        "relation": "imports",
                    }
                ],
            }
            (graph / "wiring.json").write_text(json.dumps(wiring), encoding="utf-8")
            subprocess.run(("git", "-C", str(root), "init", "-q"), check=True)
            subprocess.run(("git", "-C", str(root), "add", "-A"), check=True)
            subprocess.run(
                (
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.email=t@t",
                    "-c",
                    "user.name=t",
                    "commit",
                    "-qm",
                    "after-index",
                ),
                check=True,
                env={
                    **os.environ,
                    "GIT_AUTHOR_DATE": "2030-01-01T00:00:00Z",
                    "GIT_COMMITTER_DATE": "2030-01-01T00:00:00Z",
                },
            )
            structural = GraftStructuralSource(
                REPO, root, artifact_dir=root / "structural" / REPO
            )
            evidence = FixtureEvidenceSource(
                REPO,
                {
                    "src/a.py": "import b\n",
                    "src/b.py": "VALUE = 1\n",
                },
            )
            store = SqliteSemanticStore(":memory:")
            try:
                ops.initialize_repository(
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator=str(root),
                        authority_seeds=(),
                    ),
                    repository_id=REPO,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                )
                adapter = McpAdapter()
                adapter.register(
                    REPO,
                    ServiceContext(
                        structural=structural,
                        evidence=evidence,
                        store=store,
                        continuations=ContinuationStore(),
                    ),
                )
                result = _dispatch(
                    adapter,
                    "neighbors",
                    {
                        "repository_id": REPO,
                        "target": _selector_args("src/a.py"),
                        "direction": "DOWNSTREAM",
                        "edge_kinds": [],
                    },
                )
                self.assertFalse(result.is_error)
                body = json.loads(result.content)
                self.assertEqual(body["coverage"], "UNVERIFIED")
                self.assertIn(
                    "repository-population-unverified",
                    body["coverage_detail"],
                )
            finally:
                store.close()

    def test_adapter_is_sdk_free(self):
        import pathlib as _pathlib

        source = (
            _pathlib.Path(__file__).resolve().parents[2]
            / "src"
            / "span"
            / "shell"
            / "mcp.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import mcp", source)
        self.assertNotIn("from mcp", source)
        # Server constructor parses without side effects.
        from span.shell import mcp_server

        args = mcp_server._parse_args(
            ["--data-dir", "/tmp/span-data", "--repo", "/repo"]
        )
        self.assertEqual(str(args.data_dir), "/tmp/span-data")
        self.assertEqual(args.repo, ["/repo"])

    def test_empty_adapter_starts_nothing(self):
        """Startup without --repo provisions nothing (G-03).

        An empty registry answers unknown_repository with no side
        effects: no store files, no index builds, no bootstrap. Only
        explicit --repo provisioning or the init tool (with a
        provisioner) creates repository state.
        """
        import tempfile

        from span.shell.mcp import McpAdapter

        with tempfile.TemporaryDirectory() as tmp:
            adapter = McpAdapter()
            result = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": "ghost",
                    "target": _selector_args(),
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unknown_repository")
            init = _dispatch(
                adapter,
                "initialize_repository",
                {
                    "repository_locator": "/x",
                },
            )
            self.assertTrue(init.is_error)
            self.assertEqual(json.loads(init.content)["error"], "unavailable")
            self.assertEqual(list(pathlib.Path(tmp).iterdir()), [])


class ListTimeDiscoveryTest(unittest.TestCase):
    """Addendum H §7/R5: `tools/list` exposes registered canonical IDs
    pre-call; static descriptions stay untouched (SDK-independent)."""

    def test_list_tools_carries_registered_ids(self):
        from span.shell import mcp_server
        from span.shell.mcp import TOOL_DESCRIPTIONS

        adapter, _ = _harness()
        try:
            listed = mcp_server.handle_list_tools(adapter)
            by_name = {spec["name"]: spec["description"] for spec in listed}
            for name in (
                "initialize_target",
                "explain",
                "impact",
                "trace",
                "authority",
                "status",
                "refresh",
                "submit_interpretation",
                "locate",
                "neighbors",
            ):
                self.assertIn(REPO, by_name[name])
            self.assertNotIn(REPO, by_name["initialize_repository"])
            self.assertNotIn(REPO, TOOL_DESCRIPTIONS["explain"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_list_tools_empty_registry(self):
        from span.shell import mcp_server

        listed = mcp_server.handle_list_tools(McpAdapter())
        by_name = {spec["name"]: spec["description"] for spec in listed}
        self.assertIn("No repositories registered yet", by_name["explain"])


@unittest.skipUnless(_HAS_MCP_SDK, "MCP SDK unavailable")
class ServerWiringTest(unittest.TestCase):
    def test_build_server_registers_eleven_tools(self):
        from span.shell import mcp_server

        adapter, _ = _harness()
        try:
            listed = mcp_server.handle_list_tools(adapter)
            self.assertEqual(len(listed), 11)
            self.assertEqual([spec["name"] for spec in listed], list(TOOL_NAMES))
            for spec in listed:
                self.assertEqual(
                    set(spec["inputSchema"]["required"]),
                    set(TOOL_SCHEMAS[spec["name"]]["required"]),
                )
            server = mcp_server.build_server(adapter)
            self.assertEqual(server.name, "span")
        finally:
            adapter.contexts[REPO].store.close()

    def test_list_tools_handler_returns_wire_serializable_result(self):
        """tools/list must survive SDK runner serialization (wire bug).

        The runner rejects raw lists; the handler must return a
        BaseModel/dict result or every host fails tool discovery.
        """
        import asyncio

        import mcp.types as _types

        from span.shell import mcp_server

        adapter, _ = _harness()
        try:
            server = mcp_server.build_server(adapter)
            entry = server.get_request_handler("tools/list")
            assert entry is not None
            result = asyncio.run(entry.handler(None, _types.PaginatedRequestParams()))
            self.assertIsInstance(result, _types.ListToolsResult)
            self.assertEqual(len(result.tools), 11)
            self.assertTrue(all(tool.output_schema for tool in result.tools))
            json.loads(result.model_dump_json(by_alias=True))
        finally:
            adapter.contexts[REPO].store.close()

    def test_call_tool_round_trip(self):
        import asyncio

        from span.shell import mcp_server

        adapter, _ = _harness()
        try:
            content, is_error = mcp_server.handle_call_tool(
                adapter,
                "status",
                {
                    "repository_id": REPO,
                    "target": None,
                    "mode": "HOOK_FAST",
                },
            )
            self.assertFalse(is_error)
            body = json.loads(content)
            self.assertEqual(body["$type"], "HookStatusNotice")

            async def _via_sdk():
                import mcp.types as _types

                server = mcp_server.build_server(adapter)
                entry = server.get_request_handler("tools/call")
                assert entry is not None
                return await entry.handler(
                    None,
                    _types.CallToolRequestParams(
                        name="status",
                        arguments={
                            "repository_id": REPO,
                            "target": None,
                            "mode": "HOOK_FAST",
                        },
                    ),
                )

            result = asyncio.run(_via_sdk())
            self.assertFalse(result.is_error)
            sdk_body = json.loads(result.content[0].text)
            self.assertEqual(sdk_body["$type"], "HookStatusNotice")
            self.assertEqual(result.structured_content, sdk_body)
        finally:
            adapter.contexts[REPO].store.close()

    def test_structured_content_conforms_to_advertised_output_schema(self):
        import jsonschema

        from span.shell.mcp import TOOL_OUTPUT_SCHEMAS

        adapter, _ = _harness()
        try:
            cases = (
                (
                    "status",
                    {
                        "repository_id": REPO,
                        "target": None,
                        "mode": "HOOK_FAST",
                    },
                ),
                ("status", {"repository_id": REPO, "target": None}),
                (
                    "locate",
                    {
                        "repository_id": REPO,
                        "mode": "SYMBOL",
                        "query": "src/tools.py",
                    },
                ),
                (
                    "neighbors",
                    {
                        "repository_id": REPO,
                        "direction": "DOWNSTREAM",
                        "target": _selector_args(),
                    },
                ),
            )
            for tool, arguments in cases:
                with self.subTest(tool=tool, arguments=arguments):
                    result = _dispatch(adapter, tool, arguments)
                    self.assertFalse(result.is_error, result.content)
                    jsonschema.validate(
                        result.structured_content,
                        TOOL_OUTPUT_SCHEMAS[tool],
                    )
        finally:
            adapter.contexts[REPO].store.close()

    def test_pending_and_initialize_payloads_conform_to_output_schema(self):
        import jsonschema

        from span.shell.mcp import TOOL_OUTPUT_SCHEMAS, canonical_result_payload

        adapter, _ = _harness()
        try:
            context = adapter.contexts[REPO]
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "src/tools.py", (), None),
                    bounds=DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
                ),
                structural=context.structural,
                evidence=context.evidence,
                store=context.store,
                continuations=context.continuations,
                authority_seeds=(),
            )
            from span.ports.interpretation import PendingInterpretation

            self.assertIsInstance(pending, PendingInterpretation)
            jsonschema.validate(
                canonical_result_payload(pending),
                TOOL_OUTPUT_SCHEMAS["explain"],
            )
        finally:
            adapter.contexts[REPO].store.close()

        structural = InMemoryStructuralSource(
            REPO,
            tuple(InMemoryFile(p, c) for p, c in FILES.items()),
            (InMemorySubject("src/tools.py", m.SubjectKind.COMPONENT, "t"),),
        )
        evidence = FixtureEvidenceSource(REPO, dict(FILES))
        store = SqliteSemanticStore(":memory:")
        try:
            initialized = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    authority_seeds=(),
                ),
                repository_id=REPO,
                structural=structural,
                evidence=evidence,
                store=store,
            )
            jsonschema.validate(
                canonical_result_payload(initialized),
                TOOL_OUTPUT_SCHEMAS["initialize_repository"],
            )
        finally:
            store.close()


@unittest.skipUnless(_HAS_MCP_SDK, "MCP SDK unavailable")
class ProvisionPathTest(unittest.TestCase):
    """Full server path: graft structural + filesystem evidence +
    file store, provisioned explicitly, driven over MCP dispatch."""

    def test_provision_then_explain_over_wire(self):
        import hashlib
        import json
        import pathlib
        import shutil
        import subprocess
        import tempfile

        from span.shell import mcp_server
        from span.shell.mcp import McpAdapter as _Adapter

        fixture_src = (
            pathlib.Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "order-svc"
        )
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="span-mcp-"))
        try:
            work = tmp / "order-svc"
            shutil.copytree(fixture_src, work)
            (work / ".gitignore").write_text("graft/\n.ignore\n", encoding="utf-8")
            subprocess.run(
                ("git", "-C", str(work), "init", "-q"),
                check=True,
                timeout=60,
            )
            subprocess.run(
                ("git", "-C", str(work), "add", "-A"),
                check=True,
                timeout=60,
            )
            subprocess.run(
                (
                    "git",
                    "-C",
                    str(work),
                    "-c",
                    "user.email=t@t",
                    "-c",
                    "user.name=t",
                    "commit",
                    "-qm",
                    "held-out",
                ),
                check=True,
                timeout=60,
            )
            # The provider index lives in Span's data directory; this
            # in-process fixture supplies the minimal wiring it owns.
            # The graft/ tree is git-ignored above, so the tree stays
            # clean and the index postdates HEAD.
            graph_dir = tmp / "data" / "structural" / "order-svc" / ".graph"
            graph_dir.mkdir(parents=True, exist_ok=True)
            nodes = []
            for rel in ("src/orders.js", "src/inventory.js"):
                body = (work / rel).read_text(encoding="utf-8")
                nodes.append(
                    {
                        "id": rel,
                        "name": pathlib.Path(rel).name,
                        "kind": "file",
                        "path": rel,
                        "body_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    }
                )
            (graph_dir / "wiring.json").write_text(
                json.dumps({"nodes": nodes, "edges": []}),
                encoding="utf-8",
            )
            config = mcp_server.ServerConfig(data_dir=tmp / "data")
            request = ops.SemanticInitializeRepositoryRequest(
                repository_locator=str(work),
                authority_seeds=(),
            )
            context, result = mcp_server.provision_repository(config, request)
            try:
                self.assertEqual(result.repository_id, "order-svc")
                self.assertIs(result.store_readiness, m.StoreReadiness.READY)
                adapter = _Adapter(
                    provisioner=(
                        lambda req: mcp_server.provision_repository(config, req)
                    )
                )
                adapter.register(result.repository_id, context)
                status = _dispatch(
                    adapter,
                    "status",
                    {
                        "repository_id": "order-svc",
                        "target": None,
                        "mode": "HOOK_FAST",
                    },
                )
                self.assertFalse(status.is_error)
                notice = json.loads(status.content)
                self.assertEqual(notice["store_readiness"], "READY")
            finally:
                context.store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ContextualPathSmokeTest(unittest.TestCase):
    """Unchanged SubjectSelector schema reaches contextual resolution."""

    def test_eleven_tools_and_path_explain(self):
        self.assertEqual(len(TOOL_NAMES), 11)
        decoded = _decode_request(
            "explain",
            {
                "repository_id": REPO,
                "target": _selector_args("src/tools.py"),
            },
        )
        self.assertIsInstance(decoded, ops.SemanticExplainRequest)
        self.assertEqual(decoded.target.name_or_locator, "src/tools.py")
        adapter, _ = _harness()
        try:
            ctx = adapter.contexts[REPO]
            area = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="tools_area",
            )
            feature = m.SubjectId(
                repository_id=REPO,
                subject_kind=m.SubjectKind.SUBSYSTEM,
                canonical_locator="tools_feature",
            )
            eref = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-src/tools.py"),
                repository_id=REPO,
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/tools.py",
                revision_or_fingerprint=fingerprint_content(FILES["src/tools.py"]),
            )
            fp = fingerprint_content(FILES["src/tools.py"])
            claim = m.SemanticClaim(
                claim_id=m.ClaimId("c-tools"),
                subject=area,
                kind=m.ClaimKind.PURPOSE,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                value=m.PurposeValue("serves tools", ()),
                evidence=(eref,),
                trust=m.TrustState.ESTABLISHED,
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            mem = m.SemanticRelationship(
                relationship_id=m.RelationshipId("r-tools-mem"),
                source=area,
                kind=m.RelationshipKind.MEMBER_OF,
                target=feature,
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                evidence=(eref,),
                trust=m.TrustState.ESTABLISHED,
                freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            question = m.SemanticQuestionScope(
                scope_root=area,
                subject=area,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice=area.canonical_locator,
                materiality_basis="EXPLAIN question-local",
            )
            coverage = m.InterpretationCoverage(
                subjects=(area,),
                question_slice=area.canonical_locator,
                declared_complete=True,
                question=question,
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(m.ClaimRef(id=claim.claim_id),),
                disposition_basis="b",
            )
            ctx.store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(
                        m.Subject(area, "Tools Area", None),
                        m.Subject(feature, "Tools Feature", None),
                    ),
                    claims=(claim,),
                    relationships=(mem,),
                    evidence_dependencies=(
                        m.EvidenceDependency(m.ClaimRef(id=claim.claim_id), eref, fp),
                        m.EvidenceDependency(
                            m.RelationshipRef(id=mem.relationship_id),
                            eref,
                            fp,
                        ),
                    ),
                    coverage=(coverage,),
                )
            )
            pending = _dispatch(
                adapter,
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args("src/tools.py"),
                },
            )
            self.assertFalse(pending.is_error)
            answer = json.loads(pending.content)
            self.assertEqual(answer["$type"], "SemanticAnswer")
            candidates = answer["subject_resolution"]["candidates"]
            self.assertTrue(candidates)
            locators = {
                c["subject"]["subject_id"]["canonical_locator"] for c in candidates
            }
            self.assertIn("tools_area", locators)
        finally:
            adapter.contexts[REPO].store.close()


if __name__ == "__main__":
    unittest.main()


# --- S6 wire-grammar migration helpers -------------------------------------
# Tests build fully-tagged canonical payloads; the compact grammar is the
# agent-facing form. These wrappers project a payload to that grammar before
# the transport consumes it (schema-driven, exact).


def _compact_args(tool, arguments):
    if not isinstance(arguments, dict):
        return arguments
    cls = _REQUEST_CLASS.get(tool) or ops.SemanticInitializeRepositoryRequest
    return _schema.compact_payload(cls, arguments)


def _dispatch(adapter, tool, arguments):
    return McpAdapter.dispatch(adapter, tool, _compact_args(tool, arguments))


def _decode_request(tool, arguments):
    from span.shell.mcp import decode_request as _orig_decode

    return _orig_decode(tool, _compact_args(tool, arguments))
