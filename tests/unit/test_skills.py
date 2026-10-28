"""Agent Skill non-authority and contract tests.

Skills are optional lifecycle guidance only. They may orchestrate the
eleven canonical operations but cannot establish or reinterpret semantic
claims, ownership, authority, precedence, trust, or freshness.

These tests pin the contract, not the prose: operation coverage, the
required lifecycle concepts, the boundary against internal persistence
vocabulary, and the consistency of the closeout order. Exact sentences are
not pinned, so the skills can stay concise without changing behaviour.
"""

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

#: Persisted bookkeeping is Span-owned. Agent guidance names the public
#: decision and the recovery rules, never internal storage carriers.
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


def _flat(path):
    return " ".join(_text(path).split())


def _section(text, heading, following):
    start = text.index(heading)
    end = text.index(following, start)
    return text[start:end]


class SkillNonAuthorityTest(unittest.TestCase):
    def test_skill_files_exist(self):
        for path in SKILLS:
            self.assertTrue(path.is_file(), path)

    def test_only_canonical_operations(self):
        for path in SKILLS:
            with self.subTest(skill=path.parent.name):
                text = _text(path)
                mentioned = set(re.findall(r"`([a-z_]+)`", text)) & CANONICAL_OPS
                self.assertTrue(mentioned)
                self.assertEqual(set(re.findall(r"span_[a-z_]+", text)), set())

    def test_no_rule_flavored_vocabulary(self):
        for path in SKILLS:
            with self.subTest(skill=path.parent.name):
                lowered = _text(path).lower()
                for phrase in FORBIDDEN_PHRASES:
                    self.assertNotIn(phrase, lowered, phrase)

    def test_uncertainty_preservation_present(self):
        for path in SKILLS:
            with self.subTest(skill=path.parent.name):
                lowered = _text(path).lower()
                self.assertIn("never", lowered)
                self.assertIn("certainty", lowered)
                for state in ("UNRESOLVED", "STALE"):
                    self.assertIn(state, _text(path))

    def test_implementation_ignores_skills(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("skills/", content, path)
            self.assertNotIn("SKILL.md", content, path)


class PrimarySkillTest(unittest.TestCase):
    def test_every_operation_is_in_the_selection_table(self):
        text = _text(PRIMARY)
        table = _section(text, "## Operations", "## Exact target")
        for op in CANONICAL_OPS:
            with self.subTest(operation=op):
                self.assertIn(f"`{op}`", table)
        self.assertIn("There are exactly these eleven public operations", text)
        self.assertIn("no aliases", text)

    def test_identity_and_readiness_are_conditional(self):
        text = _flat(PRIMARY)
        for required in (
            "Never pass a filesystem path as",
            "canonical registered `repository_id`",
            "from MCP `tools/list`",
            "If `store_readiness` is `UNINITIALIZED`",
            "do not initialize it again",
            "`store_readiness: READY` proves operational readiness only",
        ):
            self.assertIn(required, text)

    def test_entry_branches_cover_the_three_starts(self):
        text = _flat(PRIMARY)
        for required in (
            "Ordinary orientation",
            "`explain` on the chosen target",
            "No status preflight is required",
            "Exact user-supplied directory plus objective",
            "Post-change closeout",
            "Never `refresh` on first contact",
        ):
            self.assertIn(required, text)

    def test_pending_unit_uses_the_returned_template_and_required_fields(self):
        text = _flat(PRIMARY)
        for required in (
            "request.brief.submission_rules",
            "request.task_evidence.evidence_units",
            "assertion_nature",
            "question_decision",
            "SemanticInterpretationResult",
            "canonical `EvidenceRef`",
            "paraphrase-only",
            "Before submitting",
        ):
            self.assertIn(required, text)
        # The skill must not carry a hand-maintained executable example:
        # the pending brief's template is the authority, and an example
        # here previously drifted into an invalid construction.
        self.assertNotIn("ops.submit_interpretation", text)
        self.assertNotIn("```python", _text(PRIMARY))

    def test_recovery_matrix_covers_each_outcome(self):
        text = _flat(PRIMARY)
        for required in (
            "Malformed payload",
            "Semantic validation rejection",
            "Unreadable or unverifiable evidence",
            "In-process persistence failure",
            "Successful commit",
            "Unknown, expired, lost, or consumed",
            "Post-commit response loss",
            "Crash with uncertain commit",
            "Concurrent submission or in-flight token",
            "stored recovery inputs",
            "`refresh` on the subject",
            "There is no reissue operation",
            "same continuation after correction",
        ):
            self.assertIn(required, text)

    def test_refresh_cannot_admit_a_new_question_by_proposal(self):
        text = _flat(PRIMARY)
        for required in (
            "Inside a `refresh` unit, a non-bound question is a correction nomination",
            "must already be persisted",
            "not through refresh",
        ):
            self.assertIn(required, text)

    def test_target_accounting_is_service_owned(self):
        text = _flat(PRIMARY)
        for required in (
            "complete target boundary",
            "every current inventory member",
            "Membership is never submitted",
            "first-admission",
            "target_total_count",
            "never a fabricated zero",
            "proposed_target_questions",
        ):
            self.assertIn(required, text)

    def test_freshness_planes_are_stated(self):
        text = _flat(PRIMARY)
        for required in (
            "Structural and semantic freshness are separate",
            "cannot prove completeness or absence",
            "Semantic `STALE`",
            "not current authority",
            "`CURRENT`",
        ):
            self.assertIn(required, text)

    def test_hook_scope_is_event_local_not_inventory(self):
        text = _flat(PRIMARY)
        for required in (
            "event-local scope only",
            "never means the repository is clean",
            "`NORMAL` `status`",
        ):
            self.assertIn(required, text)

    def test_closeout_order_is_explicit(self):
        text = _flat(PRIMARY)
        tests_at = text.index("external tests/review")
        refresh_at = text.index("`refresh`", tests_at)
        final_at = text.rindex("scoped `status` again")
        self.assertIn("scoped `status`", text[:tests_at])
        self.assertLess(tests_at, refresh_at)
        self.assertLess(refresh_at, final_at)
        self.assertIn("impact` is preparation, not", text)

    def test_granularity_is_meaning_based_not_file_based(self):
        text = _flat(PRIMARY)
        for required in (
            "exact target structurally",
            "coherent baseline area",
            "descend to member questions",
            "semantic subject per file",
            "ownership, authority, lifecycle",
            "host-owned",
            "fabricating a directory",
            "provider exposes only",
        ):
            self.assertIn(required, text)

    def test_primary_avoids_persistence_internal_vocabulary(self):
        text = _text(PRIMARY)
        self.assertIn("question_decision", text)
        for forbidden in INTERNAL_VOCABULARY:
            self.assertNotIn(forbidden, text, forbidden)


class SpecializedSkillTest(unittest.TestCase):
    def test_both_specialties_defer_to_the_primary(self):
        for path in (CHANGE, DOCUMENT):
            with self.subTest(skill=path.parent.name):
                text = _flat(path)
                self.assertIn("primary span skill", text.lower())
                self.assertIn("authoritative", text.lower())
                self.assertIn("primary skill's order", text)

    def test_change_context_stays_pre_change(self):
        text = _flat(CHANGE)
        for required in (
            "`impact`",
            "never approval",
            "possibility, not established impact",
            "outside tests/review",
            "do not invent a second change shape",
        ):
            self.assertIn(required, text)

    def test_document_skill_preserves_target_scope_and_gap_ledger(self):
        text = _flat(DOCUMENT)
        for required in (
            "complete target boundary",
            "every material area",
            "gap ledger",
            "host-owned",
            "do not manufacture it",
            "status(TargetId)",
            "`proposed_questions`",
        ):
            self.assertIn(required, text)


class SkillLifecycleConsistencyTest(unittest.TestCase):
    def test_target_admission_is_service_owned(self):
        for path in (PRIMARY, DOCUMENT):
            text = _flat(path)
            with self.subTest(skill=path.parent.name):
                self.assertNotIn("Admit each new material area with", text)
                self.assertIn("first-admission", text)
        self.assertIn("do not manufacture it", _flat(DOCUMENT))

    def test_specialties_do_not_restate_the_full_closeout(self):
        # One closeout order lives in the primary. Specialties point to it
        # rather than maintaining a second copy that can drift.
        for path in (CHANGE, DOCUMENT):
            with self.subTest(skill=path.parent.name):
                self.assertIn("primary skill's order", _flat(path))

    def test_no_obsolete_coverage_inventory_gap_tolerance(self):
        for path in (
            PRIMARY,
            REPO_ROOT / "docs" / "skills.md",
            REPO_ROOT / "docs" / "agents-snippet.md",
        ):
            text = _text(path)
            with self.subTest(document=path.name):
                self.assertNotIn("coverage-inventory gap", text)
                self.assertNotIn("Point 4 activation gap", text)


if __name__ == "__main__":
    unittest.main()
