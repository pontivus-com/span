"""Host hook runner for Span lifecycle notices (read-only, bounded).

One canonical rule: an automatic hook maps a native event onto the same
readiness probe and support checks the ordinary runtime uses. Hooks never
initialize, migrate, record, reassess, interpret, rebuild, or run
repository-scale work. A missed or disabled hook cannot make stale
understanding look current, because correctness is evaluated by
``reassess``/retrieval, not by hook delivery.

Output is one bounded line per event. Routine current state prints nothing.

Commands:
  session-start      report an unavailable/absent store for the active repo
  source-changed     report dependent recorded conclusions for changed paths
  session-stop       same bounded notice for the session's changed paths
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from span.core import model as m
from span.core import support_rules as _support_rules
from span.shell.policy import HOOK_DIAGNOSTIC_LIMIT
from span.shell.readiness import probe_store

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
    """Select the longest registered root containing the active project."""
    active_root = repo_for_path(repo_root or os.getcwd(), mapping)
    if active_root is None:
        return {}
    return {active_root: mapping[active_root]}


def _repository_id(root: str) -> str:
    return os.path.basename(os.path.abspath(root))


def _readiness_notice(data_dir, root):
    readiness = probe_store(data_dir, _repository_id(root))
    if readiness.ready:
        return None
    action = readiness.action or "explicit setup is required"
    return (
        f"span: {readiness.repository_id} needs attention "
        f"({_readiness_label(readiness)}; {action})."
    )


def _readiness_label(readiness) -> str:
    if not readiness.exists:
        return "no store"
    if readiness.schema_version != readiness.expected_version:
        return (
            f"store schema {readiness.schema_version} "
            f"(expected {readiness.expected_version})"
        )
    return "store unbound"


def _affected_for_root(data_dir, root, rel_paths):
    """Bounded dependent lookup for changed repository-relative locators."""
    from span.shell.context import open_repository_context

    repository_id, context = open_repository_context(data_dir, root)
    affected: dict[str, m.SupportState] = {}
    try:
        for locator in tuple(rel_paths)[:HOOK_DIAGNOSTIC_LIMIT]:
            for observation_id in context.store.source_observation_ids_for_locator(
                repository_id, locator
            ):
                for ref in context.store.support_dependents("SOURCE", observation_id):
                    key = ref.understanding_id.value
                    evaluation = context.support.evaluate_revision(ref)
                    if key in affected:
                        affected[key] = _support_rules.worse_state(
                            affected[key], evaluation.state
                        )
                    else:
                        affected[key] = evaluation.state
    finally:
        context.store.close()
    return repository_id, affected


def _render_affected(repository_id, affected, *, close_prefix=False):
    if not affected:
        return None
    needing = {
        key: state
        for key, state in affected.items()
        if state is not m.SupportState.CURRENT
    }
    if not needing:
        return None
    names = sorted(needing)[:HOOK_DIAGNOSTIC_LIMIT]
    label = "close" if close_prefix else "needs attention"
    detail = ", ".join(names)
    more = "" if len(needing) <= HOOK_DIAGNOSTIC_LIMIT else "; more omitted"
    return (
        f"span: {repository_id} {label}: {len(needing)} recorded "
        f"understanding(s) affected ({detail}{more}); call reassess or "
        "understand_question."
    )


def cmd_session_start(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        print("span: no repositories registered (run span-install).")
        return
    mapping = scoped_repo_map(mapping, repo_root)
    for root in sorted(mapping):
        line = _readiness_notice(data_dir, root)
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


def _scoped_paths(mapping, paths):
    scoped: dict[str, list[str]] = {}
    for path in paths:
        root = repo_for_path(path, mapping)
        if root is None:
            continue
        scoped.setdefault(root, []).append(os.path.relpath(os.path.abspath(path), root))
    return scoped


def cmd_source_changed(data_dir, paths):
    if not paths:
        paths = _stdin_paths()
    paths = [p for p in paths if isinstance(p, str) and p]
    if not paths:
        return
    mapping = repo_map(data_dir)
    if not mapping:
        return
    for root, rel_paths in sorted(_scoped_paths(mapping, paths).items()):
        line = _readiness_notice(data_dir, root)
        if line:
            print(line)
            continue
        repository_id, affected = _affected_for_root(data_dir, root, rel_paths)
        rendered = _render_affected(repository_id, affected)
        if rendered:
            print(rendered)


def cmd_session_stop(data_dir, repo_root=None):
    mapping = repo_map(data_dir)
    if not mapping:
        return
    active = scoped_repo_map(mapping, repo_root)
    if not active:
        return
    root = next(iter(active))
    rel_paths = _scoped_paths({root: root}, _stdin_paths()).get(root, [])
    if not rel_paths:
        return
    repository_id, affected = _affected_for_root(data_dir, root, rel_paths)
    rendered = _render_affected(repository_id, affected, close_prefix=True)
    if rendered:
        print(rendered)


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
        choices=("session-start", "source-changed", "session-stop"),
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
