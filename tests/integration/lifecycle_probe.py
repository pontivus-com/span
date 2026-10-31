#!/usr/bin/env python3
"""Black-box lifecycle probe for the installed ``span-mcp`` executable.

Runs under the isolated installed interpreter with ``PYTHONPATH`` removed and
imports no ``span`` module. It drives the shipped separate-tool surface over
MCP stdio: list tools, admit evidence, record an understanding, discover it
from different wording, retrieve the exact snapshot, and confirm retired tool
names reject with replacement guidance.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys


def _text(result) -> str:
    return "".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


async def _call(session, name, arguments):
    result = await session.call_tool(name, arguments)
    text = _text(result)
    try:
        payload = json.loads(text)
    except ValueError:
        payload = {"raw": text}
    return payload, bool(result.is_error)


async def _run(exe, repo, data_dir, repository_id):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    params = StdioServerParameters(
        command=exe,
        args=["--data-dir", str(data_dir), "--repo", str(repo)],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            names = [tool.name for tool in listed.tools]

            removed, removed_error = await _call(
                session, "explain", {"repository_id": repository_id}
            )
            admitted, admitted_error = await _call(
                session,
                "evidence_start",
                {
                    "repository_id": repository_id,
                    "request_id": {"value": "probe-evidence"},
                    "scope": {"paths": ["src/alpha.py"], "evidence_refs": []},
                    "requests": [{"locator": "src/alpha.py", "ranges": []}],
                },
            )
            observation = admitted["outcomes"][0]["observation_id"]["value"]
            context_id = admitted["context"]["context_id"]["value"]
            created, created_error = await _call(
                session,
                "record_create",
                {
                    "identity": {
                        "repository_id": repository_id,
                        "context_id": context_id,
                        "submission_id": "probe-create",
                    },
                    "target": {
                        "$type": "ExplicitTargetWire",
                        "question": "What does alpha declare?",
                        "scope_paths": ["src/alpha.py"],
                        "scope_evidence_refs": [],
                    },
                    "conclusions": [
                        {
                            "conclusion_id": "c-1",
                            "statement": "Alpha declares VALUE = 1.",
                            "assertion_nature": "DESCRIPTIVE",
                            "scope_paths": ["src/alpha.py"],
                            "scope_evidence_refs": [],
                            "support": [
                                {
                                    "$type": "SourceSupportWire",
                                    "observation_id": observation,
                                }
                            ],
                            "basis_derivation": "EXPLICIT_EVIDENCE",
                            "basis_summary": "read src/alpha.py",
                            "basis_input_refs": [],
                        }
                    ],
                    "gaps": [],
                    "provenance": "installed probe",
                },
            )
            receipt = created["receipt"]
            understanding_id = receipt["accepted_understanding_ids"][0]["value"]
            found, found_error = await _call(
                session,
                "understand_question",
                {
                    "repository_id": repository_id,
                    "request_id": {"value": "probe-question"},
                    "question": "Which value does the alpha module set?",
                    "scope": {"paths": ["src/alpha.py"], "evidence_refs": []},
                },
            )
            retrieved, retrieved_error = await _call(
                session,
                "understand_retrieve",
                {
                    "$type": "UnderstandingSnapshotSelector",
                    "repository_id": repository_id,
                    "understanding_id": understanding_id,
                },
            )
            return {
                "server_version": initialized.server_info.version,
                "tools": names,
                "removed": removed,
                "removed_error": removed_error,
                "admitted_error": admitted_error,
                "created_error": created_error,
                "created": created,
                "admitted": admitted,
                "found_error": found_error,
                "retrieved_error": retrieved_error,
                "observation": observation,
                "context_id": context_id,
                "understanding_id": understanding_id,
                "found_kind": found.get("$type"),
                "statement": retrieved["conclusions"][0]["content"]["statement"],
                "version": retrieved["version"]["version"]["value"],
            }


def main(argv):
    if len(argv) != 5:
        print(
            "usage: lifecycle_probe.py <span-mcp> <repo> <data-dir> " "<repository-id>",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            asyncio.run(_run(argv[1], argv[2], argv[3], argv[4])),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
