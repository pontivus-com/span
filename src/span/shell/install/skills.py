"""Skill and AGENTS.md deployment (stdlib only)."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

from span.shell.install.constants import (
    AGENTS_END,
    AGENTS_START,
)
from span.shell.install.paths import (
    agents_snippet_path,
    canonical_skills_dir,
    distribution_version,
    install_mode,
)


def ensure_agents_rule(span_repo, target, dry_run=False):
    """Deploy the canonical lifecycle block into a target AGENTS.md.

    The block is copied verbatim from ``docs/agents-snippet.md`` between
    Span-owned markers. The installer never parses it for decisions and
    preserves all content outside the managed block. No other target
    artifact is created or modified.
    """
    dst = Path(target) / "AGENTS.md"
    print(f"+ ensure agents rule: {dst}")
    if dry_run:
        return {
            "status": "skipped",
            "reason": "dry-run",
            "path": str(dst),
        }
    src = agents_snippet_path(span_repo)
    if not src.is_file():
        raise SystemExit(f"agents snippet source missing: {src}")
    snippet = src.read_text().rstrip("\n") + "\n"
    if "## Span lifecycle" not in snippet:
        raise SystemExit(f"agents snippet source malformed: {src}")
    block = f"{AGENTS_START}\n{snippet}{AGENTS_END}"
    if not dst.is_file():
        dst.write_text(block + "\n")
        print(f"agents rule created: {dst}")
        return {"status": "wired", "path": str(dst)}
    existing = dst.read_text()
    if existing.count(AGENTS_START) > 1 or existing.count(AGENTS_END) > 1:
        raise SystemExit(
            f"agents block markers duplicated in {dst}; "
            "inspect the file before rerunning."
        )
    start = existing.find(AGENTS_START)
    end = existing.find(AGENTS_END)
    if (start != -1) != (end != -1) or (start != -1 and end != -1 and end < start):
        raise SystemExit(
            f"agents block markers malformed in {dst}; "
            "inspect the file before rerunning."
        )
    if start != -1:
        new_text = existing[:start] + block + existing[end + len(AGENTS_END) :]
    elif existing.strip():
        new_text = existing.rstrip("\n") + "\n\n" + block + "\n"
    else:
        new_text = block + "\n"
    if new_text == existing:
        return {"status": "converged", "path": str(dst)}
    dst.write_text(new_text)
    print(f"agents rule deployed: {dst}")
    return {"status": "wired", "path": str(dst)}


def remove_agents_block(target, dry_run=False):
    """Remove the managed Span block from a target ``AGENTS.md``.

    Only the block between Span's own markers is removed; surrounding
    content is preserved byte for byte apart from trailing newlines. A
    file that contained nothing else is deleted, restoring the pre-install
    state. Malformed or duplicated markers are left untouched for review —
    never guessed at.
    """
    dst = Path(target) / "AGENTS.md"
    print(f"+ remove agents rule: {dst}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run", "path": str(dst)}
    if not dst.is_file():
        return {"status": "absent", "path": str(dst)}
    existing = dst.read_text()
    if existing.count(AGENTS_START) != 1 or existing.count(AGENTS_END) != 1:
        return {
            "status": "absent",
            "path": str(dst),
            "reason": "markers absent or ambiguous; left untouched",
        }
    start = existing.find(AGENTS_START)
    end = existing.find(AGENTS_END)
    if end < start:
        return {
            "status": "absent",
            "path": str(dst),
            "reason": "markers out of order; left untouched",
        }
    remaining = (existing[:start] + existing[end + len(AGENTS_END) :]).rstrip("\n")
    if not remaining.strip():
        dst.unlink()
        print(f"agents rule removed; empty file deleted: {dst}")
        return {"status": "removed", "path": str(dst), "deleted": True}
    dst.write_text(remaining + "\n")
    print(f"agents rule removed: {dst}")
    return {"status": "removed", "path": str(dst), "deleted": False}


def deploy_agents_rules(span_repo, targets, dry_run=False):
    """Synchronize the managed lifecycle block for every target."""
    return {
        str(target): ensure_agents_rule(span_repo, target, dry_run=dry_run)
        for target in targets
    }


def deploy_skills(span_repo, dry_run=False):
    """Copy span skills into each detected host's skills directory.

    Skill directories are copied whole as opaque artifacts; content
    is never parsed or used for decisions here (implementation
    ignores skills as semantic authority). A `.span-origin.json`
    beside each skill records the source rev so doctor can detect
    drift. Nothing is merged into host-owned files.
    """

    skills_dir = canonical_skills_dir(span_repo)
    if not skills_dir.is_dir():
        print(f"no skills directory for {span_repo}; skipping.")
        return []
    names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
    if not names:
        print("no skills found; skipping.")
        return []
    home = Path(os.path.expanduser("~"))
    # Readiness is the host's own directory, not the skills subdirectory:
    # a fresh host has no skills directory yet, and skipping there would
    # silently deploy nothing for the host that was just detected. The
    # host root always pre-exists, so this never fabricates a host.
    destinations = [
        home / ".config" / "opencode",
        home / ".codex",
        home / ".claude",
    ]
    mode = install_mode(span_repo)
    version = distribution_version() if mode == "distribution" else None
    deployed = []
    try:
        rev_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(span_repo),
            capture_output=True,
            text=True,
        )
        rev = rev_proc.stdout.strip() if rev_proc.returncode == 0 else "unknown"
    except OSError:
        rev = "unknown"
    for host_root in destinations:
        if not host_root.is_dir():
            print(f"host directory absent, skipping: {host_root}")
            continue
        dest_root = host_root / "skills"
        if not dry_run:
            dest_root.mkdir(exist_ok=True)
        for name in names:
            src = skills_dir / name
            dst_dir = dest_root / name
            print(f"+ deploy skill {name} -> {dst_dir}")
            if dry_run:
                continue
            shutil.copytree(src, dst_dir, dirs_exist_ok=True)
            (dst_dir / ".span-origin.json").write_text(
                json.dumps(
                    {
                        "skill": name,
                        "install_mode": mode,
                        "span_repo": str(span_repo) if mode == "checkout" else None,
                        "distribution_version": version,
                        "span_rev": rev,
                        "installed_at": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            deployed.append(str(dst_dir))
    return deployed


def check_skills(dry_run=False):
    """Doctor helper: report deployed skills and origin drift."""
    home = Path(os.path.expanduser("~"))
    for dest_root in (
        home / ".config" / "opencode" / "skills",
        home / ".codex" / "skills",
        home / ".claude" / "skills",
    ):
        if not dest_root.is_dir():
            continue
        for skill_dir in sorted(dest_root.iterdir()):
            origin = skill_dir / ".span-origin.json"
            if not origin.exists() or dry_run:
                continue
            try:
                record = json.loads(origin.read_text())
            except ValueError:
                print(f"skills: {skill_dir} has unreadable origin.")
                continue
            source = record.get("span_repo")
            if source is None:
                source = f"span-mcp {record.get('distribution_version')}"
            print(f"skills: {skill_dir} from {source} rev {record.get('span_rev')}")


def remove_deployed_skills(dry_run=False):
    """Remove host skill directories Span deployed, marked by its origin file.

    Only directories carrying Span's own ``.span-origin.json`` marker are
    removed; a user-authored skill of the same name is never touched.
    """
    home = Path(os.path.expanduser("~"))
    removed = []
    for host_root in (home / ".config" / "opencode", home / ".codex", home / ".claude"):
        dest_root = host_root / "skills"
        if not dest_root.is_dir():
            continue
        removed_here = 0
        for candidate in sorted(dest_root.iterdir()):
            if (
                not candidate.is_dir()
                or not (candidate / ".span-origin.json").is_file()
            ):
                continue
            print(f"+ remove skill {candidate}")
            if not dry_run:
                shutil.rmtree(candidate)
            removed.append(str(candidate))
            removed_here += 1
        if removed_here and not dry_run:
            # Install created this directory when it was absent. Leave a
            # pre-existing one alone, but do not leave an empty artifact.
            try:
                if not any(dest_root.iterdir()):
                    dest_root.rmdir()
            except OSError:
                pass
    return {"status": "removed" if removed else "absent", "removed": removed}
