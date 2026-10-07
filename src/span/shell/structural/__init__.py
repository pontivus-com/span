"""Span structural-source shell implementations (plan §5.2).

One selected production provider only (plan Phase 2.1: Graft). The
deterministic in-memory source for Phase 1 lives here against the same
port. Provider-config strings are opaque shell-owned carriers (§23):
the functional core never interprets them.
"""

import pathlib as _pathlib

from span.shell.structural.graft import (
    GraftStructuralSource,
    ensure_graft_built,
)
from span.shell.structural.memory import InMemoryStructuralSource

__all__ = [
    "GraftStructuralSource",
    "InMemoryStructuralSource",
    "ensure_graft_built",
    "structural_source_from_config",
]


def structural_source_from_config(
    config: str,
) -> tuple[GraftStructuralSource | InMemoryStructuralSource, str]:
    """Build the configured structural source (explicit admin paths only:
    initialization, tests, tooling — never queries or hooks).

    Returns (source, repository_id): identity assignment (plan §8.2.1)
    lives here, derived deterministically from the locator. Supported
    configs: ``graft:<repo-path>`` (builds the index when absent —
    explicit session work, never implicit). Anything else raises; the
    in-memory source is constructed directly by its owners.
    """
    scheme, _, rest = config.partition(":")
    if scheme == "graft" and rest:
        repo_path = _pathlib.Path(rest)
        ensure_graft_built(repo_path)
        return GraftStructuralSource(repo_path.name, repo_path), repo_path.name
    raise ValueError(
        f"unsupported structural provider config: {config!r} "
        f"(supported: 'graft:<repo-path>')"
    )
