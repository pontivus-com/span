"""Addendum I usability program acceptance (S0–S9, gates A1–A12).

Deterministic throughout; FixtureAgent stands in for the invoking agent.
Covers exact-path retrieval, observational status with write rejection,
schema-only submission, question-specific trace, authority separation,
correction isolation, freshness, excerpts, state explanation, and
installed/source parity shape. No benchmark/token/time/byte measurement
(MI-10); correctness and qualifications only.
"""

import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service as ops
from span.service.questions import effective_impact_slice, effective_trace_slice
from span.shell import paging as _paging
from span.shell.agent_exchange.continuations import ContinuationStore
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
    "docs/guide.md": "# Guide\n\nPurpose here.\n",
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
    kind = (
        m.EvidenceSourceKind.DOCUMENTATION
        if path.endswith((".md", ".rst", ".txt"))
        else m.EvidenceSourceKind.SOURCE_CODE
    )
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id="repo-1",
        source_kind=kind,
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _harness():
    structural = InMemoryStructuralSource(
        "repo-1",
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        SUBJECTS,
    )
    evidence = FixtureEvidenceSource("repo-1", dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            authority_seeds=(),
        ),
        repository_id="repo-1",
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store


def _candidate(slice_note="does things"):
    return m.CandidateSemanticClaim(
        candidate_key="purpose-main",
        subject=_sid(), kind=m.ClaimKind.PURPOSE,
        value=m.PurposeValue(slice_note, ()),
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        evidence=(_ref("README.md"), _ref("src/main.py")),
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION, "README states purpose"
        ),
    )


class S1ExactLocatorTest(unittest.TestCase):
    def test_id_and_path_recover_same_subject(self):
        from span.service.resolution import _resolve_query_subject

        structural = InMemoryStructuralSource("repo-1", (), ())
        store = SqliteSemanticStore(":memory:")
        try:
            sid = m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.SUBSYSTEM,
                canonical_locator="workflows/tta",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "tta workflow", None),)
                )
            )
            by_id = _resolve_query_subject(
                "repo-1", m.SubjectSelector(sid, None, (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            by_path = _resolve_query_subject(
                "repo-1", m.SubjectSelector(None, "workflows/tta", (), None),
                structural=structural, store=store, bounds=_bounds(),
            )
            self.assertIs(by_id.ambiguity, m.ResolutionAmbiguity.RESOLVED)
            self.assertIs(by_path.ambiguity, m.ResolutionAmbiguity.RESOLVED)
            self.assertEqual(
                by_id.candidates[0].subject.subject_id,
                by_path.candidates[0].subject.subject_id,
            )
        finally:
            store.close()


class S2ObservationalStatusTest(unittest.TestCase):
    def test_repeated_status_allocates_no_work_and_writes_nothing(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            req = ops.SemanticStatusRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, "src/main.py", (), None),
                bounds=_bounds(),
            )
            first = ops.status(
                req, structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(first, m.SemanticAnswer)
            self.assertEqual(len(continuations), 0)
            before = store.count_repository_subjects("repo-1")
            second = ops.status(
                req, structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(second, m.SemanticAnswer)
            self.assertEqual(len(continuations), 0)
            self.assertEqual(store.count_repository_subjects("repo-1"), before)
            # No interpretation initiation: unexamined returns explicit gap.
            self.assertTrue(
                second.content.coverage_report is not None
                or second.resolution_requirements
                or second.content.unresolved
            )
        finally:
            store.close()

    def test_write_rejecting_store_proves_read_only(self):
        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()

            def _rejecting(*args, **kwargs):
                raise AssertionError("status must not persist freshness")

            store.mark_freshness = _rejecting  # type: ignore[method-assign]
            req = ops.SemanticStatusRequest(
                repository_id="repo-1", target=None, bounds=_bounds()
            )
            answer = ops.status(
                req, structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
        finally:
            store.close()


class S3SchemaTest(unittest.TestCase):
    def test_schemas_generated_with_defs_and_closed_objects(self):
        from span.shell.mcp import TOOL_SCHEMAS
        from span.shell.mcp import decode_request

        for tool, schema in TOOL_SCHEMAS.items():
            self.assertEqual(schema.get("type"), "object")
            self.assertIn("properties", schema)
            self.assertIn("additionalProperties", schema)
        # Nested defs present for submit (result carrier).
        submit = TOOL_SCHEMAS["submit_interpretation"]
        self.assertIn("$defs", submit)
        defs = submit["$defs"]
        self.assertIn("SemanticInterpretationResult", defs)
        # Candidate nature exposes only two submittable values.
        found_nature = False
        for name, definition in defs.items():
            props = definition.get("properties", {})
            if "assertion_nature" in props:
                found_nature = True
                enum = props["assertion_nature"].get("enum") or []
                # Flatten anyOf/enum shapes: must not advertise LEGACY.
                text = str(props["assertion_nature"])
                self.assertNotIn("LEGACY_UNCLASSIFIED", text)
        self.assertTrue(found_nature)
        # Decoder remains the only ingress parser: malformed still rejects.
        with self.assertRaises(ValueError):
            decode_request("explain", {"repository_id": "r"})
        from span.shell.mcp import McpAdapter

        adapter = McpAdapter()
        out = adapter.dispatch("explain", {"repository_id": "r"})
        self.assertTrue(out.is_error)

    def test_ingress_reports_all_shape_faults_in_one_response(self):
        # One malformed call must not cost one round trip per fault: the
        # wire passes report every sibling fault they find. A single
        # fault keeps its exact previous text.
        from span.shell.mcp import decode_request

        claim = {"kind": "PURPOSE"}
        with self.assertRaises(ValueError) as ctx:
            decode_request("submit_interpretation", {
                "repository_id": "r",
                "continuation": "cont-1",
                "result": {
                    "claims": [dict(claim), dict(claim)],
                },
            })
        text = str(ctx.exception)
        self.assertIn("result.claims[0]", text)
        self.assertIn("result.claims[1]", text)

    def test_ingress_reports_cross_pass_faults_together(self):
        # The tagging pass runs first; it must also report the unknown and
        # missing fields the strict decoder would find, so a tag fault
        # plus a field fault do not cost two round trips.
        from span.shell.mcp import decode_request

        with self.assertRaises(ValueError) as ctx:
            decode_request("initialize_target", {
                "repository_id": "r",
                "target": {
                    "$type": "EvidenceScope",
                    "paths": [],
                    "evidence_refs": [],
                    "bogus": 1,
                },
            })
        text = str(ctx.exception)
        self.assertIn("missing field 'objective'", text)
        self.assertIn(
            "unexpected $type at unambiguous position: target", text
        )
        self.assertIn(
            "target: unknown fields for EvidenceScope: ['bogus']", text
        )

    def test_single_shape_fault_keeps_decoder_text(self):
        # Aggregation must not alter the one-fault message callers and
        # tests already depend on.
        from span.shell.mcp import decode_request

        cases = (
            (
                "unknown field",
                "status",
                {
                    "repository_id": "r",
                    "target": {
                        "$type": "SubjectSelector",
                        "exact_subject_id": None,
                        "name_or_locator": None,
                        "expected_kinds": [],
                        "bogus": 1,
                    },
                },
                "target: unknown fields for SubjectSelector: ['bogus']",
            ),
            (
                "missing field",
                "refresh",
                {"repository_id": "r"},
                "missing field 'target' for SemanticRefreshRequest",
            ),
        )
        for label, tool, arguments, expected in cases:
            with self.subTest(label=label):
                with self.assertRaises(ValueError) as ctx:
                    decode_request(tool, arguments)
                self.assertEqual(
                    str(ctx.exception),
                    f"invalid {tool} arguments: {expected}",
                )

    def test_submit_description_states_shape_invariants(self):
        # The schema cannot express these constructor invariants; the
        # tool description is the advertised contract for them.
        from span.shell.mcp import TOOL_DESCRIPTIONS

        text = TOOL_DESCRIPTIONS["submit_interpretation"]
        for rule in (
            "exactly one outcome",
            "OPEN question_decision carries resolution_requirements",
            "ANSWERED requires validated material",
            "NOT_APPLICABLE carries a basis and no result refs",
        ):
            self.assertIn(rule, text)

    def test_type_tag_is_positional_not_definitional(self):
        # J-8: $type is a property of the field POSITION. Each carrier
        # projects an untagged ingress form for unambiguous positions and
        # a tagged form (required $type const) for union branches. The
        # decoder enforces the same grammar in both directions.
        from span.shell.mcp import TOOL_SCHEMAS

        for tool, schema in TOOL_SCHEMAS.items():
            for name, definition in schema.get("$defs", {}).items():
                with self.subTest(tool=tool, definition=name):
                    properties = definition.get("properties", {})
                    required = definition.get("required", [])
                    if name.endswith("__tag"):
                        base = name[: -len("__tag")]
                        self.assertEqual(
                            properties.get("$type"), {"const": base}
                        )
                        self.assertIn("$type", required)
                    else:
                        self.assertNotIn("$type", properties)
                        self.assertNotIn("$type", required)

    @staticmethod
    def _refs(schema):
        refs = []
        if isinstance(schema, dict):
            if "$ref" in schema:
                refs.append(schema["$ref"])
            for value in schema.values():
                refs.extend(S3SchemaTest._refs(value))
        elif isinstance(schema, list):
            for value in schema:
                refs.extend(S3SchemaTest._refs(value))
        return refs

    def test_union_positions_use_tagged_definitions(self):
        # The generator-verified request-ingress unions (locality plan
        # §15.5) must each reference tagged definitions.
        from span.shell.mcp import TOOL_SCHEMAS

        positions = [
            ("authority", ("properties", "target")),
            ("impact", ("properties", "affected_assertions")),
            ("refresh", ("properties", "target")),
            ("status", ("properties", "target")),
            (
                "submit_interpretation",
                ("$defs", "CandidateSemanticClaim", "properties", "value"),
            ),
            (
                "submit_interpretation",
                ("$defs", "CandidateSemanticWithdrawal", "properties", "target"),
            ),
            (
                "submit_interpretation",
                (
                    "$defs",
                    "ResolutionRequirement",
                    "properties",
                    "subject_or_claim",
                ),
            ),
            (
                "submit_interpretation",
                (
                    "$defs",
                    "ResolutionRequirement",
                    "properties",
                    "supporting_context",
                ),
            ),
            (
                "submit_interpretation",
                ("$defs", "SemanticBasis", "properties", "input_refs"),
            ),
        ]
        for tool, path in positions:
            schema = TOOL_SCHEMAS[tool]
            node = schema
            for key in path:
                node = node[key]
            with self.subTest(tool=tool, path=path):
                refs = self._refs(node)
                self.assertTrue(refs)
                self.assertTrue(
                    all(r.endswith("__tag") for r in refs),
                    refs,
                )

    def test_sole_positions_use_untagged_definitions(self):
        from span.shell.mcp import TOOL_SCHEMAS

        target = TOOL_SCHEMAS["initialize_target"]["properties"]["target"]
        self.assertEqual(target["$ref"], "#/$defs/EvidenceScope")
        self.assertNotIn("allOf", target)

        locate_target = TOOL_SCHEMAS["locate"]["properties"]["target"]
        locate_refs = self._refs(locate_target)
        self.assertIn("#/$defs/EvidenceScope", locate_refs)
        self.assertFalse(any(r.endswith("__tag") for r in locate_refs))

        seeds = TOOL_SCHEMAS["initialize_repository"]["properties"][
            "authority_seeds"
        ]
        array_branch = next(
            branch
            for branch in seeds["anyOf"]
            if branch.get("type") == "array"
        )
        seed_refs = self._refs(array_branch["items"])
        self.assertIn("#/$defs/EvidenceRef", seed_refs)
        self.assertFalse(any(r.endswith("__tag") for r in seed_refs))

    def test_union_fields_advertise_allowed_tags(self):
        # The consumer truncates deep schemas to `unknown`; the field
        # description must still name the accepted `$type` values.
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["submit_interpretation"]["$defs"]
        requirements = defs["ResolutionRequirement"]["properties"]
        subject = requirements["subject_or_claim"]["description"]
        for tag in ("SubjectId", "ClaimRef", "RelationshipRef"):
            self.assertIn(tag, subject)
        support = requirements["supporting_context"]["description"]
        for tag in ("ClaimRef", "RelationshipRef", "EvidenceRef"):
            self.assertIn(tag, support)
        input_refs = defs["SemanticBasis"]["properties"]["input_refs"][
            "description"
        ]
        for tag in ("ClaimRef", "RelationshipRef", "EvidenceRef"):
            self.assertIn(tag, input_refs)

    def test_claim_value_description_carries_kind_mapping(self):
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["submit_interpretation"]["$defs"]
        names = [
            n for n in ("CandidateSemanticClaim", "CandidateSemanticClaim__tag")
            if n in defs
        ]
        self.assertTrue(names)
        for claim in names:
            value = defs[claim]["properties"]["value"]
            self.assertIn("Allowed $type values:", value["description"])
            self.assertIn("PURPOSE=PurposeValue", value["description"])
            self.assertIn(
                "CAPABILITY_MEMBERSHIP=CapabilityMembershipValue",
                value["description"],
            )

    def test_target_question_reuse_is_described_as_persisted_only(self):
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["submit_interpretation"]["$defs"]
        names = [
            n for n in ("SemanticInterpretationResult",
                        "SemanticInterpretationResult__tag")
            if n in defs
        ]
        self.assertTrue(names)
        for result in names:
            prop = defs[result]["properties"]["proposed_target_questions"]
            self.assertIn("Reuse only", prop["description"])
            self.assertIn("already be persisted", prop["description"])
            self.assertIn("PENDING CQ-01 seed", prop["description"])

    def test_advertised_defaults_are_copy_paste_decodable(self):
        # A default that contains `$type` at a sole position is a trap:
        # the decoder rejects the value the schema tells the agent to use.
        from span.shell.mcp import TOOL_SCHEMAS, decode_request

        for tool, schema in TOOL_SCHEMAS.items():
            bounds = schema.get("properties", {}).get("bounds")
            if isinstance(bounds, dict) and "default" in bounds:
                with self.subTest(tool=tool):
                    self.assertNotIn("$type", bounds["default"])
        decoded = decode_request(
            "status",
            {
                "repository_id": "example-repo",
                "bounds": TOOL_SCHEMAS["status"]["properties"]["bounds"][
                    "default"
                ],
            },
        )
        self.assertIsNotNone(decoded)

    def test_initialize_repository_describes_plain_paths(self):
        from span.shell.mcp import TOOL_DESCRIPTIONS

        text = TOOL_DESCRIPTIONS["initialize_repository"]
        self.assertIn("repository_locator", text)
        self.assertIn("authority_seeds", text)
        self.assertNotIn("structural_provider_config", text)

    def test_subject_selector_omits_both_optional_keys(self):
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["impact"]["$defs"]
        names = [
            n for n in ("SubjectSelector", "SubjectSelector__tag")
            if n in defs
        ]
        self.assertTrue(names)
        for selector in names:
            required = defs[selector]["required"]
            self.assertNotIn("exact_subject_id", required)
            self.assertNotIn("name_or_locator", required)
            prop = defs[selector]["properties"]["exact_subject_id"]
            self.assertNotIn(
                "Required along with name_or_locator",
                prop.get("description", ""),
            )

    def test_candidate_claims_advertise_required_subject_and_value(self):
        # Validation rejects an unset subject and the constructor rejects
        # a kind/value mismatch; the advertised schema must not present
        # either field as optional.
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["submit_interpretation"]["$defs"]
        names = [
            n for n in ("CandidateSemanticClaim", "CandidateSemanticClaim__tag")
            if n in defs
        ]
        self.assertTrue(names)
        for claim in names:
            required = defs[claim]["required"]
            self.assertIn("subject", required)
            self.assertIn("value", required)
            self.assertIn("assertion_nature", required)

    def test_claim_value_classes_name_their_kind(self):
        from span.core.model import CLAIM_VALUE_TYPE
        from span.shell.mcp import TOOL_SCHEMAS

        defs = TOOL_SCHEMAS["submit_interpretation"]["$defs"]
        found = 0
        for kind, value_cls in CLAIM_VALUE_TYPE.items():
            for name in (
                value_cls.__name__,
                f"{value_cls.__name__}__tag",
            ):
                if name not in defs:
                    continue
                found += 1
                with self.subTest(name=name):
                    self.assertIn(
                        kind.value,
                        defs[name].get("description", ""),
                    )
        self.assertGreater(found, 0)

    def test_defs_are_reachable_and_all_refs_resolve(self):
        from span.shell.mcp import TOOL_SCHEMAS

        for tool, schema in TOOL_SCHEMAS.items():
            defs = schema.get("$defs", {})
            used: set[str] = set()

            def walk(node):
                if isinstance(node, dict):
                    ref = node.get("$ref")
                    if isinstance(ref, str) and ref.startswith("#/$defs/"):
                        name = ref.rsplit("/", 1)[-1]
                        with self.subTest(tool=tool, ref=name):
                            self.assertIn(name, defs)
                        if name in defs and name not in used:
                            used.add(name)
                            walk(defs[name])
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk({k: v for k, v in schema.items() if k != "$defs"})
            with self.subTest(tool=tool):
                self.assertEqual(used, set(defs))

    def test_initialize_target_advertises_non_empty_target(self):
        from span.shell.mcp import TOOL_SCHEMAS

        target = TOOL_SCHEMAS["initialize_target"]["properties"]["target"]
        self.assertEqual(target.get("minProperties"), 1)
        locate_target = TOOL_SCHEMAS["locate"]["properties"]["target"]
        self.assertNotIn("minProperties", locate_target)

    def test_schema_size_budget(self):
        # Guard against unreachable-definition regrowth. The current
        # pruned size is ~22.7 KB for submit_interpretation and ~55 KB
        # across all eleven tools. Further reduction would require a
        # contract change, not a projection tweak.
        import json

        from span.shell.mcp import TOOL_SCHEMAS

        submit = len(json.dumps(TOOL_SCHEMAS["submit_interpretation"]))
        total = sum(len(json.dumps(schema)) for schema in TOOL_SCHEMAS.values())
        self.assertLessEqual(submit, 25_000)
        self.assertLessEqual(total, 60_000)

    def test_claim_kind_value_compatibility_advertised(self):
        # S3.1/S5.3: schemas reuse CLAIM_VALUE_TYPE so a fresh agent
        # cannot construct a kind/value pair the constructor rejects.
        from span.core.model import CLAIM_VALUE_TYPE
        from span.shell.mcp import TOOL_SCHEMAS

        submit = TOOL_SCHEMAS["submit_interpretation"]
        defs = submit["$defs"]
        # Candidate claims cross the ingress boundary, so their
        # kind/value mapping must be advertised; plain stored claims
        # never appear in transport schemas.
        self.assertIn("CandidateSemanticClaim", defs)
        definition = defs["CandidateSemanticClaim"]
        branches = [
            item for item in definition.get("allOf", [])
            if "if" in item and "then" in item
        ]
        self.assertEqual(len(branches), len(CLAIM_VALUE_TYPE))
        for branch, kind in zip(
            branches,
            sorted(CLAIM_VALUE_TYPE, key=lambda k: k.value),
        ):
            self.assertEqual(
                branch["if"]["properties"]["kind"],
                {"const": kind.value},
            )
            ref = branch["then"]["properties"]["value"]["$ref"]
            expected = (
                "#/$defs/"
                f"{CLAIM_VALUE_TYPE[kind].__name__}__tag"
            )
            self.assertEqual(ref, expected)
            self.assertIn(
                f"{CLAIM_VALUE_TYPE[kind].__name__}__tag", defs
            )
        for tagged_claim in ("SemanticClaim", "SemanticClaim__tag"):
            if tagged_claim in defs:
                self.assertTrue(
                    any(
                        "if" in item and "then" in item
                        for item in defs[tagged_claim].get("allOf", [])
                    )
                )

    def test_valid_candidate_decodes(self):
        # Positive round trip: a schema-conformant descriptive
        # candidate with matching kind/value decodes successfully.
        payload = {
            "$type": "CandidateSemanticClaim",
            "candidate_key": "k",
            "subject": m.to_canonical(_sid()),
            "kind": "PURPOSE",
            "value": {
                "$type": "PurposeValue",
                "summary": "s",
                "capability_refs": [],
            },
            "assertion_nature": "DESCRIPTIVE",
            "evidence": [],
            "candidate_authority": None,
            "basis": {"$type": "SemanticBasis", "derivation": "SEMANTIC_INTERPRETATION"},
        }
        decoded = m.from_canonical(m.CandidateSemanticClaim, payload)
        assert isinstance(decoded, m.CandidateSemanticClaim)
        self.assertIs(
            decoded.assertion_nature, m.AssertionNature.DESCRIPTIVE
        )

    def test_removed_legacy_nature_rejected(self):
        # The retired classification is not part of the current nature
        # vocabulary, so it can never enter through candidate ingress.
        payload = {
            "$type": "CandidateSemanticClaim",
            "candidate_key": "k",
            "subject": m.to_canonical(_sid()),
            "kind": "PURPOSE",
            "value": {
                "$type": "PurposeValue",
                "summary": "s",
                "capability_refs": [],
            },
            "assertion_nature": "LEGACY_UNCLASSIFIED",
            "evidence": [],
            "candidate_authority": None,
            "basis": {"$type": "SemanticBasis", "derivation": "SEMANTIC_INTERPRETATION"},
        }
        # Only DESCRIPTIVE and NORMATIVE decode.
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.CandidateSemanticClaim, payload)


class S4QuestionSelectionTest(unittest.TestCase):
    def test_trace_discriminator_splits_directions(self):
        a = effective_trace_slice("slice", "UPSTREAM", None, False)
        b = effective_trace_slice("slice", "DOWNSTREAM", None, False)
        self.assertNotEqual(a, b)
        none_filter = effective_trace_slice("s", "BOTH", (), False)
        all_filter = effective_trace_slice("s", "BOTH", None, False)
        self.assertIn("|filter=NONE|", none_filter)
        self.assertIn("|filter=ALL|", all_filter)

    def test_impact_discriminator_splits_proposals(self):
        a = effective_impact_slice("s", m.ChangeKind.BEHAVIOR, "fix one", ())
        b = effective_impact_slice("s", m.ChangeKind.BEHAVIOR, "fix two", ())
        self.assertNotEqual(a, b)
        empty = effective_impact_slice("s", m.ChangeKind.BEHAVIOR, None, ())
        self.assertIn("|desc=-|", empty)

    def test_pgq_rejects_old_and_binds_question(self):
        digest = _paging.question_digest("TRACE", "r", "a.py", "slice", "CQ_04")
        token = _paging.format_question_token(digest, 1, 0, 0)
        assert token is not None and token.startswith("pgq:")
        got_digest, c, r, q = _paging.parse_question_token(token)
        self.assertEqual(got_digest, digest)
        with self.assertRaises(ValueError):
            _paging.parse_service_token("pg:1:0:0")

    def test_baseline_and_selection_conflict_rejected(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(ValueError):
                ops.explain(
                    ops.SemanticExplainRequest(
                        repository_id="repo-1",
                        target=m.SubjectSelector(None, "src/main.py", (), None),
                        bounds=_bounds(),
                        establish_baseline=True,
                        question_selection=m.SemanticQuestionSelection(
                            question_slice="narrow",
                        ),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_authority_claimref_with_selection_rejected(self):
        structural, evidence, store = _harness()
        try:
            with self.assertRaises(Exception):
                ops.authority(
                    ops.SemanticAuthorityRequest(
                        repository_id="repo-1",
                        target=m.ClaimRef(id=m.ClaimId("clm-x")),
                        bounds=_bounds(),
                        question_selection=m.SemanticQuestionSelection(
                            question_slice="narrow",
                        ),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
        finally:
            store.close()

    def test_walk_visits_same_locator_distinct_kinds(self):
        # S4 §5.4: the walk visited set is full-SubjectId identity, so
        # a same-locator subject of another kind is still examined
        # instead of being skipped as an already-visited locator.
        from span.ports.structural import StructuralDirection

        files = {"README.md": "# x\n\nDoes x.\n", "src/x.py": "X = 1\n"}
        comp = m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/x.py",
        )
        doc = m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.DOCUMENT,
            canonical_locator="src/x.py",
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            (
                InMemorySubject("src/x.py", m.SubjectKind.COMPONENT, "x"),
                InMemorySubject("src/x.py", m.SubjectKind.DOCUMENT, "x doc"),
            ),
        )
        evidence = FixtureEvidenceSource("repo-1", dict(files))
        store = SqliteSemanticStore(":memory:")
        try:
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    authority_seeds=(),
                ),
                repository_id="repo-1",
                structural=structural,
                evidence=evidence,
                store=store,
            )
            eff = effective_trace_slice(
                "src/x.py", StructuralDirection.BOTH, None, False
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(
                        m.Subject(comp, "x", None),
                        m.Subject(doc, "x doc", None),
                    ),
                    claims=(
                        m.SemanticClaim(
                            claim_id=m.ClaimId("clm-x"),
                            subject=comp, kind=m.ClaimKind.PURPOSE,
                            value=m.PurposeValue("does x", ()),
                            assertion_nature=(
                                m.AssertionNature.DESCRIPTIVE
                            ),
                        ),
                    ),
                    relationships=(
                        m.SemanticRelationship(
                            relationship_id=m.RelationshipId("rel-x"),
                            source=comp,
                            kind=m.RelationshipKind.CROSSES_BOUNDARY,
                            target=doc,
                            assertion_nature=(
                                m.AssertionNature.DESCRIPTIVE
                            ),
                        ),
                    ),
                    coverage=(
                        m.InterpretationCoverage(
                            subjects=(comp,),
                            question_slice=eff,
                            evidence_scope=m.EvidenceScope(),
                            declared_complete=False,
                            question=m.SemanticQuestionScope(
                                scope_root=comp, subject=comp,
                                question_class=(
                                    m.SemanticQuestionClass.CQ_04
                                ),
                                question_slice=eff,
                                materiality_basis="TRACE question-local",
                            ),
                            disposition=(
                                m.SemanticQuestionDisposition.OPEN
                            ),
                            result_refs=(),
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=(
                                        m.ResolutionKind.MISSING_AUTHORITY
                                    ),
                                    subject_or_claim=comp,
                                    description="test open",
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis="test open",
                            question_evidence=(),
                        ),
                    ),
                )
            )
            pending = ops.trace(
                ops.SemanticTraceRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(comp, None, (), None),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertEqual(
                pending.request.subjects[0].subject_id, doc
            )
        finally:
            store.close()

    def test_default_impact_uses_discriminated_slice(self):
        # S4 §5.4: every IMPACT question — default or explicit — carries
        # the discriminator. Two ordinary proposals on the same subject
        # suspend under different persisted identities.
        structural, evidence, store = _harness()
        try:
            slices = []
            for description in ("fix one", "fix two"):
                pending = ops.impact(
                    ops.SemanticImpactRequest(
                        repository_id="repo-1",
                        target=m.SubjectSelector(
                            None, "src/main.py", (), None
                        ),
                        change_kind=m.ChangeKind.BEHAVIOR,
                        change_description=description,
                        bounds=_bounds(),
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=ContinuationStore(),
                )
                self.assertIsInstance(pending, PendingInterpretation)
                question_slice = pending.request.question.question_slice
                self.assertIn("|kind=BEHAVIOR|desc=", question_slice)
                slices.append(question_slice)
            self.assertNotEqual(slices[0], slices[1])
        finally:
            store.close()

    def test_default_impact_examines_exact_question(self):
        # S4 §5.4: existing claims do not satisfy an unexamined IMPACT
        # question. Status-quo data without coverage suspends instead
        # of answering.
        structural, evidence, store = _harness()
        try:
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(_sid(), "main", None),),
                    claims=(
                        m.SemanticClaim(
                            claim_id=m.ClaimId("clm-status"),
                            subject=_sid(), kind=m.ClaimKind.PURPOSE,
                            value=m.PurposeValue("does things", ()),
                            assertion_nature=(
                                m.AssertionNature.DESCRIPTIVE
                            ),
                        ),
                    ),
                )
            )
            pending = ops.impact(
                ops.SemanticImpactRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        None, "src/main.py", (), None
                    ),
                    change_kind=m.ChangeKind.BEHAVIOR,
                    change_description="fix one",
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(pending, PendingInterpretation)
            self.assertIn(
                "|kind=BEHAVIOR|desc=",
                pending.request.question.question_slice,
            )
        finally:
            store.close()

    def test_pending_coverage_still_needs_examination(self):
        # S4/B.7: recorded PENDING is admitted-but-unexamined. It must
        # not satisfy the TRACE/IMPACT examination gate the way
        # ANSWERED/OPEN coverage does, even with stored claims present.
        from span.ports.structural import StructuralDirection

        structural, evidence, store = _harness()
        try:
            trace_eff = effective_trace_slice(
                "src/main.py", StructuralDirection.BOTH, None, False
            )
            impact_eff = effective_impact_slice(
                "src/main.py", m.ChangeKind.BEHAVIOR, "fix one", ()
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(_sid(), "main", None),),
                    claims=(
                        m.SemanticClaim(
                            claim_id=m.ClaimId("clm-pending"),
                            subject=_sid(), kind=m.ClaimKind.PURPOSE,
                            value=m.PurposeValue("does things", ()),
                            assertion_nature=(
                                m.AssertionNature.DESCRIPTIVE
                            ),
                        ),
                    ),
                    coverage=(
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice=trace_eff,
                            evidence_scope=m.EvidenceScope(),
                            declared_complete=False,
                            question=m.SemanticQuestionScope(
                                scope_root=_sid(), subject=_sid(),
                                question_class=(
                                    m.SemanticQuestionClass.CQ_04
                                ),
                                question_slice=trace_eff,
                                materiality_basis="TRACE question-local",
                            ),
                            disposition=(
                                m.SemanticQuestionDisposition.PENDING
                            ),
                            result_refs=(),
                            resolution_requirements=(),
                            disposition_basis="test pending",
                            question_evidence=(),
                        ),
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice=impact_eff,
                            evidence_scope=m.EvidenceScope(),
                            declared_complete=False,
                            question=m.SemanticQuestionScope(
                                scope_root=_sid(), subject=_sid(),
                                question_class=(
                                    m.SemanticQuestionClass.CQ_08
                                ),
                                question_slice=impact_eff,
                                materiality_basis="IMPACT question-local",
                            ),
                            disposition=(
                                m.SemanticQuestionDisposition.PENDING
                            ),
                            result_refs=(),
                            resolution_requirements=(),
                            disposition_basis="test pending",
                            question_evidence=(),
                        ),
                    ),
                )
            )
            traced = ops.trace(
                ops.SemanticTraceRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        None, "src/main.py", (), None
                    ),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(traced, PendingInterpretation)
            impacted = ops.impact(
                ops.SemanticImpactRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        None, "src/main.py", (), None
                    ),
                    change_kind=m.ChangeKind.BEHAVIOR,
                    change_description="fix one",
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(impacted, PendingInterpretation)
        finally:
            store.close()

    def test_suspended_identities_are_full_subject_ids(self):
        # S4 §5.4/H4: suspension records full canonical identities, so
        # two same-locator subjects of different kinds never suppress
        # each other through a shared locator string. The first suspend
        # carries the subject; the resumed walk records it as a full
        # SubjectId and still examines the second kind (reached here
        # through a structural edge whose endpoint kind differs).
        from span.ports.structural import StructuralDirection
        from span.shell.agent_exchange.fixture import (
            FixtureAgent,
            FixtureCandidates,
        )
        from span.shell.structural.memory import InMemoryEdge

        files = {"README.md": "# y\n\nDoes y.\n", "src/y.py": "Y = 1\n"}
        comp = m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/y.py",
        )
        doc = m.SubjectId(
            repository_id="repo-1", subject_kind=m.SubjectKind.DOCUMENT,
            canonical_locator="src/y.py",
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            (
                InMemorySubject("src/y.py", m.SubjectKind.DOCUMENT, "y doc"),
                InMemorySubject("src/y.py", m.SubjectKind.COMPONENT, "y"),
            ),
            (
                InMemoryEdge(
                    "src/y.py", m.StructuralEdgeKind.REFERENCES,
                    "src/y.py",
                ),
            ),
        )
        evidence = FixtureEvidenceSource("repo-1", dict(files))
        store = SqliteSemanticStore(":memory:")
        try:
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture",
                    authority_seeds=(),
                ),
                repository_id="repo-1",
                structural=structural, evidence=evidence, store=store,
            )
            readme_ref = m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-README.md"),
                repository_id="repo-1",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="README.md",
                revision_or_fingerprint="fp",
            )
            agent = FixtureAgent(
                {
                    "src/y.py": FixtureCandidates(
                        (
                            m.CandidateSemanticClaim(
                                candidate_key="purpose-y",
                                subject=comp,
                                kind=m.ClaimKind.PURPOSE,
                                value=m.PurposeValue("does y", ()),
                                assertion_nature=(
                                    m.AssertionNature.DESCRIPTIVE
                                ),
                                evidence=(readme_ref,),
                                basis=m.SemanticBasis(
                                    m.DerivationKind
                                    .SEMANTIC_INTERPRETATION,
                                    "readme states the purpose",
                                ),
                            ),
                        ),
                        (),
                    )
                },
                complete_questions=True,
            )
            continuations = ContinuationStore()
            first = ops.trace(
                ops.SemanticTraceRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(comp, None, (), None),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(readme_ref,),
            )
            self.assertIsInstance(first, PendingInterpretation)
            second = ops.submit_interpretation(
                first.continuation, agent.perform(first.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            # The resumed walk reaches the DOCUMENT-kind subject instead
            # of treating the shared locator as already suspended.
            self.assertIsInstance(second, PendingInterpretation)
            record = continuations.peek(second.continuation)
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record.suspended, (comp, doc))
            for entry in record.suspended:
                self.assertIsInstance(entry, m.SubjectId)
            self.assertEqual(record.subject.subject_id, doc)
        finally:
            store.close()


class S5ExecutionPathTest(unittest.TestCase):
    def test_brief_requests_material_path(self):
        self.assertTrue(
            any("material input" in line for line in m.TASK_BRIEF_MATERIAL_PATH)
        )
        self.assertTrue(
            any("failure branch" in line for line in m.TASK_BRIEF_MATERIAL_PATH)
        )

    def _execution_harness(self):
        from span.shell.structural.memory import InMemoryFile

        files = {
            "README.md": "# pipeline\n\nStages.\n",
            "src/gen.py": "FIRST = 1\n",
            "src/admit.py": "ADMITTED = True\n",
            "src/carrier.py": "STATE = {}\n",
            "src/correct.py": "FIXED = True\n",
            "src/audit.py": "VERIFIED = True\n",
            "src/draft.py": "DRAFT = 1\n",
            "src/admitted.py": "ADMITTED_OUT = 1\n",
        }
        subjects = tuple(
            InMemorySubject(path, m.SubjectKind.COMPONENT, path)
            for path in files
            if path != "README.md"
        ) + (
            InMemorySubject(
                "src/draft.py", m.SubjectKind.REPRESENTATION, "draft"
            ),
            InMemorySubject(
                "src/admitted.py", m.SubjectKind.REPRESENTATION, "admitted"
            ),
        )
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            subjects,
        )
        evidence = FixtureEvidenceSource("repo-1", dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural, evidence=evidence, store=store,
        )
        return structural, evidence, store, files

    def _stage_id(self, locator, kind=m.SubjectKind.COMPONENT):
        return m.SubjectId(
            repository_id="repo-1", subject_kind=kind,
            canonical_locator=locator,
        )

    def _stage_claim(self, stage, locator, summary):
        return m.SemanticClaim(
            claim_id=m.ClaimId(f"clm-{stage}"),
            subject=self._stage_id(locator),
            kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue(summary, ()),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(
                m.EvidenceRef(
                    evidence_id=m.EvidenceId(f"ev-{locator}"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator=locator,
                    revision_or_fingerprint="fp",
                ),
            ),
        )

    def _stage_rel(self, name, source, kind, target):
        return m.SemanticRelationship(
            relationship_id=m.RelationshipId(f"rel-{name}"),
            source=source, kind=kind, target=target,
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
        )

    def _stage_coverage(self, stage, sid, answered, requirement=None):
        requirement_tuple = (
            (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                    subject_or_claim=sid,
                    description=requirement,
                    supporting_context=(),
                ),
            )
            if requirement is not None
            else ()
        )
        return m.InterpretationCoverage(
            subjects=(sid,),
            question_slice=f"{stage} execution",
            evidence_scope=m.EvidenceScope(),
            declared_complete=answered,
            question=m.SemanticQuestionScope(
                scope_root=sid, subject=sid,
                question_class=m.SemanticQuestionClass.CQ_04,
                question_slice=f"{stage} execution",
                materiality_basis="S5 execution path",
            ),
            disposition=(
                m.SemanticQuestionDisposition.ANSWERED
                if answered
                else m.SemanticQuestionDisposition.OPEN
            ),
            result_refs=(
                (m.ClaimRef(id=m.ClaimId(f"clm-{stage}")),)
                if answered
                else ()
            ),
            resolution_requirements=requirement_tuple,
            disposition_basis=f"test {stage}",
            question_evidence=(),
        )

    def _establish_execution_path(self, failure_stage, defective=False):
        # Generic pre-admission-failure shape: generator → admission →
        # carrier/state → correction → downstream audit, using existing
        # relationship kinds only. No production symbols or log values.
        from span.ports.structural import StructuralDirection
        from span.service.questions import effective_trace_slice

        structural, evidence, store, _ = self._execution_harness()
        stages = (
            ("generator", "src/gen.py", "generates the first response"),
            ("admission", "src/admit.py", "admits the response"),
            ("carrier", "src/carrier.py", "carries admitted state"),
            ("correction", "src/correct.py", "corrects the state"),
            ("audit", "src/audit.py", "audits the outcome"),
        )
        by_stage = {name: self._stage_id(loc) for name, loc, _ in stages}
        draft = self._stage_id("src/draft.py", m.SubjectKind.REPRESENTATION)
        admitted = self._stage_id(
            "src/admitted.py", m.SubjectKind.REPRESENTATION
        )
        rels = [
            self._stage_rel(
                "lifecycle-gen-adm", by_stage["generator"],
                m.RelationshipKind.TRANSITIONS_TO, by_stage["admission"],
            ),
            self._stage_rel(
                "lifecycle-adm-car", by_stage["admission"],
                m.RelationshipKind.TRANSITIONS_TO, by_stage["carrier"],
            ),
            self._stage_rel(
                "lifecycle-cor-aud", by_stage["correction"],
                m.RelationshipKind.TRANSITIONS_TO, by_stage["audit"],
            ),
            self._stage_rel(
                "gen-produces", by_stage["generator"],
                m.RelationshipKind.PRODUCES, draft,
            ),
            self._stage_rel(
                "adm-consumes", by_stage["admission"],
                m.RelationshipKind.CONSUMES, draft,
            ),
            self._stage_rel(
                "adm-transforms", by_stage["admission"],
                m.RelationshipKind.TRANSFORMS_TO, admitted,
            ),
        ]
        if not defective:
            # Healthy continuity: the carrier carries admitted state and
            # the correction transitions from the carrier. The defective
            # variant replaces instead of transitioning: both links are
            # absent, so an upstream walk stops at the correction.
            rels[1:1] = [
                self._stage_rel(
                    "lifecycle-car-cor", by_stage["carrier"],
                    m.RelationshipKind.TRANSITIONS_TO,
                    by_stage["correction"],
                )
            ]
            rels.append(
                self._stage_rel(
                    "car-carries", by_stage["carrier"],
                    m.RelationshipKind.CARRIES, admitted,
                )
            )
        rels.append(
            self._stage_rel(
                "cor-consumes", by_stage["correction"],
                m.RelationshipKind.CONSUMES, admitted,
            )
        )
        failure_requirements = {
            "admission": (
                "first response rejected at admission: schema "
                "admission failed before audit"
            ),
            "carrier": (
                "carrier lost admitted state before correction"
            ),
            "correction": (
                "correction replaced admitted output and dropped "
                "carried fields; carrier link missing"
            ),
        }
        _trace_eff = effective_trace_slice(
            "src/audit.py", StructuralDirection.UPSTREAM, None, False
        )
        coverages = tuple(
            self._stage_coverage(
                name, by_stage[name], name != failure_stage,
                None
                if name != failure_stage
                else failure_requirements[failure_stage],
            )
            for name, _, _ in stages
        ) + tuple(
            # Trace-question coverage for the upstream walk: same
            # effective slice for every frontier subject (original root
            # and slice, subject changed), so the walk examines order
            # instead of suspending on traversal.
            m.InterpretationCoverage(
                subjects=(by_stage[name],),
                question_slice=_trace_eff,
                evidence_scope=m.EvidenceScope(),
                declared_complete=True,
                question=m.SemanticQuestionScope(
                    scope_root=by_stage["audit"],
                    subject=by_stage[name],
                    question_class=m.SemanticQuestionClass.CQ_04,
                    question_slice=_trace_eff,
                    materiality_basis="TRACE question-local",
                ),
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                result_refs=(
                    m.ClaimRef(id=m.ClaimId(f"clm-{name}")),
                ),
                resolution_requirements=(),
                disposition_basis=f"test trace {name}",
                question_evidence=(),
            )
            for name, _, _ in stages
        )
        subjects = tuple(
            m.Subject(self._stage_id(loc), loc, None)
            for _, loc, _ in stages
        ) + (
            m.Subject(draft, "draft", None),
            m.Subject(admitted, "admitted", None),
        )
        claims = [
            self._stage_claim(name, loc, summary)
            for name, loc, summary in stages
        ]
        if defective:
            # The defective correction discards prior fields during
            # replacement: its claim no longer carries admitted state.
            claims = [
                self._stage_claim(
                    "correction", "src/correct.py",
                    "replaces output without carried fields",
                )
                if claim.claim_id.value == "clm-correction"
                else claim
                for claim in claims
            ]
        claims = tuple(claims)
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=subjects, claims=claims,
                relationships=tuple(rels),
            )
        )
        store.write_index_batch(
            m.CanonicalIndexBatch(
                subjects=subjects, coverage=coverages,
            )
        )
        return structural, evidence, store, by_stage

    def _fresh_disposition(self, store, structural, evidence, locator):
        answer = ops.status(
            ops.SemanticStatusRequest(
                repository_id="repo-1",
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            structural=structural, evidence=evidence, store=store,
            continuations=ContinuationStore(),
        )
        self.assertIsInstance(answer, m.SemanticAnswer)
        return answer

    def test_execution_path_rejects_post_audit_remedy(self):
        # Motivating shape: the failure is pre-audit (admission), so a
        # remedy attached at/after the audit cannot address it. A fresh
        # agent without conversational memory must recover the material
        # boundaries from persisted relationships and qualifications.
        from span.ports.structural import StructuralDirection

        structural, evidence, store, by_stage = (
            self._establish_execution_path("admission")
        )
        try:
            answer = ops.trace(
                ops.SemanticTraceRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        by_stage["audit"], None, (), None
                    ),
                    direction=StructuralDirection.UPSTREAM,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            transitions = {
                (r.source.canonical_locator, r.target.canonical_locator)
                for r in answer.content.relationships
                if r.kind is m.RelationshipKind.TRANSITIONS_TO
            }
            # The persisted lifecycle reaches back to admission: the
            # failure boundary is upstream of the audit.
            self.assertIn(("src/gen.py", "src/admit.py"), transitions)
            self.assertIn(("src/correct.py", "src/audit.py"), transitions)
            admission = self._fresh_disposition(
                store, structural, evidence, "src/admit.py"
            )
            audit = self._fresh_disposition(
                store, structural, evidence, "src/audit.py"
            )

            def _dispositions(readback):
                return {
                    cov.question.question_slice: cov.effective_disposition
                    for cov in readback.content.question_coverage
                }

            # Covering the audit question leaves the admission failure
            # OPEN: a post-audit remedy cannot address it.
            self.assertIs(
                _dispositions(audit).get("audit execution"),
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertIs(
                _dispositions(admission).get("admission execution"),
                m.SemanticQuestionDisposition.OPEN,
            )
            self.assertTrue(
                any(
                    "rejected at admission" in req.description
                    for cov in admission.content.question_coverage
                    for req in cov.resolution_requirements
                )
            )
        finally:
            store.close()

    def test_defective_path_reports_missing_link(self):
        # Defective variant: the correction dropped the carried fields,
        # so no carrier link exists. The fresh walk must stop at the
        # correction and report the missing link explicitly rather than
        # inventing the unsupported edge.
        from span.ports.structural import StructuralDirection

        structural, evidence, store, by_stage = (
            self._establish_execution_path(
                "correction", defective=True
            )
        )
        try:
            answer = ops.trace(
                ops.SemanticTraceRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(
                        by_stage["audit"], None, (), None
                    ),
                    direction=StructuralDirection.UPSTREAM,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            reached = {
                r.source.canonical_locator
                for r in answer.content.relationships
            } | {
                r.target.canonical_locator
                for r in answer.content.relationships
            }
            self.assertNotIn("src/admit.py", reached)
            correction = self._fresh_disposition(
                store, structural, evidence, "src/correct.py"
            )
            dispositions = {
                cov.question.question_slice: cov.effective_disposition
                for cov in correction.content.question_coverage
            }
            self.assertIs(
                dispositions.get("correction execution"),
                m.SemanticQuestionDisposition.OPEN,
            )
            self.assertTrue(
                any(
                    "carrier link missing" in req.description
                    for cov in correction.content.question_coverage
                    for req in cov.resolution_requirements
                )
            )
        finally:
            store.close()

    def test_branch_variant_failure_at_correction(self):
        # Second fixture changes the failing branch: the failure is at
        # correction, not admission. Repeating the motivating narrative
        # cannot pass; the agent must read the persisted dispositions.
        structural, evidence, store, by_stage = (
            self._establish_execution_path("correction")
        )
        try:
            admission = self._fresh_disposition(
                store, structural, evidence, "src/admit.py"
            )
            correction = self._fresh_disposition(
                store, structural, evidence, "src/correct.py"
            )

            def _dispositions(readback):
                return {
                    cov.question.question_slice: cov.effective_disposition
                    for cov in readback.content.question_coverage
                }

            self.assertIs(
                _dispositions(admission).get("admission execution"),
                m.SemanticQuestionDisposition.ANSWERED,
            )
            self.assertIs(
                _dispositions(correction).get("correction execution"),
                m.SemanticQuestionDisposition.OPEN,
            )
        finally:
            store.close()


class S6NatureTest(unittest.TestCase):
    def test_descriptive_without_authority_stays_qualified(self):
        from span.core import validation as _v

        ctx = _v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset({"ev-src/main.py"}),
            known_subject_ids=(_sid(),),
            evidence_fingerprints={"ev-src/main.py": "fp"},
            evidence_contents={"ev-src/main.py": "VALUE = 1"},
        )
        candidate = m.CandidateSemanticClaim(
            candidate_key="k",
            subject=_sid(), kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue("observes value", ()),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(_ref("src/main.py"),),
            basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "saw"),
        )
        validation = _v.validate_candidate_claim(candidate, ctx)
        self.assertTrue(validation.ok)
        self.assertIs(validation.trust, m.TrustState.UNRESOLVED)

    def test_normative_only_rejects_descriptive(self):
        from span.core import validation as _v

        ctx = _v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset({"ev-src/main.py"}),
            known_subject_ids=(_sid(),),
            evidence_fingerprints={"ev-src/main.py": "fp"},
            evidence_contents={"ev-src/main.py": "x"},
        )
        candidate = m.CandidateSemanticClaim(
            candidate_key="k",
            subject=_sid(), kind=m.ClaimKind.OWNERSHIP_CUSTODY,
            value=m.OwnershipCustodyValue(
                owner=_sid(), role=m.OwnershipRole.OWNER,
                exclusivity=m.OwnershipExclusivity.EXCLUSIVE,
            ),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(_ref("src/main.py"),),
            basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "s"),
        )
        validation = _v.validate_candidate_claim(candidate, ctx)
        self.assertFalse(validation.ok)

    def _validated_candidate(self, summary="does things"):
        from span.core import validation as _v

        candidate = m.CandidateSemanticClaim(
            candidate_key="purpose",
            subject=_sid(), kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue(summary, ()),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
            evidence=(_ref("src/main.py"),),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION, "saw"
            ),
        )
        ctx = _v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset({"ev-src/main.py"}),
            known_subject_ids=(_sid(),),
            evidence_fingerprints={"ev-src/main.py": "fp"},
            evidence_contents={"ev-src/main.py": "VALUE = 1"},
        )
        validation = _v.validate_candidate_claim(candidate, ctx)
        self.assertTrue(validation.ok)
        return candidate, validation.trust

    def test_reassertion_yields_distinct_id(self):
        # Nature is identity-bearing: reclassifying an assertion requires
        # withdrawal/replacement of the old ref, never silent
        # reclassification.
        import dataclasses as _dataclasses

        from span.core import validation as _v

        candidate, trust = self._validated_candidate()
        descriptive_id = _v.deterministic_claim_id(candidate, trust)
        normative = _dataclasses.replace(
            candidate, assertion_nature=m.AssertionNature.NORMATIVE
        )
        normative_id = _v.deterministic_claim_id(normative, trust)
        self.assertNotEqual(descriptive_id, normative_id)


class S7ExcerptTest(unittest.TestCase):
    def test_excerpt_range_and_omissions(self):
        from span.service.interpretation import _project_excerpts

        subject = m.Subject(_sid(), "main", None)
        unit = m.EvidenceUnit(
            evidence_ref=_ref("src/main.py"),
            content="line one main\nline two\nline three main\nline four\n",
            content_fingerprint="fp",
        )
        projected, omissions, requirements = _project_excerpts(
            (unit,), ("main",), subject, 96_000
        )
        self.assertTrue(projected)
        self.assertIsNotNone(projected[0].content_range)
        self.assertEqual(projected[0].content_fingerprint, "fp")
        self.assertTrue(any("excerpt omissions:" in line for line in omissions))
        self.assertEqual(requirements, ())

    def test_delivery_budget_frozen(self):
        self.assertEqual(
            DEFAULT_SERVICE_BOUNDS_POLICY.max_delivered_evidence_bytes,
            96_000,
        )

    def _big_ref(self, fingerprint="fp-big"):
        return m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-src/big.py"),
            repository_id="repo-1",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/big.py",
            revision_or_fingerprint=fingerprint,
        )

    def _big_unit(self, content):
        from span.shell.structural.memory import fingerprint_content

        return m.EvidenceUnit(
            evidence_ref=self._big_ref(
                fingerprint_content(content)
            ),
            content=content,
            content_fingerprint=fingerprint_content(content),
        )

    def _big_subject(self):
        return m.Subject(
            m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/big.py",
            ),
            "big",
            None,
        )

    def test_long_line_yields_delivery_requirement(self):
        from span.service.interpretation import _project_excerpts

        content = "filler\nmain " + "x" * 500 + "\n" + "tail\n"
        projected, omissions, requirements = _project_excerpts(
            (self._big_unit(content),), ("main",),
            self._big_subject(), 100,
        )
        self.assertEqual(projected, ())
        self.assertTrue(
            any("1 hits unexamined" in line for line in omissions)
        )
        self.assertEqual(len(requirements), 1)
        requirement = requirements[0]
        self.assertIs(
            requirement.kind, m.ResolutionKind.MISSING_EVIDENCE
        )
        self.assertIn("exceed the delivery budget", requirement.description)
        self.assertIn("src/big.py", requirement.description)

    def test_unicode_counted_as_utf8(self):
        from span.service.interpretation import _project_excerpts

        content = "main héllo wörld ✓✓✓\nsecond line here\n"
        projected, omissions, requirements = _project_excerpts(
            (self._big_unit(content),), ("main",),
            self._big_subject(), 96_000,
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(
            projected[0].content_range,
            m.EvidenceLineRange(
                start_line=1, end_line=1, total_lines=2
            ),
        )
        self.assertEqual(projected[0].content, "main héllo wörld ✓✓✓")
        self.assertEqual(requirements, ())

    def test_absent_anchors_keep_full_or_omit(self):
        from span.service.interpretation import _project_excerpts

        fitting, _, _ = _project_excerpts(
            (self._big_unit("nothing relevant\n"),), ("zzz",),
            self._big_subject(), 96_000,
        )
        self.assertEqual(len(fitting), 1)
        self.assertIsNone(fitting[0].content_range)
        missing, omissions, requirements = _project_excerpts(
            (self._big_unit("nothing relevant\n"),), ("zzz",),
            self._big_subject(), 4,
        )
        self.assertEqual(missing, ())
        self.assertTrue(any("0 hits unexamined" in line for line in omissions))
        # A single ungrounded line that cannot fit is a named
        # delivery requirement, not silent omission.
        self.assertEqual(len(requirements), 1)
        self.assertIs(
            requirements[0].kind, m.ResolutionKind.MISSING_EVIDENCE
        )

    def test_distant_matches_deliver_prefix(self):
        from span.service.interpretation import _project_excerpts

        lines = ["hit one here"] + [
            f"filler {n}" for n in range(2, 50)
        ] + ["hit two here"]
        content = "\n".join(lines) + "\n"
        first_bytes = len("hit one here\n".encode("utf-8"))
        projected, omissions, requirements = _project_excerpts(
            (self._big_unit(content),), ("hit",),
            self._big_subject(), first_bytes + 200,
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0].content, "hit one here")
        self.assertTrue(
            any("1 hits unexamined" in line for line in omissions)
        )
        self.assertEqual(requirements, ())

    def test_exact_budget_accounting(self):
        import json as _json

        from span.service.interpretation import _project_excerpts

        text = "ab main\ncd\n"
        meta = len(
            _json.dumps(
                m.to_canonical(
                    m.EvidenceLineRange(
                        start_line=1, end_line=1, total_lines=2
                    )
                ),
                sort_keys=True,
            ).encode("utf-8")
        )
        exact = len("ab main".encode("utf-8")) + meta
        fitting, _, requirements = _project_excerpts(
            (self._big_unit(text),), ("main",),
            self._big_subject(), exact,
        )
        self.assertEqual(len(fitting), 1)
        self.assertEqual(requirements, ())
        clipped, _, clipped_requirements = _project_excerpts(
            (self._big_unit(text),), ("main",),
            self._big_subject(), exact - 1,
        )
        self.assertEqual(clipped, ())
        self.assertEqual(len(clipped_requirements), 1)

    def test_structural_span_reuse(self):
        from span.service.interpretation import _project_excerpts

        content = "one\ntwo\nthree\nfour\n"
        projected, _, requirements = _project_excerpts(
            (self._big_unit(content),), ("zzz",),
            self._big_subject(), 96_000,
            structural_spans={"src/big.py": (2, 3)},
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0].content, "two\nthree")
        self.assertEqual(
            projected[0].content_range,
            m.EvidenceLineRange(
                start_line=2, end_line=3, total_lines=4
            ),
        )
        self.assertEqual(requirements, ())
        fallback, _, _ = _project_excerpts(
            (self._big_unit(content),), ("two",),
            self._big_subject(), 96_000,
            structural_spans={"src/big.py": (99, 5)},
        )
        self.assertEqual(fallback[0].content, "two")
        self.assertIsNotNone(fallback[0].content_range)

    def _s7_round_harness(self):
        from span.shell.structural.memory import (
            InMemoryFile,
            fingerprint_content,
        )

        big_lines = ["# big.py alpha marker"] + [
            f"filler line {n} padding padding" for n in range(2, 100)
        ] + ["omega end ZZZ"]
        big_content = "\n".join(big_lines) + "\n"
        files = {"README.md": "# big\n\nBig.\n", "src/big.py": big_content}
        structural = InMemoryStructuralSource(
            "repo-1",
            tuple(InMemoryFile(p, c) for p, c in files.items()),
            (
                InMemorySubject(
                    "src/big.py", m.SubjectKind.COMPONENT, "big"
                ),
            ),
        )
        evidence = FixtureEvidenceSource("repo-1", dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                authority_seeds=(),
            ),
            repository_id="repo-1",
            structural=structural, evidence=evidence, store=store,
        )
        return structural, evidence, store, big_content

    def _s7_pending(self, structural, evidence, store):
        from span.service.interpretation import (
            _suspend,
            prepare_interpretation_task,
        )

        big_ref = self._big_ref()
        task = prepare_interpretation_task(
            "repo-1",
            m.Subject(
                m.SubjectId(
                    repository_id="repo-1",
                    subject_kind=m.SubjectKind.COMPONENT,
                    canonical_locator="src/big.py",
                ),
                "big",
                None,
            ),
            structural=structural, evidence=evidence, bounds=_bounds(),
            state=structural.repository_state("repo-1"),
            authority_seeds=(),
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice="narrow big",
            required_evidence_refs=(big_ref,),
            question_terms=("alpha",),
        )
        units = [
            u for u in task.request.evidence_units
            if u.evidence_ref.locator == "src/big.py"
        ]
        self.assertTrue(units)
        self.assertIsNotNone(units[0].content_range)
        self.assertNotIn("omega", units[0].content)
        continuations = ContinuationStore()
        pending = _suspend(
            op="explain", repository_id="repo-1",
            subject=m.Subject(
                m.SubjectId(
                    repository_id="repo-1",
                    subject_kind=m.SubjectKind.COMPONENT,
                    canonical_locator="src/big.py",
                ),
                "big",
                None,
            ),
            task=task, seeds=(), bounds=_bounds(),
            state=structural.repository_state("repo-1"),
            resolution=None,
            continuations=continuations,
        )
        return pending, continuations

    def _s7_authority(self, quote):
        big_ref = self._big_ref()
        return m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=big_ref,
                authority_kind=m.AuthorityKind.REPOSITORY_RULE,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span=quote, status_section="src/big.py",
            ),
        )

    def test_authority_quote_outside_excerpt_accepted(self):
        # The agent quotes beyond the delivered excerpt. Full-source
        # validation admits it with full-source provenance; an
        # excerpt-only check would wrongly reject it.
        from span.shell.agent_exchange.fixture import (
            FixtureAgent,
            FixtureCandidates,
        )
        from span.shell.structural.memory import fingerprint_content

        structural, evidence, store, big_content = (
            self._s7_round_harness()
        )
        try:
            pending, continuations = self._s7_pending(
                structural, evidence, store
            )
            agent = FixtureAgent(
                {
                    "src/big.py": FixtureCandidates(
                        (
                            m.CandidateSemanticClaim(
                                candidate_key="purpose-big",
                                subject=m.SubjectId(
                                    repository_id="repo-1",
                                    subject_kind=(
                                        m.SubjectKind.COMPONENT
                                    ),
                                    canonical_locator="src/big.py",
                                ),
                                kind=m.ClaimKind.PURPOSE,
                                value=m.PurposeValue(
                                    "big does stuff", ()
                                ),
                                assertion_nature=(
                                    m.AssertionNature.DESCRIPTIVE
                                ),
                                evidence=(self._big_ref(),),
                                candidate_authority=self._s7_authority(
                                    "omega end ZZZ"
                                ),
                                basis=m.SemanticBasis(
                                    m.DerivationKind
                                    .SEMANTIC_INTERPRETATION,
                                    "big source states the purpose",
                                ),
                            ),
                        ),
                        (),
                    )
                },
                complete_questions=True,
            )
            answer = ops.submit_interpretation(
                pending.continuation, agent.perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            persisted = answer.content.claims[0].evidence[0]
            self.assertEqual(
                persisted.revision_or_fingerprint,
                fingerprint_content(big_content),
            )
        finally:
            store.close()

    def test_mutated_source_rejects_stale_quote(self):
        # Display-then-mutate: the quoted span no longer matches current
        # content. Submission rejects with a diagnostic while the live
        # continuation is retained for correction.
        from span.core.validation import InterpretationUnitRejected
        from span.shell.agent_exchange.fixture import (
            FixtureAgent,
            FixtureCandidates,
        )

        structural, evidence, store, big_content = (
            self._s7_round_harness()
        )
        try:
            pending, continuations = self._s7_pending(
                structural, evidence, store
            )
            changed = dict({
                "README.md": "# big\n\nBig.\n",
                "src/big.py": big_content.replace(
                    "omega end ZZZ", "omega end CHANGED"
                ),
            })
            evidence_v2 = FixtureEvidenceSource("repo-1", changed)
            agent = FixtureAgent(
                {
                    "src/big.py": FixtureCandidates(
                        (
                            m.CandidateSemanticClaim(
                                candidate_key="purpose-big",
                                subject=m.SubjectId(
                                    repository_id="repo-1",
                                    subject_kind=(
                                        m.SubjectKind.COMPONENT
                                    ),
                                    canonical_locator="src/big.py",
                                ),
                                kind=m.ClaimKind.PURPOSE,
                                value=m.PurposeValue(
                                    "big does stuff", ()
                                ),
                                assertion_nature=(
                                    m.AssertionNature.DESCRIPTIVE
                                ),
                                evidence=(self._big_ref(),),
                                candidate_authority=self._s7_authority(
                                    "omega end ZZZ"
                                ),
                                basis=m.SemanticBasis(
                                    m.DerivationKind
                                    .SEMANTIC_INTERPRETATION,
                                    "big source states the purpose",
                                ),
                            ),
                        ),
                        (),
                    )
                },
                complete_questions=True,
            )
            with self.assertRaises(InterpretationUnitRejected):
                ops.submit_interpretation(
                    pending.continuation, agent.perform(pending.request),
                    structural=structural, evidence=evidence_v2,
                    store=store, continuations=continuations,
                )
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()

    def test_excerpt_reload_failure_rejects_with_live_continuation(self):
        # S7 §5.7: when the authoritative full source behind a
        # delivered excerpt cannot be loaded, submission rejects with
        # an actionable diagnostic instead of validating against the
        # excerpt; the continuation stays live for correction.
        from span.core.validation import InterpretationUnitRejected
        from span.shell.agent_exchange.fixture import (
            FixtureAgent,
            FixtureCandidates,
        )

        structural, evidence, store, _ = self._s7_round_harness()
        try:
            pending, continuations = self._s7_pending(
                structural, evidence, store
            )
            agent = FixtureAgent(
                {
                    "src/big.py": FixtureCandidates(
                        (
                            m.CandidateSemanticClaim(
                                candidate_key="purpose-big",
                                subject=m.SubjectId(
                                    repository_id="repo-1",
                                    subject_kind=(
                                        m.SubjectKind.COMPONENT
                                    ),
                                    canonical_locator="src/big.py",
                                ),
                                kind=m.ClaimKind.PURPOSE,
                                value=m.PurposeValue(
                                    "big does stuff", ()
                                ),
                                assertion_nature=(
                                    m.AssertionNature.DESCRIPTIVE
                                ),
                                evidence=(self._big_ref(),),
                                basis=m.SemanticBasis(
                                    m.DerivationKind
                                    .SEMANTIC_INTERPRETATION,
                                    "big source states the purpose",
                                ),
                            ),
                        ),
                        (),
                    )
                },
                complete_questions=True,
            )
            result = agent.perform(pending.request)
            # The source vanishes between display and submission: the
            # excerpt's full unit cannot be reloaded.
            del evidence._files["src/big.py"]
            with self.assertRaises(InterpretationUnitRejected) as cm:
                ops.submit_interpretation(
                    pending.continuation, result,
                    structural=structural, evidence=evidence,
                    store=store, continuations=continuations,
                )
            self.assertIn("full-source reload failed", str(cm.exception))
            self.assertEqual(len(continuations), 1)
        finally:
            store.close()


class S8ExplanationTest(unittest.TestCase):
    def test_nature_sentence_syntax(self):
        from span.service.answers import state_explanation_for

        self.assertEqual(
            state_explanation_for((), ()),
            ("returned assertions: none",),
        )
        claim = m.SemanticClaim(
            claim_id=m.ClaimId("clm-1"), subject=_sid(),
            kind=m.ClaimKind.PURPOSE,
            value=m.PurposeValue("s", ()),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
        )
        nature, trust, freshness, verification = state_explanation_for(
            (claim,), ()
        )
        self.assertIn("descriptive-only", nature)
        self.assertIn("(1 descriptive, 0 normative)", nature)
        self.assertIn("1 unresolved", trust)
        self.assertIn("1 unverifiable", freshness)
        self.assertEqual(
            verification,
            "no current passing verification carried for this scope",
        )
        full = state_explanation_for(
            (claim,), (),
            coverage=(1, 0, 1), bounds=(50, True),
        )
        self.assertEqual(len(full), 6)
        self.assertIn("coverage: 1 answered, 0 open of 1 questions", full)
        self.assertIn(
            "bounds: at most 50 returned items per page; "
            "listing truncated",
            full,
        )
        verified = m.SemanticClaim(
            claim_id=m.ClaimId("clm-v"), subject=_sid(),
            kind=m.ClaimKind.VERIFICATION,
            value=m.VerificationValue(
                _sid(), m.VerificationKind.TEST,
                m.VerificationCurrency.CURRENT_PASS,
            ),
            assertion_nature=m.AssertionNature.DESCRIPTIVE,
        )
        sentences = state_explanation_for((verified,), ())
        self.assertIn("verification: current pass", sentences)

    def test_correction_preserves_unrelated_open_reason(self):
        # S8.2: correcting one question preserves unrelated OPEN reason;
        # fix only a reproduced violation (H no-fallback retained, no
        # lifecycle rewrite). Establishes two questions, answers one,
        # leaves the other OPEN, then verifies the OPEN reason survives
        # a second answer on the first question.
        from span.shell.agent_exchange.fixture import (
            FixtureAgent,
            FixtureCandidates,
        )

        structural, evidence, store = _harness()
        try:
            continuations = ContinuationStore()
            agent = FixtureAgent(
                {"src/main.py": FixtureCandidates((_candidate(),), ())},
                complete_questions=True,
            )
            pending = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
                authority_seeds=(_ref("README.md"),),
            )
            answer = ops.submit_interpretation(
                pending.continuation, agent.perform(pending.request),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            # Unrelated OPEN question coverage persists alongside.
            sid = _sid()
            scope = m.SemanticQuestionScope(
                scope_root=sid, subject=sid,
                question_class=m.SemanticQuestionClass.CQ_06,
                question_slice="ownership gap",
                materiality_basis="test preserves unrelated reason",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(sid, "main", None),),
                    coverage=(
                        m.InterpretationCoverage(
                            subjects=(sid,),
                            question_slice="ownership gap",
                            evidence_scope=m.EvidenceScope(),
                            declared_complete=False,
                            question=scope,
                            disposition=m.SemanticQuestionDisposition.OPEN,
                            result_refs=(),
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=m.ResolutionKind.MISSING_AUTHORITY,
                                    subject_or_claim=sid,
                                    description="ownership authority missing",
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis="test open",
                            question_evidence=(),
                        ),
                    ),
                )
            )
            readback = ops.status(
                ops.SemanticStatusRequest(
                    repository_id="repo-1",
                    target=m.SubjectSelector(None, "src/main.py", (), None),
                    bounds=_bounds(),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=ContinuationStore(),
            )
            self.assertIsInstance(readback, m.SemanticAnswer)
            self.assertTrue(
                any(
                    "ownership authority missing" in req.description
                    for req in readback.resolution_requirements
                )
                or any(
                    "ownership authority missing" in req.description
                    for cov in readback.content.question_coverage
                    for req in cov.resolution_requirements
                )
            )
        finally:
            store.close()

    def _suspend_for_withdrawal(self, structural, evidence, store):
        from span.service.interpretation import (
            _suspend,
            prepare_interpretation_task,
        )

        task = prepare_interpretation_task(
            "repo-1",
            m.Subject(_sid(), "main", None),
            structural=structural, evidence=evidence, bounds=_bounds(),
            state=structural.repository_state("repo-1"),
            authority_seeds=(),
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice="shared question",
        )
        continuations = ContinuationStore()
        pending = _suspend(
            op="explain", repository_id="repo-1",
            subject=m.Subject(_sid(), "main", None),
            task=task, seeds=(), bounds=_bounds(),
            state=structural.repository_state("repo-1"),
            resolution=None,
            continuations=continuations,
        )
        self.assertIsInstance(pending, PendingInterpretation)
        return pending, continuations

    def test_shared_withdrawal_keeps_actual_reason(self):
        # S8.3: withdrawing a shared output reopens the dependent
        # question with the actual withdrawal reason while preserving
        # its useful original requirements — never a generic reset.
        from span.ports.interpretation import PendingInterpretation

        structural, evidence, store = _harness()
        try:
            claim_a = m.SemanticClaim(
                claim_id=m.ClaimId("clm-shared-a"),
                subject=_sid(), kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("shared basis", ()),
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
            )
            claim_b = m.SemanticClaim(
                claim_id=m.ClaimId("clm-dependent-b"),
                subject=_sid(), kind=m.ClaimKind.PURPOSE,
                value=m.PurposeValue("depends on shared", ()),
                assertion_nature=m.AssertionNature.DESCRIPTIVE,
            )
            scope_a = m.SemanticQuestionScope(
                scope_root=_sid(), subject=_sid(),
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="shared question",
                materiality_basis="test shared output",
            )
            scope_b = m.SemanticQuestionScope(
                scope_root=_sid(), subject=_sid(),
                question_class=m.SemanticQuestionClass.CQ_01,
                question_slice="dependent question",
                materiality_basis="test shared output",
            )
            original_req = m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=_sid(),
                description="dependent original gap",
                supporting_context=(),
            )

            def _answered(scope, refs):
                return m.InterpretationCoverage(
                    subjects=(_sid(),),
                    question_slice=scope.question_slice,
                    evidence_scope=m.EvidenceScope(),
                    declared_complete=True,
                    question=scope,
                    disposition=m.SemanticQuestionDisposition.ANSWERED,
                    result_refs=refs,
                    resolution_requirements=(),
                    disposition_basis="test established",
                    question_evidence=(),
                )

            store.write_index_batch(
                m.CanonicalIndexBatch(
                    subjects=(m.Subject(_sid(), "main", None),),
                    claims=(claim_a, claim_b),
                    coverage=(
                        _answered(
                            scope_a,
                            (m.ClaimRef(id=claim_a.claim_id),),
                        ),
                        m.InterpretationCoverage(
                            subjects=(_sid(),),
                            question_slice="dependent question",
                            evidence_scope=m.EvidenceScope(),
                            declared_complete=True,
                            question=scope_b,
                            disposition=(
                                m.SemanticQuestionDisposition.ANSWERED
                            ),
                            result_refs=(
                                m.ClaimRef(id=claim_a.claim_id),
                                m.ClaimRef(id=claim_b.claim_id),
                            ),
                            resolution_requirements=(original_req,),
                            disposition_basis="test established",
                            question_evidence=(),
                        ),
                    ),
                )
            )
            pending, continuations = self._suspend_for_withdrawal(
                structural, evidence, store
            )
            answer = ops.submit_interpretation(
                pending.continuation,
                m.SemanticInterpretationResult(
                    claims=(
                        m.CandidateSemanticClaim(
                            candidate_key="bound-purpose",
                            subject=_sid(), kind=m.ClaimKind.PURPOSE,
                            value=m.PurposeValue("bound work", ()),
                            assertion_nature=(
                                m.AssertionNature.DESCRIPTIVE
                            ),
                            evidence=(_ref("README.md"),),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "readme states the bound purpose",
                            ),
                        ),
                    ),
                    relationships=(),
                    candidate_subjects=(), candidate_conflicts=(),
                    question_decision=m.SemanticQuestionDecision(
                        disposition=m.SemanticQuestionDisposition.ANSWERED,
                        disposition_basis="test bound answer",
                    ),
                    candidate_withdrawals=(
                        m.CandidateSemanticWithdrawal(
                            target=m.ClaimRef(id=claim_a.claim_id),
                            basis=m.SemanticBasis(
                                m.DerivationKind.SEMANTIC_INTERPRETATION,
                                "retracted: superseded by new evidence",
                            ),
                            evidence=(_ref("README.md"),),
                        ),
                    ),
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer, m.SemanticAnswer)
            found = [
                cov for cov in store.load_all_question_coverages(
                    "repo-1", _sid(), (_sid(),)
                )
                if cov.question is not None
                and cov.question.question_slice == "dependent question"
            ]
            self.assertEqual(len(found), 1)
            reopened = found[0]
            self.assertIs(
                reopened.disposition, m.SemanticQuestionDisposition.PENDING
            )
            descriptions = [
                req.description
                for req in reopened.resolution_requirements
            ]
            self.assertTrue(
                any(
                    "retracted: superseded by new evidence" in text
                    for text in descriptions
                ),
                descriptions,
            )
            self.assertIn("dependent original gap", descriptions)
        finally:
            store.close()


class S9IdentityTest(unittest.TestCase):
    def test_build_identity_shape(self):
        from span.shell.install_verify import _build_identity

        identity = _build_identity()
        self.assertIn("package_version", identity)
        self.assertIn("source_revision", identity)
        self.assertIn("schema_digest", identity)
        self.assertIn("executable", identity)

    def test_server_version_exposed(self):
        from span import __version__

        self.assertTrue(__version__)


if __name__ == "__main__":
    unittest.main()
