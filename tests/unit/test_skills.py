"""Agent Skill non-authority and contract tests.

Skills project the required lifecycle contract. They may orchestrate the shipped
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
FUNCTIONAL_PYRAMID = REPO_ROOT / "skills" / "span-functional-pyramid" / "SKILL.md"
SKILLS = (ROUTER, BEFORE, AFTER, RECORD, FUNCTIONAL_PYRAMID)

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

    def test_router_separates_capture_from_shared_reuse(self):
        text = _text(ROUTER)
        for required in (
            "CAPTURED",
            "CURATED",
            "PendingCurationSelector",
            "shared reuse",
            "reviewer/curator",
        ):
            self.assertIn(required, text, required)

    def test_router_preserves_lifecycle_without_hook_delivery(self):
        text = _text(ROUTER).lower()
        self.assertIn("required lifecycle even", text)
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

    def test_record_skill_covers_all_record_kinds(self):
        text = _text(RECORD)
        self.assertIn('kind="understanding"', text)
        self.assertIn('kind="verification"', text)
        self.assertIn('kind="surface"', text)
        self.assertIn('kind="functional_pyramid"', text)

    def test_curation_guidance_is_present_at_the_relevant_moments(self):
        before = _text(BEFORE)
        record = _text(RECORD)
        after = _text(AFTER)
        self.assertIn("Gap/pending_curation", before)
        self.assertIn("PendingCurationSelector", before)
        self.assertIn("PendingCurationSelector", record)
        self.assertIn('"curate"', record)
        self.assertIn("CAPTURED", record)
        self.assertIn("CURATED", record)
        self.assertIn("does not change curation", after)
        self.assertIn("requires separate curation", after)

    def test_skill_prose_matches_beta3_action_and_review_contract(self):
        router = _text(ROUTER)
        before = _text(BEFORE)
        after = _text(AFTER)
        record = _text(RECORD)
        pyramid = _text(FUNCTIONAL_PYRAMID)

        self.assertIn("deactivate/exclude", router)
        self.assertIn("next_after", router)
        self.assertIn("next_after", before)
        self.assertIn("next_after", record)
        self.assertIn("surface declaration or Functional Pyramid lifecycle", record)
        self.assertNotIn("action` is used only for a", record)
        self.assertIn('"assertion_nature": "NORMATIVE"', record)
        self.assertIn("direct challenge evidence derives its context", after)
        self.assertIn("not a semantic-truth certification", after)
        self.assertIn(
            "#71-functional-pyramid-initializationadoption-lifecycle",
            pyramid,
        )

    def test_functional_pyramid_skill_covers_result_driven_lifecycle(self):
        text = _text(FUNCTIONAL_PYRAMID)
        for required in (
            "FunctionalPyramidSelector",
            "FunctionalPyramidCandidateSelector",
            "UNCONFIGURED",
            "EXCLUDED",
            "ACTIVE",
            "VALID",
            "DEGRADED",
            "REASSESSMENT_REQUIRED",
            "UNVERIFIABLE",
            "CURRENT",
            '"kind": "functional_pyramid"',
            '"action": "exclude"',
        ):
            self.assertIn(required, text, required)
        # FD-88A replaces caller-managed installation/activation. The
        # candidate contract remains for separately authorized membership changes.
        initialization = text.split("## Initialize or revise governed installation")[1]
        initialization = initialization.split(
            "## Status and explicit lifecycle operations"
        )[0]
        self.assertIn("one file per intended member", initialization)
        self.assertIn("Span owns every", initialization)
        self.assertIn("governed `span-install` form", initialization)
        self.assertIn("do not reconstruct a manual fallback workflow", initialization)
        self.assertNotIn('"action": "activate"', initialization)
        self.assertNotIn("FunctionalPyramidCandidateSelector", initialization)
        self.assertIn("Acceptance is not completion", text)
        self.assertIn("outside Span and then use `reconsider`", text)
        self.assertIn("before candidate validation", text)
        self.assertIn("Do not call `reconsider` again", text)
        self.assertIn("Semantic curation is independent", text)
        self.assertIn("does not change participation", text)


class SkillLifecycleConsistencyTest(unittest.TestCase):
    def test_every_operation_is_known(self):
        allowed = CANONICAL_OPS | {
            "repository_id",
            "context",
            "context_id",
            "request_id",
            "version",
            "understanding_id",
            "observation_id",
            "invalidated",
            "unverifiable",
            "unassessed",
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
            "challenge_id",
            "expected_challenge_revision",
            "target_conclusion_ids",
            "evidence_refs",
            "expected_boundary_version",
            "expected_version",
            "conclusion_id",
            "scope_paths",
            "next_after",
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
