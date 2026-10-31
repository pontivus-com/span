"""Installed-stdio lifecycle fixture: question, record, restart, replay."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import LifecycleStore

SPAN = pathlib.Path(__file__).resolve().parents[2]
REPOSITORY_ID = "repo-lifecycle"
BOUNDS = {
    "max_results": 10,
    "max_depth": 2,
    "max_subjects": 8,
    "max_evidence_units": 10,
    "max_evidence_bytes": 10_000,
    "max_candidate_claims": 64,
    "max_candidate_relationships": 64,
}


def _write(root: pathlib.Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class LifecycleMcpTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.repo = base / REPOSITORY_ID
        self.repo.mkdir()
        _write(self.repo, "src/app.py", "line1\nline2\nline3\n")
        _write(self.repo, "styles/site.css", "body { color: red; }\n")
        self.data = base / "data"
        self.data.mkdir()
        store = LifecycleStore(
            self.data / f"{REPOSITORY_ID}.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )
        store.register_repository(REPOSITORY_ID, str(self.repo.resolve()))
        store.close()
        self.env = {
            **os.environ,
            "PYTHONPATH": str(SPAN / "src"),
        }

    async def _call(self, session: ClientSession, name: str, arguments: dict) -> dict:
        result = await session.call_tool(name, arguments)
        if result.is_error:
            self.fail(f"{name} failed: {result.content}")
        self.assertIsNotNone(result.structured_content)
        payload = result.structured_content or {}
        if name.startswith("record_") and isinstance(payload.get("receipt"), dict):
            return payload["receipt"]
        return payload

    async def _session(self, callback):
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "span.shell.mcp_server",
                "--data-dir",
                str(self.data),
                "--repo",
                str(self.repo),
            ],
            env=self.env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await callback(session)

    def _create_wire(
        self, context_id: str, observation_id: str, submission: str
    ) -> dict:
        return {
            "identity": {
                "repository_id": "repo-lifecycle",
                "context_id": context_id,
                "submission_id": submission,
            },
            "target": {"$type": "ContextBoundTargetWire"},
            "conclusions": [
                {
                    "conclusion_id": "c-1",
                    "statement": "The app emits line1.",
                    "assertion_nature": "DESCRIPTIVE",
                    "scope_paths": ["src/app.py"],
                    "scope_evidence_refs": [],
                    "support": [
                        {
                            "$type": "SourceSupportWire",
                            "observation_id": observation_id,
                        }
                    ],
                    "basis_derivation": "EXPLICIT_EVIDENCE",
                    "basis_summary": "read the source",
                    "basis_input_refs": [],
                }
            ],
        }

    async def test_full_lifecycle_and_restart(self) -> None:
        async def first(session: ClientSession) -> dict:
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            self.assertIn("understand_question", names)
            self.assertIn("record_create", names)
            self.assertIn("evidence_start", names)

            cold = await self._call(
                session,
                "understand_question",
                {
                    "repository_id": "repo-lifecycle",
                    "request_id": {"value": "req-1"},
                    "question": "What happens in the app?",
                    "scope": {"paths": ["src"], "evidence_refs": []},
                    "bounds": BOUNDS,
                },
            )
            self.assertIn("context", cold)
            self.assertIn("evidence", cold)
            self.assertIn("line1", cold["evidence"][0]["content"])
            context_id = cold["context"]["context_id"]["value"]
            observation_id = cold["outcomes"][0]["observation_id"]["value"]

            created = await self._call(
                session,
                "record_create",
                self._create_wire(context_id, observation_id, "sub-create-1"),
            )
            self.assertEqual(created["accepted_understanding_versions"][0]["value"], 1)
            understanding_id = created["accepted_understanding_ids"][0]["value"]
            committed_at = created["committed_at"]

            verification = await self._call(
                session,
                "record_verification",
                {
                    "identity": {
                        "repository_id": "repo-lifecycle",
                        "context_id": context_id,
                        "submission_id": "sub-v-1",
                    },
                    "run": {
                        "repository_id": "repo-lifecycle",
                        "scope_description": "app entry",
                        "scope_paths": ["src/app.py"],
                        "observations": [observation_id],
                        "command": "python3 -m unittest",
                        "scenario": None,
                        "outcome": "PASS",
                        "observed_at": "2026-10-31T08:00:00+00:00",
                        "observer": "host-trial",
                        "environment_limitations": [],
                        "provenance": "",
                    },
                },
            )
            run_id = verification["accepted_verification_run_ids"][0]["value"]
            verification_current = await self._call(
                session,
                "verification_support",
                {"repository_id": REPOSITORY_ID, "run_id": run_id},
            )
            self.assertEqual(verification_current["state"], "CURRENT")

            found = await self._call(
                session,
                "understand_question",
                {
                    "repository_id": "repo-lifecycle",
                    "request_id": {"value": "req-2"},
                    "question": "Explain the application behavior",
                    "scope": {"paths": ["src/app.py"], "evidence_refs": []},
                    "bounds": BOUNDS,
                },
            )
            self.assertIn("retrieved", found)
            self.assertEqual(
                found["retrieved"][0]["conclusions"][0]["content"]["statement"],
                "The app emits line1.",
            )

            retrieved = await self._call(
                session,
                "understand_retrieve",
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": understanding_id,
                },
            )
            self.assertEqual(
                retrieved["conclusions"][0]["content"]["statement"],
                "The app emits line1.",
            )

            replay = await self._call(
                session,
                "record_create",
                self._create_wire(context_id, observation_id, "sub-create-1"),
            )
            self.assertEqual(replay["committed_at"], committed_at)

            added = await self._call(
                session,
                "record_add",
                {
                    "identity": {
                        "repository_id": "repo-lifecycle",
                        "context_id": context_id,
                        "submission_id": "sub-add-1",
                    },
                    "understanding_id": understanding_id,
                    "expected_version": 1,
                    "conclusion": {
                        "conclusion_id": "c-2",
                        "statement": "The app has three fixture lines.",
                        "assertion_nature": "DESCRIPTIVE",
                        "scope_paths": ["src/app.py"],
                        "scope_evidence_refs": [],
                        "support": [
                            {
                                "$type": "SourceSupportWire",
                                "observation_id": observation_id,
                            }
                        ],
                        "basis_derivation": "EXPLICIT_EVIDENCE",
                        "basis_summary": "read the source",
                        "basis_input_refs": [],
                    },
                },
            )
            self.assertEqual(added["accepted_understanding_versions"][0]["value"], 2)

            challenge_args = {
                "identity": {
                    "repository_id": "repo-lifecycle",
                    "context_id": context_id,
                    "submission_id": "sub-ch-1",
                },
                "understanding_id": understanding_id,
                "target_version": 1,
                "target_conclusions": [
                    {
                        "understanding_id": understanding_id,
                        "conclusion_id": "c-1",
                        "revision": 1,
                    }
                ],
                "reason": "The entry point claim is disputed.",
                "evidence_refs": [],
                "provenance": "host trial",
            }
            challenge = await self._call(session, "record_challenge", challenge_args)
            challenge_id = challenge["accepted_challenge_ids"][0]["value"]
            disputed = await self._call(
                session,
                "understand_retrieve",
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": understanding_id,
                },
            )
            self.assertEqual(disputed["challenges"][0]["state"], "OPEN")
            updated = await self._call(
                session,
                "record_update",
                {
                    "identity": {
                        "repository_id": "repo-lifecycle",
                        "context_id": context_id,
                        "submission_id": "sub-ch-update",
                    },
                    "understanding_id": understanding_id,
                    "expected_version": 2,
                    "confirm": [
                        {
                            "conclusion_id": "c-1",
                            "statement": "The app emits line1, confirmed.",
                            "assertion_nature": "DESCRIPTIVE",
                            "scope_paths": ["src/app.py"],
                            "scope_evidence_refs": [],
                            "support": [
                                {
                                    "$type": "SourceSupportWire",
                                    "observation_id": observation_id,
                                }
                            ],
                            "basis_derivation": "EXPLICIT_EVIDENCE",
                            "basis_summary": "rechecked the source",
                            "basis_input_refs": [],
                        }
                    ],
                    "challenge_dispositions": [
                        {
                            "$type": "UnresolvedDispositionWire",
                            "challenge_id": challenge_id,
                            "expected_challenge_revision": 1,
                            "remaining_question": "Is the entry point complete?",
                            "basis": "more evidence is needed",
                        }
                    ],
                },
            )
            self.assertEqual(updated["accepted_understanding_versions"][0]["value"], 3)
            settled = await self._call(
                session,
                "understand_retrieve",
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": understanding_id,
                },
            )
            self.assertEqual(settled["challenges"][0]["state"], "UNRESOLVED")
            self.assertEqual(settled["challenges"][0]["challenge_revision"]["value"], 2)

            reassessed = await self._call(
                session,
                "reassess",
                {
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": understanding_id,
                },
            )
            self.assertEqual(reassessed["state"], "CURRENT")
            _write(self.repo, "src/app.py", "changed\n")
            changed = await self._call(
                session,
                "reassess",
                {
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": understanding_id,
                },
            )
            self.assertEqual(changed["state"], "REASSESSMENT_REQUIRED")
            verification_changed = await self._call(
                session,
                "verification_support",
                {"repository_id": REPOSITORY_ID, "run_id": run_id},
            )
            self.assertEqual(verification_changed["state"], "REASSESSMENT_REQUIRED")
            failed_add = await session.call_tool(
                "record_add",
                {
                    "identity": {
                        "repository_id": "repo-lifecycle",
                        "context_id": context_id,
                        "submission_id": "sub-drift-1",
                    },
                    "understanding_id": understanding_id,
                    "expected_version": 3,
                    "conclusion": {
                        "conclusion_id": "c-3",
                        "statement": "This must be rejected after drift.",
                        "assertion_nature": "DESCRIPTIVE",
                        "scope_paths": ["src/app.py"],
                        "scope_evidence_refs": [],
                        "support": [
                            {
                                "$type": "SourceSupportWire",
                                "observation_id": observation_id,
                            }
                        ],
                        "basis_derivation": "EXPLICIT_EVIDENCE",
                        "basis_summary": "stale source",
                        "basis_input_refs": [],
                    },
                },
            )
            self.assertTrue(failed_add.is_error)

            evidence = await self._call(
                session,
                "evidence_start",
                {
                    "repository_id": "repo-lifecycle",
                    "request_id": {"value": "req-ev-1"},
                    "scope": {
                        "paths": ["styles"],
                        "evidence_refs": [],
                    },
                    "requests": [{"locator": "styles/site.css", "ranges": []}],
                    "bounds": BOUNDS,
                },
            )
            self.assertEqual(
                evidence["outcomes"][0]["observation_id"]["value"][:4],
                "obs:",
            )
            return {
                "understanding_id": understanding_id,
                "context_id": context_id,
                "observation_id": observation_id,
                "committed_at": committed_at,
                "challenge_args": challenge_args,
                "challenge_committed_at": challenge["committed_at"],
            }

        state = await self._session(first)

        async def after_restart(session: ClientSession) -> None:
            retrieved = await self._call(
                session,
                "understand_retrieve",
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": state["understanding_id"],
                },
            )
            self.assertEqual(retrieved["understanding"]["current_version"]["value"], 3)
            replay = await self._call(
                session,
                "record_create",
                self._create_wire(
                    state["context_id"],
                    state["observation_id"],
                    "sub-create-1",
                ),
            )
            self.assertEqual(replay["committed_at"], state["committed_at"])
            reassessed = await self._call(
                session,
                "reassess",
                {
                    "repository_id": REPOSITORY_ID,
                    "understanding_id": state["understanding_id"],
                },
            )
            self.assertEqual(reassessed["state"], "REASSESSMENT_REQUIRED")
            challenge_replay = await self._call(
                session,
                "record_challenge",
                state["challenge_args"],
            )
            self.assertEqual(
                challenge_replay["committed_at"],
                state["challenge_committed_at"],
            )

        await self._session(after_restart)


if __name__ == "__main__":
    unittest.main()
