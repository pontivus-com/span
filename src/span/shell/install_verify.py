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
                "repos": repos,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
