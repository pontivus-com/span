"""Initialization/readiness contract tests (plan Phase 0.7).

Pins the INITIALIZATION_CONTRACT.md behavior before implementation
exists: fresh tree is uninitialized, and no code path can implicitly
bootstrap. Full readiness-state behavior belongs to its owning phases
(Phase 1 preflight, Phase 2.8 bootstrap, Phase 4.9–4.10 hooks).
"""

import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "INITIALIZATION_CONTRACT.md"

# Store-artifact names that would indicate an initialized repository.
# None may exist in a fresh checkout (contract §2).
INITIALIZED_STORE_MARKERS = (
    "span.db",
    "semantic.db",
    "store.sqlite",
    "span.sqlite",
)


class InitializationContractTest(unittest.TestCase):
    def test_contract_document_exists_and_states_explicit_only(self):
        self.assertTrue(CONTRACT.is_file(), "INITIALIZATION_CONTRACT.md missing")
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("span_initialize_repository", text)
        self.assertIn("UNINITIALIZED", text)
        self.assertIn("must never start initialization implicitly", text)

    def test_fresh_tree_carries_no_initialized_store(self):
        offenders = []
        for path in REPO_ROOT.rglob("*"):
            if ".git" in path.parts:
                continue
            if path.is_file() and path.name in INITIALIZED_STORE_MARKERS:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], f"initialized store present: {offenders}")

    def test_no_implicit_bootstrap_call_sites(self):
        # No query/hook code path may invoke initialization. The explicit
        # admin operation (``def initialize_repository``) is allowed and
        # required by Phase 2.8; what is forbidden is *calling* it — or
        # any auto-init — from query/hook paths. The server provisioning
        # function (``provision_repository`` in Phase 4.2) is likewise
        # an explicit admin path: it serves the explicit
        # `span_initialize_repository` tool and dedicated startup
        # registration, never queries or hooks. Structural scan: guards
        # Phases 1–4 against introducing auto-init call sites.
        offenders = []
        for path in sorted((REPO_ROOT / "src").rglob("*.py")):
            relative = str(path.relative_to(REPO_ROOT))
            in_provision = False
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("def "):
                    in_provision = (
                        relative == "src/span/shell/mcp_server.py"
                        and stripped.startswith("def provision_repository(")
                    )
                    if stripped.startswith("def initialize_repository("):
                        continue
                if in_provision:
                    continue
                if "initialize_repository(" in line or "auto_init" in line:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}"
                    )
        for path in sorted((REPO_ROOT / "integrations").rglob("*.py")):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if "initialize_repository(" in line and not line.strip().startswith(
                    "def initialize_repository("
                ):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}"
                    )
        self.assertEqual(offenders, [], f"implicit bootstrap sites: {offenders}")


if __name__ == "__main__":
    unittest.main()
