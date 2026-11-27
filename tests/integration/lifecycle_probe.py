#!/usr/bin/env python3
"""Black-box lifecycle probe for the installed ``span-mcp`` executable.

Runs under the isolated installed interpreter with ``PYTHONPATH`` removed and
imports no ``span`` module. It drives the shipped three-tool surface over MCP
stdio: list tools, ask cold, record, ask warm, retrieve an exact snapshot, and
confirm a non-current tool name follows the ordinary unknown-tool path.
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

            unknown, unknown_error = await _call(
                session, "explain", {"repository_id": repository_id}
            )
            cold, cold_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repository_id,
                    "reference": "src/alpha.py",
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
            understanding_id = created["understanding_id"]["value"]
            conclusion_id = created["affected_revisions"][0]["conclusion_id"]["value"]
            curated, curated_error = await _call(
                session,
                "record",
                {
                    "repository_id": repository_id,
                    "request_id": "probe-curate",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": created["version"]["value"],
                    "actions": {
                        "curate": [
                            {
                                "conclusion_id": conclusion_id,
                                "reasoning": "installed probe review",
                            }
                        ]
                    },
                    "provenance": "installed probe reviewer",
                },
            )
            warm, warm_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repository_id,
                    "reference": "src/alpha.py",
                },
            )
            retrieved, retrieved_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "UnderstandingSnapshotSelector",
                        "repository_id": repository_id,
                        "understanding_id": understanding_id,
                    },
                },
            )

            fp_member = {
                "repository_id": repository_id,
                "declaration_sources": [
                    {"locator": "docs/functional-pyramid.json", "ranges": []}
                ],
            }
            fp_status_before, fp_status_before_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidSelector",
                        "repository_id": repository_id,
                    }
                },
            )
            fp_candidate, fp_candidate_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidCandidateSelector",
                        "action": "activate",
                        "members": [fp_member],
                    }
                },
            )
            fp_activate, fp_activate_error = await _call(
                session,
                "record",
                {
                    "request_id": "fp-installed-activate",
                    "kind": "functional_pyramid",
                    "action": "activate",
                    "members": [fp_member],
                },
            )
            fp_status_after, fp_status_after_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidSelector",
                        "repository_id": repository_id,
                    }
                },
            )
            fp_receipt, fp_receipt_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidReceiptSelector",
                        "request_id": {"value": "fp-installed-activate"},
                    }
                },
            )
            return {
                "server_version": initialized.server_info.version,
                "tools": names,
                "unknown": unknown,
                "unknown_error": unknown_error,
                "cold_error": cold_error,
                "cold_kind": cold.get("$type"),
                "created_error": created_error,
                "curated_error": curated_error,
                "curated_kind": curated.get("$type"),
                "warm_error": warm_error,
                "retrieved_error": retrieved_error,
                "understanding_id": understanding_id,
                "found_kind": warm.get("$type"),
                "statement": warm["groups"][0]["conclusions"][0]["statement"],
                "version": retrieved["version"]["value"],
                "fp_status_before_error": fp_status_before_error,
                "fp_status_before_kind": fp_status_before.get("$type"),
                "fp_status_before_state": fp_status_before.get("state"),
                "fp_candidate_error": fp_candidate_error,
                "fp_candidate_kind": fp_candidate.get("$type"),
                "fp_activation_ready": fp_candidate.get("activation_ready"),
                "fp_activate_error": fp_activate_error,
                "fp_activate_kind": fp_activate.get("$type"),
                "fp_status_after_error": fp_status_after_error,
                "fp_status_after_state": fp_status_after.get("state"),
                "fp_status_after_health": fp_status_after.get("health"),
                "fp_receipt_error": fp_receipt_error,
                "fp_receipt_kind": fp_receipt.get("$type"),
                "fp_receipt_action": fp_receipt.get("action"),
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
