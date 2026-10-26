"""Code-budget and duplication gate (plan §6, F8 + D8).

Deterministic AST checks. Every metric has a recorded baseline in
``tests/code_budget_baseline.json``; the gate fails when the tree exceeds it.
Each wave lowers the baseline as it removes debt, so a regression cannot land.
"""

from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "span"
TESTS = ROOT / "tests"
BASELINE = TESTS / "code_budget_baseline.json"

# Composition roots may mix layer concerns; only the size budget applies.
COMPOSITION_ROOTS = {
    "shell/context.py",
    "shell/mcp_server.py",
    "shell/install_verify.py",
    "shell/structural/__init__.py",
}
PROVIDER_MODULES = {"shell/structural/graft.py", "shell/structural/memory.py"}
MIGRATION_MODULE = "shell/sqlite_store/schema.py"
PROVIDER_MODULE_LIMIT = 2_000

#: The canonical test-factory names (one definition per concept) plus the two
#: provider/adapter harness configurations that are not expressible as a
#: partial. A second definition of any of these is the duplication D7 removed.
HELPER_NAMES = {
    "query_bounds",
    "subject_id",
    "evidence_ref",
    "semantic_harness",
    "candidate_claim",
    "candidate_claim_for",
    "question_decision",
    "proposed_questions",
    "proposed_question",
    "answered_decision",
    "pending_suspension",
    "_harness",
}

TEST_DOUBLES = {"FixtureEvidenceSource", "FixtureCandidates", "FixtureAgent"}
MAPPING_SYMBOLS = (
    "CandidateTargetInventoryAccount",
    "mapping_mode",
    "mapping_mode=",
    "exclusion_basis",
)


def _python_files(base: pathlib.Path) -> list[pathlib.Path]:
    return [path for path in base.rglob("*.py") if "__pycache__" not in path.parts]


def _relative(path: pathlib.Path, base: pathlib.Path) -> str:
    return str(path.relative_to(base))


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(errors="ignore"))


def _branches(node: ast.AST) -> int:
    return sum(
        isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp, ast.IfExp))
        for child in ast.walk(node)
    )


def _body_key(node: ast.AST) -> str | None:
    """Structural hash of a function body, ignoring docstrings and stubs."""
    body = [
        child
        for child in node.body
        if not (
            isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Constant)
            and isinstance(child.value.value, str)
        )
    ]
    if not body:
        return None
    if all(
        isinstance(child, ast.Pass)
        or (
            isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Constant)
            and child.value.value is Ellipsis
        )
        for child in body
    ):
        return None
    if len(body) == 1 and isinstance(body[0], ast.Expr):
        call = body[0].value
        if isinstance(call, ast.Call):
            # A single delegation to another function. The logic lives in the
            # callee; the call site is not a second copy of it.
            return None
    payload = "\n".join(
        ast.dump(child, annotate_fields=False, include_attributes=False)
        for child in body
    )
    return hashlib.sha1(payload.encode()).hexdigest()


def _is_enum(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(base, ast.Name) and base.id == "Enum")
        or (isinstance(base, ast.Attribute) and base.attr == "Enum")
        for base in node.bases
    )


def _carrier_fields(node: ast.ClassDef) -> int:
    return sum(
        1
        for child in node.body
        if isinstance(child, ast.AnnAssign)
        or (isinstance(child, ast.Assign) and not isinstance(child, ast.Name))
    )


def _imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
    return found


def measure() -> dict[str, int]:
    source_files = _python_files(SRC)
    test_files = _python_files(TESTS)
    metrics: dict[str, int] = {}

    longest_function = 0
    most_branches = 0
    most_parameters = 0
    functions_over_150 = 0
    duplicate_source_groups = 0
    source_bodies: dict[str, int] = {}
    for path in source_files:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = node.end_lineno - node.lineno + 1
                longest_function = max(longest_function, length)
                functions_over_150 += length > 150
                most_branches = max(most_branches, _branches(node))
                params = (
                    len(node.args.posonlyargs)
                    + len(node.args.args)
                    + len(node.args.kwonlyargs)
                )
                most_parameters = max(most_parameters, params)
                key = _body_key(node)
                if key:
                    source_bodies[key] = source_bodies.get(key, 0) + 1

    duplicate_source_groups = sum(1 for count in source_bodies.values() if count > 1)

    module_sizes = {
        _relative(path, SRC): len(path.read_text().splitlines())
        for path in source_files
    }
    metrics["longest_function"] = longest_function
    metrics["functions_over_150"] = functions_over_150
    metrics["most_branches"] = most_branches
    metrics["most_parameters"] = most_parameters
    metrics["longest_module"] = max(module_sizes.values())
    metrics["modules_over_600"] = sum(
        1
        for module, size in module_sizes.items()
        if size > 600 and module not in COMPOSITION_ROOTS
    )
    metrics["provider_module_over_limit"] = sum(
        1
        for module, size in module_sizes.items()
        if module in PROVIDER_MODULES and size > PROVIDER_MODULE_LIMIT
    )
    metrics["duplicate_source_groups"] = duplicate_source_groups

    model_files = sorted((SRC / "core" / "model").glob("*.py"))
    classes = [
        node
        for path in model_files
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    ]
    carriers = [node for node in classes if not _is_enum(node)]
    metrics["concrete_carriers"] = len(carriers)
    metrics["carriers_over_15_fields"] = sum(
        1 for carrier in carriers if _carrier_fields(carrier) > 15
    )

    source_text = "\n".join(path.read_text(errors="ignore") for path in source_files)
    metrics["inline_addendum_refs"] = len(re.findall(r"Addendum", source_text))
    # The schema migration is the one legitimate reader of the legacy field
    # names; the gate measures the runtime surface it must not leave behind.
    mapping_text = "\n".join(
        text
        for path, text in (
            (path, path.read_text(errors="ignore")) for path in source_files
        )
        if _relative(path, SRC) != MIGRATION_MODULE
    )
    migration_text = (SRC / MIGRATION_MODULE).read_text(errors="ignore")
    migration_tree = ast.parse(migration_text)
    for node in ast.walk(migration_tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_rewrite_target_accounting"
        ):
            lines = migration_text.splitlines(keepends=True)
            lines[node.lineno - 1 : node.end_lineno] = []
            mapping_text += "\n" + "".join(lines)
    metrics["mapping_symbols"] = sum(
        mapping_text.count(symbol) for symbol in MAPPING_SYMBOLS
    )

    mutable_tables = 0
    for path in source_files:
        if not _relative(path, SRC).startswith(("core/", "service/")):
            continue
        for node in _tree(path).body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                if isinstance(node.value, ast.Dict):
                    mutable_tables += 1
    metrics["mutable_module_tables"] = mutable_tables

    metrics["service_shell_imports"] = sum(
        1
        for path in source_files
        if _relative(path, SRC).startswith("service/")
        for module in _imports(_tree(path))
        if module == "span.shell" or module.startswith("span.shell.")
    )
    metrics["core_layer_violations"] = sum(
        1
        for path in source_files
        if _relative(path, SRC).startswith("core/")
        for module in _imports(_tree(path))
        if module.startswith(("span.ports", "span.service", "span.shell"))
    )

    metrics["test_doubles_in_src"] = sum(
        1 for name in TEST_DOUBLES if re.search(rf"^class {name}\b", source_text, re.M)
    )
    metrics["test_files"] = len(test_files)
    metrics["test_lines"] = sum(
        len(path.read_text().splitlines()) for path in test_files
    )
    metrics["test_helper_definitions"] = sum(
        1
        for path in test_files
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in HELPER_NAMES
    )

    helper_bodies: dict[str, int] = {}
    for path in test_files:
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in HELPER_NAMES
            ):
                key = _body_key(node)
                if key:
                    helper_bodies[key] = helper_bodies.get(key, 0) + 1
    metrics["duplicate_helper_bodies"] = sum(
        1 for count in helper_bodies.values() if count > 1
    )

    metrics["evidence_select_implementations"] = sum(
        1
        for path in source_files
        if not _relative(path, SRC).startswith("ports/")
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "select_evidence"
    )
    metrics["provider_paging_helpers"] = len(
        re.findall(r"^    def _versioned_page\b", source_text, re.M)
    )
    metrics["provider_edge_helpers"] = len(
        re.findall(r"^    def edges\(", source_text, re.M)
    )

    metrics["any_count"] = len(re.findall(r"\bAny\b", source_text))
    metrics["type_ignore"] = source_text.count("type: ignore")
    metrics["bare_generics"] = len(
        re.findall(r"(?:->|:)\s*(?:dict|list)\s*(?!\[)", source_text)
    )
    metrics["untyped_defs"] = sum(
        1
        for path in source_files
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.returns is None
        and not (node.name.startswith("__") and node.name.endswith("__"))
    )
    metrics["getattr"] = source_text.count("getattr(")
    metrics["broad_excepts"] = source_text.count("except Exception")
    return metrics


class CodeBudgetGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        baseline = json.loads(BASELINE.read_text())
        cls.baseline = baseline
        cls.metrics = measure()

    def test_no_metric_regresses(self) -> None:
        regressions = {
            metric: (self.baseline[metric], value)
            for metric, value in self.metrics.items()
            if metric in self.baseline and value > self.baseline[metric]
        }
        self.assertEqual(regressions, {}, "budget regression (baseline, now)")

    def test_baseline_covers_every_metric(self) -> None:
        missing = sorted(set(self.metrics) - set(self.baseline))
        self.assertEqual(missing, [], "record the new metric in the baseline")

    def test_hard_rules_hold(self) -> None:
        self.assertEqual(self.metrics["core_layer_violations"], 0)
        self.assertEqual(self.metrics["provider_module_over_limit"], 0)
        self.assertEqual(self.metrics["mutable_module_tables"], 0)
        self.assertEqual(self.metrics["carriers_over_15_fields"], 0)
        self.assertLessEqual(self.metrics["concrete_carriers"], 111)
