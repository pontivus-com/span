#!/usr/bin/env python3
"""Black-box cold-start probe for the installed ``span-mcp`` executable.

Runs under the isolated installed interpreter with ``PYTHONPATH``
removed. It proves the MCP handshake completes before any repository
provisioning: ``initialize`` and ``tools/list`` succeed on a fresh
process, data directory, and repository with no structural cache and no
semantic database. The explicit ``initialize_repository`` call then
performs the build, so the probe also proves the expensive setup moved
out of process startup.

No ``span`` import: this is an external MCP client.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys


def _registered_ids(tools):
    marker = "Registered repositories: "
    for tool in tools:
        text = tool.description or ""
        if marker not in text:
            continue
        tail = text.split(marker, 1)[1]
        listing = tail.split(".", 1)[0]
        return [part.strip() for part in listing.split(",") if part.strip()]
    return []


async def _run(exe, repo, data_dir):
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
            registered = _registered_ids(listed.tools)
            repo_id = registered[0] if len(registered) == 1 else None
            wiring = (
                pathlib.Path(data_dir)
                / "structural"
                / str(repo_id)
                / ".graph"
                / "wiring.json"
            )
            database = pathlib.Path(data_dir) / f"{repo_id}.db"
            before = {
                "wiring": wiring.is_file(),
                "database": database.is_file(),
            }
            result = await session.call_tool(
                "initialize_repository",
                {"repository_locator": str(repo)},
            )
            text = "".join(
                block.text
                for block in result.content
                if getattr(block, "type", "") == "text"
            )
            payload = json.loads(text)
            return {
                "server_version": initialized.server_info.version,
                "tools": names,
                "registered": registered,
                "before_initialize": before,
                "initialize": payload,
                "initialize_error": bool(result.is_error),
                "after_initialize": {
                    "wiring": wiring.is_file(),
                    "database": database.is_file(),
                },
            }


def main(argv):
    if len(argv) != 4:
        print(
            "usage: cold_start_probe.py <span-mcp> <repo> <data-dir>",
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
