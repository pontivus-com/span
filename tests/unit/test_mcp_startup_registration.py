"""MCP startup registration/provisioning separation (Addendum M friction).

`span-mcp --repo` registers repository identity before serving MCP. It
must not provision, open a semantic store, or build structural state.
Repository contexts open lazily on the first repository-scoped call,
and explicit `initialize_repository` still provisions and replaces the
lazy registration.
"""

import json
import pathlib
import unittest
from unittest import mock

from span.core import model as m
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.evidence import FixtureEvidenceSource
from span.shell.mcp import McpAdapter, ServiceContext
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
)

REPO = "startup-svc"
FILES = {
    "README.md": "# startup-svc\n\nServes tools.\n",
    "src/tools.py": "run = True\n",
}


def _context() -> ServiceContext:
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(path, body) for path, body in FILES.items()),
        (InMemorySubject("src/tools.py", m.SubjectKind.COMPONENT, "tools"),),
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="/fixture",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return ServiceContext(
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=ContinuationStore(),
        authority_seeds=(),
    )


def _status(adapter: McpAdapter):
    return adapter.dispatch(
        "status",
        {
            "repository_id": REPO,
            "target": None,
            "mode": "HOOK_FAST",
        },
    )


class StartupRegistrationTest(unittest.TestCase):
    def test_cs01_startup_registration_does_not_provision(self):
        import tempfile

        from span.shell import mcp_server

        captured = {}

        async def _fake_serve(adapter):
            captured["adapter"] = adapter

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            with (
                mock.patch.object(mcp_server, "_serve", side_effect=_fake_serve),
                mock.patch.object(mcp_server, "provision_repository") as provision,
            ):
                mcp_server.main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "--repo",
                        str(pathlib.Path(tmp) / REPO),
                    ]
                )
            provision.assert_not_called()
            adapter = captured["adapter"]
            self.assertEqual(adapter.contexts, {})
            self.assertEqual(adapter.registered_repository_ids(), (REPO,))
            # Registration touched no filesystem state.
            self.assertFalse(data_dir.exists())

    def test_cs02_startup_registration_does_not_open_context(self):
        from span.shell import mcp_server

        loader = mock.Mock(
            side_effect=AssertionError("tools/list must not open a context")
        )
        adapter = McpAdapter(context_loader=loader)
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")
        listed = mcp_server.handle_list_tools(adapter)
        loader.assert_not_called()
        self.assertEqual(adapter.contexts, {})
        descriptions = {spec["name"]: spec["description"] for spec in listed}
        self.assertIn(REPO, descriptions["explain"])
        self.assertIn(REPO, descriptions["neighbors"])

    def test_cs03_first_repository_request_opens_once(self):
        context = _context()
        self.addCleanup(context.store.close)
        loader = mock.Mock(return_value=context)
        adapter = McpAdapter(context_loader=loader)
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")

        first = _status(adapter)
        self.assertFalse(first.is_error, first.content)
        loader.assert_called_once_with("/tmp/startup-svc")

        second = _status(adapter)
        self.assertFalse(second.is_error, second.content)
        loader.assert_called_once_with("/tmp/startup-svc")
        self.assertIs(adapter.contexts[REPO], context)

    def test_cs04_explicit_initialization_still_provisions(self):
        context = _context()
        self.addCleanup(context.store.close)
        result = ops.SemanticInitializeRepositoryResult(
            repository_id=REPO,
            store_readiness=m.StoreReadiness.READY,
            structural_source_status="ready",
            evidence_inventory_status="ready:0items",
            semantic_store_status="ready:schema-6",
            warnings=(),
            bound_info=m.BoundInfo(
                requested_max_results=50,
                requested_max_depth=5,
                returned_results=0,
                truncated=False,
                continuation_token=None,
            ),
        )
        provisioner = mock.Mock(return_value=(context, result))
        adapter = McpAdapter(provisioner=provisioner)

        dispatched = adapter.dispatch(
            "initialize_repository",
            {"repository_locator": "/tmp/startup-svc"},
        )

        self.assertFalse(dispatched.is_error, dispatched.content)
        provisioner.assert_called_once()
        self.assertIs(adapter.contexts[REPO], context)
        payload = json.loads(dispatched.content)
        self.assertEqual(payload["store_readiness"], "READY")

    def test_cs05_provisioning_replaces_lazy_state(self):
        lazy = _context()
        self.addCleanup(lazy.store.close)
        provisioned = _context()
        self.addCleanup(provisioned.store.close)
        loader = mock.Mock(return_value=lazy)
        result = ops.SemanticInitializeRepositoryResult(
            repository_id=REPO,
            store_readiness=m.StoreReadiness.READY,
            structural_source_status="ready",
            evidence_inventory_status="ready:0items",
            semantic_store_status="ready:schema-6",
            warnings=(),
            bound_info=m.BoundInfo(
                requested_max_results=50,
                requested_max_depth=5,
                returned_results=0,
                truncated=False,
                continuation_token=None,
            ),
        )
        adapter = McpAdapter(
            context_loader=loader,
            provisioner=mock.Mock(return_value=(provisioned, result)),
        )
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")

        initialized = adapter.dispatch(
            "initialize_repository",
            {"repository_locator": "/tmp/startup-svc"},
        )
        self.assertFalse(initialized.is_error, initialized.content)

        dispatched = _status(adapter)
        self.assertFalse(dispatched.is_error, dispatched.content)
        loader.assert_not_called()
        self.assertIs(adapter.contexts[REPO], provisioned)

    def test_cs06_tools_list_performs_no_repository_io(self):
        from span.shell import mcp_server

        adapter = McpAdapter()
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")
        forbidden = AssertionError("tools/list must not touch a repository")
        with (
            mock.patch.object(
                mcp_server, "provision_repository", side_effect=forbidden
            ) as provision,
            mock.patch.object(
                mcp_server,
                "structural_source_from_config",
                side_effect=forbidden,
            ) as structural,
            mock.patch.object(
                mcp_server, "FilesystemEvidenceSource", side_effect=forbidden
            ) as evidence,
            mock.patch.object(
                mcp_server, "SqliteSemanticStore", side_effect=forbidden
            ) as store,
        ):
            listed = mcp_server.handle_list_tools(adapter)

        self.assertEqual(len(listed), 11)
        provision.assert_not_called()
        structural.assert_not_called()
        evidence.assert_not_called()
        store.assert_not_called()
        self.assertEqual(adapter.contexts, {})

    def test_cs07_uninitialized_read_creates_no_store(self):
        # Opening the lazy context is not setup: a repository explicit
        # initialization has not provisioned returns the canonical
        # UNINITIALIZED notice without creating `<data-dir>/<id>.db`.
        import tempfile

        from span.shell import mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / REPO
            root.mkdir()
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir()
            repository_id, context = mcp_server.open_repository_context(
                mcp_server.ServerConfig(data_dir=data_dir), str(root)
            )
            try:
                notice = ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=repository_id,
                        target=None,
                        bounds=(ops.DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds),
                        mode=m.StatusMode.HOOK_FAST,
                    ),
                    structural=context.structural,
                    evidence=context.evidence,
                    store=context.store,
                    continuations=context.continuations,
                )
            finally:
                context.store.close()
            self.assertIs(notice.store_readiness, m.StoreReadiness.UNINITIALIZED)
            self.assertEqual(list(data_dir.iterdir()), [])
            self.assertFalse((data_dir / f"{repository_id}.db").exists())


if __name__ == "__main__":
    unittest.main()
