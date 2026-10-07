"""Isolation gate (plan Phase 0.6 + bootstrap §19 safeguard).

Fails on accidental coupling to the enclosing private workspace:

- absolute workspace dependencies (``<workspace>/...``);
- required parent-relative filesystem references (``../src`` etc.);
- Pontivus/Pontivus Legal/Pontivus Graph imports;
- required symlinks outside Span;
- parent-generated artifacts used as required inputs.

Supplemental backstop only — does not replace MI-11 isolation acceptance.

Prose governance mentions of the enclosing workspace (``AGENTS.md``,
``*.md`` reference-only statements) are not dependencies and are exempt;
code, config, tests, and fixtures are scanned strictly.
"""

import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# File classes scanned strictly (code/config/fixtures — a hit here fails).
STRICT_SUFFIXES = {
    ".py", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json",
}

ABSOLUTE_WORKSPACE = "<workspace>"

PARENT_RELATIVE_MARKERS = (
    "../src",
    "../projects",
    "../packages",
    "../graft",
    "../.claude",
    "../config",
)

PONTIVUS_IMPORT_MARKERS = (
    "example_legal",
    "projects.example_legal",
    "worker_server",
    "from pontivus",
    "import pontivus",
    "Pontivus Graph",
    "PontivusGraph",
)

# Parent-generated artifacts that must never be required inputs.
PARENT_ARTIFACT_MARKERS = (
    "graft/INDEX.md",
    ".graft/",
    "projects/example_legal",
)


def _repo_files():
    for path in sorted(REPO_ROOT.rglob("*")):
        if ".git" in path.parts:
            continue
        if path.is_dir():
            continue
        yield path


# This gate file carries the detection vocabulary as string literals.
# Those literals are the scanner, not dependencies — exempt this file
# from the strict scans below.
SELF = pathlib.Path(__file__).resolve()


class IsolationGateTest(unittest.TestCase):
    def test_no_required_symlinks_outside_span(self):
        offenders = [
            str(p) for p in _repo_files() if p.is_symlink()
        ]
        self.assertEqual(offenders, [], f"required symlinks: {offenders}")

    def test_strict_files_have_no_workspace_coupling(self):
        offenders = []
        for path in _repo_files():
            if path.resolve() == SELF:
                continue
            if path.suffix not in STRICT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                offenders.append(f"{path}: unreadable strict file")
                continue
            rel = str(path.relative_to(REPO_ROOT))
            markers = (
                (ABSOLUTE_WORKSPACE,)
                + PARENT_RELATIVE_MARKERS
                + PONTIVUS_IMPORT_MARKERS
                + PARENT_ARTIFACT_MARKERS
            )
            for marker in markers:
                if marker in text:
                    offenders.append(f"{rel}: {marker!r}")
        self.assertEqual(offenders, [], f"workspace coupling: {offenders}")

    def test_no_parent_generated_artifact_required(self):
        offenders = []
        for path in _repo_files():
            if path.resolve() == SELF:
                continue
            if path.suffix not in STRICT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = str(path.relative_to(REPO_ROOT))
            for marker in PARENT_ARTIFACT_MARKERS:
                if marker in text:
                    offenders.append(f"{rel}: {marker!r}")
        self.assertEqual(offenders, [], f"parent artifacts: {offenders}")

    def test_build_and_test_from_span_root_only(self):
        # Phase 0 exit: build/test/runtime require no private workspace
        # access. The Span root must be self-sufficient: package source,
        # project metadata, and tests resolve from inside the repo.
        self.assertTrue((REPO_ROOT / "pyproject.toml").is_file())
        self.assertTrue((REPO_ROOT / "src" / "span").is_dir())
        self.assertTrue((REPO_ROOT / "tests").is_dir())


if __name__ == "__main__":
    unittest.main()
