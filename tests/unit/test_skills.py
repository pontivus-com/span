"""Agent Skill non-authority tests (plan Phase 4.7).

Skills are optional lifecycle guidance only. They may orchestrate the
eleven canonical operations but cannot establish or reinterpret
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
                mentioned = set(re.findall(r"`([a-z_]+)`", text)) & CANONICAL_OPS
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

    def test_primary_quick_reference_selects_each_operation(self):
        text = _text(SKILLS[0])
        table_start = text.index("### Operation selection")
        table_end = text.index("`initialize_repository` is not routine", table_start)
        table = text[table_start:table_end]
        for op in CANONICAL_OPS:
            with self.subTest(operation=op):
                self.assertIn(f"`{op}`", table)
        self.assertIn("There are no semantic aliases", text)

    def test_repository_identity_and_initialization_are_conditional(self):
        text = _text(SKILLS[0])
        for required in (
            "Never pass a filesystem path as",
            "canonical registered ID",
            "from MCP `tools/list`",
            "If `store_readiness` is `UNINITIALIZED`",
            "do not initialize it again",
            "`store_readiness: READY` proves operational readiness only",
        ):
            self.assertIn(required, text)

    def test_continuation_recovery_matrix_preserves_ownership(self):
        text = _text(SKILLS[0])
        matrix_start = text.index("## Continuation recovery")
        matrix_end = text.index("## Freshness, authority, and closeout", matrix_start)
        matrix = text[matrix_start:matrix_end]
        for required in (
            "Malformed submit payload",
            "Semantic validation rejection",
            "Unreadable or unverifiable evidence rejection",
            "In-process persistence failure",
            "Successful commit",
            "Unknown, expired, lost, or already consumed continuation",
            "Post-commit response loss",
            "Process crash with uncertain commit",
            "Concurrent submission or in-flight token",
            "There is no reissue operation",
            "same continuation after correction",
            "original",
            "idempotent operation",
        ):
            self.assertIn(required, matrix)

    def test_submission_example_uses_existing_typed_contract(self):
        text = _text(SKILLS[0])
        for required in (
            "Worked typed submission excerpt",
            "request.evidence_units[0].evidence_ref",
            "CandidateSemanticClaim",
            "SemanticQuestionDecision",
            "SemanticInterpretationResult",
            "question_decision",
            "ops.submit_interpretation",
            "same typed result is the MCP submit payload",
        ):
            self.assertIn(required, text)

    def test_lifecycle_reference_matches_primary_heading(self):
        lifecycle = _text(REPO_ROOT / "docs" / "lifecycle.md")
        primary = _text(SKILLS[0])
        self.assertIn("Freshness, authority, and closeout", lifecycle)
        self.assertIn("## Freshness, authority, and closeout", primary)

    def test_submission_and_target_accounting_guidance_is_canonical(self):
        text = _text(SKILLS[0])
        for required in (
            "canonical `EvidenceRef`",
            "evidence_units",
            "provider-backed evidence",
            "SemanticInterpretationResult",
            "proposed_target_inventory_accounting",
            "proposed_questions",
            "proposed_target_questions",
            "exact same persisted question scope",
            "explicit mapping requirement",
            "NOT_APPLICABLE",
            "stale_only=False",
            "exact `SubjectSelector`",
        ):
            self.assertIn(required, text)

    def test_primary_preserves_agent_judgment_and_uncertainty(self):
        text = _text(SKILLS[0])
        for required in (
            "does not make a wrong interpretation correct",
            "Missing authority",
            "contradictions",
            "OPEN`/`PENDING",
            "Span never",
            "impact` is preparation, not",
        ):
            self.assertIn(required, text)

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
            "exact directory supplied by the user",
            "complete target boundary",
            "every current inventory member",
            "fresh `status`/`explain` readback",
        ):
            self.assertIn(required, text)

    def test_entry_decision_comes_first(self):
        # One canonical three-branch entry decision follows the quick
        # reference. Ordinary orientation starts with the needed operation;
        # refresh is never routine first-contact.
        text = _text(SKILLS[0])
        quick_ref_at = text.index("## Agent quick reference")
        entry_at = text.index("## Entry decision")
        self.assertLess(quick_ref_at, entry_at)
        for required in (
            "Ordinary orientation",
            "`explain` on the chosen target",
            "no status preflight",
            "Exact user-supplied directory plus objective",
            "`initialize_target`",
            "Post-change closeout",
            "Never `refresh` on first contact",
        ):
            self.assertIn(required, text)

    def test_freshness_planes_stated(self):
        # Structural orientation evidence and semantic decision currency
        # remain distinct.
        text = _text(SKILLS[0])
        for required in (
            "Structural and semantic freshness are separate",
            "cannot prove completeness or absence",
            "Semantic `STALE`",
            "not current authority",
            "`CURRENT`",
        ):
            self.assertIn(required, text)

    def test_hook_scope_is_event_local_not_inventory(self):
        # HOOK_FAST is event-local, not the inventory path.
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
            "primary skill's shared card",
        ):
            self.assertIn(required, text)

    def test_semantic_granularity_is_architectural_not_file_count_based(self):
        text = _text(SKILLS[0])
        for required in (
            "map the exact target structurally",
            "establish a\ncoherent baseline area",
            "descend to member questions",
            "semantic subject per file",
            "ownership, authority, lifecycle",
            "host-owned",
            "boundary",
            "do not fabricate a directory/document subject",
            "provider exposes only",
        ):
            self.assertIn(required, text)

    def test_primary_avoids_persistence_internal_vocabulary(self):
        # Addendum M M-09/M-12: persisted coverage bookkeeping is
        # Span-owned. Ordinary agent guidance names the public
        # question_decision and the recovery rules, never internal
        # storage carriers, token grammars, or a reissue operation.
        text = _text(SKILLS[0])
        self.assertIn("question_decision", text)
        for forbidden in (
            "InterpretationCoverage",
            "question-result join",
            "coverage dependency storage",
            "SQLite",
            "result-ID materialization",
            "pgq:",
            "pgv:",
            "pgn:",
            "cont-",
            "reissue_interpretation",
        ):
            self.assertNotIn(forbidden, text, forbidden)

    def test_implementation_ignores_skills(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("skills/", content, path)
            self.assertNotIn("SKILL.md", content, path)


class SkillLifecycleConsistencyTest(unittest.TestCase):
    """One lifecycle protocol, stated the same way in every skill."""

    def _normalized(self, path):
        return " ".join(_text(path).split())

    def test_target_admission_is_service_owned_in_all_skills(self):
        # A new material area is admitted through target inventory
        # accounting; Span creates the first-admission CQ-01 seed. No
        # skill may send the agent back to manufacturing that question.
        for path in SKILLS:
            text = self._normalized(path)
            with self.subTest(skill=path.name):
                self.assertNotIn("Admit each new material area with", text)
                self.assertNotIn("proposed_questions` entry for a new area", text)
        for path in (SKILLS[0], SKILLS[2]):
            text = self._normalized(path)
            with self.subTest(skill=path.name):
                self.assertIn("Span creates the", text)
                self.assertIn("first-admission", text)
        self.assertIn("do not manufacture it", self._normalized(SKILLS[2]))

    def test_closeout_order_is_consistent_in_all_skills(self):
        # edit -> scoped status -> external tests/review -> scoped
        # refresh and submit -> scoped status again.
        for path in SKILLS:
            text = self._normalized(path)
            with self.subTest(skill=path.name):
                tests_at = text.index("external tests/review")
                refresh_at = text.index("`refresh`", tests_at)
                final_at = text.rindex("scoped `status` again")
                self.assertIn("scoped `status`", text[:tests_at])
                self.assertLess(tests_at, refresh_at)
                self.assertLess(refresh_at, final_at)

    def test_no_obsolete_coverage_inventory_gap_tolerance(self):
        # Readiness-only output is event-local by design (HOOK_FAST),
        # never a tolerated coverage-inventory gap on normal calls.
        for path in (
            SKILLS[0],
            REPO_ROOT / "docs" / "skills.md",
            REPO_ROOT / "docs" / "agents-snippet.md",
        ):
            text = _text(path)
            with self.subTest(document=path.name):
                self.assertNotIn("coverage-inventory gap", text)
                self.assertNotIn("Point 4 activation gap", text)


if __name__ == "__main__":
    unittest.main()
