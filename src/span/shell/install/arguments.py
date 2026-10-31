"""Command-line argument grammar (stdlib only)."""

from __future__ import annotations

import argparse


def _add_transition_arguments(parser) -> None:
    """The one offline transition command surface (§8.5)."""
    parser.add_argument(
        "--transition-store",
        default=None,
        metavar="REPOSITORY_ID",
        help="Explicitly transition one repository's schema-7/8/9 store to "
        "the schema-10 lifecycle store. Requires --transition-phase. This "
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
    parser.add_argument(
        "--migrate-store",
        default=None,
        metavar="REPOSITORY_ID",
        help=argparse.SUPPRESS,
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
        help="opencode.json to merge the span MCP entry into. "
        "Default: ./opencode.json when present, else skipped.",
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
    parser.add_argument(
        "--with-claude",
        action="store_true",
        default=None,
        help="Register via `claude mcp add` (default: automatic when "
        "the claude CLI is present; --no-claude to skip).",
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Skip all Claude Code integration even when detected.",
    )
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
    parser.add_argument(
        "--list-orphans",
        action="store_true",
        help="Report IDs present on disk and absent from the receipt. "
        "Deletes nothing; absence from a receipt is evidence, not proof.",
    )
    return parser.parse_args(argv)
