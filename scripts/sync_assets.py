"""Materialize packaged assets from their canonical repository sources.

The repository-owned skills, lifecycle snippet and OpenCode plugin remain the
only canonical copies. Builds consume the same manifest as test generation, so
a wheel contains generated assets without committing a second package copy.
"""

from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]


def asset_manifest() -> tuple[tuple[pathlib.Path, pathlib.Path], ...]:
    """Return canonical source -> package-relative asset mappings."""
    entries: list[tuple[pathlib.Path, pathlib.Path]] = []
    skills = ROOT / "skills"
    for name in sorted(path.name for path in skills.iterdir() if path.is_dir()):
        source = skills / name / "SKILL.md"
        if source.is_file():
            entries.append((source, pathlib.Path("skills") / name / "SKILL.md"))
    entries.append(
        (
            ROOT / "docs" / "agents-snippet.md",
            pathlib.Path("agents-snippet.md"),
        )
    )
    entries.append(
        (
            ROOT / "integrations" / "hosts" / "opencode" / "span-hooks.js",
            pathlib.Path("opencode-plugin") / "index.js",
        )
    )
    return tuple(entries)


def sync_assets(destination: pathlib.Path) -> tuple[pathlib.Path, ...]:
    """Copy the canonical asset manifest below the destination."""
    dest = pathlib.Path(destination)
    written: list[pathlib.Path] = []
    manifest = asset_manifest()
    for source, relative in manifest:
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)

    names = {
        relative.parts[1]
        for _, relative in manifest
        if len(relative.parts) >= 3 and relative.parts[0] == "skills"
    }
    stale = dest / "skills"
    if stale.is_dir():
        for child in stale.iterdir():
            if child.is_dir() and child.name not in names:
                shutil.rmtree(child)
    return tuple(written)
