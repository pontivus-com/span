"""MCP startup registration and lazy context opening.

``span-mcp --repo`` registers repository identity before serving MCP. It must
not provision, open a store, or build structural state. Contexts open lazily
on the first repository-scoped call. Setup is owned by the installer, not a
public lifecycle tool.
"""

from __future__ import annotations

import json
import pathlib
import datetime
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.shell.context import compose_context
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import TOOL_NAMES, McpAdapter, ServiceContext
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.functional_pyramid import (
    FunctionalPyramidInstallationStore,
    functional_pyramid_installation_path,
)
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


def _ask(adapter: McpAdapter):
    return adapter.dispatch(
        "ask",
        {
            "repository_id": REPO,
            "reference": "README.md",
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
        for name in TOOL_NAMES:
            self.assertIn(REPO, descriptions[name])

    def test_cs03_first_repository_request_opens_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, context = _open(tmp)
            self.addCleanup(context.store.close)
            loader = mock.Mock(return_value=context)
            adapter = McpAdapter(context_loader=loader)
            adapter.register_repository_locator(REPO, "/tmp/startup-svc")

            first = _ask(adapter)
            self.assertFalse(first.is_error, first.content)
            loader.assert_called_once_with("/tmp/startup-svc")

            second = _ask(adapter)
            self.assertFalse(second.is_error, second.content)
            loader.assert_called_once_with("/tmp/startup-svc")
            self.assertIs(adapter.contexts[REPO], context)

    def test_cs04_initialize_repository_is_not_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, context = _open(tmp)
            self.addCleanup(context.store.close)
            provisioner = mock.Mock()
            adapter = McpAdapter(provisioner=provisioner)

            dispatched = adapter.dispatch(
                "initialize_repository",
                {"repository_locator": "/tmp/startup-svc"},
            )

            self.assertTrue(dispatched.is_error)
            payload = json.loads(dispatched.content)
            self.assertEqual(payload["kind"], "unknown_tool")
            provisioner.assert_not_called()

    def test_cs05_provisioning_is_installer_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, lazy = _open(tmp)
            self.addCleanup(lazy.store.close)
            loader = mock.Mock(return_value=lazy)
            adapter = McpAdapter(context_loader=loader)
            adapter.register_repository_locator(REPO, "/tmp/startup-svc")

            initialized = adapter.dispatch(
                "initialize_repository",
                {"repository_locator": "/tmp/startup-svc"},
            )
            self.assertTrue(initialized.is_error)

            dispatched = _ask(adapter)
            self.assertFalse(dispatched.is_error, dispatched.content)
            loader.assert_called_once_with("/tmp/startup-svc")
            self.assertIs(adapter.contexts[REPO], lazy)

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

    def test_cs08_functional_pyramid_ask_is_installation_scoped(self):
        loader = mock.Mock(side_effect=AssertionError("must not open repository context"))
        service = mock.Mock()
        service.status.return_value = m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.UNCONFIGURED
        )
        adapter = McpAdapter(
            context_loader=loader,
            functional_pyramid=service,
        )
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")

        result = adapter.dispatch(
            "ask",
            {
                "selector": {
                    "$type": "FunctionalPyramidSelector",
                    "repository_id": REPO,
                }
            },
        )

        self.assertFalse(result.is_error, result.content)
        loader.assert_not_called()
        selector = service.status.call_args.args[0]
        self.assertEqual(selector.repository_id, REPO)

    def test_cs09_functional_pyramid_record_is_installation_scoped(self):
        loader = mock.Mock(side_effect=AssertionError("must not open repository context"))
        service = mock.Mock()
        service.record.return_value = m.FunctionalPyramidRecorded(
            receipt_selector=m.FunctionalPyramidReceiptSelector(
                m.RequestId("fp-exclude-1")
            ),
            committed_at=datetime.datetime(
                2026, 11, 21, tzinfo=datetime.timezone.utc
            ),
            action=m.FunctionalPyramidAction.EXCLUDE,
            pyramid_id=None,
            version=None,
            members=(),
            participation_effects=(
                m.FunctionalPyramidParticipationEffect(
                    repository_id=REPO,
                    state=m.FunctionalPyramidParticipationState.EXCLUDED,
                ),
            ),
        )
        adapter = McpAdapter(
            context_loader=loader,
            functional_pyramid=service,
        )
        adapter.register_repository_locator(REPO, "/tmp/startup-svc")

        result = adapter.dispatch(
            "record",
            {
                "request_id": "fp-exclude-1",
                "kind": "functional_pyramid",
                "action": "exclude",
                "repository_id": REPO,
            },
        )

        self.assertFalse(result.is_error, result.content)
        loader.assert_not_called()
        self.assertEqual(
            service.record.call_args.kwargs["action"],
            m.FunctionalPyramidAction.EXCLUDE,
        )
        self.assertEqual(service.record.call_args.kwargs["repository_id"], REPO)

    def test_cs10_startup_does_not_create_missing_functional_pyramid_store(self):
        from span.shell import mcp_server

        captured = {}

        async def _fake_serve(adapter):
            captured["adapter"] = adapter

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            root = pathlib.Path(tmp) / REPO
            root.mkdir()
            with mock.patch.object(mcp_server, "_serve", side_effect=_fake_serve):
                mcp_server.main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "--repo",
                        str(root),
                    ]
                )

            self.assertIsNone(captured["adapter"].functional_pyramid)
            self.assertFalse(functional_pyramid_installation_path(data_dir).exists())

    def test_cs11_startup_opens_existing_functional_pyramid_store_without_repo_io(self):
        from span.shell import mcp_server
        from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION

        captured = {}

        async def _fake_serve(adapter):
            captured["adapter"] = adapter
            self.assertEqual(adapter.contexts, {})

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir()
            root = pathlib.Path(tmp) / REPO
            root.mkdir()
            store = FunctionalPyramidInstallationStore.create(
                functional_pyramid_installation_path(data_dir),
                retention=DEFAULT_LIFECYCLE_RETENTION,
            )
            store.close()

            with mock.patch.object(mcp_server, "_serve", side_effect=_fake_serve):
                mcp_server.main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "--repo",
                        str(root),
                    ]
                )

            self.assertIsNotNone(captured["adapter"].functional_pyramid)
            self.assertEqual(captured["adapter"].contexts, {})


if __name__ == "__main__":
    unittest.main()
