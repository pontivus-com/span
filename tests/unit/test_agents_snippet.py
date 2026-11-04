"""AGENTS.md lifecycle-block governance tests (plan §3.5).

The lifecycle block is orchestration guidance only. It may tell an
agent when/how to invoke the eleven canonical operations but defines
no semantic rules. The single canonical source is
docs/agents-snippet.md; the installer copies it verbatim between
span markers and never parses it for decisions.
"""

import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "docs" / "agents-snippet.md"

sys.path.insert(0, str(REPO_ROOT / "src"))

from span.shell import install

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


def _text(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


class AgentsSnippetTest(unittest.TestCase):
    def test_snippet_exists_with_heading(self):
        self.assertTrue(SNIPPET.is_file(), SNIPPET)
        self.assertIn("## Span lifecycle", _text(SNIPPET))

    def test_lists_all_canonical_operations(self):
        text = _text(SNIPPET)
        for op in CANONICAL_OPS:
            self.assertIn(op, text, op)

    def test_only_canonical_operations(self):
        text = _text(SNIPPET)
        mentioned = set(re.findall(r"`([a-z_]+)`", text)) & CANONICAL_OPS
        self.assertTrue(mentioned)
        self.assertEqual(set(re.findall(r"span_[a-z_]+", text)), set())
        self.assertNotIn("semantic_", text)

    def test_no_rule_flavored_vocabulary(self):
        lowered = _text(SNIPPET).lower()
        for phrase in FORBIDDEN_PHRASES:
            self.assertNotIn(phrase, lowered, phrase)

    def test_recovery_guidance_present(self):
        text = _text(SNIPPET)
        self.assertIn("continuation", text)
        self.assertIn("never fetch a context id", text)

    def test_no_match_recovery_present(self):
        text = _text(SNIPPET)
        self.assertIn("no_match", text)
        self.assertIn("without a question", text)

    def test_docs_pointer_present(self):
        text = _text(SNIPPET)
        for required in (
            "docs/mcp.md",
            "skills/span-router/SKILL.md",
        ):
            self.assertIn(required, text, required)

    def test_entry_guidance_uses_direct_operation(self):
        text = _text(SNIPPET)
        self.assertIn("Before `Read`/`Grep`", text)
        self.assertIn("`ask`", text)
        self.assertIn("`record`", text)

    def test_managed_block_carries_lifecycle_hard_rules(self):
        text = _text(SNIPPET)
        for required in (
            "Before `Read`/`Grep`",
            "After editing",
            "After establishing a conclusion",
            "continuation",
        ):
            self.assertIn(required, text, required)
        for forbidden in (
            "reissue_interpretation",
            "pgv:",
            "pgn:",
            "cont-*",
            "CQ-01",
            "initialize_target",
        ):
            self.assertNotIn(forbidden, text)

    def test_implementation_ignores_snippet(self):
        for path in (REPO_ROOT / "src").rglob("*.py"):
            if "shell/install" in path.as_posix():
                continue
            self.assertNotIn("agents-snippet", path.read_text(encoding="utf-8"), path)


class AgentsRuleDeployTest(unittest.TestCase):
    def _run(self, span_repo, target):
        return install.ensure_agents_rule(span_repo, target, dry_run=False)

    def test_deploys_verbatim_and_converges(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            first = self._run(REPO_ROOT, target)
            self.assertEqual(first["status"], "wired")
            dst = target / "AGENTS.md"
            content = dst.read_text(encoding="utf-8")
            self.assertIn(install.AGENTS_START, content)
            self.assertIn(install.AGENTS_END, content)
            inner = (
                content.split(install.AGENTS_START)[1]
                .split(install.AGENTS_END)[0]
                .strip("\n")
            )
            self.assertEqual(inner, _text(SNIPPET).rstrip("\n"))
            self.assertIn("Before `Read`/`Grep`", inner)
            self.assertFalse(dst.with_name("AGENTS.md.bak-span").exists())
            second = self._run(REPO_ROOT, target)
            self.assertEqual(second["status"], "converged")
            self.assertEqual(dst.read_text(encoding="utf-8"), content)

    def test_appends_to_existing_file_without_extra_artifacts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            dst = target / "AGENTS.md"
            dst.write_text("# Existing\n", encoding="utf-8")
            other = target / "other.txt"
            other.write_text("unchanged\n", encoding="utf-8")
            before = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            self._run(REPO_ROOT, target)
            after = {
                path.relative_to(target): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            # No target artifact other than the managed AGENTS.md block.
            self.assertEqual(set(after), set(before))
            self.assertEqual(
                after[pathlib.Path("other.txt")],
                before[pathlib.Path("other.txt")],
            )
            content = dst.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# Existing\n"))
            self.assertIn("## Span lifecycle", content)
            self.assertFalse(dst.with_name("AGENTS.md.bak-span").exists())
            self.assertEqual(
                sorted(path.name for path in target.iterdir()),
                ["AGENTS.md", "other.txt"],
            )

    def test_replaces_stale_block_and_preserves_surrounding_content(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            dst = target / "AGENTS.md"
            dst.write_text(
                "# Top\n\n"
                + install.AGENTS_START
                + "\nSTALE\n"
                + install.AGENTS_END
                + "\n\n## Next\n",
                encoding="utf-8",
            )
            self._run(REPO_ROOT, target)
            content = dst.read_text(encoding="utf-8")
            self.assertNotIn("\nSTALE\n", content)
            self.assertIn("## Span lifecycle", content)
            self.assertTrue(content.startswith("# Top\n\n"))
            self.assertTrue(content.endswith("\n\n## Next\n"))

    def test_duplicate_markers_fail_closed_without_artifacts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            dst = target / "AGENTS.md"
            original = (
                install.AGENTS_START
                + "\nA\n"
                + install.AGENTS_END
                + "\n"
                + install.AGENTS_START
                + "\nB\n"
                + install.AGENTS_END
                + "\n"
            )
            dst.write_text(original, encoding="utf-8")
            before = sorted(path.name for path in target.iterdir())
            with self.assertRaises(SystemExit):
                self._run(REPO_ROOT, target)
            self.assertEqual(dst.read_text(encoding="utf-8"), original)
            self.assertEqual(sorted(path.name for path in target.iterdir()), before)
            self.assertFalse(dst.with_name("AGENTS.md.bak-span").exists())

    def test_malformed_markers_fail_closed_without_writing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            dst = target / "AGENTS.md"
            original = "# Existing\n" + install.AGENTS_START + "\n"
            dst.write_text(original, encoding="utf-8")
            before = sorted(path.name for path in target.iterdir())
            with self.assertRaises(SystemExit):
                self._run(REPO_ROOT, target)
            self.assertEqual(dst.read_text(encoding="utf-8"), original)
            self.assertEqual(sorted(path.name for path in target.iterdir()), before)
            self.assertFalse(dst.with_name("AGENTS.md.bak-span").exists())

    def test_dry_run_writes_nothing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            result = install.ensure_agents_rule(REPO_ROOT, target, dry_run=True)
            self.assertEqual(result["status"], "skipped")
            self.assertFalse((target / "AGENTS.md").exists())

    def test_missing_source_fails_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "proj"
            target.mkdir()
            empty_repo = pathlib.Path(tmp) / "span"
            # A checkout is identified by src/span; the snippet then has
            # to come from that checkout and is missing, so the install
            # must fail closed rather than resolve an unrelated asset.
            (empty_repo / "src" / "span").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                install.ensure_agents_rule(empty_repo, target, dry_run=False)

    def test_no_agents_flag_rejected(self):
        with self.assertRaises(SystemExit):
            install.parse_args(["--no-agents"])


if __name__ == "__main__":
    unittest.main()
