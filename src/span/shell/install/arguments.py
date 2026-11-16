"""Command-line argument grammar (stdlib only)."""

from __future__ import annotations

import argparse


def _add_transition_arguments(parser) -> None:
    """The one offline transition command surface (§8.5)."""
    parser.add_argument(
        "--transition-store",
        default=None,
        metavar="REPOSITORY_ID",
        help="Explicitly transition one repository's schema-7/8/9/10 store to "
        "the schema-11 lifecycle store. Requires --transition-phase. This "
        "is the only supported store upgrade path; the runtime never "
        "migrates at open.",
    )
    parser.add_argument(
        "--transition-phase",
        default=None,
        choices=("inspect", "apply", "verify", "rollback"),
        help="Transition phase: inspect/verify are observational; apply "
        "archives, stages and activates; rollback restores a verified old "
        "store while preserving new-format writes. Refused without "
        "--transition-store.",
    )
    parser.add_argument(
        "--transition-root",
        default=None,
        metavar="TARGET_DIR",
        help="Explicit repository root for the transition binding. "
        "Required for apply; reported by inspect when supplied.",
    )


def _add_opencode_plugin_scope_argument(parser) -> None:
    """The explicit OpenCode plugin scope; never inferred from disk."""
    parser.add_argument(
        "--opencode-plugin-scope",
        choices=("global", "local", "none"),
        default=None,
        help=(
            "Where Span manages the OpenCode lifecycle plugin. `global` "
            "installs it under Span's data root. `local` and `none` leave the target "
            "plugin to the user and remove Span's global registration. A "
            "fresh install defaults to global; an upgrade uses the receipt "
            "scope and stops if it is absent or ambiguous."
        ),
    )


def _add_claude_arguments(parser) -> None:
    parser.add_argument(
        "--with-claude",
        action="store_true",
        default=None,
        help="Register via `claude mcp add` (default: automatic when "
        "the Claude CLI or host footprint is present; --no-claude to skip).",
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Skip all Claude Code integration even when detected.",
    )


def _add_recovery_arguments(parser) -> None:
    """Operator-facing data recovery surface (one-shot commands)."""
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Take a verified point-in-time backup of the data directory "
        "(databases, install receipt, indexer pointer, manifest) and exit.",
    )
    parser.add_argument(
        "--backup-root",
        default=None,
        metavar="DIR",
        help="Directory receiving backup artifacts (default: "
        "<DATA_DIR>/backups). Used by --backup, --restore-backup and "
        "--reap-backups.",
    )
    parser.add_argument(
        "--verify-backup",
        default=None,
        metavar="BACKUP_DIR",
        help="Verify one backup artifact's manifest, file identity, database "
        "integrity and schema compatibility, then exit.",
    )
    parser.add_argument(
        "--restore-backup",
        default=None,
        metavar="BACKUP_DIR",
        help="Restore one verified backup artifact into the data directory. "
        "Requires --restore-confirm and stops every Span process first.",
    )
    parser.add_argument(
        "--restore-confirm",
        default=None,
        metavar="NAME",
        help="Repeat the backup directory name to confirm a restore. "
        "Required by --restore-backup; never inferred.",
    )
    parser.add_argument(
        "--reap-backups",
        default=None,
        type=int,
        metavar="KEEP",
        help="Delete all but the newest KEEP recognized backup artifacts. "
        "The count is explicit; there is no default retention interval.",
    )


def _add_repository_recovery_arguments(parser) -> None:
    """Repository-portable artifact commands (one-shot)."""
    parser.add_argument(
        "--backup-repository",
        default=None,
        metavar="REPO_ROOT",
        help="Write one deployable artifact into <REPO_ROOT>/.span/backups/ "
        "and exit. Commit it with the repository.",
    )
    parser.add_argument(
        "--verify-repository-backup",
        default=None,
        metavar="ARTIFACT_DIR",
        help="Verify one repository artifact and exit.",
    )
    parser.add_argument(
        "--load-repository-backup",
        default=None,
        metavar="TARGET_ROOT",
        help="Load the newest (or --repository-artifact) repository artifact "
        "into the data directory and rebind it to TARGET_ROOT.",
    )
    parser.add_argument(
        "--repository-artifact",
        default=None,
        metavar="ARTIFACT_DIR",
        help="Explicit artifact directory for --load-repository-backup. "
        "Never inferred when supplied.",
    )
    parser.add_argument(
        "--reap-repository-backups",
        nargs=2,
        default=None,
        metavar=("REPO_ROOT", "KEEP"),
        help="Delete all but the newest KEEP working-tree artifacts under "
        "REPO_ROOT/.span/backups. Git history is unaffected.",
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="span-install",
        description=(
            "Install span-mcp, register host MCP entries, initialize "
            "target repositories, and verify readiness. Linux only; "
            "other platforms are structurally reserved, not silently attempted."
        ),
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="TARGET_DIR",
        help=(
            "Target repository root (repeatable). Provisioning builds "
            "the structural index into Span's data directory when "
            "needed (no --deep, no credentials, no target writes)."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="SQLite store directory (default: platform data dir). "
        "Refused when inside any target repo.",
    )
    parser.add_argument(
        "--venv-dir",
        default=None,
        help="Virtualenv location (default: platform venv dir).",
    )
    parser.add_argument(
        "--bin-dir",
        default=None,
        help="Directory receiving the span-mcp symlink " "(default: platform bin dir).",
    )
    parser.add_argument(
        "--span-repo",
        default=".",
        help="Span source checkout to install (default: cwd).",
    )
    parser.add_argument(
        "--opencode-config",
        default=None,
        help="opencode.json to merge the Span MCP entry into. "
        "Default: ./opencode.json when present, otherwise the global "
        "OpenCode config for a global plugin scope.",
    )
    parser.add_argument(
        "--with-codex",
        action="store_true",
        default=None,
        help="Register via `codex mcp add` (default: automatic when "
        "the codex CLI is present; --no-codex to skip).",
    )
    parser.add_argument(
        "--no-codex",
        action="store_true",
        help="Skip all Codex integration even when detected.",
    )
    _add_claude_arguments(parser)
    parser.add_argument(
        "--with-hooks",
        action="store_true",
        default=None,
        help="Wire report-only lifecycle hooks (default: automatic "
        "when a supported host is detected; --no-hooks to skip). "
        "Hooks only report readiness/dependents/closure; they never "
        "write, interpret, refresh, or initialize.",
    )
    parser.add_argument(
        "--no-hooks",
        action="store_true",
        help="Skip hook wiring even when hosts are detected.",
    )
    _add_opencode_plugin_scope_argument(parser)
    parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Skip skill deployment even when hosts are detected.",
    )
    parser.add_argument(
        "--authority-seeds-file",
        default=None,
        help="JSON file with canonical EvidenceRef items for init. "
        "Absent means no seeds; seeds are never invented.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions; execute nothing.",
    )
    parser.add_argument(
        "--snapshot-census",
        default=None,
        metavar="OUT_JSON",
        help="Write a read-only target artifact census snapshot and exit.",
    )
    parser.add_argument(
        "--compare-census",
        nargs=2,
        default=None,
        metavar=("BEFORE", "AFTER"),
        help="Diff two census snapshots with a readable verdict and exit.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip install; verify an existing installation and exit.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Reverse install writes (host registration, hooks, managed "
        "AGENTS.md block, deployed skills, receipt). Never touches "
        "repository data. Idempotent.",
    )
    parser.add_argument(
        "--purge",
        default=None,
        metavar="REPOSITORY_ID",
        help="Remove one repository ID's data (`<id>.db` and "
        "`<data-dir>/structural/<id>/`). Explicit ID only.",
    )
    _add_transition_arguments(parser)
    _add_recovery_arguments(parser)
    _add_repository_recovery_arguments(parser)
    parser.add_argument(
        "--list-orphans",
        action="store_true",
        help="Report IDs present on disk and absent from the receipt. "
        "Deletes nothing; absence from a receipt is evidence, not proof.",
    )
    return parser.parse_args(argv)
