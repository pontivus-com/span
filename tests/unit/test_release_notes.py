"""The GitHub Release body is extracted from the canonical changelog."""

import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class ReleaseNotesTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "scripts/release_notes.py", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_extracts_the_current_section(self):
        result = self._run("0.7.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## 0.7.0"))
        self.assertIn("Bounded answers, labeled staleness", result.stdout)
        self.assertNotIn("## 0.6.2", result.stdout)

    def test_missing_version_fails_closed(self):
        result = self._run("9.9.9")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no changelog section", result.stderr)


if __name__ == "__main__":
    unittest.main()
