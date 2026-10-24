#!/usr/bin/env python3
"""Black-box external MCP client process (Addendum M §M-10).

Runs outside the Span source tree with ``PYTHONPATH`` removed and
against the non-editably installed ``span-mcp`` executable. The client
logic lives in the sibling ``external_client`` module, which imports
only the standard library and the MCP client SDK. A meta-path guard
fails immediately if any ``span`` or ``span.*`` module is imported in
this process, and an audit hook records any attempt to read a Span
source or test module.

The client does not load Span source, Span test helpers, or this
repository's unit/integration modules. It consumes only the server's
``tools/list`` schemas/descriptions, previous responses, and fixture
content available to the simulated coding agent.
"""

from __future__ import annotations

import asyncio as _asyncio
import importlib.util as _importlib_util
import json as _json
import os as _os
import pathlib as _pathlib
import sys as _sys

_CLIENT_MODULE = _pathlib.Path(__file__).with_name("external_client.py").resolve()
_CLIENT_BYTECODE_PREFIX = str(
    _CLIENT_MODULE.parent / "__pycache__" / "external_client."
)
_FORBIDDEN_READS: list[str] = []


class _SpanImportGuard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "span" or fullname.startswith("span."):
            raise ImportError(
                "external client must not import Span implementation "
                f"module: {fullname}"
            )
        return None


def _install_read_guard() -> None:
    """Record reads of Span source, test, or installed modules.

    The sibling external-client module is the only Span test file the
    runner may load (§11). Everything else under Span source/test or
    the installed ``span`` package is a private-implementation read.
    """

    allowed = str(_CLIENT_MODULE)

    def _hook(event, args):
        if event != "open":
            return
        path = args[0] if args else None
        if isinstance(path, bytes):
            try:
                path = path.decode()
            except Exception:
                return
        if not isinstance(path, str) or not path.startswith("/"):
            return
        absolute = _os.path.abspath(path)
        if absolute == allowed:
            return
        if absolute.startswith(_CLIENT_BYTECODE_PREFIX):
            return
        if (
            "/src/span/" in absolute
            or "/site-packages/span/" in absolute
            or "/tests/unit/" in absolute
            or "/tests/acceptance/" in absolute
            or "/tests/integration/" in absolute
        ):
            _FORBIDDEN_READS.append(absolute)

    _sys.addaudithook(_hook)


_sys.meta_path.insert(0, _SpanImportGuard())
_install_read_guard()


def _load_client():
    module_path = _pathlib.Path(__file__).with_name("external_client.py")
    spec = _importlib_util.spec_from_file_location("_span_external_client", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load external client module: {module_path}")
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _check_host_artifacts(
    config_path, agents_path, exe, repo, data_dir, transcript
) -> None:
    config = _json.loads(_pathlib.Path(config_path).read_text(encoding="utf-8"))
    mcp = config["mcp"]
    assert "span" not in mcp, "legacy flat mcp.span registration remains"
    nested = mcp["servers"]["span"]
    assert nested["type"] == "local", nested
    assert nested["codemode"] is False, nested
    assert nested.get("disabled") in (None, False), nested
    expected_command = [
        str(exe),
        "--data-dir",
        str(data_dir),
        "--repo",
        str(repo),
    ]
    assert nested["command"] == expected_command, nested
    transcript.append(
        {
            "phase": "EC-28",
            "ok": True,
            "registration": "mcp.servers.span",
            "codemode": nested["codemode"],
            "disabled": nested.get("disabled"),
            "command": nested["command"],
        }
    )

    text = _pathlib.Path(agents_path).read_text(encoding="utf-8")
    for required in (
        "No status preflight is required",
        "every inventory member",
        "first-admission CQ-01 seed",
        "There is no separate reissue operation",
        "pass a returned page token unchanged",
        "reads and hooks never rebuild structural state",
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
    transcript.append(
        {
            "phase": "EC-29",
            "ok": True,
            "guidance": str(agents_path),
        }
    )


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: external_client_runner.py <span-mcp> <repo> "
            "<data-dir> <opencode-config> <agents-md>",
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
    _check_host_artifacts(
        argv[4],
        argv[5],
        argv[1],
        argv[2],
        argv[3],
        transcript,
    )
    forbidden = [
        name for name in _sys.modules if name == "span" or name.startswith("span.")
    ]
    if forbidden:
        raise SystemExit(
            "external client imported Span modules: " + ", ".join(forbidden)
        )
    if _FORBIDDEN_READS:
        raise SystemExit(
            "external client read Span implementation/test modules: "
            + ", ".join(sorted(set(_FORBIDDEN_READS)))
        )
    transcript.append(
        {
            "phase": "EC-30",
            "ok": True,
            "span_imports": [],
            "forbidden_reads": [],
        }
    )
    ec_results = {
        entry["phase"]: entry["ok"]
        for entry in transcript
        if str(entry.get("phase", "")).startswith("EC-")
    }
    expected = [f"EC-{index:02d}" for index in range(1, 31)]
    missing = [name for name in expected if name not in ec_results]
    if missing:
        raise SystemExit(
            "external acceptance matrix incomplete: missing " + ", ".join(missing)
        )
    print(
        _json.dumps(
            {
                "claims": [alpha, beta],
                "transcript": transcript,
                "span_imports": forbidden,
                "forbidden_reads": [],
                "ec_results": ec_results,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv))
