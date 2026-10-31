"""Shipped MCP surface: exact tool list, routing, and typed rejections."""

from __future__ import annotations

import json
import unittest
from unittest import mock

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

EXPECTED = {
    "initialize_repository",
    "start_context",
    "understand_question",
    "understand_retrieve",
    "reassess",
    "verification_support",
    "evidence_start",
    "evidence_extend",
    "record_create",
    "record_add",
    "record_confirm",
    "record_correct",
    "record_replace",
    "record_withdraw",
    "record_challenge",
    "record_update",
    "record_verification",
    "locate",
    "neighbors",
}


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
    )


def _adapter(context):
    return McpAdapter(contexts={REPO: context})


class ToolListTest(unittest.TestCase):
    def test_exact_shipped_tool_list(self):
        self.assertEqual(set(TOOL_NAMES), EXPECTED)
        self.assertEqual(len(TOOL_NAMES), len(EXPECTED))

    def test_every_tool_has_object_request_and_result_schema(self):
        for name in EXPECTED:
            self.assertEqual(TOOL_SCHEMAS[name]["type"], "object", name)
            self.assertEqual(TOOL_OUTPUT_SCHEMAS[name]["type"], "object", name)

    def test_retired_names_are_not_registered(self):
        self.assertFalse(set(REMOVED_TOOLS) & set(TOOL_NAMES))
        self.assertEqual(
            set(REMOVED_TOOLS),
            {
                "explain",
                "trace",
                "impact",
                "authority",
                "status",
                "refresh",
                "initialize_target",
                "submit_interpretation",
            },
        )

    def test_retired_name_rejects_with_replacement_and_no_work(self):
        context = _context()
        adapter = _adapter(context)
        result = adapter.dispatch("explain", {"repository_id": REPO})
        self.assertTrue(result.is_error)
        payload = json.loads(result.content)
        self.assertEqual(payload["$type"], "ToolError")
        self.assertEqual(payload["kind"], "removed")
        self.assertIn("understand_question", payload["replacement"])
        context.lifecycle.create.assert_not_called()

    def test_unknown_tool_rejects(self):
        result = _adapter(_context()).dispatch("nope", {})
        self.assertTrue(result.is_error)
        self.assertEqual(json.loads(result.content)["kind"], "unknown_tool")


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

    def test_record_tools_map_to_one_service_method_each(self):
        mapping = {
            "record_create": "create",
            "record_add": "add",
            "record_confirm": "confirm",
            "record_correct": "correct",
            "record_replace": "replace",
            "record_withdraw": "withdraw",
            "record_challenge": "challenge",
            "record_update": "update",
            "record_verification": "verification",
        }
        for tool, method in mapping.items():
            with self.subTest(tool=tool):
                context = _context()
                result, sentinel = self._dispatch(context, tool)
                getattr(context.lifecycle, method).assert_called_once_with(sentinel)
                if method in {"challenge"}:
                    context.lifecycle.qualify_challenge.assert_called_once()
                elif method in {"verification"}:
                    context.lifecycle.qualify_verification.assert_called_once()
                else:
                    context.lifecycle.qualify_understanding.assert_called_once()

    def test_understand_and_support_tools_map_once(self):
        from types import SimpleNamespace

        request = SimpleNamespace(
            repository_id=REPO,
            understanding_id="u-1",
            version=None,
            run_id="run-1",
            context_id=SimpleNamespace(value="ctx-1"),
        )
        context = _context()
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=request),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            adapter = _adapter(context)
            adapter.dispatch("understand_question", {})
            adapter.dispatch("evidence_start", {})
            adapter.dispatch("evidence_extend", {})
            adapter.dispatch("understand_retrieve", {})
            adapter.dispatch("reassess", {})
            adapter.dispatch("verification_support", {})
        context.understand.question.assert_called_once_with(request)
        context.evidence_service.start.assert_called_once_with(request)
        context.evidence_service.extend.assert_called_once_with(request)
        context.understand.retrieve.assert_called_once_with(request)
        context.support.evaluate_version.assert_called_once_with("u-1", None)
        context.support.evaluate_verification.assert_called_once_with("run-1")

    def test_verification_support_rejects_another_repository(self):
        from types import SimpleNamespace

        context = _context()
        adapter = _adapter(context)
        with (
            mock.patch.object(
                adapter_module,
                "decode_request",
                return_value=SimpleNamespace(repository_id="other", run_id="run-1"),
            ),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            result = adapter.dispatch("verification_support", {})
        self.assertEqual(json.loads(result.content)["kind"], "validation")

    def test_routed_requests_advertise_repository_identity(self):
        cases = {
            "understand_retrieve": (
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": REPO,
                    "understanding_id": "u-1",
                },
                "UnderstandingSnapshotSelector",
            ),
            "reassess": (
                {"repository_id": REPO, "understanding_id": "u-1"},
                "ReassessRequest",
            ),
            "verification_support": (
                {"repository_id": REPO, "run_id": "run-1"},
                "VerificationSupportRequest",
            ),
            "evidence_extend": (
                {
                    "repository_id": REPO,
                    "context_id": {
                        "$type": "InvestigationContextId",
                        "value": "ctx-1",
                    },
                    "requests": [{"locator": "a.py", "ranges": []}],
                    "bounds": {
                        "max_results": 10,
                        "max_depth": 2,
                        "max_subjects": 8,
                        "max_evidence_units": 10,
                        "max_evidence_bytes": 10_000,
                        "max_candidate_claims": 64,
                        "max_candidate_relationships": 64,
                    },
                },
                "EvidenceExtendRequest",
            ),
        }
        for tool, (payload, expected) in cases.items():
            with self.subTest(tool=tool):
                schema = TOOL_SCHEMAS[tool]
                text = json.dumps(schema)
                self.assertIn("repository_id", text)
                request = decode_request(tool, payload)
                self.assertEqual(type(request).__name__, expected)
                self.assertEqual(request.repository_id, REPO)

    def test_routed_tool_without_identity_rejects(self):
        with self.assertRaisesRegex(ValueError, r"missing \$type"):
            decode_request("understand_retrieve", {"understanding_id": "u-1"})

    def test_bounds_default_is_injected(self):
        request = decode_request(
            "evidence_start",
            {
                "repository_id": REPO,
                "request_id": {"value": "r"},
                "scope": {"paths": ["a.py"], "evidence_refs": []},
                "requests": [{"locator": "a.py", "ranges": []}],
            },
        )
        self.assertEqual(request.bounds.max_results, 50)


class ErrorEnvelopeTest(unittest.TestCase):
    def test_validation_and_source_drift_are_distinct(self):
        from span.core.recording import RecordingValidationError

        context = _context()
        context.lifecycle.create.side_effect = RecordingValidationError(
            "support is not current: REASSESSMENT_REQUIRED: changed"
        )
        adapter = _adapter(context)
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=object()),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            result = adapter.dispatch("record_create", {})
        payload = json.loads(result.content)
        self.assertEqual(payload["kind"], "source_drift")
        self.assertEqual(payload["$type"], "ToolError")

    def test_conflict_maps_to_conflict(self):
        from span.core.recording import RecordingConflict

        context = _context()
        context.lifecycle.create.side_effect = RecordingConflict("already used")
        adapter = _adapter(context)
        with (
            mock.patch.object(adapter_module, "decode_request", return_value=object()),
            mock.patch.object(adapter_module, "strip_route", return_value=({}, None)),
            mock.patch.object(adapter_module, "repository_route", return_value=REPO),
        ):
            result = adapter.dispatch("record_create", {})
        self.assertEqual(json.loads(result.content)["kind"], "conflict")


if __name__ == "__main__":
    unittest.main()
