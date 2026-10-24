"""Canonical repository-context opener (shell lifecycle).

One opener serves every repository-scoped runtime path that needs a
working context without performing setup: the MCP adapter's first
repository call and the lifecycle hook runner. Opening constructs the
structural source, filesystem evidence, the existing semantic store,
and continuation state. It never calls `ensure_current`, never runs a
provider build, and never writes to the target repository.

Storage is opened only when it already exists. A repository with no
persistent store is served by an empty in-memory store and no authority
seeds, so an ordinary read returns the canonical `UNINITIALIZED` answer
instead of creating `<data-dir>/<repository_id>.db` (or its schema) on a
path that explicit `initialize_repository` owns. An existing store must
be schema 7; its persisted authority seeds are rehydrated here for every
later operation and process restart. Any other store version fails
closed rather than being migrated or served.
"""

from __future__ import annotations

import pathlib as _pathlib

from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import ServiceContext
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural import (
    repo_root_from_config,
    structural_source_from_config,
)

__all__ = ["open_repository_context"]


def open_repository_context(
    data_dir: str | _pathlib.Path,
    repository_locator: str,
) -> tuple[str, ServiceContext]:
    """Open an already-provisioned repository context without setup.

    Returns ``(repository_id, context)``. The repository ID comes from
    the same deterministic locator rule explicit initialization uses,
    so both paths address the same store.
    """
    data_root = _pathlib.Path(data_dir)
    structural, repository_id = structural_source_from_config(
        repository_locator, data_dir=data_root
    )
    root = repo_root_from_config(repository_locator)
    evidence = FilesystemEvidenceSource(repository_id, root)
    store_path = data_root / f"{repository_id}.db"
    store = SqliteSemanticStore(str(store_path) if store_path.is_file() else ":memory:")
    context = ServiceContext(
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=ContinuationStore(),
        authority_seeds=store.load_repository_authority_seeds(repository_id),
    )
    return repository_id, context
