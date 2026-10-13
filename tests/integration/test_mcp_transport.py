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
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    McpAdapter,
    ServiceContext,
    decode_request,
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
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _candidate():
    return m.CandidateSemanticClaim(
        candidate_key="purpose",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
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
            structural_provider_config="memory:test",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    agent = FixtureAgent(
        {"src/tools.py": FixtureCandidates((_candidate(),), ())}
    )
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

    def test_twelve_canonical_tools(self):
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
                "reissue_interpretation",
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
                    f.name for f in fields
                    if f.default is dataclasses.MISSING
                    and f.default_factory is dataclasses.MISSING
                } - {"bounds"}
                schema = TOOL_SCHEMAS[tool]
                self.assertEqual(
                    set(schema["required"]), required, tool
                )
                self.assertTrue(
                    set(schema["properties"]) >= names, tool
                )

    def test_nullable_targets_advertise_null(self):
        # Nullable contract targets must survive schema-driven bridges:
        # status/refresh/locate targets accept explicit null at ingress.
        for tool in ("status", "refresh", "locate"):
            with self.subTest(tool=tool):
                target_schema = TOOL_SCHEMAS[tool]["properties"]["target"]
                self.assertEqual(target_schema["type"], ["object", "null"])
        for tool in (
            "explain", "impact", "trace", "authority",
            "initialize_target", "neighbors",
        ):
            with self.subTest(tool=tool):
                target_schema = TOOL_SCHEMAS[tool]["properties"]["target"]
                self.assertNotIn("null", target_schema["type"])

    def test_submit_and_init_shapes(self):
        submit = TOOL_SCHEMAS["submit_interpretation"]
        self.assertEqual(
            set(submit["required"]),
            {"continuation", "result", "repository_id"},
        )
        init = TOOL_SCHEMAS["initialize_repository"]
        self.assertEqual(
            set(init["required"]),
            {"repository_locator", "structural_provider_config"},
        )


class IngressTest(unittest.TestCase):
    def test_decode_explain(self):
        request = decode_request(
            "explain",
            {
                "repository_id": REPO,
                "target": _selector_args(),
            },
        )
        self.assertIsInstance(request, ops.SemanticExplainRequest)
        self.assertEqual(
            request.bounds,
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
        )

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            decode_request(
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
            decode_request("trace", args)

    def test_missing_required_rejected(self):
        with self.assertRaises(ValueError):
            decode_request("explain", {"repository_id": REPO})

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ValueError):
            decode_request("span_nope", {})


class DispatchTest(unittest.TestCase):
    def test_initialize_target_advances_complete_boundary(self):
        adapter, agent = _harness()
        try:
            pending = adapter.dispatch(
                "initialize_target",
                {
                    "repository_id": REPO,
                    "target": m.to_canonical(
                        m.EvidenceScope(
                            paths=("src/tools.py",), evidence_refs=()
                        )
                    ),
                    "objective": "Understand the tool boundary and its use.",
                },
            )
            self.assertFalse(pending.is_error)
            envelope = json.loads(pending.content)
            self.assertEqual(envelope["$type"], "PendingInterpretation")
            task = m.from_canonical(
                m.SemanticInterpretationRequest,
                envelope["request"],
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
            self.assertIsNotNone(task.target_inventory_item)
            assert task.target_inventory_item is not None
            item_ref = task.target_inventory_item.evidence_ref
            area = m.SubjectId(
                repository_id=REPO, subject_kind=m.SubjectKind.OTHER,
                canonical_locator="tools-area",
            )
            map_q = m.SemanticQuestionScope(
                scope_root=area, subject=area,
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="tools purpose",
                materiality_basis="mapping admits tools",
            )
            map_cov = m.InterpretationCoverage(
                subjects=(area,), question_slice="tools purpose",
                evidence_scope=m.EvidenceScope(), declared_complete=False,
                question=map_q,
                disposition=m.SemanticQuestionDisposition.PENDING,
                result_refs=(), resolution_requirements=(),
                disposition_basis="admitted", question_evidence=(),
            )
            answered = adapter.dispatch(
                "submit_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "result": m.to_canonical(
                        m.SemanticInterpretationResult(
                            claims=(), relationships=(),
                            governing_source_refs=(), diagnostics=("mapping",),
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
                            proposed_question_coverages=(map_cov,),
                            candidate_withdrawals=(),
                            proposed_target_inventory_accounting=(
                                m.TargetInventoryAccount(
                                    evidence_ref=item_ref,
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

    def test_explain_suspend_then_submit_over_wire(self):
        adapter, agent = _harness()
        try:
            pending = adapter.dispatch(
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            self.assertFalse(pending.is_error)
            envelope = json.loads(pending.content)
            self.assertEqual(envelope["$type"], "PendingInterpretation")
            task = m.from_canonical(
                m.SemanticInterpretationRequest,
                envelope["request"],
            )
            result = agent.perform(task)
            answered = adapter.dispatch(
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
            carried = {
                c["claim_id"]["value"]
                for c in answer["content"]["claims"]
            }
            for conflict in answer["content"]["conflicts"]:
                for side in ("left", "right"):
                    self.assertIn(
                        conflict[side]["id"]["value"], carried
                    )
        finally:
            adapter.contexts[REPO].store.close()

    def test_reissue_is_available_over_wire(self):
        adapter, agent = _harness()
        try:
            pending = adapter.dispatch(
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            reissued = adapter.dispatch(
                "reissue_interpretation",
                {
                    "continuation": envelope["continuation"],
                    "repository_id": REPO,
                },
            )
            self.assertFalse(reissued.is_error)
            replacement = json.loads(reissued.content)
            self.assertEqual(replacement["$type"], "PendingInterpretation")
            task = m.from_canonical(
                m.SemanticInterpretationRequest,
                replacement["request"],
            )
            answered = adapter.dispatch(
                "submit_interpretation",
                {
                    "continuation": replacement["continuation"],
                    "result": m.to_canonical(agent.perform(task)),
                    "repository_id": REPO,
                },
            )
            self.assertFalse(answered.is_error)
        finally:
            adapter.contexts[REPO].store.close()

    def test_status_hook_fast_notice_shape(self):
        adapter, _ = _harness()
        try:
            notice = adapter.dispatch(
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
            result = adapter.dispatch(
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
            self.assertEqual(report["persisted_subject_count"], 0)
            self.assertEqual(report["returned_subject_count"], 0)
            self.assertEqual(report["entries"], [])
        finally:
            adapter.contexts[REPO].store.close()

    def test_unknown_tool_is_typed_error(self):
        adapter, _ = _harness()
        try:
            result = adapter.dispatch("span_nope", {})
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unknown_tool")
        finally:
            adapter.contexts[REPO].store.close()

    def test_bad_continuation_is_unavailable(self):
        adapter, _ = _harness()
        try:
            result = adapter.dispatch(
                "submit_interpretation",
                {
                    "continuation": "cont-999",
                    "result": m.to_canonical(
                        m.SemanticInterpretationResult()
                    ),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unavailable")
        finally:
            adapter.contexts[REPO].store.close()

    def test_malformed_submit_preserves_continuation(self):
        """Invalid submissions never consume the continuation (G-04).

        A malformed typed result over MCP fails ingress; the same
        continuation then accepts the corrected result — recovery
        without reissue, without laundering.
        """
        adapter, agent = _harness()
        try:
            pending = adapter.dispatch(
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            continuation = envelope["continuation"]
            task = m.from_canonical(
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
            rejected = adapter.dispatch(
                "submit_interpretation",
                {
                    "continuation": continuation,
                    "result": bad,
                    "repository_id": REPO,
                },
            )
            self.assertTrue(rejected.is_error)
            self.assertEqual(
                json.loads(rejected.content)["error"], "ingress"
            )
            recovered = adapter.dispatch(
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
            result = adapter.dispatch(
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
            result = adapter.dispatch(
                "submit_interpretation",
                {
                    "continuation": "pg:0",
                    "result": m.to_canonical(
                        m.SemanticInterpretationResult()
                    ),
                    "repository_id": REPO,
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "ingress")
            self.assertIn("page_token", body["message"])
            self.assertIn("continuation", body["message"])
        finally:
            adapter.contexts[REPO].store.close()

    def test_continuation_as_page_token_names_both_mechanisms(self):
        adapter, _ = _harness()
        try:
            result = adapter.dispatch(
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
            self.assertIn("page_token", body["message"])
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
            pending = adapter.dispatch(
                "explain",
                {
                    "repository_id": REPO,
                    "target": _selector_args(),
                },
            )
            envelope = json.loads(pending.content)
            task = m.from_canonical(
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
            rejected = adapter.dispatch(
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
                REPO, (_sid(),), (),
                DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
            )
            self.assertEqual(page.items, ())
            self.assertEqual(store.load_subjects(REPO, (_sid(),)), ())
        finally:
            adapter.contexts[REPO].store.close()

    def test_encode_result_is_deterministic(self):
        first = encode_result(m.SemanticInterpretationResult())
        self.assertEqual(first, encode_result(
            m.SemanticInterpretationResult()
        ))
        json.loads(first)

    def test_adapter_is_sdk_free(self):
        import pathlib as _pathlib

        source = (
            _pathlib.Path(__file__).resolve().parents[2]
            / "src" / "span" / "shell" / "mcp.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import mcp", source)
        self.assertNotIn("from mcp", source)
        # Server constructor parses without side effects.
        from span.shell import mcp_server

        args = mcp_server._parse_args(
            ["--data-dir", "/tmp/span-data", "--repo", "graft:/repo"]
        )
        self.assertEqual(str(args.data_dir), "/tmp/span-data")
        self.assertEqual(args.repo, ["graft:/repo"])

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
            result = adapter.dispatch(
                "explain",
                {
                    "repository_id": "ghost",
                    "target": _selector_args(),
                },
            )
            self.assertTrue(result.is_error)
            body = json.loads(result.content)
            self.assertEqual(body["error"], "unknown_repository")
            init = adapter.dispatch(
                "initialize_repository",
                {
                    "repository_locator": "x",
                    "structural_provider_config": "graft:/x",
                },
            )
            self.assertTrue(init.is_error)
            self.assertEqual(
                json.loads(init.content)["error"], "unavailable"
            )
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
            by_name = {
                spec["name"]: spec["description"] for spec in listed
            }
            for name in (
                "initialize_target", "explain", "impact", "trace",
                "authority", "status", "refresh",
                "submit_interpretation", "reissue_interpretation",
                "locate", "neighbors",
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
        self.assertIn(
            "No repositories registered yet", by_name["explain"]
        )


@unittest.skipUnless(_HAS_MCP_SDK, "MCP SDK unavailable")
class ServerWiringTest(unittest.TestCase):
    def test_build_server_registers_twelve_tools(self):
        from span.shell import mcp_server

        adapter, _ = _harness()
        try:
            listed = mcp_server.handle_list_tools(adapter)
            self.assertEqual(len(listed), 12)
            self.assertEqual(
                [spec["name"] for spec in listed], list(TOOL_NAMES)
            )
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
            result = asyncio.run(
                entry.handler(None, _types.PaginatedRequestParams())
            )
            self.assertIsInstance(result, _types.ListToolsResult)
            self.assertEqual(len(result.tools), 12)
            json.loads(result.model_dump_json(by_alias=True))
        finally:
            adapter.contexts[REPO].store.close()

    def test_call_tool_round_trip(self):
        import asyncio

        from span.shell import mcp_server

        adapter, _ = _harness()
        try:
            content, is_error = mcp_server.handle_call_tool(
                adapter, "status",
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
        finally:
            adapter.contexts[REPO].store.close()


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
        from span.shell.agent_exchange.fixture import (
            FixtureAgent as _Agent,
        )
        from span.shell.mcp import McpAdapter as _Adapter

        fixture_src = (
            pathlib.Path(__file__).resolve().parents[2]
            / "tests" / "fixtures" / "order-svc"
        )
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="span-mcp-"))
        try:
            work = tmp / "order-svc"
            shutil.copytree(fixture_src, work)
            (work / ".gitignore").write_text(
                "graft/\n.ignore\n", encoding="utf-8"
            )
            subprocess.run(
                ("git", "-C", str(work), "init", "-q"),
                check=True, timeout=60,
            )
            subprocess.run(
                ("git", "-C", str(work), "add", "-A"),
                check=True, timeout=60,
            )
            subprocess.run(
                (
                    "git", "-C", str(work),
                    "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "held-out",
                ),
                check=True, timeout=60,
            )
            # The server never builds the structural index (F §4.0, G
            # §2): write the minimal explicitly-built wiring the test
            # owns. The graft/ tree is git-ignored above, so the tree
            # stays clean and the index postdates HEAD.
            graph_dir = work / "graft" / ".graph"
            graph_dir.mkdir(parents=True, exist_ok=True)
            nodes = []
            for rel in ("src/orders.js", "src/inventory.js"):
                body = (work / rel).read_text(encoding="utf-8")
                nodes.append({
                    "id": rel,
                    "name": pathlib.Path(rel).name,
                    "kind": "file",
                    "path": rel,
                    "body_hash": hashlib.sha256(
                        body.encode("utf-8")
                    ).hexdigest(),
                })
            (graph_dir / "wiring.json").write_text(
                json.dumps({"nodes": nodes, "edges": []}),
                encoding="utf-8",
            )
            config = mcp_server.ServerConfig(data_dir=tmp / "data")
            request = ops.SemanticInitializeRepositoryRequest(
                repository_locator=str(work),
                structural_provider_config=f"graft:{work}",
                authority_seeds=(),
            )
            context, result = mcp_server.provision_repository(
                config, request
            )
            try:
                self.assertEqual(result.repository_id, "order-svc")
                self.assertIs(
                    result.readiness, m.RepositoryReadiness.READY
                )
                adapter = _Adapter(
                    provisioner=(
                        lambda req: mcp_server.provision_repository(
                            config, req
                        )
                    )
                )
                adapter.register(result.repository_id, context)
                status = adapter.dispatch(
                    "status",
                    {
                        "repository_id": "order-svc",
                        "target": None,
                        "mode": "HOOK_FAST",
                    },
                )
                self.assertFalse(status.is_error)
                notice = json.loads(status.content)
                self.assertEqual(
                    notice["readiness"], "READY"
                )
            finally:
                context.store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
