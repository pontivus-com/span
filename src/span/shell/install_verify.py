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

from span.shell.readiness import (
    probe_active_functional_pyramid,
    probe_functional_pyramid_installation_store,
    probe_functional_pyramid_repository,
    probe_store,
    probe_structural,
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
    parser.add_argument(
        "--pending-setup", action="store_true", help=argparse.SUPPRESS
    )
    return parser.parse_args(argv)


def _build_identity() -> dict:
    """Embedded build identity + schema digest; never a runtime repo scan."""
    import hashlib as _hashlib
    import sys as _sys

    try:
        from span import __version__ as _pkg_version
    except Exception:
        _pkg_version = "unknown"
    try:
        from span.shell.mcp import TOOL_SCHEMAS as _schemas

        _schema_digest = _hashlib.sha256(
            json.dumps(_schemas, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
    except Exception:
        _schema_digest = "unknown"
    _revision = "unknown"
    _source_digest = "unknown"
    _origin = "unknown"
    try:
        import span as _span_pkg

        packaged = pathlib.Path(_span_pkg.__file__).resolve().parent / "BUILD_IDENTITY"
        text = packaged.read_text(encoding="utf-8").strip()
        try:
            document = json.loads(text)
            _revision = str(document.get("source_revision") or "unknown")
            _source_digest = str(document.get("source_digest") or "unknown")
        except Exception:
            _revision = text or "unknown"
        if _revision != "unknown":
            _origin = "packaged"
    except Exception:
        pass
    if _origin == "unknown":
        try:
            import subprocess as _sp

            root = pathlib.Path(__file__).resolve().parents[3]
            _revision = _sp.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
                timeout=5,
            ).strip()
            dirty = (
                _sp.call(["git", "-C", str(root), "diff", "--quiet"], timeout=5) != 0
            )
            _revision += "-dirty" if dirty else ""
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
    data_dir = pathlib.Path(args.data_dir)
    repos = []
    roots_by_repository: dict[str, str] = {}
    for target in args.repo:
        repository_id = repository_id_from_config(target)
        canonical_root = canonical_root_from_config(target)
        roots_by_repository[repository_id] = canonical_root
        readiness = probe_store(data_dir, repository_id)
        repos.append(
            {
                "locator": target,
                "canonical_root": canonical_root,
                "store": readiness.payload(),
                "provider": probe_structural(data_dir, repository_id),
                "functional_pyramid": probe_functional_pyramid_repository(
                    data_dir,
                    repository_id,
                    canonical_root,
                    pending_setup=args.pending_setup,
                ),
            }
        )
    installation = probe_functional_pyramid_installation_store(data_dir)
    active = probe_active_functional_pyramid(data_dir, roots_by_repository)
    repositories_accept = all(
        bool(repo["store"].get("ready"))
        and bool(repo["functional_pyramid"]["declarations"].get("valid"))
        and repo["functional_pyramid"]["provenance"].get("state")
        not in ("PROVENANCE_MISMATCH", "PENDING_GOVERNED_INITIALIZATION")
        for repo in repos
    )
    from span.shell.install.governed import PENDING
    from span.shell.install.receipt import read_receipt

    receipt = read_receipt(data_dir) or {}
    pending = receipt.get(PENDING)
    pending_ok = pending is None
    if args.pending_setup and isinstance(pending, dict):
        pending_entries = pending.get("repositories")
        pending_ok = (
            isinstance(pending_entries, dict)
            and set(pending_entries).issubset(roots_by_repository)
            and all(
                repo["functional_pyramid"]["provenance"].get("state") == "PROVENANCE_MATCH"
                for repo in repos
                if repo["functional_pyramid"]["repository_id"] in pending_entries
            )
        )
    acceptance_ok = (
        pending_ok and bool(installation.get("ready"))
        and active.get("status") in ("valid", "not_active")
        and repositories_accept
    )
    print(
        json.dumps(
            {
                "build_identity": _build_identity(),
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
