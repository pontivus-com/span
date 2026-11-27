"""Post-install verification for ``span-install``.

Runs under the installed interpreter and is strictly observational. It
reports build/schema/root binding and store/provider availability for each
registered repository. It never initializes, migrates, rebuilds or invokes a
semantic operation; an absent store reports the explicit setup action.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import typing

from span.shell.readiness import (
    probe_active_functional_pyramid,
    probe_functional_pyramid_installation_store,
    observe_repositories,
    probe_governed_provenance,
    project_repository_guidance,
)
from span.shell.structural import canonical_root_from_config, repository_id_from_config


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="span-install-verify")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when structural or provenance acceptance fails",
    )
    parser.add_argument("--pending-setup", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _build_identity() -> dict[str, object]:
    """Observe the packaged revision, never infer it from a checkout."""
    import hashlib
    import sys

    from span import __version__
    from span.shell.build_identity import installed_build_identity
    from span.shell.mcp import TOOL_SCHEMAS

    identity = installed_build_identity()
    return {
        "package_version": __version__,
        "source_revision": identity["source_revision"] if identity else "unknown",
        "source_digest": identity["source_digest"] if identity else "unknown",
        "revision_origin": "packaged" if identity else "unknown",
        "schema_digest": hashlib.sha256(
            json.dumps(TOOL_SCHEMAS, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
        "executable": sys.executable,
    }


def _acceptance(
    installation: dict[str, object],
    active: dict[str, object],
    repos: list[dict[str, object]],
    receipt: dict[str, object],
    selected: set[str],
    *,
    pending_setup: bool = False,
) -> bool:
    from span.shell.install.governed import PENDING

    facts = [
        typing.cast(dict[str, object], repo["functional_pyramid"]) for repo in repos
    ]
    repositories_accept = all(
        bool(typing.cast(dict[str, object], repo["store"]).get("ready"))
        and bool(typing.cast(dict[str, object], fact["declarations"]).get("valid"))
        and typing.cast(dict[str, object], fact["provenance"]).get("state")
        not in ("PROVENANCE_MISMATCH", "PENDING_GOVERNED_INITIALIZATION")
        and typing.cast(dict[str, object], fact["activation_readiness"]).get("status")
        not in ("unavailable", "requires_repair")
        for repo, fact in zip(repos, facts)
    )
    pending = receipt.get(PENDING)
    pending_ok = pending is None
    if pending_setup and isinstance(pending, dict):
        entries = pending.get("repositories")
        pending_ok = (
            isinstance(entries, dict)
            and set(entries).issubset(selected)
            and all(
                typing.cast(dict[str, object], fact["provenance"]).get("state")
                == "PROVENANCE_MATCH"
                for fact in facts
                if fact["repository_id"] in entries
            )
        )
    return (
        pending_ok
        and bool(installation.get("ready"))
        and active.get("status") in ("valid", "not_active")
        and repositories_accept
    )


def project_final_receipt(
    data_dir: pathlib.Path,
    report: dict[str, object],
    receipt: dict[str, object],
    *,
    strict: bool,
) -> None:
    """Reproject installed observations against the unpublished receipt candidate."""
    repos = typing.cast(list[dict[str, object]], report.get("repos", []))
    if not repos and not strict:
        return
    active = typing.cast(dict[str, object], report["active_functional_pyramid"])
    installation = typing.cast(dict[str, object], report["functional_pyramid"])
    roots: dict[str, str | pathlib.Path] = {
        str(
            typing.cast(dict[str, object], repo["functional_pyramid"])["repository_id"]
        ): str(repo["canonical_root"])
        for repo in repos
    }
    if active != probe_active_functional_pyramid(data_dir, roots):
        raise ValueError("ACTIVE observations changed before receipt publication")
    for repo in repos:
        facts = typing.cast(dict[str, object], repo["functional_pyramid"])
        repository_id = str(facts["repository_id"])
        facts["provenance"] = probe_governed_provenance(
            data_dir,
            repository_id,
            str(repo["canonical_root"]),
            receipt_context=receipt,
        )
    project_repository_guidance(repos, active, receipt)
    report["acceptance_ok"] = _acceptance(
        installation, active, repos, receipt, set(roots)
    )
    if strict and not report["acceptance_ok"]:
        raise ValueError("finalized receipt candidate failed governed acceptance")


def main(argv=None):
    args = parse_args(argv)
    data_dir = pathlib.Path(args.data_dir)
    roots_by_repository: dict[str, str | pathlib.Path] = {
        repository_id_from_config(target): canonical_root_from_config(target)
        for target in args.repo
    }
    from span.shell.install.receipt import read_receipt

    receipt = read_receipt(data_dir) or {}
    installation = probe_functional_pyramid_installation_store(data_dir)
    active = probe_active_functional_pyramid(data_dir, roots_by_repository)
    repos = observe_repositories(
        data_dir, roots_by_repository, active, receipt, pending_setup=args.pending_setup
    )
    identity = _build_identity()
    acceptance_ok = _acceptance(
        installation,
        active,
        repos,
        receipt,
        set(roots_by_repository),
        pending_setup=args.pending_setup,
    )
    acceptance_ok = acceptance_ok and identity["revision_origin"] == "packaged"
    print(
        json.dumps(
            {
                "build_identity": identity,
                "data_dir": str(data_dir),
                "restart_required": True,
                "acceptance_ok": acceptance_ok,
                "functional_pyramid": installation,
                "active_functional_pyramid": active,
                "repos": repos,
            },
            sort_keys=True,
        )
    )
    if args.strict and not acceptance_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
