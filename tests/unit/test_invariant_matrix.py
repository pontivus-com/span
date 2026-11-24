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
FUNCTIONAL_ACCEPTANCE = REPO_ROOT / "docs" / "functional-acceptance.md"

_ROW = re.compile(
    r"^\|\s*(I-\d{2})\s*\|\s*(.+?)\s*\|\s*(Test|Review)\s*\|\s*(.+?)\s*\|\s*$"
)
_FA_ROW = re.compile(r"^\|\s*(FA-\d{2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
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


def _functional_acceptance_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in FUNCTIONAL_ACCEPTANCE.read_text(encoding="utf-8").splitlines():
        match = _FA_ROW.match(line)
        if match:
            rows.append((match.group(1), match.group(2), match.group(3)))
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
            [f"I-{number:02d}" for number in range(1, 49)],
            "the matrix must carry I-01..I-48 in order, one row each",
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


class FunctionalAcceptanceMatrixTest(unittest.TestCase):
    def setUp(self):
        self.rows = _functional_acceptance_rows()
        self.index = _live_tests()

    def test_matrix_lists_every_version_one_acceptance_case_once_in_order(self):
        self.assertEqual(
            [row[0] for row in self.rows],
            [f"FA-{number:02d}" for number in range(1, 65)],
            "the Version-1 acceptance matrix must carry FA-01..FA-64 in order",
        )

    def test_every_acceptance_case_names_live_boundary_tests(self):
        unnamed = []
        unresolved = []
        ambiguous = []
        for identifier, _behavior, evidence in self.rows:
            claimed = _claimed_tests(evidence)
            if not claimed:
                unnamed.append(identifier)
            for token in claimed:
                locations = self.index.get(token, ())
                if not locations:
                    unresolved.append(f"{identifier} → {token}")
                elif len(locations) != 1:
                    ambiguous.append(f"{identifier} → {token}: {', '.join(locations)}")
        self.assertEqual(unnamed, [], "acceptance rows that name no boundary test")
        self.assertEqual(
            unresolved,
            [],
            "acceptance rows naming a missing boundary test",
        )
        self.assertEqual(
            ambiguous,
            [],
            "acceptance rows naming an ambiguous boundary test",
        )


class FunctionalPyramidArchitectureTest(unittest.TestCase):
    """Version-1 installation composition keeps semantics out of shell adapters."""

    def test_shell_functional_pyramid_has_no_semantic_effect_coordinator(self):
        path = REPO_ROOT / "src/span/shell/functional_pyramid.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        imports = {
            module
            for module in (
                node.module for node in tree.body if isinstance(node, ast.ImportFrom)
            )
            if module is not None
        }
        self.assertNotIn("FunctionalPyramidEffectCoordinator", classes)
        self.assertNotIn("span.service.effects", imports)
        self.assertNotIn("span.service.support", imports)

    def test_reconsider_has_no_local_effect_engine_fallback(self):
        path = REPO_ROOT / "src/span/service/reconsider.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        service = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ReconsiderService"
        )
        init = next(
            node
            for node in service.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        calls = [
            node
            for node in ast.walk(init)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "DependencyEffectService"
        ]
        self.assertEqual(calls, [])
        effects_index = [argument.arg for argument in init.args.kwonlyargs].index(
            "effects"
        )
        self.assertIsNone(
            init.args.kw_defaults[effects_index],
            "ReconsiderService.effects must be a required capability",
        )

    def test_dependency_effect_service_has_no_local_store_support_mode(self):
        path = REPO_ROOT / "src/span/service/effects.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        service = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "DependencyEffectService"
        )
        init = next(
            node
            for node in service.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        parameter_names = [argument.arg for argument in init.args.kwonlyargs]
        parameters = set(parameter_names)
        required = {
            "repository_runtime",
            "registered_repository_ids",
            "support_for_repository",
            "functional_route_impacts",
        }
        self.assertFalse({"store", "support"} & parameters)
        self.assertTrue(required <= parameters)
        for name in required:
            index = parameter_names.index(name)
            self.assertIsNone(
                init.args.kw_defaults[index],
                f"{name} must be a required effect-engine capability",
            )

    def test_repository_change_cannot_skip_functional_route_impacts(self):
        path = REPO_ROOT / "src/span/service/effects.py"
        source = path.read_text(encoding="utf-8")
        self.assertNotIn(
            "if self._functional_route_impacts is not None",
            source,
        )
        self.assertIn("self._functional_route_impacts(", source)

    def test_semantic_hooks_use_installation_runtime(self):
        path = REPO_ROOT / "src/span/shell/hooks.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn("open_installation_runtime", source)
        self.assertNotIn("open_functional_pyramid_service", source)

    def test_governing_edge_admissibility_has_one_core_owner(self):
        path = REPO_ROOT / "src/span/core/functional_pyramid.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        owner = functions["_governing_edge_is_valid"]
        owner_calls = {
            node.func.id
            for node in ast.walk(owner)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertNotIn("_layer_rank", owner_calls)

        for consumer_name in ("_rule_edge_findings", "_resolve_rule_refs"):
            calls = {
                node.func.id
                for node in ast.walk(functions[consumer_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertIn("_governing_edge_is_valid", calls)
            self.assertNotIn("_layer_rank", calls)

        edge_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_governing_edge_is_valid"
        ]
        rank_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_layer_rank"
        ]
        self.assertEqual(len(edge_calls), 2)
        self.assertEqual(len(rank_calls), 1)

    def test_context_composition_wires_all_mandatory_pyramid_capabilities(self):
        path = REPO_ROOT / "src/span/shell/context.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls: dict[str, ast.Call] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in {
                "SupportService",
                "LifecycleService",
                "DependencyEffectService",
                "AnswerService",
            }:
                calls[node.func.id] = node

        expected = {
            "SupportService": {"functional_route_resolver", "repository_runtime"},
            "LifecycleService": {"functional_pyramid_route"},
            "DependencyEffectService": {
                "functional_route_impacts",
                "repository_runtime",
                "registered_repository_ids",
                "support_for_repository",
            },
            "AnswerService": {"functional_pyramid_orientation"},
        }
        self.assertEqual(set(calls), set(expected))
        for service, required in expected.items():
            supplied = {keyword.arg for keyword in calls[service].keywords}
            self.assertTrue(
                required <= supplied,
                f"{service} missing mandatory Functional Pyramid wiring: "
                f"{sorted(required - supplied)}",
            )


class Beta2CurationArchitectureTest(unittest.TestCase):
    """Beta-3 keeps curation inside the existing semantic architecture."""

    def _class_locations(self, name: str) -> list[str]:
        locations: list[str] = []
        for path in sorted((REPO_ROOT / "src" / "span").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == name:
                    locations.append(str(path.relative_to(REPO_ROOT)))
        return locations

    def test_curation_carriers_have_one_canonical_definition(self):
        expected = {
            "CurateConclusion": "src/span/core/model/commands.py",
            "CurationDisposition": "src/span/core/model/understanding.py",
            "PendingCurationSelector": "src/span/core/model/understanding.py",
            "PendingCurationItem": "src/span/core/model/understanding.py",
            "PendingCuration": "src/span/core/model/understanding.py",
        }
        for name, owner in expected.items():
            self.assertEqual(self._class_locations(name), [owner], name)

    def test_curation_persistence_has_one_writer(self):
        writers = []
        for path in sorted((REPO_ROOT / "src" / "span").rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "INSERT INTO conclusion_curations" in source:
                writers.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(writers, ["src/span/shell/sqlite_store/lifecycle.py"])

    def test_pending_reuse_has_one_answer_composer(self):
        composers = []
        for path in sorted((REPO_ROOT / "src" / "span").rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "GapReason.PENDING_CURATION" in source:
                composers.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(composers, ["src/span/service/answer.py"])

    def test_curation_reuses_the_single_support_evaluator(self):
        self.assertEqual(
            self._class_locations("SupportService"),
            ["src/span/service/support.py"],
        )
        answer = (REPO_ROOT / "src/span/service/answer.py").read_text(encoding="utf-8")
        lifecycle = (REPO_ROOT / "src/span/service/lifecycle.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("self._support.evaluate_revision", answer)
        self.assertIn("self._support.evaluate_revision", lifecycle)

    def test_shell_has_no_curation_semantic_decision(self):
        shell = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((REPO_ROOT / "src/span/shell").rglob("*.py"))
        )
        self.assertNotIn("GapReason.PENDING_CURATION", shell)
        self.assertNotIn("CurationState.CURATED", shell)

    def test_missing_curation_never_defaults_to_approval(self):
        answer = (REPO_ROOT / "src/span/service/answer.py").read_text(encoding="utf-8")
        self.assertIn("and self._store.find_curation(", answer)
        self.assertIn("is not None", answer)
        transition = (
            REPO_ROOT / "src/span/shell/store_transition_schema14.py"
        ).read_text(encoding="utf-8")
        self.assertIn('curation_rows": 0', transition)

    def test_no_parallel_curate_operation_or_rejected_state(self):
        from span.shell.mcp.schemas import TOOL_NAMES

        self.assertEqual(TOOL_NAMES, ("ask", "record", "reconsider"))
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((REPO_ROOT / "src/span").rglob("*.py"))
        )
        self.assertNotIn("rejected_curation", source)


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
