"""Shipped MCP surface: three tools, exact routing, and typed rejections."""

from __future__ import annotations

import json
import pathlib
import unittest
from unittest import mock

from span.core import model as m
from span.core.schema import record_wire as rw
from span.shell.mcp import (
    REMOVED_TOOLS,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_SCHEMAS,
    McpAdapter,
    ServiceContext,
    decode_request,
)
from span.shell.mcp import adapter as adapter_module

REPO = "surface-repo"
EXPECTED = {"ask", "record", "reconsider"}


def _context():
    return ServiceContext(
        repository_id=REPO,
        root="/repo",
        structural=mock.Mock(),
        evidence=mock.Mock(),
        store=mock.Mock(),
        lifecycle=mock.Mock(),
        evidence_service=mock.Mock(),
        understand=mock.Mock(),
        support=mock.Mock(),
        reconsider=mock.Mock(),
        answer=mock.Mock(),
    )


def _adapter(context):
    return McpAdapter(contexts={REPO: context})


class ToolListTest(unittest.TestCase):
    def test_exact_shipped_tool_list(self):
        self.assertEqual(set(TOOL_NAMES), EXPECTED)
        self.assertEqual(len(TOOL_NAMES), len(EXPECTED))

    def test_every_output_schema_is_json_serializable(self):
        for name, schema in TOOL_OUTPUT_SCHEMAS.items():
            self.assertIsInstance(json.dumps(schema), str, name)

    def test_record_exposes_the_closed_result_union(self):
        text = json.dumps(TOOL_OUTPUT_SCHEMAS["record"])
        for variant in (
            "UnderstandingRecorded",
            "VerificationRecorded",
            "SurfaceDeclared",
            "Rejected",
            "Unavailable",
        ):
            self.assertIn(variant, text)
        ask = json.dumps(TOOL_OUTPUT_SCHEMAS["ask"])
        for variant in ("Answer", "Gap", "EvidencePage", "RetrievedUnderstanding"):
            self.assertIn(variant, ask)
        reconsider = json.dumps(TOOL_OUTPUT_SCHEMAS["reconsider"])
        for variant in ("Changed", "Challenged", "Rejected", "Unavailable"):
            self.assertIn(variant, reconsider)

    def test_every_tool_has_object_request_and_result_schema(self):
        for name in EXPECTED:
            self.assertEqual(TOOL_SCHEMAS[name]["type"], "object", name)
            self.assertEqual(TOOL_OUTPUT_SCHEMAS[name]["type"], "object", name)

    def test_retired_names_are_not_registered(self):
        self.assertFalse(set(REMOVED_TOOLS) & set(TOOL_NAMES))
        for name in (
            "understand_question",
            "understand_retrieve",
            "record_create",
            "record_update",
            "record_verification",
            "start_context",
            "evidence_start",
            "initialize_repository",
        ):
            self.assertIn(name, REMOVED_TOOLS)

    def test_retired_name_rejects_with_replacement_and_no_work(self):
        context = _context()
        adapter = _adapter(context)
        result = adapter.dispatch("understand_question", {"repository_id": REPO})
        self.assertTrue(result.is_error)
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "ToolError")
        self.assertEqual(payload["kind"], "removed")
        self.assertIn("ask", payload["replacement"])
        context.answer.ask.assert_not_called()

    def test_unknown_tool_rejects(self):
        result = _adapter(_context()).dispatch("nope", {})
        self.assertTrue(result.is_error)
        self.assertEqual(json.loads(result.content)["kind"], "unknown_tool")


class ResponseBudgetTest(unittest.TestCase):
    def test_server_config_applies_the_installed_budget(self):
        from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
        from span.shell.mcp_server import ServerConfig, _policy

        default = _policy(ServerConfig(data_dir=pathlib.Path("/tmp/span")))
        self.assertEqual(
            default.max_response_bytes,
            DEFAULT_SERVICE_BOUNDS_POLICY.max_response_bytes,
        )
        configured = _policy(
            ServerConfig(data_dir=pathlib.Path("/tmp/span"), response_budget_bytes=1234)
        )
        self.assertEqual(configured.max_response_bytes, 1234)


class RoutingTest(unittest.TestCase):
    def _dispatch(self, context, tool):
        adapter = _adapter(context)
        sentinel = object()
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=sentinel),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            result = adapter.dispatch(tool, {})
        return result, sentinel

    def test_tools_map_to_one_service_method_each(self):
        mapping = {
            "ask": "ask",
            "record": "record",
            "reconsider": "reconsider",
        }
        for tool, method in mapping.items():
            with self.subTest(tool=tool):
                context = _context()
                _, sentinel = self._dispatch(context, tool)
                if tool == "ask":
                    context.answer.ask.assert_called_once_with(sentinel)
                elif tool == "record":
                    context.lifecycle.record.assert_called_once_with(sentinel)
                else:
                    context.reconsider.reconsider.assert_called_once_with(sentinel)

    def test_ask_accepts_an_exact_surface(self):
        request = decode_request(
            "ask",
            {
                "repository_id": REPO,
                "request_id": "req-1",
                "surface": {"kind": "FILE", "locator": "src/a.py"},
                "question": "What does it do?",
            },
        )
        self.assertIsInstance(request, m.AskRequest)
        assert isinstance(request, m.AskRequest)
        self.assertEqual(request.surface.kind, m.SurfaceKind.FILE)
        self.assertEqual(request.surface.locator, "src/a.py")

    def test_ask_accepts_a_continuation_without_request_id(self):
        request = decode_request(
            "ask", {"repository_id": REPO, "continuation": "span1_token"}
        )
        assert isinstance(request, m.AskRequest)
        self.assertEqual(request.continuation, "span1_token")
        self.assertIsNone(request.request_id)

    def test_record_accepts_the_flat_identity_and_actions(self):
        request = decode_request(
            "record",
            {
                "repository_id": REPO,
                "request_id": "write-1",
                "kind": "understanding",
                "surface": {"kind": "FILE", "locator": "src/a.py"},
                "question": "What does it do?",
                "scope_paths": ["src/a.py"],
                "conclusion": "It does a thing.",
                "assertion_nature": "DESCRIPTIVE",
                "locator": "src/a.py",
            },
        )
        assert isinstance(request, rw.RecordRequestWire)
        self.assertEqual(request.kind, m.RecordKind.UNDERSTANDING)
        self.assertEqual(request.request_id, "write-1")
        self.assertEqual(request.conclusion, "It does a thing.")
        self.assertEqual(request.locator, "src/a.py")

    def test_record_accepts_a_surface_declaration(self):
        request = decode_request(
            "record",
            {
                "repository_id": REPO,
                "request_id": "surface-1",
                "kind": "surface",
                "action": "create",
                "surface": {
                    "kind": "SERVICE",
                    "locator": "billing",
                    "boundary": {"paths": ["src/billing"], "symbols": []},
                    "parent": None,
                },
            },
        )
        assert isinstance(request, rw.RecordRequestWire)
        self.assertEqual(request.kind, m.RecordKind.SURFACE)
        self.assertEqual(request.action, m.SurfaceAction.CREATE)

    def test_ask_rejects_context_id(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            decode_request(
                "ask",
                {
                    "repository_id": REPO,
                    "request_id": "req-1",
                    "reference": "src/a.py",
                    "context_id": "ctx-1",
                    "question": "What?",
                },
            )

    def test_no_public_operation_accepts_a_response_budget(self):
        for name, schema in TOOL_SCHEMAS.items():
            self.assertNotIn("max_evidence_bytes", json.dumps(schema), name)
            self.assertNotIn('"bounds"', json.dumps(schema), name)


class ErrorEnvelopeTest(unittest.TestCase):
    def _dispatch(self, context, exc):
        context.lifecycle.record.side_effect = exc
        adapter = _adapter(context)
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=object()),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            return adapter.dispatch("record", {})

    def test_validation_and_source_drift_are_distinct(self):
        from span.core.recording import RecordingValidationError
        from span.core.rejection import RejectionCauseKind

        result = self._dispatch(
            _context(),
            RecordingValidationError(
                "support is not current: REASSESSMENT_REQUIRED: changed",
                cause_kind=RejectionCauseKind.SOURCE_DRIFT,
            ),
        )
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Rejected")
        self.assertFalse(result.is_error)
        self.assertEqual(payload["cause_kind"], "source_drift")
        self.assertEqual(
            payload["cause"],
            "support is not current: REASSESSMENT_REQUIRED: changed",
        )

    def test_version_conflict_names_the_current_version(self):
        from span.core.recording import RecordingConflict

        result = self._dispatch(
            _context(),
            RecordingConflict(
                "expected understanding version 1 does not match current 3",
                current_version=3,
            ),
        )
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Rejected")
        self.assertEqual(payload["cause_kind"], "version_conflict")
        self.assertEqual(payload["current_version"], 3)
        self.assertIn("current version", payload["required_action"])

    def test_surface_conflict_is_rejected_with_the_current_boundary_version(self):
        from span.core.rejection import Rejection, RejectionCauseKind

        result = self._dispatch(
            _context(),
            Rejection(
                "surface 'billing' is at boundary version 2, not 1",
                cause_kind=RejectionCauseKind.SURFACE_CONFLICT,
                current_boundary_version=2,
            ),
        )
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Rejected")
        self.assertFalse(result.is_error)
        self.assertEqual(payload["cause_kind"], "surface_conflict")
        self.assertEqual(payload["current_boundary_version"], 2)
        self.assertIsNone(payload["current_version"])

    def test_schema_version_failure_is_unavailable_not_rejected(self):
        from span.shell.sqlite_store.lifecycle import SchemaVersionError

        result = self._dispatch(_context(), SchemaVersionError("schema 9 is newer"))
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Unavailable")
        self.assertFalse(result.is_error)

    def test_replay_conflict_carries_its_own_cause(self):
        from span.core.recording import RecordingConflict
        from span.core.rejection import RejectionCauseKind

        result = self._dispatch(
            _context(),
            RecordingConflict(
                "this request identity already committed different content",
                cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
            ),
        )
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Rejected")
        self.assertEqual(payload["cause_kind"], "replay_conflict")
        self.assertIsNone(payload["current_version"])

    def test_malformed_ingress_is_a_transport_error(self):
        adapter = _adapter(_context())
        with mock.patch.object(
            adapter_module, "decode_request", side_effect=ValueError("unknown fields")
        ):
            result = adapter.dispatch("record", {})
        self.assertTrue(result.is_error)
        self.assertEqual(json.loads(result.content)["kind"], "ingress")

    def test_ingress_reason_names_no_internal_carrier(self):
        with self.assertRaises(ValueError) as raised:
            decode_request(
                "record",
                {
                    "repository_id": REPO,
                    "request_id": "r-1",
                    "kind": "understanding",
                    "action": "create",
                    "question": "What does it do?",
                    "scope_paths": ["src/a.py"],
                    "conclusion": "It does a thing.",
                    "locator": "src/a.py",
                },
            )
        message = str(raised.exception)
        self.assertNotIn("RecordRequestWire", message)
        self.assertIn("flat", message)

    def test_ask_operational_failure_is_an_unavailable_result(self):
        context = _context()
        context.answer.ask.return_value = m.Unavailable(
            operation="ask", failure="store down", recovery="retry"
        )
        adapter = _adapter(context)
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=object()),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            result = adapter.dispatch("ask", {})
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "Unavailable")
        self.assertFalse(result.is_error)

    def test_challenge_rejection_names_the_string_understanding_id(self):
        request = m.ReconsiderRequest(
            repository_id=REPO,
            challenge=m.ChallengeRaise(
                request_id="ch-1",
                understanding_id="u-1",
                target_version=1,
                target_conclusions=(
                    m.ChallengeConclusionRef(
                        understanding_id="u-1",
                        conclusion_id="c-1",
                        revision=1,
                    ),
                ),
                reason="the cited source does not support the statement",
            ),
        )
        self.assertEqual(
            adapter_module._request_identity(request),
            f"{REPO}/ch-1/u-1",
        )


if __name__ == "__main__":
    unittest.main()
