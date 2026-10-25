"""Host hook runner for Span lifecycle notices (read-only, fast).

One canonical policy: every automatic hook maps to exactly one
``status(..., mode=HOOK_FAST)`` call through the same shell opener the
MCP runtime uses, and prints only what that notice reports. This module
holds no semantic policy of its own — no SQL, no fingerprint
classification, no readiness interpretation, no next-action wording
beyond the notice's own ``recommended_action``.

Automatic hooks never initialize, explain, impact, trace,
authority-check, refresh, interpret, rebuild, or run repository-size
work. Any internal failure exits 0 silently (a hook must never break a
host session); diagnostics go to stderr.

Repository roots come from the install receipt
(``<data-dir>/install.json``: ``repos``). The canonical repository ID is
derived from the locator by the same rule explicit initialization uses;
storage is ``<data-dir>/<repository_id>.db`` and is opened only when it
already exists.

Commands (exception-oriented per addendum D §9: routine current state
prints nothing — silence is the all-current statement):
  session-start      readiness notice for the active repo only when it
                     needs action (unavailable or uninitialized)
  source-changed     read absolute paths from argv or stdin JSON and
                     report the canonical notice for that evidence scope
  session-stop       same canonical notice for the session's changed
                     paths when the host supplies them
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from span import service as ops
from span.core import model as m
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.context import open_repository_context

__all__ = [
    "cmd_session_start",
    "cmd_source_changed",
    "cmd_session_stop",
    "default_data_dir",
    "main",
]


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
    """Map absolute repository roots to their canonical locator."""
    receipt = load_receipt(data_dir)
    repos = receipt.get("repos", []) if isinstance(receipt, dict) else []
    return {
        os.path.abspath(root): os.path.abspath(root)
        for root in repos
        if isinstance(root, str)
    }


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

    Lifecycle hooks run in a host's active project directory. Selecting
    the longest registered root keeps nested repositories deterministic and
    prevents a session in one repository from reporting every installation
    in the shared Span data directory.
    """
    active_root = repo_for_path(repo_root or os.getcwd(), mapping)
    if active_root is None:
        return {}
    return {active_root: mapping[active_root]}


def _context_for(data_dir, root):
    """Open the canonical working context for one registered repository.

    The single seam every command uses; tests replace it with fixture
    providers. Production always goes through the shell opener.
    """
    return open_repository_context(data_dir, root)


def _notice(data_dir, root, scope_paths=None, close_prefix=False):
    """Run the canonical HOOK_FAST status call and render its notice.

    ``scope_paths is None`` maps to the no-target readiness intent;
    a tuple maps to the changed-evidence scope intent, with an empty
    tuple left explicitly empty (the service treats it as no subjects).
    """
    repository_id, context = _context_for(data_dir, root)
    try:
        target = (
            None
            if scope_paths is None
            else m.EvidenceScope(paths=tuple(scope_paths), evidence_refs=())
        )
        notice = ops.status(
            ops.SemanticStatusRequest(
                repository_id=repository_id,
                target=target,
                bounds=DEFAULT_SERVICE_BOUNDS_POLICY.hook_fast_bounds,
                mode=m.StatusMode.HOOK_FAST,
            ),
            structural=context.structural,
            evidence=context.evidence,
            store=context.store,
            continuations=context.continuations,
            authority_seeds=context.authority_seeds,
        )
    finally:
        context.store.close()
    return _render(repository_id, notice, close_prefix=close_prefix)


def _render(repository_id, notice, close_prefix=False):
    if notice.store_readiness is m.StoreReadiness.UNAVAILABLE:
        return f"span: {repository_id} needs attention " f"(repository unavailable)."
    if notice.store_readiness is m.StoreReadiness.UNINITIALIZED:
        action = (
            notice.recommended_action
            or "run initialize_repository in a dedicated setup session"
        )
        return f"span: {repository_id} UNINITIALIZED ({action})."
    if not (notice.affected_count or notice.stale_count or notice.unverifiable_count):
        return None
    parts = []
    if notice.stale_count:
        parts.append(f"{notice.stale_count} stale")
    if notice.unverifiable_count:
        parts.append(f"{notice.unverifiable_count} unverifiable")
    if not parts:
        parts.append(f"{notice.affected_count} affected")
    counts = ", ".join(parts)
    action = f" {notice.recommended_action}" if notice.recommended_action else ""
    if close_prefix:
        return f"span: {repository_id} close: {counts}.{action}"
    return f"span: {repository_id} needs attention ({counts}).{action}"


def cmd_session_start(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        print("span: no repositories registered (run span-install).")
        return
    mapping = scoped_repo_map(mapping, repo_root)
    for root in sorted(mapping):
        line = _notice(data_dir, root)
        if line:
            print(line)


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
                    "file_path",
                    "filePath",
                    "path",
                    "filename",
                    "file",
                    "absolute_path",
                ) and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(payload)
    return found


def cmd_source_changed(data_dir, paths):
    if not paths:
        paths = _stdin_paths()
    paths = [p for p in paths if isinstance(p, str) and p]
    if not paths:
        return
    mapping = repo_map(data_dir)
    if not mapping:
        return
    scoped = {}
    for path in paths:
        root = repo_for_path(path, mapping)
        if root is None:
            continue
        scoped.setdefault(root, []).append(os.path.relpath(os.path.abspath(path), root))
    for root in sorted(scoped):
        line = _notice(data_dir, root, scope_paths=tuple(scoped[root]))
        if line:
            print(line)


def cmd_session_stop(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        return
    active = scoped_repo_map(mapping, repo_root)
    if not active:
        return
    root = next(iter(active))
    # A host may supply the session's changed paths on stdin. Without
    # them the close carries an empty event scope, which the canonical
    # HOOK_FAST path reports as no affected subjects (silence).
    rel_paths = []
    for path in _stdin_paths():
        if repo_for_path(path, {root: root}) is None:
            continue
        rel_paths.append(os.path.relpath(os.path.abspath(path), root))
    line = _notice(data_dir, root, scope_paths=tuple(rel_paths), close_prefix=True)
    if line:
        print(line)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="span-hooks")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Store directory (default: platform data dir).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "Active repository root for session lifecycle commands "
            "(default: current working directory)."
        ),
    )
    parser.add_argument(
        "command",
        choices=(
            "session-start",
            "source-changed",
            "session-stop",
        ),
    )
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
