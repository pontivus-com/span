"""Host hook runner for Span lifecycle notices (read-only, bounded).

One canonical rule: an automatic hook maps a native event onto the same
readiness and dependency-effect projection the ordinary runtime uses. Hooks
never initialize, migrate, record, issue re-establishment contexts, interpret,
rebuild, or run repository-scale work. A missed or disabled hook cannot make
stale understanding look current, because correctness is evaluated by the
lifecycle operations, not by hook delivery.

Output is one bounded line per event. Routine current state prints nothing.

Commands:
  session-start      report an unavailable/absent store for the active repo
  source-changed     report dependent recorded conclusions for changed paths
  session-stop       same bounded notice for the session's changed paths
  codex-post-tool    translate Codex apply_patch PostToolUse into JSON context
  claude-post-tool   translate Claude Write/Edit PostToolUse into JSON context
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import typing as _typing

from span.core import model as m
from span.shell.install.receipt import read_receipt
from span.shell.policy import HOOK_DIAGNOSTIC_LIMIT
from span.shell.readiness import probe_store

__all__ = [
    "ADOPTION_PRIMER",
    "cmd_adoption_primer",
    "cmd_claude_post_tool",
    "cmd_codex_post_tool",
    "cmd_session_start",
    "cmd_source_changed",
    "cmd_session_stop",
    "default_data_dir",
    "main",
]

#: FD-58 adoption notice. It states existence, not currency; it names the
#: operation and the direct tool; it names no surface and asks no question.
ADOPTION_PRIMER = (
    "Span lifecycle is active for this repository. Before ordinary governed "
    "work, use the direct tool ending in `_ask` with FunctionalPyramidSelector "
    "to resolve participation and health; follow the span-functional-pyramid "
    "skill for UNCONFIGURED or ACTIVE/DEGRADED state. For exact directory "
    "governance in ACTIVE state, use FunctionalPyramidDirectorySelector through "
    "the same ask tool; never infer applicability from filenames or proximity. "
    "For ACTIVE/VALID or descriptive-only EXCLUDED work, ask the relevant surface "
    "before source "
    "access used to derive understanding, with no question or request identity. "
    "Use exact recorded-question selection only when that metadata is known."
)


def _fail_silent(message):
    print(f"span-hooks: {message}", file=sys.stderr)
    raise SystemExit(0)


def load_receipt(data_dir):
    try:
        return read_receipt(data_dir)
    except SystemExit as exc:
        _fail_silent(str(exc))
    return None


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


def _installation_inputs(
    mapping: dict[str, str],
) -> tuple[dict[str, str], _typing.Callable[[str], str]]:
    """Return the exact registered repository set and locator resolver."""
    roots = {_repository_id(root): root for root in mapping}

    def repository_locator(repository_id: str) -> str:
        try:
            return roots[repository_id]
        except KeyError as exc:
            raise ValueError(f"repository is not registered: {repository_id}") from exc

    return roots, repository_locator


def _functional_pyramid_status(
    data_dir: str | pathlib.Path,
    mapping: dict[str, str],
    repository_id: str,
) -> m.FunctionalPyramidStatus | None:
    """Obtain canonical participation/health through installation composition."""
    from span.shell.installation_runtime import open_installation_runtime

    roots, repository_locator = _installation_inputs(mapping)
    with open_installation_runtime(
        data_dir,
        repository_locator=repository_locator,
        registered_repository_ids=lambda: tuple(sorted(roots)),
    ) as installation:
        service = installation.functional_pyramid
        if service is None:
            return None
        return service.status(m.FunctionalPyramidSelector(repository_id=repository_id))


def _functional_pyramid_obligation(
    repository_id: str,
    status: m.FunctionalPyramidStatus,
) -> str | None:
    """Render only the FD-94 Functional Pyramid obligation for one status."""
    if status.state is m.FunctionalPyramidParticipationState.EXCLUDED:
        return None
    if status.state is m.FunctionalPyramidParticipationState.UNCONFIGURED:
        return (
            "Functional Pyramid UNCONFIGURED; governed use requires the "
            "span-functional-pyramid status/candidate lifecycle before activation"
        )
    if status.health is m.FunctionalPyramidHealth.DEGRADED:
        return (
            "Functional Pyramid ACTIVE/DEGRADED; governance needs attention "
            "before governed completion via FunctionalPyramidSelector and the "
            "span-functional-pyramid lifecycle"
        )
    return None


def _functional_pyramid_notice(
    data_dir: str | pathlib.Path,
    mapping: dict[str, str],
    root: str,
) -> str | None:
    """Render only the FD-94 governance obligation from canonical status."""
    repository_id = _repository_id(root)
    try:
        status = _functional_pyramid_status(data_dir, mapping, repository_id)
    except (OSError, ValueError):
        return (
            f"span: {repository_id} Functional Pyramid state is unavailable; "
            "run installer verification before governance work."
        )
    if status is None:
        return (
            f"span: {repository_id} Functional Pyramid state is unavailable; "
            "run installer verification before governance work."
        )
    obligation = _functional_pyramid_obligation(repository_id, status)
    return f"span: {repository_id} {obligation}." if obligation else None


def _session_entry_notice(
    data_dir: str | pathlib.Path,
    mapping: dict[str, str],
    root: str,
) -> str:
    """Compose exactly one FD-58/FD-94 entry notice from canonical state."""
    repository_id = _repository_id(root)
    try:
        status = _functional_pyramid_status(data_dir, mapping, repository_id)
    except (OSError, ValueError):
        status = None

    semantic = (
        "ask the relevant surface before source access used to derive "
        "understanding, with no question or request identity"
    )
    if status is None:
        return (
            f"span: {repository_id} Functional Pyramid state is unavailable; "
            "run installer verification before governance work. For descriptive "
            f"semantic work, {semantic}."
        )

    obligation = _functional_pyramid_obligation(repository_id, status)
    if status.state is m.FunctionalPyramidParticipationState.EXCLUDED:
        return (
            f"span: {repository_id} Functional Pyramid EXCLUDED; there is no "
            f"initialization obligation. For descriptive-only work, {semantic}."
        )
    if status.state is m.FunctionalPyramidParticipationState.UNCONFIGURED:
        return (
            f"span: {repository_id} {obligation}. Descriptive-only work remains "
            f"available; {semantic}."
        )
    if status.health is m.FunctionalPyramidHealth.DEGRADED:
        return (
            f"span: {repository_id} {obligation}. For semantic orientation, "
            f"{semantic}."
        )
    return (
        f"span: {repository_id} Functional Pyramid ACTIVE/VALID; no separate "
        f"Pyramid action is required. For governed semantic work, {semantic}."
    )


def _affected_for_root(data_dir, root, rel_paths):
    """Read the canonical changed-scope projection without issuing contexts."""
    from span.shell.installation_runtime import open_installation_runtime

    mapping = repo_map(data_dir)
    roots, repository_locator = _installation_inputs(mapping)
    repository_id = _repository_id(root)
    changed_paths = tuple(dict.fromkeys(rel_paths))
    with open_installation_runtime(
        data_dir,
        repository_locator=repository_locator,
        registered_repository_ids=lambda: tuple(sorted(roots)),
    ) as installation:
        context = installation.context_for_locator(root)
        changed = context.reconsider.preview_changed_scope(
            m.ReconsiderRequest(
                repository_id=repository_id,
                changed_paths=changed_paths,
            )
        )
    return repository_id, changed


def _render_affected(repository_id, changed, *, close_prefix=False):
    needing: list[tuple[str, str]] = []
    for surface in changed.surfaces:
        for conclusion in surface.conclusions:
            support = conclusion.support
            if (
                isinstance(support, m.SupportEvaluation)
                and support.state is m.SupportState.CURRENT
            ):
                continue
            key = (
                surface.surface.repository_id,
                conclusion.ref.understanding_id.value,
            )
            if key not in needing:
                needing.append(key)

    if not needing and not changed.truncated:
        return None

    label = "close" if close_prefix else "needs attention"
    if not needing:
        return (
            f"span: {repository_id} {label}: affected projection truncated; "
            "call reconsider after editing before completing work."
        )

    labels = [
        understanding_id if owner == repository_id else f"{owner}:{understanding_id}"
        for owner, understanding_id in sorted(needing)
    ]
    names = labels[:HOOK_DIAGNOSTIC_LIMIT]
    detail = ", ".join(names)
    more = "" if len(labels) <= HOOK_DIAGNOSTIC_LIMIT else "; more omitted"
    cross_repo = (
        "; crosses repositories"
        if any(owner != repository_id for owner, _ in needing)
        else ""
    )
    truncated = "; projection truncated" if changed.truncated else ""
    return (
        f"span: {repository_id} {label}: {len(needing)} recorded "
        f"understanding(s) affected ({detail}{more}{cross_repo}{truncated}); "
        "call reconsider after editing, then investigate and record dispositions."
    )


def cmd_adoption_primer(data_dir, repo_root=None):
    """Print the FD-58 lifecycle notice for an operational registered repository."""
    mapping = repo_map(data_dir)
    if not mapping:
        return
    active = scoped_repo_map(mapping, repo_root)
    if not active:
        return
    root = next(iter(active))
    from span.shell.context import close_repository_runtime, open_repository_runtime

    try:
        runtime = open_repository_runtime(data_dir, root)
    except Exception:  # noqa: BLE001 - a hook never breaks the session
        return
    close_repository_runtime(runtime)
    print(ADOPTION_PRIMER)


def cmd_session_start(data_dir, repo_root=None):
    """Print one composed lifecycle-entry notice for the active repository."""
    mapping = repo_map(data_dir)
    if not mapping:
        print("span: no repositories registered (run span-install).")
        return
    mapping = scoped_repo_map(mapping, repo_root)
    for root in sorted(mapping):
        line = _readiness_notice(data_dir, root)
        if line:
            print(line)
            continue
        print(_session_entry_notice(data_dir, mapping, root))


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
        if depth > 6:
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


def _source_change_notices(data_dir, paths) -> tuple[str, ...]:
    """Project complete changed paths and return only bounded advisory text."""
    paths = [p for p in paths if isinstance(p, str) and p]
    if not paths:
        return ()
    mapping = repo_map(data_dir)
    if not mapping:
        return ()
    notices: list[str] = []
    for root, rel_paths in sorted(_scoped_paths(mapping, paths).items()):
        line = _readiness_notice(data_dir, root)
        if line:
            notices.append(line)
            continue
        repository_id, changed = _affected_for_root(data_dir, root, rel_paths)
        rendered = _render_affected(repository_id, changed)
        if rendered:
            notices.append(rendered)
    return tuple(notices)


def cmd_source_changed(data_dir, paths):
    if not paths:
        paths = _stdin_paths()
    for notice in _source_change_notices(data_dir, paths):
        print(notice)


_CODEX_PATCH_MARKERS = (
    "*** Add File: ",
    "*** Update File: ",
    "*** Delete File: ",
    "*** Move to: ",
)


def _codex_apply_patch_paths(command: str) -> tuple[str, ...] | None:
    """Extract exact file paths from Codex's documented apply_patch payload."""
    paths: list[str] = []
    saw_file_marker = False
    for line in command.splitlines():
        for marker in _CODEX_PATCH_MARKERS:
            if not line.startswith(marker):
                continue
            saw_file_marker = True
            path = line[len(marker) :].strip()
            if not path:
                return None
            paths.append(path)
            break
    if not saw_file_marker:
        return None
    return tuple(dict.fromkeys(paths))


def _codex_post_tool_notice(data_dir, repo_root, payload) -> str | None:
    """Translate only the documented Codex PostToolUse/apply_patch shape."""
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != "PostToolUse":
        return None
    if payload.get("tool_name") != "apply_patch":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return (
            "span: Codex observed apply_patch but its documented "
            "tool_input.command is unavailable; reconsider the complete edited "
            "scope before completing work."
        )
    parsed = _codex_apply_patch_paths(command)
    if parsed is None:
        return (
            "span: Codex observed apply_patch but could not normalize the complete "
            "changed scope from the documented patch payload; reconsider the "
            "complete edited scope before completing work."
        )
    absolute = tuple(
        path if os.path.isabs(path) else os.path.join(repo_root, path)
        for path in parsed
    )
    notices = _source_change_notices(data_dir, absolute)
    reminder = (
        f"span: Codex observed apply_patch across {len(parsed)} changed file(s); "
        "call reconsider with the complete changed scope from this apply_patch "
        "before completing work."
    )
    return " ".join((*notices, reminder))


def cmd_codex_post_tool(data_dir, repo_root=None):
    """Emit Codex's documented structured PostToolUse additional context."""
    try:
        raw = sys.stdin.read()
    except OSError:
        return
    if not raw.strip():
        return
    try:
        payload = json.loads(raw)
    except ValueError:
        return
    notice = _codex_post_tool_notice(data_dir, repo_root or os.getcwd(), payload)
    if notice is None:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": notice,
                }
            },
            separators=(",", ":"),
        )
    )


def _claude_post_tool_notice(data_dir, payload) -> str | None:
    """Translate only Claude Code's documented PostToolUse file-tool shape."""
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != "PostToolUse":
        return None
    tool_name = payload.get("tool_name")
    if tool_name not in ("Write", "Edit"):
        return None
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path or not os.path.isabs(file_path):
        return (
            f"span: Claude Code observed {tool_name} but its documented absolute "
            "tool_input.file_path is unavailable; reconsider the complete edited "
            "scope before completing work."
        )
    notices = _source_change_notices(data_dir, (file_path,))
    reminder = (
        f"span: Claude Code observed {tool_name} on 1 changed file; call reconsider "
        "with the complete changed scope from this edit before completing work."
    )
    return " ".join((*notices, reminder))


def cmd_claude_post_tool(data_dir, repo_root=None):
    """Emit Claude Code's documented structured PostToolUse additional context."""
    del repo_root
    try:
        raw = sys.stdin.read()
    except OSError:
        return
    if not raw.strip():
        return
    try:
        payload = json.loads(raw)
    except ValueError:
        return
    notice = _claude_post_tool_notice(data_dir, payload)
    if notice is None:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": notice,
                }
            },
            separators=(",", ":"),
        )
    )


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
    repository_id, changed = _affected_for_root(data_dir, root, rel_paths)
    rendered = _render_affected(repository_id, changed, close_prefix=True)
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
        choices=(
            "session-start",
            "adoption-primer",
            "source-changed",
            "session-stop",
            "codex-post-tool",
            "claude-post-tool",
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
        elif args.command == "adoption-primer":
            cmd_adoption_primer(data_dir, repo_root)
        elif args.command == "source-changed":
            cmd_source_changed(data_dir, args.paths)
        elif args.command == "session-stop":
            cmd_session_stop(data_dir, repo_root)
        elif args.command == "codex-post-tool":
            cmd_codex_post_tool(data_dir, repo_root)
        elif args.command == "claude-post-tool":
            cmd_claude_post_tool(data_dir, repo_root)
    except BrokenPipeError:
        raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001 - hooks never break sessions
        _fail_silent(f"internal error: {exc}")


if __name__ == "__main__":
    main()
