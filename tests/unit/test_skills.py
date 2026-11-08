"""Agent Skill non-authority and contract tests.

Skills are optional lifecycle guidance only. They may orchestrate the shipped
operations but cannot establish or reinterpret semantic claims, ownership,
authority, precedence, trust, or freshness.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTER = REPO_ROOT / "skills" / "span-router" / "SKILL.md"
BEFORE = REPO_ROOT / "skills" / "span-before-you-read" / "SKILL.md"
AFTER = REPO_ROOT / "skills" / "span-after-change" / "SKILL.md"
RECORD = REPO_ROOT / "skills" / "span-record" / "SKILL.md"
SKILLS = (ROUTER, BEFORE, AFTER, RECORD)

CANONICAL_OPS = {"ask", "record", "reconsider"}

FORBIDDEN_PHRASES = (
    "source of truth",
    "confidence",
    "trust score",
    "risk score",
    "severity",
    "auto-refresh",
    "automatically initialize",
    "implicitly initialize",
    "implicit bootstrap",
    "determines who owns",
    "owner is",
    "precedence order",
    "claim kind",
    "relationship kind",
)

INTERNAL_VOCABULARY = (
    "InterpretationCoverage",
    "question-result join",
    "coverage dependency storage",
    "SQLite",
    "result-ID materialization",
    "pgv:",
    "pgn:",
    "reissue_interpretation",
)


def _text(path):
    return path.read_text(encoding="utf-8")


class SkillNonAuthorityTest(unittest.TestCase):
    def test_skill_files_exist(self):
        for path in SKILLS:
            self.assertTrue(path.is_file(), path)

    def test_only_canonical_operations(self):
        for path in SKILLS:
            text = _text(path)
            mentioned = set(re.findall(r"`([a-z_]+)`", text)) & CANONICAL_OPS
            self.assertTrue(mentioned, path)
            self.assertEqual(set(re.findall(r"span_[a-z_]+", text)), set(), path)
            self.assertNotIn("semantic_", text, path)

    def test_no_rule_flavored_vocabulary(self):
        for path in SKILLS:
            lowered = _text(path).lower()
            for phrase in FORBIDDEN_PHRASES:
                self.assertNotIn(phrase, lowered, f"{path}: {phrase}")

    def test_no_internal_persistence_vocabulary(self):
        for path in SKILLS:
            text = _text(path)
            for token in INTERNAL_VOCABULARY:
                self.assertNotIn(token, text, f"{path}: {token}")

    def test_uncertainty_preservation_present_in_router(self):
        text = _text(ROUTER)
        for state in (
            "CURRENT",
            "REASSESSMENT_REQUIRED",
            "UNVERIFIABLE",
            "OPEN",
            "UNRESOLVED",
            "RESOLVED",
        ):
            self.assertIn(state, text, state)
        self.assertIn("verbatim", text.lower())

    def test_implementation_ignores_skills(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            if "shell/install" in path.as_posix():
                continue
            self.assertNotIn("skills/", path.read_text(encoding="utf-8"), path)


class RouterSkillTest(unittest.TestCase):
    def test_router_covers_the_three_moments(self):
        text = _text(ROUTER)
        for required in (
            "`ask`",
            "`record`",
            "`reconsider`",
            "exact `surface`",
            '`record(kind="surface")`',
        ):
            self.assertIn(required, text, required)

    def test_router_states_hooks_are_optional(self):
        text = _text(ROUTER).lower()
        self.assertIn("hooks are optional", text)
        self.assertIn("never record", text)

    def test_router_marks_reconsider_as_after_edit(self):
        text = _text(ROUTER).lower()
        self.assertIn("after editing", text)
        self.assertIn("before editing", text)


class SpecializedSkillTest(unittest.TestCase):
    def test_after_change_skill_covers_reconsider(self):
        text = _text(AFTER)
        self.assertIn("`reconsider`", text)
        self.assertIn("REASSESSMENT_REQUIRED", text)
        self.assertIn("CURRENT", text)

    def test_before_read_skill_covers_surface_and_continuation(self):
        text = _text(BEFORE)
        self.assertIn("AmbiguousSurface", text)
        self.assertIn("continuation", text)
        self.assertIn("`ask`", text)

    def test_record_skill_covers_all_three_kinds(self):
        text = _text(RECORD)
        self.assertIn('kind="understanding"', text)
        self.assertIn('kind="verification"', text)
        self.assertIn('kind="surface"', text)


class SkillLifecycleConsistencyTest(unittest.TestCase):
    def test_every_operation_is_known(self):
        allowed = CANONICAL_OPS | {
            "repository_id",
            "context_id",
            "request_id",
            "version",
            "understanding_id",
            "observation_id",
            "invalidated",
            "unverifiable",
            "unassessed",
            "no_match",
            "kind",
            "surface",
            "actions",
            "create",
            "add",
            "confirm",
            "correct",
            "replace",
            "withdraw",
            "challenge_dispositions",
            "expected_boundary_version",
            "expected_version",
            "conclusion_id",
            "scope_paths",
        }
        for path in SKILLS:
            text = _text(path)
            for name in set(re.findall(r"`([a-z_]+)`", text)):
                if "_" not in name:
                    continue
                self.assertIn(name, allowed, f"{path}: {name}")

    def test_record_guidance_distinguishes_scope_support_and_context(self):
        from span.shell.mcp.schemas import TOOL_SPECS

        documents = (
            _text(RECORD),
            _text(REPO_ROOT / "docs" / "mcp.md"),
            next(spec.description for spec in TOOL_SPECS if spec.name == "record"),
        )
        for text in documents:
            with self.subTest(document=text[:60]):
                lowered = text.lower()
                for term in (
                    "semantic scope",
                    "support",
                    "fixed",
                    "repository-wide",
                    "context-bound",
                ):
                    self.assertIn(term, lowered)
                self.assertIn("both may coexist", lowered)
                self.assertNotIn("either observations or evidence, not both", lowered)
                self.assertNotIn("only when the answer spans several files", lowered)

    def test_skills_are_self_contained(self):
        for path in SKILLS:
            text = _text(path)
            self.assertIn("docs/", text, path)
            self.assertIn("span", text.lower(), path)

    def test_json_examples_decode_through_the_mcp_wire(self):
        """A skill example that the server would reject is a guidance defect."""
        import json as _json

        from span.shell.mcp.wire import decode_request

        for path in SKILLS:
            text = _text(path)
            for block in re.findall(r"```json\n(.*?)```", text, re.S):
                try:
                    payload = _json.loads(block)
                except ValueError as exc:
                    self.fail(f"{path} has invalid JSON: {exc}")
                keys = set(payload)
                if {"changed_paths", "challenge"} & keys:
                    tool = "reconsider"
                elif "kind" in keys:
                    tool = "record"
                else:
                    tool = "ask"
                try:
                    decode_request(tool, payload)
                except ValueError as exc:
                    self.fail(f"{path}: example does not decode as {tool}: {exc}")


if __name__ == "__main__":
    unittest.main()
