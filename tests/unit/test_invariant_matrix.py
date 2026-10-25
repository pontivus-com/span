"""Invariant matrix gate (remediation plan Step 09, decision D13).

``docs/invariants.md`` is a contract: every row declares whether the
invariant is test-enforced or review-enforced. A table that drifts from
the suite is worse than no table, because it turns an untested claim into
apparent evidence. This gate keeps the two aligned:

- every invariant ID appears once, in order;
- every ``Test`` row names at least one live boundary test, and every
  named test resolves to a class, function, or module in ``tests/``;
- every ``Review`` row names no test — a claim that a mechanical probe
  exists belongs under ``Test``.

The two scans below back rows whose evidence is a property of the source
tree rather than a behavioural exchange (I-18 annotation discipline,
I-20 demand-driven indexing). They live here because the matrix names
them; the matrix cannot claim them without this module.
"""

import ast
import dataclasses as _dataclasses
import pathlib
import re
import unittest

from span.core import model as m

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "invariants.md"

_ROW = re.compile(
    r"^\|\s*(I-\d{2})\s*\|\s*(.+?)\s*\|\s*(Test|Review)\s*\|\s*(.+?)\s*\|\s*$"
)
_BACKTICK = re.compile(r"`([^`]+)`")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ANY = re.compile(r"\bAny\b")


def _rows() -> list[tuple[str, str, str, str]]:
    rows = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            rows.append(
                (match.group(1), match.group(2), match.group(3), match.group(4))
            )
    return rows


def _live_tests() -> dict[str, list[str]]:
    """Every test class, test function, and test module, by name."""
    index: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        relative = str(path.relative_to(REPO_ROOT))
        index.setdefault(path.name, []).append(relative)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Test"):
                index.setdefault(node.name, []).append(f"{relative}::{node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name.startswith("test_")
            ):
                index.setdefault(node.name, []).append(f"{relative}::{node.name}")
    return index


def _claimed_tests(evidence: str) -> list[str]:
    """Backticked names that claim a test boundary.

    Domain terms in backticks (``ChangeKind``, ``src/``) are not claims;
    CamelCase names ending in ``Test``, ``test_*`` functions, and test
    modules are.
    """
    claimed = []
    for raw in _BACKTICK.findall(evidence):
        token = raw.strip()
        if token.endswith(".py"):
            claimed.append(token)
        elif _IDENTIFIER.match(token) and (
            token.endswith("Test") or token.startswith("test_")
        ):
            claimed.append(token)
    return claimed


class InvariantMatrixTest(unittest.TestCase):
    def setUp(self):
        self.rows = _rows()
        self.index = _live_tests()

    def test_matrix_lists_every_invariant_once_in_order(self):
        self.assertEqual(
            [row[0] for row in self.rows],
            [f"I-{number:02d}" for number in range(1, 40)],
            "the matrix must carry I-01..I-39 in order, one row each",
        )

    def test_every_test_row_names_a_live_boundary_test(self):
        unnamed = []
        unresolved = []
        for identifier, _invariant, verdict, evidence in self.rows:
            if verdict != "Test":
                continue
            claimed = _claimed_tests(evidence)
            if not claimed:
                unnamed.append(identifier)
            for token in claimed:
                if token not in self.index:
                    unresolved.append(f"{identifier} → {token}")
        self.assertEqual(unnamed, [], "Test rows that name no boundary test")
        self.assertEqual(unresolved, [], "Test rows naming a missing test")

    def test_review_rows_do_not_claim_test_enforcement(self):
        overclaimed = {
            identifier: _claimed_tests(evidence)
            for identifier, _invariant, verdict, evidence in self.rows
            if verdict == "Review" and _claimed_tests(evidence)
        }
        self.assertEqual(overclaimed, {}, "Review rows that claim a test")


def _annotations(node: ast.AST):
    if isinstance(node, ast.arg) and node.annotation is not None:
        yield node.annotation
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.returns is not None:
            yield node.returns
    elif isinstance(node, ast.AnnAssign):
        yield node.annotation


class SemanticTypingTest(unittest.TestCase):
    """I-18: the semantic layers annotate no `Any`, and decode refuses it."""

    def test_semantic_layers_annotate_no_any(self):
        offenders = []
        for root in ("src/span/core", "src/span/service"):
            for path in sorted((REPO_ROOT / root).rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    for annotation in _annotations(node):
                        if _ANY.search(ast.unparse(annotation)):
                            offenders.append(
                                f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                            )
        self.assertEqual(offenders, [], "semantic annotations using Any")

    def test_canonical_decode_refuses_an_untyped_collection(self):
        @_dataclasses.dataclass(frozen=True)
        class BareCollection:
            items: tuple

        with self.assertRaises(m.CanonicalDecodeError) as caught:
            m.from_canonical(BareCollection, {"$type": "BareCollection", "items": [1]})
        self.assertIn("untyped collection", str(caught.exception))


class DemandDrivenIndexingTest(unittest.TestCase):
    """I-20: indexing is provider-owned, never a semantic-layer crawl."""

    _ENUMERATION = ("os.walk", "rglob(", "iterdir(", "listdir(")

    def test_service_layer_performs_no_filesystem_enumeration(self):
        offenders = []
        for path in sorted((REPO_ROOT / "src/span/service").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for needle in self._ENUMERATION:
                if needle in text:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}: {needle.strip('(')}"
                    )
        self.assertEqual(
            offenders,
            [],
            "demand-driven units are provider-owned; the service layer "
            "must not enumerate the filesystem",
        )


if __name__ == "__main__":
    unittest.main()
