#!/usr/bin/env python3
"""Black-box lifecycle probe for the installed ``span-mcp`` executable.

Runs under the isolated installed interpreter with ``PYTHONPATH`` removed and
imports no ``span`` module. It drives the shipped three-tool surface over MCP
stdio: list tools, ask cold, record, ask warm, retrieve an exact snapshot, and
confirm a retired tool name rejects with replacement guidance.
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
            cold, cold_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repository_id,
                    "request_id": "probe-ask-cold",
                    "reference": "src/alpha.py",
                    "question": "What does alpha declare?",
                },
            )
            created, created_error = await _call(
                session,
                "record",
                {
                    "repository_id": repository_id,
                    "request_id": "probe-create",
                    "kind": "understanding",
                    "surface": {"kind": "FILE", "locator": "src/alpha.py"},
                    "question": "What does alpha declare?",
                    "scope_paths": ["src/alpha.py"],
                    "conclusion": "Alpha declares VALUE = 1.",
                    "locator": "src/alpha.py",
                    "provenance": "installed probe",
                },
            )
            understanding_id = created["receipt"]["accepted_understanding_ids"][0][
                "value"
            ]
            warm, warm_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repository_id,
                    "request_id": "probe-ask-warm",
                    "reference": "src/alpha.py",
                    "question": "What does alpha declare?",
                },
            )
            retrieved, retrieved_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repository_id,
                    "selector": {
                        "$type": "UnderstandingSnapshotSelector",
                        "repository_id": repository_id,
                        "understanding_id": understanding_id,
                    },
                },
            )
            return {
                "server_version": initialized.server_info.version,
                "tools": names,
                "removed": removed,
                "removed_error": removed_error,
                "cold_error": cold_error,
                "cold_kind": cold.get("$type"),
                "created_error": created_error,
                "warm_error": warm_error,
                "retrieved_error": retrieved_error,
                "understanding_id": understanding_id,
                "found_kind": warm.get("$type"),
                "statement": warm["conclusions"][0]["statement"],
                "version": retrieved["version"]["version"]["value"],
            }


def main(argv):
    if len(argv) != 5:
        print(
            "usage: lifecycle_probe.py <span-mcp> <repo> <data-dir> <repository-id>",
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
