"""Repository runtime opening and canonical lifecycle service composition.

Raw repository capabilities are opened independently of semantic services.
Installation-scoped Functional Pyramid composition consumes those raw runtimes;
only afterwards is a repository ServiceContext composed. This keeps the shell
as the effects/adapter owner and prevents a ServiceContext -> Functional Pyramid
-> ServiceContext construction cycle.
"""

from __future__ import annotations

import pathlib as _pathlib
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.ports.functional_pyramid import FunctionalPyramidRepositoryRuntime
from span.ports.structural import StructuralSource
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.mcp import ServiceContext
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.shell.sqlite_ownership import store_use_ownership
from span.shell.sqlite_store.lifecycle import (
    LifecycleStore,
    LifecycleStoreError,
)
from span.shell.sqlite_store.functional_pyramid import (
    FunctionalPyramidInstallationStore,
    ensure_functional_pyramid_installation_store,
    functional_pyramid_installation_path,
)
from span.shell.structural import (
    canonical_root_from_config,
    structural_source_from_config,
)
from span.service.administration import initialize_repository
from span.service.answer import AnswerService
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.addressing import AddressingService
from span.service.effects import DependencyEffectService
from span.service.evidence import EvidenceService
from span.service.functional_pyramid import FunctionalPyramidService
from span.service.lifecycle import LifecycleService
from span.service.reconsider import ReconsiderService
from span.service.support import SupportService
from span.service.understand import UnderstandService

__all__ = [
    "RepositoryNotInitialized",
    "RepositoryRuntime",
    "close_repository_context",
    "close_repository_runtime",
    "compose_context",
    "open_repository_context",
    "open_repository_runtime",
    "provision_repository",
    "provision_repository_runtime",
]


class RepositoryNotInitialized(LifecycleStoreError):
    """No compatible store exists for this repository; explicit setup is due."""


@_dataclass(frozen=True)
class RepositoryRuntime:
    """Raw registered-repository capabilities; no semantic services."""

    repository_id: str
    root: str
    structural: StructuralSource
    evidence: FilesystemEvidenceSource
    store: LifecycleStore


def _open_store(
    data_root: _pathlib.Path,
    *,
    repository_id: str,
    root: str,
) -> LifecycleStore:
    store_path = data_root / f"{repository_id}.db"
    if not store_path.is_file():
        raise RepositoryNotInitialized(
            f"repository {repository_id} is not initialized; run the installer "
            "to bind it"
        )
    store = LifecycleStore(
        store_path,
        retention=DEFAULT_LIFECYCLE_RETENTION,
        initialize_schema=False,
        ownership_root=data_root,
    )
    try:
        try:
            bound_root = store.require_repository(repository_id)
        except LifecycleStoreError:
            raise RepositoryNotInitialized(
                f"store {store_path} has no binding for {repository_id}; "
                "run the installer to bind this repository"
            ) from None
        if bound_root != root:
            raise LifecycleStoreError(
                f"repository {repository_id} is bound to {bound_root!r}, "
                f"not {root!r}; refusing to serve a different root"
            )
    except BaseException:
        store.close()
        raise
    return store


def open_repository_runtime(
    data_dir: str | _pathlib.Path,
    repository_locator: str,
) -> RepositoryRuntime:
    """Open raw repository capabilities without composing semantic services."""
    data_root = _pathlib.Path(data_dir)
    structural, repository_id = structural_source_from_config(
        repository_locator, data_dir=data_root
    )
    root = canonical_root_from_config(repository_locator)
    store = _open_store(data_root, repository_id=repository_id, root=root)
    return RepositoryRuntime(
        repository_id=repository_id,
        root=root,
        structural=structural,
        evidence=FilesystemEvidenceSource(repository_id, root),
        store=store,
    )


def close_repository_runtime(runtime: FunctionalPyramidRepositoryRuntime) -> None:
    """Close a raw runtime when its store is the canonical SQLite implementation."""
    store = runtime.store
    if not isinstance(store, LifecycleStore):
        raise TypeError("repository runtime store is not a LifecycleStore")
    store.close()


def compose_context(
    *,
    runtime: RepositoryRuntime,
    functional_pyramid: FunctionalPyramidService,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
    addressing: AddressingService | None = None,
) -> ServiceContext:
    """Compose one repository context from raw + installation capabilities."""
    repository_id = runtime.repository_id
    store = runtime.store
    store.reap_expired()
    evidence = runtime.evidence
    seeds = store.load_authority_seeds(repository_id)

    def support_for(repository: str) -> SupportService:
        selected = repository_runtime(repository)
        return SupportService(
            store=selected.store,
            evidence=selected.evidence,
            authority=selected.store,
            policy=policy,
            functional_route_resolver=functional_pyramid.support_route,
            repository_runtime=repository_runtime,
        )

    support = support_for(repository_id)
    evidence_service = EvidenceService(store=store, evidence=evidence, policy=policy)
    effects = DependencyEffectService(
        store_for_repository=lambda owner: repository_runtime(owner).store,
        registered_repository_ids=lambda: tuple(
            sorted(functional_pyramid.registered_repository_ids())
        ),
        support_for_repository=support_for,
        functional_route_impacts=functional_pyramid.changed_route_identities,
    )
    lifecycle = LifecycleService(
        store=store,
        authority=store,
        support=support,
        evidence=evidence_service,
        effects=effects,
        functional_pyramid_route=functional_pyramid.route,
    )
    understand = UnderstandService(store=store, support=support)
    reconsider = ReconsiderService(
        store=store,
        effects=effects,
        understand=understand,
        evidence=evidence_service,
        policy=policy,
        addressing=addressing,
    )
    answer = AnswerService(
        store=store,
        support=support,
        understand=understand,
        evidence=evidence_service,
        policy=policy,
        functional_pyramid_orientation=functional_pyramid.orientation,
    )
    return ServiceContext(
        repository_id=repository_id,
        root=runtime.root,
        structural=runtime.structural,
        evidence=evidence,
        store=store,
        lifecycle=lifecycle,
        evidence_service=evidence_service,
        understand=understand,
        support=support,
        reconsider=reconsider,
        answer=answer,
        authority_seeds=seeds,
    )


def open_repository_context(
    data_dir: str | _pathlib.Path,
    repository_locator: str,
    *,
    functional_pyramid: FunctionalPyramidService,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> tuple[str, ServiceContext]:
    """Open and compose one repository through the installation runtime."""
    runtime = open_repository_runtime(data_dir, repository_locator)
    try:
        context = compose_context(
            runtime=runtime,
            functional_pyramid=functional_pyramid,
            repository_runtime=repository_runtime,
            policy=policy,
        )
    except BaseException:
        runtime.store.close()
        raise
    return runtime.repository_id, context


def close_repository_context(context: ServiceContext) -> None:
    """Close one composed repository context."""
    store = context.store
    if not isinstance(store, LifecycleStore):
        raise TypeError("repository context store is not a LifecycleStore")
    store.close()


def create_empty_repository_store(path: _pathlib.Path) -> None:
    """Create canonical empty schema; no authority or semantic registration."""
    LifecycleStore(path, retention=DEFAULT_LIFECYCLE_RETENTION).close()


def create_empty_installation_store(path: _pathlib.Path) -> None:
    FunctionalPyramidInstallationStore.create(
        path, retention=DEFAULT_LIFECYCLE_RETENTION
    ).close()


def provision_repository_runtime(
    data_dir: str | _pathlib.Path,
    request: m.InitializeRepositoryRequest,
    *,
    prepare_store: (
        _typing.Callable[[_pathlib.Path, _typing.Callable[[_pathlib.Path], None]], None]
        | None
    ) = None,
) -> tuple[RepositoryRuntime, m.InitializeRepositoryResult]:
    """Explicit setup, returning raw capabilities rather than partial services."""
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
    with store_use_ownership(data_root):
        repository_path = data_root / f"{repository_id}.db"
        if prepare_store is not None:
            prepare_store(
                functional_pyramid_installation_path(data_root),
                create_empty_installation_store,
            )
            prepare_store(repository_path, create_empty_repository_store)
        installation_store = ensure_functional_pyramid_installation_store(
            data_root, retention=DEFAULT_LIFECYCLE_RETENTION
        )
        installation_store.close()
        store = LifecycleStore(
            repository_path,
            retention=DEFAULT_LIFECYCLE_RETENTION,
            ownership_root=data_root,
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
        runtime = RepositoryRuntime(
            repository_id=repository_id,
            root=root,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    except BaseException:
        store.close()
        raise
    return runtime, result


def provision_repository(
    data_dir: str | _pathlib.Path,
    request: m.InitializeRepositoryRequest,
    *,
    functional_pyramid: FunctionalPyramidService,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> tuple[ServiceContext, m.InitializeRepositoryResult]:
    """Explicit setup followed by canonical installation-aware composition."""
    runtime, result = provision_repository_runtime(data_dir, request)
    try:
        context = compose_context(
            runtime=runtime,
            functional_pyramid=functional_pyramid,
            repository_runtime=repository_runtime,
            policy=policy,
        )
    except BaseException:
        runtime.store.close()
        raise
    return context, result
