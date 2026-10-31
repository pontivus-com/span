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
PRIMARY = REPO_ROOT / "skills" / "span" / "SKILL.md"
CHANGE = REPO_ROOT / "skills" / "span-change-context" / "SKILL.md"
DOCUMENT = REPO_ROOT / "skills" / "span-document" / "SKILL.md"
SKILLS = (PRIMARY, CHANGE, DOCUMENT)

CANONICAL_OPS = {
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

RETIRED_OPS = {
    "explain",
    "impact",
    "trace",
    "authority",
    "status",
    "refresh",
    "initialize_target",
    "submit_interpretation",
}

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
    "cont-",
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
            for retired in RETIRED_OPS:
                self.assertNotRegex(text, rf"`{retired}`", path)

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

    def test_uncertainty_preservation_present(self):
        for path in SKILLS:
            text = _text(path)
            for state in (
                "PARTIAL",
                "AMBIGUOUS",
                "CONFLICTED",
                "UNRESOLVED",
                "STALE",
                "UNVERIFIABLE",
            ):
                self.assertIn(state, text, f"{path}: {state}")
            self.assertIn("verbatim", text.lower(), path)
            self.assertIn("Missing authority stays missing", text, path)

    def test_implementation_ignores_skills(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            if "shell/install" in path.as_posix():
                continue
            self.assertNotIn("skills/", path.read_text(encoding="utf-8"), path)


class PrimarySkillTest(unittest.TestCase):
    def test_primary_covers_understand_record_reassess(self):
        text = _text(PRIMARY)
        for required in (
            "`understand_question`",
            "`evidence_start`",
            "`record_create`",
            "`record_update`",
            "`reassess`",
            "`verification_support`",
        ):
            self.assertIn(required, text, required)

    def test_primary_states_no_status_preflight(self):
        self.assertIn("No status preflight is required", _text(PRIMARY))

    def test_primary_states_hooks_are_optional(self):
        text = _text(PRIMARY).lower()
        self.assertIn("hooks are optional", text)
        self.assertIn("never", text)

    def test_primary_rejects_retired_campaign_language(self):
        text = _text(PRIMARY).lower()
        for phrase in ("campaign", "continuation", "question class", "phase 4"):
            self.assertNotIn(phrase, text, phrase)


class SpecializedSkillTest(unittest.TestCase):
    def test_change_context_defers_to_primary(self):
        text = _text(CHANGE)
        self.assertIn("Span skill", text)
        self.assertIn("reassess", text)
        self.assertIn("record_update", text)

    def test_document_skill_keeps_gap_ledger(self):
        text = _text(DOCUMENT)
        self.assertIn("gap ledger", text.lower())
        self.assertIn("understand_retrieve", text)
        self.assertIn("evidence_start", text)

    def test_specialties_do_not_restate_the_full_closeout(self):
        for path in (CHANGE, DOCUMENT):
            text = _text(path)
            self.assertLess(len(text), len(_text(PRIMARY)))


class SkillLifecycleConsistencyTest(unittest.TestCase):
    def test_every_operation_is_known(self):
        for path in SKILLS:
            text = _text(path)
            for name in set(re.findall(r"`([a-z_]+)`", text)):
                if "_" not in name:
                    continue
                allowed = (
                    CANONICAL_OPS
                    | RETIRED_OPS
                    | {
                        "repository_id",
                        "context_id",
                        "submission_id",
                        "version",
                        "understanding_id",
                        "observation_id",
                    }
                )
                self.assertIn(name, allowed, f"{path}: {name}")

    def test_skills_are_self_contained(self):
        for path in SKILLS:
            text = _text(path)
            self.assertIn("docs/", text, path)
            self.assertIn("span", text.lower(), path)


if __name__ == "__main__":
    unittest.main()
