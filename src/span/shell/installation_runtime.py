"""Installation-scoped runtime composition for the Version-1 lifecycle."""

from __future__ import annotations

import contextlib as _contextlib
import pathlib as _pathlib
import typing as _typing

from span.core import model as m
from span.shell.context import (
    RepositoryRuntime,
    close_repository_runtime,
    compose_context,
    open_repository_runtime,
)
from span.shell.filesystem_evidence import FilesystemRegisteredRoots
from span.shell.functional_pyramid import open_functional_pyramid_service
from span.shell.mcp import ServiceContext
from span.shell.sqlite_store.lifecycle import LifecycleStoreError
from span.shell.structural import canonical_root_from_config, repository_id_from_config
from span.service.addressing import AddressingService
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.functional_pyramid import FunctionalPyramidService


class InstallationRuntime:
    """Own raw repository lifetimes and compose semantic contexts afterwards."""

    def __init__(
        self,
        *,
        data_dir: str | _pathlib.Path,
        repository_locator: _typing.Callable[[str], str],
        registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
    ) -> None:
        self._data_dir = _pathlib.Path(data_dir)
        self._repository_locator = repository_locator
        self.registered_roots = FilesystemRegisteredRoots(
            lambda identity: canonical_root_from_config(repository_locator(identity)),
            registered_repository_ids,
        )
        self.addressing = AddressingService(self.registered_roots)
        self._policy = policy
        self._runtimes: dict[str, RepositoryRuntime] = {}
        self._contexts: dict[str, ServiceContext] = {}
        self._functional_pyramid: FunctionalPyramidService | None = None

    @property
    def functional_pyramid(self) -> FunctionalPyramidService | None:
        return self._functional_pyramid

    def bind_functional_pyramid(self, service: FunctionalPyramidService | None) -> None:
        if self._functional_pyramid is not None:
            raise RuntimeError("Functional Pyramid service is already bound")
        self._functional_pyramid = service

    def repository_runtime(self, repository_id: str) -> RepositoryRuntime:
        runtime = self._runtimes.get(repository_id)
        if runtime is not None:
            return runtime
        try:
            locator = self._repository_locator(repository_id)
        except (KeyError, ValueError) as exc:
            raise LifecycleStoreError(
                f"unknown registered repository: {repository_id!r}"
            ) from exc
        runtime = open_repository_runtime(self._data_dir, locator)
        if runtime.repository_id != repository_id:
            runtime.store.close()
            raise LifecycleStoreError(
                "registered repository locator resolved to a different identity: "
                f"{repository_id!r} != {runtime.repository_id!r}"
            )
        self._runtimes[repository_id] = runtime
        return runtime

    def context_for_locator(self, repository_locator: str) -> ServiceContext:
        repository_id = repository_id_from_config(repository_locator)
        context = self._contexts.get(repository_id)
        if context is not None:
            return context
        service = self._functional_pyramid
        if service is None:
            raise LifecycleStoreError(
                "Functional Pyramid installation state is unavailable; "
                "run the installer before serving repository operations"
            )
        runtime = self.repository_runtime(repository_id)
        context = compose_context(
            runtime=runtime,
            functional_pyramid=service,
            repository_runtime=self.repository_runtime,
            policy=self._policy,
            addressing=self.addressing,
        )
        self._contexts[repository_id] = context
        return context

    def close(self) -> None:
        self._contexts.clear()
        for repository_id in sorted(self._runtimes, reverse=True):
            close_repository_runtime(self._runtimes[repository_id])
        self._runtimes.clear()


@_contextlib.contextmanager
def open_installation_runtime(
    data_dir: str | _pathlib.Path,
    *,
    repository_locator: _typing.Callable[[str], str],
    registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> _typing.Iterator[InstallationRuntime]:
    """Open the one installation composition root and all lazy repository runtimes."""
    runtime = InstallationRuntime(
        data_dir=data_dir,
        repository_locator=repository_locator,
        registered_repository_ids=registered_repository_ids,
        policy=policy,
    )
    try:
        with open_functional_pyramid_service(
            data_dir,
            repository_runtime=runtime.repository_runtime,
            registered_roots=runtime.registered_roots,
            policy=policy,
        ) as functional_pyramid:
            runtime.bind_functional_pyramid(functional_pyramid)
            yield runtime
    finally:
        runtime.close()
