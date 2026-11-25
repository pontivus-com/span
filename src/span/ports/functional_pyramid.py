"""External Functional Pyramid declaration source capability."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort


class FunctionalPyramidDeclarationInvalid(ValueError):
    """A named Functional Pyramid source exists but violates its strict contract."""

    def __init__(self, message: str, *, unsupported_version: int | None = None) -> None:
        super().__init__(message)
        self.unsupported_version = unsupported_version


class FunctionalPyramidRepositoryUnavailable(OSError):
    """A declared Functional Pyramid member cannot currently be read."""


class FunctionalPyramidRepositoryRuntime(_typing.Protocol):
    """Raw registered-repository capabilities used by installation services."""

    @property
    def repository_id(self) -> str: ...

    @property
    def root(self) -> str: ...

    @property
    def store(self) -> LifecycleStorePort: ...

    @property
    def evidence(self) -> EvidenceSource: ...


class FunctionalPyramidDeclarationPort(_typing.Protocol):
    """Read only exact Functional Pyramid bootstrap/declaration sources."""

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        """Return the conventional bootstrap, or None when it is absent."""
        ...

    def directory_exists(self, repository_id: str, directory: str) -> bool:
        """Whether one canonical repository-relative directory currently exists."""
        ...

    def read_declaration(self, repository_id: str, request: m.EvidenceRequest) -> (
        tuple[
            m.EvidenceRef,
            m.FunctionalPyramidDeclaration,
            tuple[m.FunctionalPyramidFinding, ...],
        ]
        | m.EvidenceSourceFailure
    ):
        """Read and strict-decode one exact whole-document declaration source."""
        ...


class FunctionalPyramidStateTransaction(_typing.Protocol):
    """Atomic installation-state writer with attached repository context sinks."""

    def active_pyramid_id(self, repository_id: str) -> m.FunctionalPyramidId | None: ...

    def pyramid_version(
        self, pyramid_id: m.FunctionalPyramidId
    ) -> m.FunctionalPyramidVersion | None: ...

    def pyramid_members(
        self,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion | None = None,
    ) -> tuple[m.FunctionalPyramidMemberView, ...]: ...

    def is_excluded(self, repository_id: str) -> bool: ...

    def receipt(
        self, request_id: m.RequestId
    ) -> m.RetrievedFunctionalPyramidReceipt | None: ...

    def write_pyramid_version(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        content_digest: m.ContentDigest,
        committed_at: _datetime.datetime,
        members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> None: ...

    def set_current_pyramid(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> None: ...

    def clear_current_pyramid(self, pyramid_id: m.FunctionalPyramidId) -> None: ...

    def set_excluded(self, repository_id: str, excluded: bool) -> None: ...

    def write_receipt(
        self,
        receipt: m.RetrievedFunctionalPyramidReceipt,
        *,
        replay_expires_at: _datetime.datetime,
    ) -> None: ...

    def write_reestablishment_context(
        self,
        context: m.InvestigationContext,
        *,
        source_observation_ids: tuple[str, ...] = (),
        discovery_observation_ids: tuple[str, ...] = (),
    ) -> None: ...


class FunctionalPyramidStatePort(_typing.Protocol):
    """Installation-scoped durable Functional Pyramid state."""

    retention: m.LifecycleRetention

    def active_pyramid_id(self, repository_id: str) -> m.FunctionalPyramidId | None: ...

    def pyramid_version(
        self, pyramid_id: m.FunctionalPyramidId
    ) -> m.FunctionalPyramidVersion | None: ...

    def pyramid_members(
        self,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion | None = None,
    ) -> tuple[m.FunctionalPyramidMemberView, ...]: ...

    def is_excluded(self, repository_id: str) -> bool: ...

    def receipt(
        self, request_id: m.RequestId
    ) -> m.RetrievedFunctionalPyramidReceipt | None: ...

    def transaction(
        self,
        repository_paths: tuple[tuple[str, str], ...] = (),
    ) -> _typing.ContextManager[FunctionalPyramidStateTransaction]: ...
