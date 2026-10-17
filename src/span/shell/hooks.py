"""Host hook runner for Span lifecycle notices (read-only, fast).

Stdlib only. Imports no Span code so any host ``python3`` can run it.
All commands are read-only SQLite SELECTs plus file hashing; they
never write semantic state, interpret, refresh, or initialize. Any
internal failure exits 0 silently (a hook must never break a host
session); diagnostics go to stderr.

Resolution order per repository root comes from the install receipt
(``<data-dir>/install.json``: ``repos`` plus ``data_dir``). Database
file is ``<data-dir>/<repository_id>.db`` where the id is derived
from the receipt's verify record when present, else the root's base
name. Only current-schema (5) stores are read; anything else is reported as
needing attention, never migrated or touched.

Commands (exception-oriented per addendum D §9: routine current
state prints nothing — silence is the all-current statement; every
printed line names its repository scope and states only what needs
action):
  session-start      one line for the active repo when it needs action
                     (uninitialized, needs attention, no established
                     coverage, or noncurrent/open work); silent when
                     the active repo has established, current coverage
  source-changed     read absolute paths from argv or stdin JSON;
                      report only paths whose dependents moved since
                      observation; silence otherwise
  session-stop       active-repo currents/stale counts only when stale,
                     unverifiable, open, or pending work remains;
                     silent on a clean close
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys

EXPECTED_SCHEMA = "6"


def _fail_silent(message):
    print(f"span-hooks: {message}", file=sys.stderr)
    raise SystemExit(0)


def load_receipt(data_dir):
    receipt_path = os.path.join(data_dir, "install.json")
    try:
        with open(receipt_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        _fail_silent(f"no readable install receipt at {receipt_path}: {exc}")
    return {}


def repo_map(data_dir):
    """Map absolute repo roots to (repository_id, db path)."""
    receipt = load_receipt(data_dir)
    repos = receipt.get("repos", []) if isinstance(receipt, dict) else []
    verify = {}
    if isinstance(receipt, dict) and isinstance(receipt.get("verify"), dict):
        for entry in receipt["verify"].get("repos", []) or []:
            if isinstance(entry, dict) and "locator" in entry:
                verify[entry["locator"]] = entry.get("repository_id")
    mapping = {}
    for root in repos:
        if not isinstance(root, str):
            continue
        root = os.path.abspath(root)
        repo_id = verify.get(root) or os.path.basename(root.rstrip(os.sep))
        mapping[root] = (
            repo_id,
            os.path.join(data_dir, f"{repo_id}.db"),
        )
    return mapping


def open_db(path):
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error as exc:
        return None, f"cannot open store: {exc}"
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
    except sqlite3.Error as exc:
        connection.close()
        return None, f"cannot read schema: {exc}"
    version = row[0] if row else None
    if version != EXPECTED_SCHEMA:
        connection.close()
        return None, f"schema {version} (expected {EXPECTED_SCHEMA})"
    return connection, None


def repo_for_path(path, mapping):
    absolute = os.path.abspath(path)
    best = None
    for root in mapping:
        if absolute == root or absolute.startswith(root + os.sep):
            if best is None or len(root) > len(best):
                best = root
    return best


def scoped_repo_map(mapping, repo_root):
    """Select the registered repository containing ``repo_root``.

    Lifecycle hooks run in a host's active project directory.  Selecting
    the longest registered root keeps nested repositories deterministic and
    prevents a session in one repository from reporting every installation
    in the shared Span data directory.
    """
    active_root = repo_for_path(repo_root or os.getcwd(), mapping)
    if active_root is None:
        return {}
    return {active_root: mapping[active_root]}


def _scope_counts(connection):
    """Current/stale/unverifiable claims + open/pending questions.

    Returns None when the scope needs no action (established and
    fully current); otherwise a concise mapping with nonzero
    categories only. Silence-when-clean is the all-current statement.
    """
    try:
        current = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE freshness_state='CURRENT'"
        ).fetchone()[0]
        stale = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE freshness_state='STALE'"
        ).fetchone()[0]
        unverifiable = connection.execute(
            "SELECT COUNT(*) FROM claims "
            "WHERE freshness_state='UNVERIFIABLE'"
        ).fetchone()[0]
        questions = connection.execute(
            "SELECT COUNT(*) FROM question_coverages"
        ).fetchone()[0]
        pending = connection.execute(
            "SELECT COUNT(*) FROM question_coverages "
            "WHERE disposition='PENDING'"
        ).fetchone()[0]
        open_ = connection.execute(
            "SELECT COUNT(*) FROM question_coverages "
            "WHERE disposition='OPEN'"
        ).fetchone()[0]
    except sqlite3.Error:
        return None
    if questions == 0:
        return {"established": False}
    action = {}
    if stale:
        action["stale"] = stale
    if unverifiable:
        action["unverifiable"] = unverifiable
    if open_:
        action["open"] = open_
    if pending:
        action["pending"] = pending
    if not action:
        return None
    action["current"] = current
    return action


def cmd_session_start(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        print("span: no repositories registered (run span-install).")
        return
    mapping = scoped_repo_map(mapping, repo_root)
    if not mapping:
        return
    for root in sorted(mapping):
        repo_id, db_path = mapping[root]
        if not os.path.exists(db_path):
            print(f"span: {repo_id} UNINITIALIZED (no store at {db_path}).")
            continue
        connection, problem = open_db(db_path)
        if problem is not None:
            print(f"span: {repo_id} needs attention ({problem}).")
            continue
        counts = _scope_counts(connection)
        connection.close()
        if counts is None:
            continue
        if not counts.get("established", True):
            print(
                f"span: {repo_id} READY with no established coverage — "
                f"orient with explain on a bounded scope."
            )
            continue
        parts = ", ".join(f"{v} {k}" for k, v in counts.items())
        print(f"span: {repo_id} needs attention ({parts}).")


def _stdin_paths():
    try:
        raw = sys.stdin.read()
    except OSError:
        return []
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except ValueError:
        return []
    found = []

    def walk(node, depth=0):
        if depth > 6 or len(found) > 32:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key in (
                    "file_path", "filePath", "path", "filename",
                    "file", "absolute_path",
                ) and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(payload)
    return found


def _sha256_file(path):
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def cmd_source_changed(data_dir, paths):
    if not paths:
        paths = _stdin_paths()
    paths = [p for p in paths if isinstance(p, str) and p]
    if not paths:
        return
    mapping = repo_map(data_dir)
    if not mapping:
        return
    notices = []
    for path in paths:
        root = repo_for_path(path, mapping)
        if root is None:
            continue
        repo_id, db_path = mapping[root]
        if not os.path.exists(db_path):
            continue
        connection, problem = open_db(db_path)
        if problem is not None:
            connection.close() if connection else None
            continue
        try:
            relative = os.path.relpath(os.path.abspath(path), root)
            rows = connection.execute(
                "SELECT DISTINCT semantic_id, semantic_kind, "
                "observed_fingerprint FROM evidence_dependencies "
                "WHERE repository_id=? AND locator=?",
                (repo_id, relative),
            ).fetchall()
        except sqlite3.Error:
            connection.close()
            continue
        connection.close()
        if not rows:
            continue
        current = _sha256_file(path)
        moved = [
            semantic_id for semantic_id, _, observed in rows
            if current is None or observed != current
        ]
        if moved:
            notices.append(
                f"span: {repo_id}: {relative} moved; "
                f"{len(moved)} dependent semantic item(s) need "
                f"status/refresh ({', '.join(moved[:5])}"
                f"{'…' if len(moved) > 5 else ''})."
            )
        else:
            # Unchanged dependents print nothing (exception-oriented):
            # silence is the all-current statement.
            pass
    for notice in notices:
        print(notice)


def cmd_session_stop(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        return
    mapping = scoped_repo_map(mapping, repo_root)
    if not mapping:
        return
    for root in sorted(mapping):
        repo_id, db_path = mapping[root]
        if not os.path.exists(db_path):
            continue
        connection, problem = open_db(db_path)
        if problem is not None:
            continue
        counts = _scope_counts(connection)
        connection.close()
        if counts is None or not counts.get("established", True):
            # Clean close — or nothing established yet — prints nothing:
            # session-start already prompts orientation where needed.
            continue
        parts = ", ".join(f"{v} {k}" for k, v in counts.items())
        print(f"span: {repo_id} close: {parts}.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="span-hooks")
    parser.add_argument(
        "--data-dir", default=None,
        help="Store directory (default: platform data dir).",
    )
    parser.add_argument(
        "--repo-root", default=None,
        help=(
            "Active repository root for session lifecycle commands "
            "(default: current working directory)."
        ),
    )
    parser.add_argument("command", choices=(
        "session-start", "source-changed", "session-stop",
    ))
    parser.add_argument("paths", nargs="*")
    return parser.parse_args(argv)


def default_data_dir():
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "share", "span", "data"),
    ]
    for candidate in candidates:
        if os.path.exists(os.path.join(candidate, "install.json")):
            return candidate
    return candidates[0]


def main(argv=None):
    args = parse_args(argv)
    data_dir = args.data_dir or default_data_dir()
    repo_root = args.repo_root or os.getcwd()
    try:
        if args.command == "session-start":
            cmd_session_start(data_dir, repo_root)
        elif args.command == "source-changed":
            cmd_source_changed(data_dir, args.paths)
        elif args.command == "session-stop":
            cmd_session_stop(data_dir, repo_root)
    except BrokenPipeError:
        raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001 - hooks never break sessions
        _fail_silent(f"internal error: {exc}")


if __name__ == "__main__":
    main()
