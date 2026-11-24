"""The GitHub Release body is extracted from the canonical changelog."""

import json
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

    def _identity(self, version, field):
        return subprocess.run(
            [
                sys.executable,
                "scripts/release_identity.py",
                "--package-version",
                version,
                "--field",
                field,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_beta_release_identity_uses_pep440_and_registry_semver(self):
        expected = {
            "package_version": "1.0.0b1",
            "tag": "v1.0.0b1",
            "registry_version": "1.0.0-beta.1",
            "release_title": "Span 1.0.0 Beta 1",
            "prerelease": "true",
            "development": "false",
        }
        for field, value in expected.items():
            result = self._identity("1.0.0b1", field)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), value)

    def test_rc_and_dev_versions_are_classified_as_prereleases(self):
        for version, registry, development in (
            ("1.0.0rc2", "1.0.0-rc.2", "false"),
            ("1.0.0.dev3", "1.0.0-dev.3", "true"),
        ):
            registry_result = self._identity(version, "registry_version")
            prerelease_result = self._identity(version, "prerelease")
            development_result = self._identity(version, "development")
            self.assertEqual(registry_result.stdout.strip(), registry)
            self.assertEqual(prerelease_result.stdout.strip(), "true")
            self.assertEqual(development_result.stdout.strip(), development)

    def test_stable_release_identity_is_not_prerelease(self):
        result = self._identity("1.2.3", "prerelease")
        registry = self._identity("1.2.3", "registry_version")
        self.assertEqual(result.stdout.strip(), "false")
        self.assertEqual(registry.stdout.strip(), "1.2.3")

    def test_checked_in_server_versions_match_the_canonical_package_version(self):
        from span import __version__

        server = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
        registry = self._identity(__version__, "registry_version")
        self.assertEqual(registry.returncode, 0, registry.stderr)
        self.assertEqual(server["version"], registry.stdout.strip())
        self.assertEqual(server["packages"][0]["version"], __version__)

    def test_extracts_the_current_section(self):
        result = self._run("0.7.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## 0.7.0"))
        self.assertIn("Bounded answers, labeled staleness", result.stdout)
        self.assertNotIn("## 0.6.2", result.stdout)

    def test_the_shipped_version_has_release_notes(self):
        # The release workflow extracts the section for the package version,
        # so a version bump without a changelog entry fails at release time.
        from span import __version__

        result = self._run(__version__)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith(f"## {__version__}"))

    def test_missing_version_fails_closed(self):
        result = self._run("9.9.9")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no changelog section", result.stderr)

    def test_release_requires_explicit_manual_authorization(self):
        workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^  push:")
        self.assertIn("confirm_version:", workflow)
        self.assertIn("REF_NAME: ${{ github.ref_name }}", workflow)
        self.assertIn('if [[ "${REF_NAME}" != "master" ]]', workflow)
        self.assertIn('if [[ "${requested}" != "${version}" ]]', workflow)

    def test_active_release_surfaces_contain_only_beta3_identity(self):
        roots = (
            REPO_ROOT / "docs",
            REPO_ROOT / "src",
            REPO_ROOT / "skills",
            REPO_ROOT / "integrations",
            REPO_ROOT / ".github",
            REPO_ROOT / "scripts",
            REPO_ROOT / "tests",
        )
        root_files = tuple(
            path
            for path in REPO_ROOT.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
        )
        forbidden = (
            "Beta " + "2",
            "Beta-" + "2",
            "1.0.0" + "b2",
            "1.0.0-beta." + "2",
            "B2-" + "D01",
            "B2-" + "D02",
        )
        candidates = list(root_files)
        for root in roots:
            if root.exists():
                candidates.extend(path for path in root.rglob("*") if path.is_file())

        offenders = []
        for path in candidates:
            relative = path.relative_to(REPO_ROOT)
            if "1.0.0-beta2" in path.name.lower():
                offenders.append(str(relative))
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(value in text for value in forbidden):
                offenders.append(str(relative))
        self.assertEqual(sorted(set(offenders)), [])


if __name__ == "__main__":
    unittest.main()
