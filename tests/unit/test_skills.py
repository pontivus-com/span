"""Agent Skill non-authority tests (plan Phase 4.7).

Skills are optional lifecycle guidance only. They may orchestrate the
twelve canonical operations but cannot establish or reinterpret
semantic claims, ownership, authority, precedence, trust, or
freshness. These tests pin that boundary mechanically:

- only canonical public operation names appear;
- no rule-flavored vocabulary (second authorities, scores,
  automatic lifecycle actions) appears;
- the uncertainty-preservation rule is present;
- no implementation file depends on skill content.
"""

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = (
    REPO_ROOT / "skills" / "span" / "SKILL.md",
    REPO_ROOT / "skills" / "span-change-context" / "SKILL.md",
    REPO_ROOT / "skills" / "span-document" / "SKILL.md",
)

CANONICAL_OPS = {
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


def _text(path):
    return path.read_text(encoding="utf-8")


class SkillNonAuthorityTest(unittest.TestCase):
    def test_skill_files_exist(self):
        for path in SKILLS:
            self.assertTrue(path.is_file(), path)

    def test_only_canonical_operations(self):
        for path in SKILLS:
            with self.subTest(skill=path.name):
                text = _text(path)
                mentioned = set(
                    re.findall(r"`([a-z_]+)`", text)
                ) & CANONICAL_OPS
                self.assertTrue(mentioned)
                stale = set(re.findall(r"span_[a-z_]+", text))
                self.assertEqual(stale, set())

    def test_no_rule_flavored_vocabulary(self):
        for path in SKILLS:
            with self.subTest(skill=path.name):
                lowered = _text(path).lower()
                for phrase in FORBIDDEN_PHRASES:
                    self.assertNotIn(phrase, lowered, phrase)

    def test_uncertainty_preservation_present(self):
        for path in SKILLS:
            with self.subTest(skill=path.name):
                text = _text(path)
                self.assertIn("never", text.lower())
                self.assertIn("certainty", text.lower())
                for state in ("UNRESOLVED", "STALE"):
                    self.assertIn(state, text)

    def test_span_lifecycle_lists_all_operations(self):
        text = _text(SKILLS[0])
        for op in CANONICAL_OPS:
            self.assertIn(op, text)

    def test_presubmit_review_guidance_present(self):
        # §14 paraphrase-only negative is owned by host pre-submit
        # review: the directing procedure must exist in prose and be
        # pinned here (oracles backstop wrong content, never the
        # no-knowledge-gained judgment itself).
        text = _text(SKILLS[0])
        for required in (
            "paraphrase-only",
            "leg-open",
            "before submitting",
        ):
            self.assertIn(required, text)

    def test_explicit_target_is_complete_semantic_scope(self):
        text = _text(SKILLS[0])
        for required in (
            "exact directory or repository path supplied by the user",
            "complete target scope",
            "Every contained material area",
            "no unvisited material partition",
            "fresh-session `status`/`explain` readback",
        ):
            self.assertIn(required, text)

    def test_entry_decision_comes_first(self):
        # G-I13/G-11: one canonical three-branch entry decision before
        # any SA material. Ordinary orientation is status-then-explain;
        # refresh is never routine first-contact.
        text = _text(SKILLS[0])
        entry_at = text.index("## Entry decision")
        lifecycle_at = text.index("## Operation lifecycle")
        quality_at = text.index("## Uniform semantic-quality card")
        self.assertLess(entry_at, lifecycle_at)
        self.assertLess(entry_at, quality_at)
        for required in (
            "Ordinary orientation",
            "`status` with no target, then `explain`",
            "Exact user-supplied directory plus objective",
            "`initialize_target`",
            "Post-change closeout",
            "Never `refresh` on first contact",
            "status (no target), then explain <target>",
        ):
            self.assertIn(required, text)

    def test_freshness_planes_stated(self):
        # G-11: UNVERIFIED orientation-use vs STALE refresh-before-
        # reliance, in the Reading-answers section.
        text = _text(SKILLS[0])
        for required in (
            "Two freshness planes",
            "never proves",
            "completeness or absence",
            "refresh it before relying",
            "relying on it for change",
            "dirty",
            "tree alone never stales",
        ):
            self.assertIn(required, text)

    def test_hook_scope_is_event_local_not_inventory(self):        # G §4.2c: HOOK_FAST 0/0 must never read as clean. The primary
        # skill states the event-local boundary and names NORMAL status
        # as the inventory path.
        text = _text(SKILLS[0])
        for required in (
            "event-local scope only",
            "never means the repository is clean",
            "`NORMAL` `status`",
        ):
            self.assertIn(required, text)

    def test_document_skill_preserves_target_scope_quality_bar(self):
        text = _text(SKILLS[2])
        for required in (
            "exact directory",
            "complete target boundary",
            "every material area",
            "same analysis card",
        ):
            self.assertIn(required, text)

    def test_semantic_granularity_is_architectural_not_file_count_based(self):
        text = _text(SKILLS[0])
        for required in (
            "Map level",
            "Baseline level",
            "Member-question level",
            "semantic subject per file",
            "ownership, authority, lifecycle",
            "Span subject anchors",
            "host-owned",
            "boundary",
            "Do not fabricate",
            "directory/document",
            "subject when the provider cannot resolve one",
        ):
            self.assertIn(required, text)

    def test_implementation_ignores_skills(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("skills/", content, path)
            self.assertNotIn("SKILL.md", content, path)


if __name__ == "__main__":
    unittest.main()
