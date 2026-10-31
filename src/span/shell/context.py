"""Canonical lifecycle context opener (shell lifecycle).

One opener serves every repository-scoped path that needs a working context
without performing setup: the MCP adapter's lazy first call and the lifecycle
hook runner. Opening constructs the structural source, filesystem evidence,
the existing schema-10 store and its services. It never builds a structural
index, never writes to the target repository, and never creates or migrates a
store. A repository without a store fails closed with the explicit setup
action; an old schema fails closed with the transition action.
"""

from __future__ import annotations

import pathlib as _pathlib

from span.core import model as m
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import ServiceContext
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_store.lifecycle import (
    LifecycleStore,
    LifecycleStoreError,
)
from span.shell.structural import (
    canonical_root_from_config,
    structural_source_from_config,
)
from span.service.administration import initialize_repository
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService
from span.service.understand import UnderstandService
from span.service.understanding_discovery import DiscoveryService

__all__ = [
    "RepositoryNotInitialized",
    "compose_context",
    "open_repository_context",
    "provision_repository",
]


class RepositoryNotInitialized(LifecycleStoreError):
    """No schema-10 store exists for this repository; explicit setup is due."""


def compose_context(
    *,
    repository_id: str,
    root: str,
    structural,
    evidence: FilesystemEvidenceSource,
    store: LifecycleStore,
) -> ServiceContext:
    """Wire the canonical lifecycle services over one open store."""
    seeds = store.load_authority_seeds(repository_id)
    support = SupportService(store=store, evidence=evidence, authority=store)
    lifecycle = LifecycleService(store=store, authority=store, support=support)
    evidence_service = EvidenceService(store=store, evidence=evidence)
    discovery = DiscoveryService(store=store)
    understand = UnderstandService(
        store=store,
        discovery=discovery,
        evidence=evidence_service,
        evidence_source=evidence,
        support=support,
    )
    return ServiceContext(
        repository_id=repository_id,
        root=root,
        structural=structural,
        evidence=evidence,
        store=store,
        lifecycle=lifecycle,
        evidence_service=evidence_service,
        understand=understand,
        support=support,
        authority_seeds=seeds,
    )


def open_repository_context(
    data_dir: str | _pathlib.Path,
    repository_locator: str,
) -> tuple[str, ServiceContext]:
    """Open an already-provisioned repository context without setup."""
    data_root = _pathlib.Path(data_dir)
    structural, repository_id = structural_source_from_config(
        repository_locator, data_dir=data_root
    )
    root = canonical_root_from_config(repository_locator)
    store_path = data_root / f"{repository_id}.db"
    if not store_path.is_file():
        raise RepositoryNotInitialized(
            f"repository {repository_id} is not initialized; call "
            "initialize_repository in a dedicated setup session"
        )
    store = LifecycleStore(store_path, retention=DEFAULT_LIFECYCLE_RETENTION)
    try:
        try:
            bound_root = store.require_repository(repository_id)
        except LifecycleStoreError:
            raise RepositoryNotInitialized(
                f"store {store_path} has no binding for {repository_id}; "
                "call initialize_repository in a dedicated setup session"
            ) from None
        if bound_root != root:
            raise LifecycleStoreError(
                f"repository {repository_id} is bound to {bound_root!r}, "
                f"not {root!r}; refusing to serve a different root"
            )
        store.reap_expired()
    except BaseException:
        store.close()
        raise
    evidence = FilesystemEvidenceSource(repository_id, root)
    return repository_id, compose_context(
        repository_id=repository_id,
        root=root,
        structural=structural,
        evidence=evidence,
        store=store,
    )


def provision_repository(
    data_dir: str | _pathlib.Path,
    request: m.InitializeRepositoryRequest,
) -> tuple[ServiceContext, m.InitializeRepositoryResult]:
    """Explicit setup: bind identity and declared seeds (no interpretation)."""
    data_root = _pathlib.Path(data_dir)
    structural, repository_id = structural_source_from_config(
        request.repository_locator, data_dir=data_root
    )
    root = canonical_root_from_config(request.repository_locator)
    currency = structural.ensure_current(repository_id)
    from span.shell.structural.graft import GraftStructuralSource

    has_index = (
        structural.has_index()
        if isinstance(structural, GraftStructuralSource)
        else True
    )
    if not has_index:
        raise ValueError(
            f"structural indexer unavailable for {root!r}: {currency.state.value}; "
            "rerun installation to provision the indexer, then retry setup"
        )
    data_root.mkdir(parents=True, exist_ok=True)
    store = LifecycleStore(
        data_root / f"{repository_id}.db",
        retention=DEFAULT_LIFECYCLE_RETENTION,
    )
    try:
        evidence = FilesystemEvidenceSource(repository_id, root)
        result = initialize_repository(
            request,
            repository_id=repository_id,
            canonical_root=root,
            store=store,
            evidence=evidence,
            structural_status=f"index:{currency.state.value}",
        )
        context = compose_context(
            repository_id=repository_id,
            root=root,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    except BaseException:
        store.close()
        raise
    return context, result
