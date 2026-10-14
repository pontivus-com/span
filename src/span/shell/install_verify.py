"""Post-install verification for ``span-install``.

Runs under the installed interpreter (imports Span freely): provisions
each ``--repo``, asserts readiness plus schema version, performs one
status readiness check per repository, and prints a JSON receipt. Used by
both fresh installs and ``--verify`` doctor runs.

This verification is operational readiness only (A1). It never invokes
``explain`` and never establishes semantic knowledge.
"""

from __future__ import annotations

import argparse
import json
import pathlib

from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.mcp_server import ServerConfig, provision_repository
from span.shell.sqlite_store import SCHEMA_VERSION


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="span-install-verify")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--repo", action="append", default=[])
    return parser.parse_args(argv)


def _build_identity() -> dict:
    """Build identity: embedded source revision + content digest (S9 §5.9).

    Produced at packaging time so a dirty build cannot impersonate clean
    HEAD. Not a runtime repository scan, semantic fingerprint, or new
    tool. Records executable/package location with identifiers.

    Resolution order: packaged ``span/BUILD_IDENTITY`` written by the
    build (authoritative for installed distributions), then a git
    checkout probe for development trees, then ``unknown``.
    """
    import hashlib as _hashlib
    import sys as _sys

    try:
        from span import __version__ as _pkg_version
    except Exception:
        _pkg_version = "unknown"
    # Source revision: try git HEAD of the Span root, else unknown.
    # Content digest: canonical tool schemas digest (contract identity).
    try:
        from span.shell.mcp import TOOL_SCHEMAS as _schemas
        import json as _json

        _schema_digest = _hashlib.sha256(
            _json.dumps(_schemas, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
    except Exception:
        _schema_digest = "unknown"
    _revision = "unknown"
    _source_digest = "unknown"
    _origin = "unknown"
    try:
        import span as _span_pkg
        import pathlib as _pl

        _packaged = (
            _pl.Path(_span_pkg.__file__).resolve().parent / "BUILD_IDENTITY"
        )
        _text = _packaged.read_text(encoding="utf-8").strip()
        try:
            import json as _json

            _doc = _json.loads(_text)
            _revision = str(_doc.get("source_revision") or "unknown")
            _source_digest = str(_doc.get("source_digest") or "unknown")
        except Exception:
            _revision = _text or "unknown"
        if _revision != "unknown":
            _origin = "packaged"
    except Exception:
        pass
    if _origin == "unknown":
        try:
            import pathlib as _pl
            import subprocess as _sp

            _root = _pl.Path(__file__).resolve().parents[2]
            _rev = _sp.check_output(
                ["git", "-C", str(_root), "rev-parse", "HEAD"],
                text=True, timeout=5,
            ).strip()
            _dirty = _sp.call(
                ["git", "-C", str(_root), "diff", "--quiet"],
                timeout=5,
            ) != 0
            _revision = _rev + ("-dirty" if _dirty else "")
            _origin = "git"
        except Exception:
            pass
    return {
        "package_version": _pkg_version,
        "source_revision": _revision,
        "source_digest": _source_digest,
        "revision_origin": _origin,
        "schema_digest": _schema_digest,
        "executable": _sys.executable,
    }


def main(argv=None):
    args = parse_args(argv)
    config = ServerConfig(data_dir=pathlib.Path(args.data_dir))
    repos = []
    for target in args.repo:
        # Plain provider-neutral locator (canonical); legacy graft:
        # prefix still accepted transitionally by provisioning.
        provider_config = target
        try:
            context, result = provision_repository(
                config,
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator=provider_config,
                    structural_provider_config=provider_config,
                    authority_seeds=(),
                ),
            )
        except ValueError as exc:
            raise SystemExit(
                f"repository setup failed for {target}: {exc}"
            ) from None
        if result.readiness.value != "READY":
            raise SystemExit(
                f"repository not READY: {target}: {result.readiness.value}"
            )
        answer = ops.status(
            ops.SemanticStatusRequest(
                repository_id=result.repository_id,
                target=None,
                bounds=(
                    DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds
                ),
            ),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=ContinuationStore(),
            authority_seeds=(),
        )
        repos.append(
            {
                "locator": target,
                "repository_id": result.repository_id,
                "readiness": result.readiness.value,
                "store": result.semantic_store_status,
                "answer": answer.content.__class__.__name__,
            }
        )
    print(
        json.dumps(
            {
                "schema_version": int(SCHEMA_VERSION),
                "build_identity": _build_identity(),
                "repos": repos,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
