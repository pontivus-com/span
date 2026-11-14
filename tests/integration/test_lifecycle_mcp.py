"""Installed-stdio three-tool journey: ask, record, reconsider."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from span.core import model as m
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import LifecycleStore

SPAN = pathlib.Path(__file__).resolve().parents[2]
REPOSITORY_ID = "repo-lifecycle"


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
        return result.structured_content or {}

    async def _session(
        self,
        callback,
        *,
        budget: int | None = None,
        extra_repos: tuple[pathlib.Path, ...] = (),
    ):
        args = [
            "-m",
            "span.shell.mcp_server",
            "--data-dir",
            str(self.data),
            "--repo",
            str(self.repo),
        ]
        for repository in extra_repos:
            args.extend(["--repo", str(repository)])
        if budget is not None:
            args.extend(["--response-budget-bytes", str(budget)])
        params = StdioServerParameters(
            command=sys.executable,
            args=args,
            env=self.env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await callback(session)

    def _qualification_ids(self, recorded: dict) -> set[str]:
        return {
            item["ref"]["conclusion_id"]["value"]
            for item in recorded["qualification"]["conclusions"]
        }

    def _created_conclusion_id(self, recorded: dict) -> str:
        return next(iter(self._qualification_ids(recorded)))

    def _answer_conclusions(self, answer: dict) -> list[dict]:
        direct = list(answer.get("conclusions", []))
        if direct:
            return direct
        return [
            conclusion
            for group in answer.get("groups", [])
            for conclusion in group["conclusions"]
        ]

    async def _record_create(self, session: ClientSession, request: str) -> dict:
        return await self._call(
            session,
            "record",
            {
                "repository_id": REPOSITORY_ID,
                "request_id": request,
                "kind": "understanding",
                "surface": {"kind": "FILE", "locator": "src/app.py"},
                "question": "What happens in the app?",
                "scope_paths": ["src/app.py"],
                "conclusion": "The app emits line1.",
                "locator": "src/app.py",
            },
        )

    async def test_large_ranged_support_survives_restart_and_reconsiders(self) -> None:
        _write(self.repo, "src/app.py", "line1\n" + "outside\n" * 20_000)

        async def create(session):
            recorded = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "large-range-create",
                    "kind": "understanding",
                    "question": "What is the first line?",
                    "scope_paths": ["src/app.py"],
                    "conclusion": "The first line is line1.",
                    "support": [
                        {
                            "$type": "source",
                            "locator": "src/app.py",
                            "ranges": [{"start_line": 1, "end_line": 1}],
                        }
                    ],
                },
            )
            self.assertEqual(recorded["$type"], "UnderstandingRecorded")
            self.assertEqual(recorded["qualification"]["state"], "CURRENT")

        async def reuse(session):
            answer = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )
            self.assertEqual(answer["$type"], "Answer")
            self.assertEqual(answer["status"]["current"], 1)

        async def changed(session):
            result = await self._call(
                session,
                "reconsider",
                {
                    "repository_id": REPOSITORY_ID,
                    "changed_paths": ["src/app.py"],
                },
            )
            states = [
                c["support"]["state"]
                for surface in result["surfaces"]
                for c in surface["conclusions"]
            ]
            self.assertIn("REASSESSMENT_REQUIRED", states)

        await self._session(create)
        _write(self.repo, "src/app.py", "line1\n" + "changed\n" * 20_000)
        await self._session(reuse)
        _write(self.repo, "src/app.py", "changed\n" + "outside\n" * 20_000)
        await self._session(changed)

    async def test_withdrawn_revision_remains_retrievable_without_statement_projection(
        self,
    ) -> None:
        async def journey(session):
            created = await self._record_create(session, "withdraw-create")
            uid = created["understanding_id"]["value"]
            result = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "withdraw-update",
                    "kind": "understanding",
                    "understanding_id": uid,
                    "expected_version": 1,
                    "actions": {
                        "withdraw": [
                            {
                                "conclusion_id": self._created_conclusion_id(created),
                                "reason": "The explanation is retracted.",
                            }
                        ]
                    },
                },
            )
            self.assertEqual(result["$type"], "UnderstandingRecorded")
            answer = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )
            self.assertEqual(answer["$type"], "Gap")
            self.assertEqual(answer["historical"], [])
            self.assertEqual(answer["surface"]["locator"], "src/app.py")
            snapshot = await self._call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "UnderstandingSnapshotSelector",
                        "repository_id": REPOSITORY_ID,
                        "understanding_id": uid,
                        "version": 2,
                    },
                },
            )
            self.assertEqual(snapshot["$type"], "RetrievedUnderstanding")
            self.assertIn("The explanation is retracted.", str(snapshot))

        await self._session(journey)

    async def test_three_tool_journey_and_restart(self) -> None:
        async def first(session: ClientSession) -> dict:
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            self.assertEqual(names, {"ask", "record", "reconsider"})

            cold = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "reference": "src/app.py",
                },
            )
            self.assertEqual(cold["$type"], "Gap")
            self.assertEqual(cold["reason"], "unassessed")
            self.assertEqual(cold["source_pointers"][0]["locator"], "src/app.py")
            self.assertIsNone(cold["admission"])

            created = await self._record_create(session, "sub-create-1")
            self.assertEqual(created["$type"], "UnderstandingRecorded")

            warm = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )
            self.assertEqual(warm["$type"], "Answer")
            self.assertEqual(
                self._answer_conclusions(warm)[0]["statement"], "The app emits line1."
            )
            self.assertTrue(self._answer_conclusions(warm)[0]["evidence"])
            return warm

        async def second(session: ClientSession) -> dict:
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "reference": "src/app.py",
                },
            )

        await self._session(first)
        again = await self._session(second)
        self.assertEqual(again["$type"], "Answer")
        self.assertEqual(
            self._answer_conclusions(again)[0]["ref"]["understanding_id"]["value"],
            "u:sub-create-1",
        )

    async def test_cold_gap_context_is_accepted_by_record(self) -> None:
        async def journey(session: ClientSession) -> dict:
            gap = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "req-context-bound",
                    "reference": "src/app.py",
                    "evidence": [{"locator": "src/app.py"}],
                },
            )
            self.assertEqual(gap["$type"], "Gap")
            admission = gap["admission"]
            context = admission["context"]
            observation_id = admission["outcomes"][0]["observation_id"]["value"]
            recorded = await self._call(
                session,
                "record",
                {
                    "request_id": "sub-context-bound",
                    "context": context,
                    "kind": "understanding",
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                    "question": "What happens in the app?",
                    "scope_paths": ["src/app.py"],
                    "conclusion": "The app emits line1.",
                    "observation_id": observation_id,
                },
            )
            self.assertEqual(recorded["$type"], "UnderstandingRecorded")
            return recorded

        recorded = await self._session(journey)
        self.assertEqual(
            recorded["understanding_id"]["value"],
            "u:sub-context-bound",
        )

    async def test_evidence_context_accepts_an_explicit_target(self) -> None:
        async def journey(session: ClientSession) -> dict:
            gap = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "req-context-conflict",
                    "reference": "src/app.py",
                    "evidence": [{"locator": "src/app.py"}],
                },
            )
            context = gap["admission"]["context"]
            recorded = await self._call(
                session,
                "record",
                {
                    "request_id": "sub-context-conflict",
                    "context": context,
                    "kind": "understanding",
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                    "question": "What happens in the app?",
                    "scope_paths": ["src/app.py"],
                    "conclusion": "The app emits line1.",
                    "locator": "src/app.py",
                },
            )
            self.assertEqual(recorded["$type"], "UnderstandingRecorded")
            return recorded

        recorded = await self._session(journey)
        self.assertEqual(recorded["version"]["value"], 1)

    async def test_exact_surface_resolves_ambiguity(self) -> None:
        async def journey(session: ClientSession) -> dict:
            await self._record_create(session, "sub-create-1")
            declared = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "surface-1",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "app",
                        "boundary": {"paths": ["src"], "symbols": []},
                        "parent": None,
                    },
                },
            )
            self.assertEqual(declared["$type"], "SurfaceDeclared")

            ambiguous = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "reference": "src/app.py",
                },
            )
            self.assertEqual(ambiguous["$type"], "AmbiguousSurface")
            candidate = next(
                item for item in ambiguous["candidates"] if item["kind"] == "FILE"
            )
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {
                        "kind": candidate["kind"],
                        "locator": candidate["locator"],
                    },
                },
            )

        result = await self._session(journey)
        self.assertEqual(result["$type"], "Answer")

    async def test_surface_boundary_update(self) -> None:
        async def journey(session: ClientSession) -> dict:
            created = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "surface-1",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "app",
                        "boundary": {"paths": ["src"], "symbols": []},
                        "parent": None,
                    },
                },
            )
            self.assertEqual(created["surface"]["boundary_version"], 1)
            return await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "surface-2",
                    "kind": "surface",
                    "action": "update",
                    "expected_boundary_version": 1,
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "app",
                        "boundary": {"paths": ["src", "styles"], "symbols": []},
                        "parent": None,
                    },
                },
            )

        updated = await self._session(journey)
        self.assertEqual(updated["$type"], "SurfaceDeclared")
        self.assertEqual(updated["surface"]["boundary_version"], 2)

    async def test_verification_run_is_returned_with_qualification(self) -> None:
        async def journey(session: ClientSession) -> dict:
            await self._record_create(session, "sub-create-1")
            recorded = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "verify-1",
                    "kind": "verification",
                    "run": {
                        "repository_id": REPOSITORY_ID,
                        "scope_description": "app tests",
                        "scope_paths": ["src/app.py"],
                        "observations": [],
                        "evidence": [
                            {
                                "$type": "source",
                                "locator": "src/app.py",
                                "ranges": [],
                            }
                        ],
                        "command": "pytest -q",
                        "scenario": None,
                        "outcome": "PASS",
                        "observed_at": "2026-11-02T12:00:00Z",
                        "observer": "tester",
                    },
                },
            )
            self.assertEqual(recorded["$type"], "VerificationRecorded")
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )

        answer = await self._session(journey)
        self.assertEqual(answer["$type"], "Answer")
        self.assertEqual(len(answer["verification"]), 1)
        self.assertEqual(answer["verification"][0]["run"]["outcome"], "PASS")
        self.assertEqual(answer["verification"][0]["qualification"]["state"], "CURRENT")

    async def test_invalidated_ask_returns_historical_content(self) -> None:
        async def journey(session: ClientSession) -> dict:
            await self._record_create(session, "sub-historical")
            _write(self.repo, "src/app.py", "changed\n")
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )

        result = await self._session(journey)
        self.assertEqual(result["$type"], "Gap")
        self.assertEqual(result["reason"], "invalidated")
        historical = result["historical"][0]
        self.assertEqual(historical["statement"], "The app emits line1.")
        self.assertEqual(historical["state"], "REASSESSMENT_REQUIRED")
        self.assertEqual(historical["understanding_version"]["value"], 1)
        self.assertTrue(historical["evidence"])

    async def test_stale_sibling_is_referenced_in_status(self) -> None:
        async def journey(session: ClientSession) -> dict:
            declared = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "status-service-declare",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "app-and-style",
                        "boundary": {
                            "paths": ["src/app.py", "styles/site.css"],
                            "symbols": [],
                        },
                    },
                },
            )
            self.assertEqual(declared["$type"], "SurfaceDeclared")
            created = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "sub-status",
                    "kind": "understanding",
                    "surface": {"kind": "SERVICE", "locator": "app-and-style"},
                    "question": "What happens in the app?",
                    "scope_paths": ["src/app.py", "styles/site.css"],
                    "conclusion": "The app emits line1.",
                    "locator": "src/app.py",
                },
            )
            understanding_id = created["understanding_id"]["value"]
            existing_ids = self._qualification_ids(created)
            added = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "sub-status-add",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": 1,
                    "actions": {
                        "add": [
                            {
                                "conclusion": "The site styles are red.",
                                "scope_paths": ["styles/site.css"],
                                "locator": "styles/site.css",
                            }
                        ]
                    },
                },
            )
            self.assertEqual(added["$type"], "UnderstandingRecorded", added)
            added_id = (self._qualification_ids(added) - existing_ids).pop()
            _write(self.repo, "styles/site.css", "body { color: blue; }\n")
            answer = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "SERVICE", "locator": "app-and-style"},
                },
            )
            return {"answer": answer, "added_id": added_id}

        outcome = await self._session(journey)
        result = outcome["answer"]
        self.assertEqual(result["$type"], "Answer")
        self.assertEqual(result["status"]["stale"], 1)
        stale = result["status"]["stale_refs"][0]
        self.assertEqual(stale["ref"]["conclusion_id"]["value"], outcome["added_id"])
        self.assertEqual(stale["understanding_version"]["value"], 2)
        self.assertEqual(stale["state"], "REASSESSMENT_REQUIRED")

    async def test_multi_file_verification_run_is_visible_on_each_file(self) -> None:
        async def journey(session: ClientSession) -> dict:
            await self._record_create(session, "sub-multi-app")
            _write(self.repo, "src/other.py", "other\n")
            other = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "sub-multi-other",
                    "kind": "understanding",
                    "surface": {"kind": "FILE", "locator": "src/other.py"},
                    "question": "What happens in the other module?",
                    "scope_paths": ["src/other.py"],
                    "conclusion": "The other module emits other.",
                    "locator": "src/other.py",
                },
            )
            self.assertEqual(other["$type"], "UnderstandingRecorded")
            verified = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "verify-multi",
                    "kind": "verification",
                    "run": {
                        "repository_id": REPOSITORY_ID,
                        "scope_description": "both modules",
                        "scope_paths": ["src/app.py", "src/other.py"],
                        "observations": [],
                        "evidence": [
                            {
                                "$type": "source",
                                "locator": "src/app.py",
                                "ranges": [],
                            }
                        ],
                        "command": "pytest -q",
                        "scenario": None,
                        "outcome": "PASS",
                        "observed_at": "2026-11-02T12:00:00Z",
                        "observer": "tester",
                    },
                },
            )
            self.assertEqual(verified["$type"], "VerificationRecorded")
            app = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )
            other_answer = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/other.py"},
                },
            )
            return {"app": app, "other": other_answer}

        result = await self._session(journey)
        self.assertEqual(len(result["app"]["verification"]), 1)
        self.assertEqual(len(result["other"]["verification"]), 1)

    async def test_continuation_recovers_omitted_evidence(self) -> None:
        _write(self.repo, "src/big.py", "line\n" * 500)

        async def journey(session: ClientSession) -> dict:
            first = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "req-big",
                    "surface": {"kind": "FILE", "locator": "src/big.py"},
                    "evidence": [{"locator": "src/big.py"}],
                },
            )
            self.assertEqual(first["$type"], "Gap")
            self.assertTrue(first["admission"].get("continuation"))
            return await self._call(
                session,
                "ask",
                {
                    "continuation": first["admission"]["continuation"],
                },
            )

        page = await self._session(journey, budget=1500)
        self.assertEqual(page["$type"], "EvidencePage")
        self.assertTrue(page["deliveries"])

    async def test_continuation_survives_a_fresh_process(self) -> None:
        _write(self.repo, "src/big.py", "line\n" * 500)

        async def first(session: ClientSession) -> str:
            gap = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "req-big",
                    "surface": {"kind": "FILE", "locator": "src/big.py"},
                    "evidence": [{"locator": "src/big.py"}],
                },
            )
            self.assertEqual(gap["$type"], "Gap")
            self.assertTrue(gap["admission"].get("continuation"))
            return gap["admission"]["continuation"]

        token = await self._session(first, budget=1500)

        async def second(session: ClientSession) -> dict:
            return await self._call(
                session,
                "ask",
                {
                    "continuation": token,
                },
            )

        page = await self._session(second, budget=1500)
        self.assertEqual(page["$type"], "EvidencePage")
        self.assertTrue(page["deliveries"])

    async def test_reconsider_record_succeeds_without_an_intervening_ask(self) -> None:
        async def journey(session: ClientSession) -> dict:
            created = await self._record_create(session, "sub-create-reconsider")
            understanding_id = created["understanding_id"]["value"]
            target_id = self._created_conclusion_id(created)
            _write(self.repo, "src/app.py", "changed\n")
            changed = await self._call(
                session,
                "reconsider",
                {
                    "repository_id": REPOSITORY_ID,
                    "changed_paths": ["src/app.py"],
                },
            )
            surface = next(
                item
                for item in changed["surfaces"]
                if item["surface"]["locator"] == "src/app.py"
            )
            conclusion = next(
                item
                for item in surface["conclusions"]
                if item["ref"]["understanding_id"]["value"] == understanding_id
            )
            self.assertEqual(conclusion["expected_version"]["value"], 1)
            updated = await self._call(
                session,
                "record",
                {
                    "request_id": "sub-correct-reconsider",
                    "context": changed["context"],
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": conclusion["expected_version"]["value"],
                    "actions": {
                        "correct": [
                            {
                                "conclusion_id": target_id,
                                "conclusion": "The app emits changed.",
                                "locator": "src/app.py",
                            }
                        ]
                    },
                },
            )
            self.assertEqual(updated["$type"], "UnderstandingRecorded", updated)
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                },
            )

        answer = await self._session(journey)
        self.assertEqual(answer["$type"], "Answer")
        self.assertEqual(
            self._answer_conclusions(answer)[0]["statement"], "The app emits changed."
        )

    async def test_reconsider_race_rejects_on_stale_expected_version(self) -> None:
        async def journey(session: ClientSession) -> dict:
            created = await self._record_create(session, "sub-race")
            understanding_id = created["understanding_id"]["value"]
            target_id = self._created_conclusion_id(created)
            _write(self.repo, "src/app.py", "changed\n")
            changed = await self._call(
                session,
                "reconsider",
                {
                    "repository_id": REPOSITORY_ID,
                    "changed_paths": ["src/app.py"],
                },
            )
            surface = next(
                item
                for item in changed["surfaces"]
                if item["surface"]["locator"] == "src/app.py"
            )
            expected = surface["conclusions"][0]["expected_version"]["value"]
            advanced = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "sub-race-advance",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": expected,
                    "actions": {
                        "add": [
                            {
                                "conclusion": "The app also emits line2.",
                                "locator": "src/app.py",
                            }
                        ]
                    },
                },
            )
            self.assertEqual(advanced["$type"], "UnderstandingRecorded", advanced)
            rejected = await self._call(
                session,
                "record",
                {
                    "request_id": "sub-race-correct",
                    "context": changed["context"],
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": expected,
                    "actions": {
                        "correct": [
                            {
                                "conclusion_id": target_id,
                                "conclusion": "The app emits race.",
                                "locator": "src/app.py",
                            }
                        ]
                    },
                },
            )
            return {"rejected": rejected, "expected": expected}

        outcome = await self._session(journey)
        rejected = outcome["rejected"]
        self.assertEqual(rejected["$type"], "Rejected")
        self.assertEqual(rejected["cause_kind"], "version_conflict")
        self.assertEqual(rejected["current_version"], outcome["expected"] + 1)

    async def test_service_context_binds_the_scope_of_a_support_create(self) -> None:
        paths = ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]
        for path in paths:
            _write(self.repo, path, f"{path} content\n")

        async def journey(session: ClientSession) -> dict:
            declared = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "svc-ctx-declare",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "pipeline",
                        "boundary": {"paths": paths, "symbols": []},
                        "parent": None,
                    },
                },
            )
            self.assertEqual(declared["$type"], "SurfaceDeclared")
            gap = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "svc-ctx-ask",
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                    "evidence": [{"locator": path} for path in paths],
                },
            )
            self.assertEqual(gap["$type"], "Gap", gap)
            self.assertIsNotNone(gap.get("admission"))
            created = await self._call(
                session,
                "record",
                {
                    "request_id": "svc-ctx-support",
                    "context": gap["admission"]["context"],
                    "kind": "understanding",
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                    "question": "How does the pipeline move data?",
                    "scope_paths": paths,
                    "conclusion": "The pipeline flows A through D.",
                    "support": [
                        {
                            "$type": "source",
                            "locator": path,
                            "ranges": [],
                        }
                        for path in paths
                    ],
                },
            )
            self.assertEqual(created["$type"], "UnderstandingRecorded", created)
            understanding_id = created["understanding_id"]["value"]
            answer = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                },
            )
            return {"understanding_id": understanding_id, "answer": answer}

        outcome = await self._session(journey)
        self.assertEqual(outcome["answer"]["$type"], "Answer")
        store = LifecycleStore(
            self.data / f"{REPOSITORY_ID}.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )
        self.addCleanup(store.close)
        understanding = store.get_understanding(outcome["understanding_id"])
        self.assertEqual(understanding.scope.paths, tuple(paths))

    async def test_declared_service_owns_a_four_file_conclusion_lifecycle(
        self,
    ) -> None:
        paths = ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]
        for path in paths:
            _write(self.repo, path, f"{path} content\n")

        async def journey(session: ClientSession) -> dict:
            ambiguous = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "svc-ambiguous",
                    "kind": "understanding",
                    "question": "How does the pipeline move data?",
                    "scope_paths": paths,
                    "conclusion": "The pipeline flows A through D.",
                    "locator": "src/a.py",
                },
            )
            self.assertEqual(ambiguous["$type"], "Rejected")
            self.assertEqual(ambiguous["cause_kind"], "surface_ambiguous")

            declared = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "svc-declare",
                    "kind": "surface",
                    "action": "create",
                    "surface": {
                        "kind": "SERVICE",
                        "locator": "pipeline",
                        "boundary": {"paths": paths, "symbols": []},
                        "parent": None,
                    },
                },
            )
            self.assertEqual(declared["$type"], "SurfaceDeclared")
            created = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "svc-create",
                    "kind": "understanding",
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                    "question": "How does the pipeline move data?",
                    "scope_paths": paths,
                    "conclusion": "The pipeline flows A through D.",
                    "support": [
                        {
                            "$type": "source",
                            "locator": path,
                            "ranges": [],
                        }
                        for path in paths
                    ],
                },
            )
            self.assertEqual(created["$type"], "UnderstandingRecorded", created)
            understanding_id = created["understanding_id"]["value"]
            target_id = self._created_conclusion_id(created)
            before = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                },
            )
            self.assertEqual(before["$type"], "Answer", before)

            _write(self.repo, "src/b.py", "src/b.py changed\n")
            changed = await self._call(
                session,
                "reconsider",
                {
                    "repository_id": REPOSITORY_ID,
                    "changed_paths": ["src/b.py"],
                },
            )
            surface = next(
                item
                for item in changed["surfaces"]
                if item["surface"]["locator"] == "pipeline"
            )
            self.assertIn("direct", [reason for reason in surface["reasons"]], surface)
            conclusion = surface["conclusions"][0]
            self.assertEqual(
                conclusion["ref"]["understanding_id"]["value"], understanding_id
            )
            self.assertEqual(conclusion["support"]["state"], "REASSESSMENT_REQUIRED")
            updated = await self._call(
                session,
                "record",
                {
                    "request_id": "svc-correct",
                    "context": changed["context"],
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": conclusion["expected_version"]["value"],
                    "actions": {
                        "correct": [
                            {
                                "conclusion_id": target_id,
                                "conclusion": "The pipeline flows A through D.",
                                "scope_paths": paths,
                                "support": [
                                    {
                                        "$type": "source",
                                        "locator": path,
                                        "ranges": [],
                                    }
                                    for path in paths
                                ],
                            }
                        ]
                    },
                },
            )
            self.assertEqual(updated["$type"], "UnderstandingRecorded", updated)
            return await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "surface": {"kind": "SERVICE", "locator": "pipeline"},
                },
            )

        after = await self._session(journey)
        self.assertEqual(after["$type"], "Answer", after)
        self.assertEqual(
            self._answer_conclusions(after)[0]["statement"],
            "The pipeline flows A through D.",
        )
        self.assertEqual(
            self._answer_conclusions(after)[0]["support"]["state"],
            "CURRENT",
        )

    async def test_challenge_raised_by_reconsider_is_settled_by_record(self) -> None:
        async def journey(session: ClientSession) -> dict:
            created = await self._record_create(session, "sub-challenge")
            self.assertEqual(created["$type"], "UnderstandingRecorded")
            understanding_id = created["understanding_id"]["value"]
            target_id = self._created_conclusion_id(created)
            challenged = await self._call(
                session,
                "reconsider",
                {
                    "repository_id": REPOSITORY_ID,
                    "challenge": {
                        "request_id": "ch-1",
                        "understanding_id": understanding_id,
                        "target_version": 1,
                        "target_conclusions": [
                            {
                                "understanding_id": understanding_id,
                                "conclusion_id": target_id,
                                "revision": 1,
                            }
                        ],
                        "reason": ("The cited source does not support the statement."),
                        "evidence": [],
                    },
                },
            )
            self.assertEqual(challenged["$type"], "Challenged")
            challenge = challenged["challenge"]
            challenge_id = challenge["challenge_id"]["value"]
            challenge_revision = challenge["challenge_revision"]["value"]
            settled = await self._call(
                session,
                "record",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "sub-challenge-settle",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": 1,
                    "actions": {
                        "confirm": [
                            {
                                "conclusion_id": target_id,
                                "locator": "src/app.py",
                            }
                        ]
                    },
                    "challenge_dispositions": [
                        {
                            "$type": "unresolved",
                            "challenge_id": challenge_id,
                            "expected_challenge_revision": challenge_revision,
                            "remaining_question": ("What evidence settles this?"),
                            "basis": "The dispute remains open.",
                        }
                    ],
                },
            )
            return {
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
                "settled": settled,
            }

        outcome = await self._session(journey)
        settled = outcome["settled"]
        self.assertEqual(settled["$type"], "UnderstandingRecorded")
        self.assertEqual(settled["version"]["value"], 2)
        store = LifecycleStore(
            self.data / f"{REPOSITORY_ID}.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )
        self.addCleanup(store.close)
        challenge = store.get_challenge(outcome["challenge_id"])
        self.assertEqual(
            challenge.challenge_revision.value,
            outcome["challenge_revision"] + 1,
        )
        self.assertEqual(challenge.state, m.ChallengeState.UNRESOLVED)

    async def test_live_context_cannot_be_misrouted_to_another_repository(self) -> None:
        other_id = "repo-other"
        other = self.repo.parent / other_id
        other.mkdir()
        _write(other, "src/app.py", "line1\nline2\n")
        store = LifecycleStore(
            self.data / f"{other_id}.db",
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )
        store.register_repository(other_id, str(other.resolve()))
        store.close()

        async def journey(session: ClientSession) -> dict:
            gap = await self._call(
                session,
                "ask",
                {
                    "repository_id": REPOSITORY_ID,
                    "request_id": "wrong-route-ask",
                    "surface": {"kind": "FILE", "locator": "src/app.py"},
                    "evidence": [{"locator": "src/app.py"}],
                },
            )
            self.assertEqual(gap["$type"], "Gap")
            context = gap["admission"]["context"]
            result = await self._call(
                session,
                "record",
                {
                    "request_id": "wrong-route-record",
                    "context": context,
                    "kind": "understanding",
                    "question": "What happens here?",
                    "scope_paths": ["src/app.py"],
                    "conclusion": "The app has content.",
                    "locator": "src/app.py",
                },
            )
            return result

        result = await self._session(journey, extra_repos=(other,))
        self.assertNotEqual(result["$type"], "Unavailable")
        self.assertNotIn("unknown context", json.dumps(result).lower())


if __name__ == "__main__":
    unittest.main()
