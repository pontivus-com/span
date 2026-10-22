#!/usr/bin/env python3
"""Black-box external MCP client process (Addendum M §M-10).

Runs outside the Span source tree with ``PYTHONPATH`` removed and
against the non-editably installed ``span-mcp`` executable. The client
logic lives in the sibling ``external_client`` module, which imports
only the standard library and the MCP client SDK. A meta-path guard
fails immediately if any ``span`` or ``span.*`` module is imported in
this process.

The client does not load Span source, Span test helpers, or this
repository's unit/integration modules. It consumes only the server's
``tools/list`` schemas/descriptions, previous responses, and fixture
content available to the simulated coding agent.
"""

from __future__ import annotations

import asyncio as _asyncio
import importlib.util as _importlib_util
import json as _json
import pathlib as _pathlib
import sys as _sys


class _SpanImportGuard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "span" or fullname.startswith("span."):
            raise ImportError(
                "external client must not import Span implementation "
                f"module: {fullname}"
            )
        return None


_sys.meta_path.insert(0, _SpanImportGuard())


def _load_client():
    module_path = _pathlib.Path(__file__).with_name("external_client.py")
    spec = _importlib_util.spec_from_file_location(
        "_span_external_client", module_path
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load external client module: {module_path}")
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _check_host_artifacts(config_path, agents_path) -> None:
    config = _json.loads(
        _pathlib.Path(config_path).read_text(encoding="utf-8")
    )
    mcp = config["mcp"]
    assert "span" not in mcp, "legacy flat mcp.span registration remains"
    nested = mcp["servers"]["span"]
    assert nested["type"] == "local", nested
    assert nested["codemode"] is False, nested
    assert nested.get("disabled") in (None, False), nested
    text = _pathlib.Path(agents_path).read_text(encoding="utf-8")
    for required in (
        "No status preflight is required",
        "every inventory member",
        "first-admission CQ-01 seed",
        "There is no separate reissue operation",
        "pass a returned page token unchanged",
        "Ordinary Span reads and hooks never rebuild structural state",
    ):
        assert required in text, required
    for forbidden in (
        "reissue_interpretation",
        "pgq:",
        "pgv:",
        "pgn:",
        "cont-*",
        "rebuilds the structural index",
    ):
        assert forbidden not in text, forbidden


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 6):
        print(
            "usage: external_client_runner.py <span-mcp> <repo> "
            "<data-dir> [opencode-config] [agents-md]",
            file=_sys.stderr,
        )
        return 2
    client = _load_client()
    transcript: list[dict] = []
    alpha, beta = _asyncio.run(
        client.lane(
            str(argv[1]),
            _pathlib.Path(argv[2]),
            _pathlib.Path(argv[3]),
            transcript,
        )
    )
    if len(argv) == 6:
        _check_host_artifacts(argv[4], argv[5])
    forbidden = [
        name for name in _sys.modules
        if name == "span" or name.startswith("span.")
    ]
    if forbidden:
        raise SystemExit(
            "external client imported Span modules: " + ", ".join(forbidden)
        )
    print(_json.dumps({
        "claims": [alpha, beta],
        "transcript": transcript,
        "span_imports": forbidden,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv))
