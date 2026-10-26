"""Data backup and read-only target census snapshots (stdlib only)."""

from __future__ import annotations

import datetime
import json
import shutil
import sqlite3
from pathlib import Path


def backup_data_dir(data_dir, dry_run=False):
    """Online SQLite backup before mutation ([design note E](docs/design-references.md#e) §9.2).

    Copies every ``*.db`` under the data dir into a timestamped
    ``backups/`` subdirectory using the sqlite3 online backup API
    (consistent under concurrent readers). Returns the backup dir, or
    None when there is nothing to back up. Never touches targets.
    """
    data_dir = Path(data_dir)
    if dry_run or not data_dir.is_dir():
        return None
    dbs = sorted(data_dir.glob("*.db"))
    if not dbs:
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest_dir = data_dir / "backups" / stamp
    try:
        dest_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SystemExit(f"cannot create backup dir {dest_dir}: {exc}")
    for db in dbs:
        try:
            src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                dst = sqlite3.connect(str(dest_dir / db.name))
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        except Exception as exc:
            raise SystemExit(f"backup failed for {db}: {exc}")
    print(f"data dir backed up: {dest_dir} ({len(dbs)} databases).")
    return str(dest_dir)


def snapshot_census(targets, out_path, dry_run=False):
    """Write a read-only artifact census snapshot ([design note E](docs/design-references.md#e) §9.2)."""
    payload = {str(t): target_artifact_snapshot(t) for t in targets}
    print(f"+ snapshot census: {out_path}")
    if dry_run:
        return payload
    Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def compare_census(path_a, path_b):
    """Diff two census snapshots with a readable verdict (E §9.2).

    Evidence only, never a gate: a changed wiring mtime may be a
    legitimate offline rebuild. Always exits 0; the verdict is in the
    printed lines.
    """

    def _load(path):
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"cannot read census snapshot {path}: {exc}")
        if not isinstance(data, dict):
            raise SystemExit(f"census snapshot is not an object: {path}")
        return data

    before, after = _load(path_a), _load(path_b)
    changed = []
    for target in sorted(set(before) | set(after)):
        old, new = before.get(target), after.get(target)
        if old != new:
            changed.append(target)
            print(f"CHANGED: {target}")
            print(f"  before: {json.dumps(old, sort_keys=True)}")
            print(f"  after:  {json.dumps(new, sort_keys=True)}")
        else:
            print(f"UNCHANGED: {target}")
    if changed:
        print(f"census verdict: {len(changed)} target(s) changed.")
    else:
        print("census verdict: no changes.")
    return changed


def _clean_build_staging(span_repo, dry_run=False):
    """Remove regenerable build staging ([design note E](docs/design-references.md#e) §9.2).

    A stale ``build/`` directory or egg-info from before a refactor
    flip is reused by setuptools and ships deleted modules into the
    venv — the exact silent-staleness class tier 1 exists to kill.
    Both paths are gitignored regenerables; removing them can only
    force a clean build, never lose source.
    """
    removed = []
    for candidate in (
        Path(span_repo) / "build",
        *Path(span_repo, "src").glob("*.egg-info"),
    ):
        if not candidate.exists() and not candidate.is_symlink():
            continue
        print(f"+ clean build staging: {candidate}")
        if dry_run:
            removed.append(str(candidate))
            continue
        if candidate.is_symlink() or candidate.is_file():
            candidate.unlink()
        else:
            shutil.rmtree(candidate)
        removed.append(str(candidate))
    return removed


def target_artifact_snapshot(target):
    """Read-only census of the target structural-index tree (E-14).

    Stdlib-only duplicate of the provider census: counts Markdown cards
    beside the machine-readable index and records wiring identity. Creates
    nothing, builds nothing, writes nothing.
    """
    root = Path(target)
    wiring = root / "graft" / ".graph" / "wiring.json"
    try:
        stat = wiring.stat()
        wiring_info = {
            "present": True,
            "mtime_ns": stat.st_mtime_ns,
            "size_bytes": stat.st_size,
        }
    except OSError:
        wiring_info = {
            "present": False,
            "mtime_ns": None,
            "size_bytes": None,
        }
    cards = 0
    index_md = False
    graph_dir = root / "graft"
    if graph_dir.is_dir():
        try:
            paths = sorted(graph_dir.rglob("*"))
        except OSError:
            paths = []
        for path in paths:
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if path.suffix != ".md":
                continue
            if path.name == "INDEX.md" and path.parent == graph_dir:
                index_md = True
            cards += 1
    return {
        "wiring": wiring_info,
        "markdown_cards": cards,
        "index_md": index_md,
    }
