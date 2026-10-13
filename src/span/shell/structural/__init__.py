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
    "structural_source_from_config",
]


def repo_root_from_config(config: str) -> _pathlib.Path:
    """Resolve a repository locator to its filesystem root.

    Accepts the provider-neutral plain path (canonical) and the legacy
    ``graft:<path>`` form (transitional). Anything else raises.
    """
    scheme, _, rest = config.partition(":")
    # A plain path may itself contain a colon only as a Windows drive
    # letter; Span targets are Linux paths, so treat `graft:` prefix
    # plus an absolute rest as legacy, and everything else by existence.
    if scheme == "graft" and rest:
        return _pathlib.Path(rest)
    candidate = _pathlib.Path(config)
    # Reject other opaque scheme-like configs (e.g. memory:test) here;
    # the in-memory source is constructed directly by its owners.
    if scheme in ("memory",) and rest:
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(pass a plain repository path)"
        )
    return candidate


def repository_id_from_config(config: str) -> str:
    """Deterministic repository identity from the locator (plan §8.2.1)."""
    return repo_root_from_config(config).name


def structural_source_from_config(
    config: str,
    data_dir: str | _pathlib.Path | None = None,
) -> tuple[GraftStructuralSource | InMemoryStructuralSource, str]:
    """Load the configured structural source without mutating the target.

    Returns (source, repository_id): identity assignment (plan §8.2.1)
    lives here, derived deterministically from the locator. Accepted
    locators: a plain repository path (canonical) or legacy
    ``graft:<repo-path>`` (transitional). With ``data_dir`` the graft
    provider uses the provider-owned cache
    ``<data-dir>/structural/<repository-id>/``; without it (tests) the
    legacy in-target index is used. Construction never builds: a
    missing index yields an unavailable source that explicit
    `initialize_repository` / `refresh` may build via `ensure_current`;
    ordinary reads fail closed.
    """
    scheme, _, rest = config.partition(":")
    if scheme == "graft" and rest:
        repo_path = _pathlib.Path(rest)
        repository_id = repo_path.name
        artifact = (
            default_artifact_dir(data_dir, repository_id)
            if data_dir is not None
            else None
        )
        return (
            GraftStructuralSource(
                repository_id, repo_path, artifact_dir=artifact
            ),
            repository_id,
        )
    if scheme == "memory" and rest:
        raise ValueError(
            f"unsupported structural provider config: {config!r} "
            f"(in-memory source is constructed directly by its owners)"
        )
    # Plain provider-neutral path (canonical). Scheme-like configs other
    # than legacy graft:/transitional are rejected; Linux target paths
    # do not contain colons.
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
    artifact = (
        default_artifact_dir(data_dir, repository_id)
        if data_dir is not None
        else None
    )
    return (
        GraftStructuralSource(repository_id, repo_path, artifact_dir=artifact),
        repository_id,
    )
