"""Surface conformance: three lifecycle tools and no internal-boundary escape.

This is the gate that fails on the retired twenty-tool surface. It checks the
registered names, the absence of per-action or internal-preflight tools, the
declared/packaged schema agreement, and the public request shapes.
"""

from __future__ import annotations

import json
import pathlib
import re
import typing
import unittest

from span.core import model as m
from span.core.schema import record_wire as rw
from span.shell.mcp import (
    REMOVED_TOOLS,
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

    def test_no_removed_name_is_registered(self):
        self.assertFalse(set(REMOVED_TOOLS) & set(TOOL_NAMES))

    def test_removed_names_name_a_live_replacement(self):
        for name, replacement in REMOVED_TOOLS.items():
            self.assertTrue(replacement)
            if name not in {
                "locate",
                "neighbors",
                "initialize_repository",
                "trace",
                "initialize_target",
            }:
                self.assertTrue(
                    any(tool in replacement for tool in CORE),
                    f"{name}: {replacement}",
                )

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

    def test_refusals_name_only_registered_operations(self):
        """A replacement must not send the caller to an unregistered tool."""
        for retired, replacement in REMOVED_TOOLS.items():
            for name in ("structure", "setup"):
                if name in replacement:
                    self.assertIn(
                        name,
                        TOOL_NAMES,
                        f"retired {retired!r} points at unregistered {name!r}",
                    )

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
        self.assertIn("§4.5", section)
        self.assertTrue(reconsider)

    def test_no_retired_tool_name_in_current_docs(self):
        captures = DOCS / "acceptance-evidence"
        changelog = REPO_ROOT / "CHANGELOG.md"
        paths = [
            REPO_ROOT / "README.md",
            *DOCS.rglob("*.md"),
            *(REPO_ROOT / "skills").rglob("*.md"),
        ]
        offenders: list[str] = []
        for path in paths:
            if path == changelog or captures in path.parents:
                continue
            retire_section = False
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if line.startswith("### Retire from"):
                    retire_section = True
                    continue
                if retire_section and line.startswith("### "):
                    retire_section = False
                if retire_section:
                    continue
                for name in REMOVED_TOOLS:
                    if f"`{name}`" in line:
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{number}: {name}"
                        )
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
