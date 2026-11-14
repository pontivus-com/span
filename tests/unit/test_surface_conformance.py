"""Surface conformance: three lifecycle tools and no internal-boundary escape.

This gate checks the registered names, the absence of per-action or
internal-preflight tools, the declared/packaged schema agreement, and the
public request shapes.
"""

from __future__ import annotations

import json
import pathlib
import re
import typing
import unittest

from jsonschema import Draft202012Validator

from span.core import model as m
from span.core.schema import record_wire as rw
from span.shell.mcp import (
    TOOL_EXAMPLES,
    TOOL_NAMES,
    TOOL_OUTPUT_SCHEMAS,
    TOOL_REQUEST_TYPES,
    TOOL_SCHEMAS,
    decode_request,
)

CORE = {"ask", "record", "reconsider"}
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


def _backticked(text: str) -> set[str]:
    return set(re.findall(r"`([A-Z][A-Za-z0-9]+)`", text))


def _runtime_union(alias: object) -> set[str]:
    return {member.__name__ for member in typing.get_args(alias)}


def _fd38_section() -> str:
    doc = (DOCS / "functional-design.md").read_text(encoding="utf-8")
    return doc.split("**FD-38 — Closed unions.**", 1)[1].split("**FD-39", 1)[0]


def _lifecycle_ask_union() -> set[str]:
    doc = (DOCS / "lifecycle-contract.md").read_text(encoding="utf-8")
    section = doc.split("**The agent receives** exactly one of:", 1)[1]
    names: set[str] = set()
    for line in section.splitlines():
        if not line.startswith("| `"):
            if names:
                break
            continue
        names.add(line.split("|")[1].strip().strip("`"))
    return names


def _mcp_record_union() -> set[str]:
    doc = (DOCS / "mcp.md").read_text(encoding="utf-8")
    for chunk in doc.split("Results:"):
        if "UnderstandingRecorded" in chunk:
            return _backticked(chunk.split(".", 1)[0])
    raise AssertionError("the record Results declaration is missing")


class SurfaceConformanceTest(unittest.TestCase):
    def test_only_the_three_core_tools_are_registered(self):
        self.assertEqual(set(TOOL_NAMES), CORE)

    def test_no_per_action_or_preflight_tool_is_registered(self):
        forbidden_fragments = (
            "record_",
            "evidence_",
            "_context",
            "understand_",
            "reassess",
            "verification_support",
            "initialize_",
        )
        for name in TOOL_NAMES:
            for fragment in forbidden_fragments:
                self.assertNotIn(fragment, name, name)

    def test_declared_and_packaged_request_types_agree(self):
        for name in TOOL_NAMES:
            self.assertIn(name, TOOL_REQUEST_TYPES)
            self.assertIn(name, TOOL_SCHEMAS)
            self.assertIn(name, TOOL_OUTPUT_SCHEMAS)

    def test_ask_has_no_context_input(self):
        text = json.dumps(TOOL_SCHEMAS["ask"])
        self.assertNotIn("context_id", text)
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            decode_request(
                "ask",
                {
                    "repository_id": "r",
                    "request_id": "q",
                    "reference": "a.py",
                    "context_id": "ctx",
                    "question": "Why?",
                },
            )

    def test_record_is_one_request_with_kind_and_actions(self):
        schema = TOOL_SCHEMAS["record"]
        text = json.dumps(schema)
        self.assertIn('"kind"', text)
        self.assertIn('"actions"', text)
        self.assertIn('"conclusion"', text)
        self.assertNotIn("record_create", text)
        request = decode_request(
            "record",
            {
                "repository_id": "r",
                "request_id": "w",
                "kind": "understanding",
                "surface": {"kind": "FILE", "locator": "a.py"},
                "question": "Why?",
                "scope_paths": ["a.py"],
                "conclusion": "Because.",
                "locator": "a.py",
            },
        )
        self.assertIsInstance(request, rw.RecordRequestWire)

    def test_ask_exposes_exact_surface_and_continuation(self):
        schema = TOOL_SCHEMAS["ask"]
        text = json.dumps(schema)
        for field in ("surface", "reference", "continuation", "selector"):
            self.assertIn(field, text)

    def test_reconsider_takes_paths_or_a_challenge(self):
        schema = TOOL_SCHEMAS["reconsider"]
        text = json.dumps(schema)
        self.assertIn("changed_paths", text)
        self.assertIn("challenge", text)

    def test_result_unions_are_closed(self):
        self.assertIn(
            m.RetrievedUnderstanding, set(__import__("typing").get_args(m.AskResult))
        )
        self.assertIn(
            m.SurfaceDeclared, set(__import__("typing").get_args(m.RecordResult))
        )

    def test_request_examples_decode(self):
        for name, examples in TOOL_EXAMPLES.items():
            self.assertTrue(examples, name)
            for example in examples:
                try:
                    decode_request(name, example)
                except ValueError as exc:
                    self.fail(f"{name} example does not decode: {exc}")

    def test_contract_action_vocabulary_matches_the_wire(self):
        """Layer 2's action vocabulary is the wire's, not a second copy."""
        import dataclasses as _dc

        text = (DOCS / "lifecycle-contract.md").read_text(encoding="utf-8")
        wire = {field.name for field in _dc.fields(rw.RecordActionsWire)}
        sentence = re.search(
            r"An update carries `actions`, an object\s+whose keys are (.+?)\.",
            text,
            re.S,
        )
        self.assertIsNotNone(sentence, "layer 2 no longer states the actions object")
        stated = set(re.findall(r"`([a-z_]+)`", sentence.group(1)))
        self.assertEqual(stated, wire)
        table = re.search(
            r"\| Action \| Meaning \|\n\|[^\n]*\|\n((?:\| `[a-z_]+` \|.*\n)+)",
            text,
        )
        self.assertIsNotNone(table, "layer 2 no longer has the action table")
        tabulated = set(re.findall(r"^\| `([a-z_]+)` \|", table.group(1), re.M))
        self.assertEqual(tabulated, wire)

    def test_public_record_grammar_derives_new_identities(self):
        """F7/L7: the caller selects existing objects, never creates new IDs."""
        schema = TOOL_SCHEMAS["record"]
        properties = schema["properties"]
        defs = schema["$defs"]
        self.assertNotIn("conclusion_id", properties)
        self.assertNotIn("scope_evidence_refs", properties)
        self.assertIn("expected_version", properties)
        add = defs["AddConclusion"]["properties"]
        self.assertNotIn("conclusion_id", add)
        self.assertNotIn("scope_evidence_refs", add)
        replace = defs["ReplaceConclusion"]["properties"]
        self.assertNotIn("new_conclusion_id", replace)
        self.assertNotIn("scope_evidence_refs", replace)
        for name in (
            "ConfirmConclusion",
            "CorrectConclusion",
            "ReplaceConclusion",
            "WithdrawConclusion",
        ):
            self.assertIn("conclusion_id", defs[name]["properties"])
        with self.assertRaisesRegex(ValueError, "expected_version"):
            decode_request(
                "record",
                {
                    "repository_id": "r",
                    "request_id": "u",
                    "kind": "understanding",
                    "understanding_id": "u-1",
                    "actions": {"add": [{"conclusion": "X.", "locator": "a.py"}]},
                },
            )
        self.assertEqual(set(TOOL_NAMES), CORE)

    def test_record_description_carries_every_call_template(self):
        text = TOOL_SCHEMAS["record"]["description"]
        for marker in (
            "CREATE TEMPLATE",
            "UPDATE TEMPLATE",
            "SURFACE TEMPLATE",
            "VERIFICATION TEMPLATE",
        ):
            self.assertIn(marker, text)

    def test_public_metadata_matches_the_package_version(self):
        from span import __version__

        server = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
        self.assertEqual(server["version"], __version__)
        self.assertEqual(server["packages"][0]["version"], __version__)
        self.assertLessEqual(len(server["description"]), 100)
        for name in (
            "README.md",
            "docs/overview.md",
            "docs/install.md",
            "docs/mcp.md",
            "docs/usage.md",
        ):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("0.9 candidate", text, name)
            self.assertNotIn("0.10 candidate", text, name)

    def test_schema_and_decoder_agree_on_pure_surface_obtain(self):
        payload = {
            "repository_id": "r",
            "surface": {"kind": "FILE", "locator": "a.py"},
        }
        errors = list(Draft202012Validator(TOOL_SCHEMAS["ask"]).iter_errors(payload))
        self.assertEqual(errors, [])
        request = decode_request("ask", payload)
        self.assertIsInstance(request, m.AskRequest)

    def test_schema_and_decoder_agree_on_conflicting_evidence_modes(self):
        payload = {
            "repository_id": "r",
            "request_id": "w",
            "kind": "understanding",
            "question": "Why?",
            "scope_paths": ["a.py"],
            "conclusion": "Because.",
            "locator": "a.py",
            "observation_id": "obs-1",
        }
        errors = list(Draft202012Validator(TOOL_SCHEMAS["record"]).iter_errors(payload))
        self.assertTrue(errors, "schema must reject mutually exclusive evidence modes")
        with self.assertRaises(ValueError):
            decode_request("record", payload)

    def test_t03_schema_and_decoder_equivalence_matrix(self):
        challenge = {
            "request_id": "challenge-1",
            "understanding_id": "u-1",
            "target_version": 1,
            "target_conclusions": [
                {
                    "understanding_id": "u-1",
                    "conclusion_id": "c-1",
                    "revision": 1,
                }
            ],
            "reason": "Source changed.",
        }
        bound_challenge = {
            **challenge,
            "context": {
                "repository_id": "r",
                "context_id": {"value": "ctx-1"},
            },
        }
        valid_create = {
            "repository_id": "r",
            "request_id": "w",
            "kind": "understanding",
            "question": "Why?",
            "scope_paths": ["a.py"],
            "conclusion": "Because.",
            "locator": "a.py",
        }
        cases = (
            ("ask-empty", "ask", {}, False),
            (
                "ask-admission-needs-request-id",
                "ask",
                {
                    "repository_id": "r",
                    "surface": {"kind": "FILE", "locator": "a.py"},
                    "evidence": [{"locator": "a.py"}],
                },
                False,
            ),
            (
                "ask-empty-admission",
                "ask",
                {
                    "repository_id": "r",
                    "request_id": "q",
                    "surface": {"kind": "FILE", "locator": "a.py"},
                    "evidence": [],
                },
                False,
            ),
            (
                "ask-selector-rejects-repository-override",
                "ask",
                {
                    "repository_id": "r",
                    "selector": {
                        "$type": "RecordedQuestionSelector",
                        "repository_id": "r",
                        "surface": {"kind": "FILE", "locator": "a.py"},
                        "question": "Why?",
                    },
                },
                False,
            ),
            (
                "ask-surface-rejects-embedded-repository",
                "ask",
                {
                    "repository_id": "r",
                    "surface": {
                        "repository_id": "r",
                        "kind": "FILE",
                        "locator": "a.py",
                    },
                },
                False,
            ),
            ("reconsider-empty", "reconsider", {}, False),
            (
                "reconsider-changed-scope-needs-repository",
                "reconsider",
                {"changed_paths": ["a.py"]},
                False,
            ),
            (
                "reconsider-context-challenge-rejects-repository-override",
                "reconsider",
                {"repository_id": "r", "challenge": bound_challenge},
                False,
            ),
            (
                "reconsider-direct-challenge-needs-repository",
                "reconsider",
                {"challenge": challenge},
                False,
            ),
            (
                "record-update-needs-effect",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "understanding",
                    "understanding_id": "u-1",
                    "expected_version": 1,
                    "actions": {},
                },
                False,
            ),
            (
                "record-path-surface-is-not-declarable",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "surface",
                    "action": "create",
                    "surface": {"kind": "FILE", "locator": "a.py"},
                },
                False,
            ),
            (
                "record-declared-surface-needs-boundary",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "surface",
                    "action": "create",
                    "surface": {"kind": "SERVICE", "locator": "svc"},
                },
                False,
            ),
            (
                "record-empty-request-id",
                "record",
                {**valid_create, "request_id": ""},
                False,
            ),
            (
                "record-empty-conclusion",
                "record",
                {**valid_create, "conclusion": ""},
                False,
            ),
            (
                "ask-null-defaults-match-omission",
                "ask",
                {
                    "repository_id": "r",
                    "request_id": None,
                    "surface": {"kind": "FILE", "locator": "a.py"},
                    "evidence": None,
                },
                True,
            ),
            (
                "ask-selector-empty-question",
                "ask",
                {
                    "selector": {
                        "$type": "RecordedQuestionSelector",
                        "repository_id": "r",
                        "surface": {"kind": "FILE", "locator": "a.py"},
                        "question": "",
                    }
                },
                False,
            ),
            (
                "ask-selector-rejects-embedded-surface-repository",
                "ask",
                {
                    "selector": {
                        "$type": "RecordedQuestionSelector",
                        "repository_id": "r",
                        "surface": {
                            "repository_id": "r",
                            "kind": "FILE",
                            "locator": "a.py",
                        },
                        "question": "Why?",
                    }
                },
                False,
            ),
            (
                "reconsider-null-challenge-matches-default",
                "reconsider",
                {
                    "repository_id": "r",
                    "changed_paths": ["a.py"],
                    "challenge": None,
                },
                True,
            ),
            (
                "record-context-bound-rejects-repository-override",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "understanding",
                    "context": {
                        "repository_id": "r",
                        "context_id": {"value": "ctx-1"},
                    },
                    "conclusion": "Because.",
                    "locator": "a.py",
                },
                False,
            ),
            (
                "record-context-bound-null-repository-matches-omission",
                "record",
                {
                    "repository_id": None,
                    "request_id": "w",
                    "kind": "understanding",
                    "context": {
                        "repository_id": "r",
                        "context_id": {"value": "ctx-1"},
                    },
                    "conclusion": "Because.",
                    "locator": "a.py",
                },
                True,
            ),
            (
                "record-unknown-surface-kind",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "UNKNOWN",
                        "locator": "svc",
                        "boundary": {"paths": ["src"], "symbols": []},
                    },
                },
                False,
            ),
            (
                "ask-explicit-admission",
                "ask",
                {
                    "repository_id": "r",
                    "request_id": "q",
                    "surface": {"kind": "FILE", "locator": "a.py"},
                    "evidence": [{"locator": "a.py"}],
                },
                True,
            ),
            (
                "reconsider-changed-scope",
                "reconsider",
                {"repository_id": "r", "changed_paths": ["a.py"]},
                True,
            ),
            (
                "record-declared-surface",
                "record",
                {
                    "repository_id": "r",
                    "request_id": "w",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "svc",
                        "boundary": {"paths": ["src"], "symbols": []},
                    },
                },
                True,
            ),
        )
        for label, tool, payload, accepted in cases:
            with self.subTest(label=label):
                errors = list(
                    Draft202012Validator(TOOL_SCHEMAS[tool]).iter_errors(payload)
                )
                if accepted:
                    self.assertEqual(errors, [])
                    decode_request(tool, payload)
                else:
                    self.assertTrue(errors, "schema unexpectedly accepted payload")
                    with self.assertRaises(ValueError):
                        decode_request(tool, payload)

    def test_public_discriminator_values_do_not_expose_wire_class_names(self):
        def tag_values(node):
            if isinstance(node, dict):
                if "$type" in node and isinstance(node["$type"], dict):
                    value = node["$type"].get("const")
                    if isinstance(value, str):
                        yield value
                for value in node.values():
                    yield from tag_values(value)
            elif isinstance(node, list):
                for value in node:
                    yield from tag_values(value)

        values = {
            value
            for schema in (*TOOL_SCHEMAS.values(), *TOOL_OUTPUT_SCHEMAS.values())
            for value in tag_values(schema)
        }
        self.assertTrue(values)
        self.assertFalse(
            [value for value in values if value.endswith("Wire")],
            "public discriminator vocabulary must not expose runtime wire class names",
        )

    def test_result_union_declarations_agree(self):
        ask = _runtime_union(m.AskResult)
        record = _runtime_union(m.RecordResult)
        reconsider = _runtime_union(m.ReconsiderResult)
        self.assertEqual(_lifecycle_ask_union(), ask)
        self.assertEqual(_mcp_record_union(), record)
        # FD-38 owns the invariant, not a second copy of the unions.
        section = _fd38_section()
        self.assertNotIn("`ask` →", section)
        self.assertNotIn("`record` →", section)
        self.assertIn("§4.1", section)
        self.assertIn("§4.3", section)
        self.assertTrue(reconsider)


if __name__ == "__main__":
    unittest.main()
