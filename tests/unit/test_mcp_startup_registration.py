"""MCP startup registration and lazy context opening.

``span-mcp --repo`` registers repository identity before serving MCP. It must
not provision, open a store, or build structural state. Contexts open lazily
on the first repository-scoped call, and explicit ``initialize_repository``
still provisions through the injected provisioner.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.shell.context import compose_context
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import TOOL_NAMES, McpAdapter, ServiceContext
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import LifecycleStore
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


def _open(tmp: str) -> tuple[pathlib.Path, ServiceContext]:
    root = pathlib.Path(tmp) / REPO
    root.mkdir()
    for path, body in FILES.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    data = pathlib.Path(tmp) / "data"
    data.mkdir()
    store = LifecycleStore(data / f"{REPO}.db", retention=DEFAULT_LIFECYCLE_RETENTION)
    store.register_repository(REPO, str(root.resolve()))
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(path, body) for path, body in FILES.items()),
        (InMemorySubject("src/tools.py", m.SubjectKind.COMPONENT, "tools"),),
    )
    context = compose_context(
        repository_id=REPO,
        root=str(root.resolve()),
        structural=structural,
        evidence=FilesystemEvidenceSource(REPO, root),
        store=store,
    )
    return data, context


def _start(adapter: McpAdapter):
    return adapter.dispatch(
        "start_context",
        {
            "repository_id": REPO,
            "request_id": {"value": "req-startup"},
            "scope": {"paths": [], "evidence_refs": []},
            "question": "What does the service do?",
        },
    )


class StartupRegistrationTest(unittest.TestCase):
    def test_cs01_startup_registration_does_not_provision(self):
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
        self.assertIn(REPO, descriptions["understand_question"])
        self.assertIn(REPO, descriptions["neighbors"])

    def test_cs03_first_repository_request_opens_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, context = _open(tmp)
            self.addCleanup(context.store.close)
            loader = mock.Mock(return_value=context)
            adapter = McpAdapter(context_loader=loader)
            adapter.register_repository_locator(REPO, "/tmp/startup-svc")

            first = _start(adapter)
            self.assertFalse(first.is_error, first.content)
            loader.assert_called_once_with("/tmp/startup-svc")

            second = _start(adapter)
            self.assertFalse(second.is_error, second.content)
            loader.assert_called_once_with("/tmp/startup-svc")
            self.assertIs(adapter.contexts[REPO], context)

    def test_cs04_explicit_initialization_still_provisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, context = _open(tmp)
            self.addCleanup(context.store.close)
            result = m.InitializeRepositoryResult(
                repository_id=REPO,
                canonical_root=context.root,
                schema_version=10,
                store_ready=True,
                structural_status="index:CURRENT",
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
            self.assertTrue(payload["store_ready"])

    def test_cs05_provisioning_replaces_lazy_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, lazy = _open(tmp)
            self.addCleanup(lazy.store.close)
            provisioned = lazy
            loader = mock.Mock(return_value=lazy)
            result = m.InitializeRepositoryResult(
                repository_id=REPO,
                canonical_root=lazy.root,
                schema_version=10,
                store_ready=True,
                structural_status="index:CURRENT",
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

            dispatched = _start(adapter)
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
                mcp_server, "_open_context", side_effect=forbidden
            ) as opener,
        ):
            listed = mcp_server.handle_list_tools(adapter)

        self.assertEqual(len(listed), len(TOOL_NAMES))
        provision.assert_not_called()
        opener.assert_not_called()
        self.assertEqual(adapter.contexts, {})

    def test_cs07_uninitialized_context_creates_no_store(self):
        from span.shell import mcp_server
        from span.shell.context import RepositoryNotInitialized

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / REPO
            root.mkdir()
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir()
            with self.assertRaises(RepositoryNotInitialized):
                mcp_server.open_repository_context(
                    mcp_server.ServerConfig(data_dir=data_dir), str(root)
                )
            self.assertEqual(list(data_dir.iterdir()), [])
            self.assertFalse((data_dir / f"{REPO}.db").exists())


if __name__ == "__main__":
    unittest.main()
