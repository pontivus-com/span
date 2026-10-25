"""Span structural-source shell implementations (plan §5.2).

One selected production provider only (plan Phase 2.1: Graft). The
deterministic in-memory source for Phase 1 lives here against the same
port. Provider-config strings are opaque shell-owned carriers (§23):
the functional core never interprets them. The public locator is a
plain repository path; the shell resolves it to the configured
provider internally, with provider artifacts under Span's data
directory (never in the target).
"""

import pathlib as _pathlib

from span.shell.structural.graft import (
    GraftStructuralSource,
    default_artifact_dir,
)
from span.shell.structural.memory import InMemoryStructuralSource

__all__ = [
    "GraftStructuralSource",
    "InMemoryStructuralSource",
    "default_artifact_dir",
    "repo_root_from_config",
    "repository_id_from_config",
    "canonical_root_from_config",
    "containing_registered_root",
    "structural_source_from_config",
]


def repo_root_from_config(config: str) -> _pathlib.Path:
    """Resolve a repository locator to its filesystem root.

    The locator is a plain provider-neutral repository path. Provider
    selection stays shell-internal, so a scheme-prefixed config is never
    part of the public surface; anything other than a plain path raises.
    """
    if not config or ":" in config:
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(pass a plain repository path)"
        )
    return _pathlib.Path(config)


def repository_id_from_config(config: str) -> str:
    """Deterministic repository identity from the locator (plan §8.2.1)."""
    return repo_root_from_config(config).name


def canonical_root_from_config(config: str) -> str:
    """Absolute, symlink-resolved root for identity provenance.

    Identity is still the basename; this is what proves *which* root a store
    belongs to when two directories share a name.
    """
    return str(repo_root_from_config(config).resolve())


def structural_source_from_config(
    config: str,
    data_dir: str | _pathlib.Path,
) -> tuple[GraftStructuralSource | InMemoryStructuralSource, str]:
    """Load the configured structural source without mutating the target.

    Returns (source, repository_id): identity assignment (plan §8.2.1)
    lives here, derived deterministically from the locator. The only
    accepted locator is a plain repository path; provider selection is
    shell-internal and never named by the caller. The graft provider
    uses only the provider-owned cache
    ``<data-dir>/structural/<repository-id>/``. Construction never
    builds: a missing index yields an unavailable source that explicit
    `initialize_repository` / `refresh` may build via `ensure_current`;
    ordinary reads fail closed.
    """
    if config.startswith("memory:"):
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(in-memory source is constructed directly by its owners)"
        )
    # Provider-neutral plain path only. Provider selection stays
    # shell-internal; Linux target paths do not contain colons, so a
    # scheme-like config is rejected rather than interpreted.
    if ":" in config:
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(pass a plain repository path)"
        )
    repo_path = _pathlib.Path(config)
    if not str(config):
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(pass a plain repository path)"
        )
    repository_id = repo_path.name
    artifact = default_artifact_dir(data_dir, repository_id)
    return (
        GraftStructuralSource(repository_id, repo_path, artifact_dir=artifact),
        repository_id,
    )


def containing_registered_root(data_dir: str | _pathlib.Path, root: str) -> str | None:
    """Deepest other root already recorded in this data directory.

    Provenance is the only place a root is bound to an ID, so it is the only
    honest source for "nested within". Read-only: a store that cannot be read
    contributes nothing.
    """
    import sqlite3 as _sqlite3

    target = _pathlib.Path(root)
    best: str | None = None
    for db in sorted(_pathlib.Path(data_dir).glob("*.db")):
        try:
            connection = _sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = connection.execute(
                    "SELECT value FROM meta WHERE key LIKE 'repository_root:%'"
                ).fetchall()
            finally:
                connection.close()
        except _sqlite3.Error:
            continue
        for (value,) in rows:
            candidate = _pathlib.Path(str(value))
            if candidate == target:
                continue
            try:
                target.relative_to(candidate)
            except ValueError:
                continue
            if best is None or len(candidate.parts) > len(_pathlib.Path(best).parts):
                best = str(value)
    return best
