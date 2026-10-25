#!/usr/bin/env python3
"""Black-box authority-restart probe for installed ``span-mcp`` (EC-31).

Runs under the isolated installed interpreter with ``PYTHONPATH``
removed. It starts the installed server twice over MCP stdio against the
same data directory and repository:

1. process A initializes the repository with one authority seed;
2. process A exits;
3. process B starts fresh and performs no ``initialize_repository``;
4. process B asks one previously unestablished semantic question;
5. the returned ``PendingInterpretation`` must carry the restored
   authority seed in its task brief.

No ``span`` import and no direct SQLite inspection: this is an external
MCP client exercising the public lifecycle only.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys


def _text(result):
    return "".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


async def _call(exe, repo, data_dir, tool, arguments):
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
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            payload = json.loads(_text(result))
            return {
                "is_error": bool(result.is_error),
                "payload": payload,
            }


def _brief_authority(payload):
    return list(
        payload.get("request", {}).get("brief", {}).get("evidence_authority", ())
    )


async def _run(exe, repo, data_dir):
    repository_id = pathlib.Path(repo).name
    seed = {
        "$type": "EvidenceRef",
        "evidence_id": {
            "$type": "EvidenceId",
            "value": f"ev-{repository_id}-README.md",
        },
        "repository_id": repository_id,
        "source_kind": "DOCUMENTATION",
        "locator": "README.md",
    }
    first = await _call(
        exe,
        repo,
        data_dir,
        "initialize_repository",
        {
            "repository_locator": str(repo),
            "authority_seeds": [seed],
        },
    )
    if first["is_error"]:
        raise AssertionError(f"first initialize_repository failed: {first['payload']}")
    if first["payload"].get("store_readiness") != "READY":
        raise AssertionError(
            "first initialize_repository was not READY: " f"{first['payload']!r}"
        )

    question_slice = "EC-31 previously unasked authority restart question"
    # Fresh process, same data directory. No initialize_repository call:
    # the context must rehydrate the persisted seed by itself.
    second = await _call(
        exe,
        repo,
        data_dir,
        "explain",
        {
            "repository_id": repository_id,
            "target": {"name_or_locator": "src/alpha.py"},
            "question_selection": {"question_slice": question_slice},
        },
    )
    if second["is_error"]:
        raise AssertionError(f"fresh-process explain failed: {second['payload']}")
    payload = second["payload"]
    if payload.get("$type") != "PendingInterpretation":
        raise AssertionError(
            "fresh-process new question did not return "
            f"PendingInterpretation: {payload.get('$type')!r}"
        )
    if not payload.get("continuation"):
        raise AssertionError("fresh-process PendingInterpretation has no continuation")
    authority = _brief_authority(payload)
    if not any("README.md" in line for line in authority):
        raise AssertionError(
            "fresh-process pending brief did not carry the restored "
            f"authority seed: {authority!r}"
        )
    pending_question = payload.get("request", {}).get("question") or {}
    if pending_question.get("question_slice") != question_slice:
        raise AssertionError(
            "fresh-process pending question does not match the new "
            f"question: {pending_question.get('question_slice')!r}"
        )
    return {
        "phase": "EC-31",
        "ok": True,
        "repository_id": repository_id,
        "first_ready": first["payload"].get("store_readiness"),
        "restart_called_initialize": False,
        "pending": True,
        "question_slice": question_slice,
        "authority_seed_locator": "README.md",
        "brief_evidence_authority": authority,
    }


def main(argv):
    if len(argv) != 4:
        print(
            "usage: authority_restart_probe.py <span-mcp> <repo> <data-dir>",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            asyncio.run(_run(argv[1], argv[2], argv[3])),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
