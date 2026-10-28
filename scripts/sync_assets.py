"""Materialize the packaged skill assets from their canonical sources.

``skills/`` and ``docs/agents-snippet.md`` are the only sources. A wheel has
no repository root, so the build copies them into the package. Nothing is
committed at the destination and nothing is edited there.
"""

from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sync_assets(destination: pathlib.Path) -> tuple[pathlib.Path, ...]:
    """Copy every canonical skill and the lifecycle snippet below ``destination``."""
    dest = pathlib.Path(destination)
    written: list[pathlib.Path] = []
    skills = ROOT / "skills"
    names = sorted(path.name for path in skills.iterdir() if path.is_dir())
    for name in names:
        source = skills / name / "SKILL.md"
        if not source.is_file():
            continue
        target = dest / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)
    snippet = ROOT / "docs" / "agents-snippet.md"
    target = dest / "agents-snippet.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snippet, target)
    written.append(target)
    stale = dest / "skills"
    if stale.is_dir():
        for child in stale.iterdir():
            if child.is_dir() and child.name not in names:
                shutil.rmtree(child)
    return tuple(written)
