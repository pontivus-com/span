"""Uninstall, purge, and orphan reporting (stdlib only)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from span.shell.install.hosts import (
    remove_claude_hooks,
    remove_claude_registration,
    remove_codex_hooks,
    remove_codex_registration,
    remove_opencode_registration,
)
from span.shell.install.receipt import (
    read_receipt,
)
from span.shell.install.skills import (
    remove_agents_block,
    remove_deployed_skills,
)


def uninstall(data_dir, targets, opencode_config, dry_run=False):
    """Reverse every host-side write install performs.

    Registration, hook entries, the managed ``AGENTS.md`` block, deployed
    skills, and the receipt are removed. Repository data — stores and
    structural indexes — is never touched; ``--purge`` owns that, one
    explicit ID at a time. Each step tolerates an already-absent artifact,
    so a second run is a no-op.
    """
    receipt = read_receipt(data_dir) or {}
    registered = [Path(repo) for repo in receipt.get("repos", [])]
    effective_targets = list(dict.fromkeys([*targets, *registered]))
    config = opencode_config
    if config is None:
        registration = receipt.get("host_registration", {})
        opencode = (
            registration.get("opencode", {}) if isinstance(registration, dict) else {}
        )
        if isinstance(opencode, dict) and opencode.get("config"):
            config = opencode["config"]
    report = {
        "opencode": (
            remove_opencode_registration(config, dry_run=dry_run)
            if config is not None
            else {"status": "absent", "reason": "no opencode config known"}
        ),
        "codex": remove_codex_registration(dry_run=dry_run),
        "claude": remove_claude_registration(dry_run=dry_run),
        "hooks": {
            "codex": remove_codex_hooks(dry_run=dry_run),
            "claude": remove_claude_hooks(dry_run=dry_run),
        },
        "skills": remove_deployed_skills(dry_run=dry_run),
        "agents": {
            str(target): remove_agents_block(target, dry_run=dry_run)
            for target in effective_targets
        },
        "receipt": {"status": "absent"},
    }
    receipt_path = Path(data_dir) / "install.json"
    if receipt_path.is_file():
        print(f"+ remove receipt: {receipt_path}")
        if not dry_run:
            receipt_path.unlink()
        report["receipt"] = {"status": "removed", "path": str(receipt_path)}
    print("uninstall complete.")
    return report


def _valid_repository_id(repository_id):
    """One directory name: no separators, no traversal."""
    if not repository_id or repository_id in (".", ".."):
        return False
    if "/" in repository_id or "\\" in repository_id:
        return False
    if os.sep in repository_id or (
        os.altsep is not None and os.altsep in repository_id
    ):
        return False
    return True


def purge_repository(data_dir, repository_id, dry_run=False):
    """Remove exactly one repository ID's store and structural index.

    Explicit ID only. Nothing else in the data directory is touched, and
    an already-absent artifact is not an error.
    """
    if not _valid_repository_id(repository_id):
        raise SystemExit(
            f"invalid repository id {repository_id!r}: one directory name, "
            "no separators"
        )
    data = Path(data_dir)
    candidates = [
        data / f"{repository_id}.db",
        data / f"{repository_id}.db-wal",
        data / f"{repository_id}.db-shm",
        data / f"{repository_id}.db-journal",
    ]
    index_dir = data / "structural" / repository_id
    removed = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        print(f"+ purge {candidate}")
        if not dry_run:
            candidate.unlink()
        removed.append(str(candidate))
    if index_dir.is_dir():
        print(f"+ purge {index_dir}")
        if not dry_run:
            shutil.rmtree(index_dir)
        removed.append(str(index_dir))
    print(
        f"purge {repository_id}: {len(removed)} artifact(s) removed."
        if removed
        else f"purge {repository_id}: nothing to remove."
    )
    return {"repository_id": repository_id, "removed": removed}


def _present_repository_ids(data_dir):
    data = Path(data_dir)
    ids = {path.stem for path in data.glob("*.db")}
    structural = data / "structural"
    if structural.is_dir():
        ids |= {path.name for path in structural.iterdir() if path.is_dir()}
    return ids


def list_orphans(data_dir):
    """Report IDs on disk that the receipt does not name. Deletes nothing.

    A repository can be registered through ``--repo`` alone, so absence
    from a receipt is evidence of an unreceipted ID, not proof that the
    data is unused.
    """
    receipt = read_receipt(data_dir)
    registered = (
        {Path(repo).name for repo in receipt.get("repos", [])}
        if receipt is not None
        else set()
    )
    present = sorted(_present_repository_ids(data_dir))
    orphans = sorted(set(present) - registered)
    print(
        f"orphans: {len(orphans)} of {len(present)} id(s) are absent from "
        "the receipt (report only; no deletion)."
    )
    for orphan in orphans:
        print(f"  {orphan}")
    if receipt is None:
        print("no receipt found; every id is unreceipted, not necessarily unused.")
    return {
        "present": present,
        "registered": sorted(registered),
        "orphans": orphans,
        "receipt_present": receipt is not None,
    }
