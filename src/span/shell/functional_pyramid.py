"""Filesystem-backed Functional Pyramid declaration source."""

from __future__ import annotations

import contextlib as _contextlib
import datetime as _datetime
import json as _json
import pathlib as _pathlib
import typing as _typing

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryRuntime,
    FunctionalPyramidRepositoryUnavailable,
    FunctionalPyramidStatePort,
)
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_ownership import store_use_ownership
from span.shell.sqlite_store.functional_pyramid import (
    FunctionalPyramidInstallationStore,
    functional_pyramid_installation_path,
)
from span.shell.sqlite_store.lifecycle import UnknownRepository
from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.functional_pyramid import FunctionalPyramidService


class FilesystemFunctionalPyramidDeclarations(FunctionalPyramidDeclarationPort):
    """Read strict declarations from registered repository roots."""

    def __init__(self, repository_root: _typing.Callable[[str], str]) -> None:
        self._repository_root = repository_root

    def _source(self, repository_id: str) -> FilesystemEvidenceSource:
        try:
            root = self._repository_root(repository_id)
        except (OSError, ValueError, UnknownRepository) as exc:
            raise FunctionalPyramidRepositoryUnavailable(
                f"Functional Pyramid member {repository_id!r} is unavailable"
            ) from exc
        return FilesystemEvidenceSource(repository_id, root)

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        request = m.EvidenceRequest(".span/functional-pyramid.json")
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            if result.kind is m.EvidenceSourceFailureKind.MISSING:
                return None
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid bootstrap cannot be read"
            )
        try:
            bootstrap = _fp.decode_functional_pyramid_bootstrap(result.content)
        except ValueError as exc:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid bootstrap violates the Version-2 contract"
            ) from exc
        return result.evidence_ref, bootstrap

    def directory_exists(self, repository_id: str, directory: str) -> bool:
        root = _pathlib.Path(self._repository_root(repository_id)).resolve()
        selected = root if directory == "." else (root / directory).resolve()
        try:
            selected.relative_to(root)
        except ValueError:
            return False
        return selected.is_dir()

    def read_declaration(self, repository_id: str, request: m.EvidenceRequest) -> (
        tuple[
            m.EvidenceRef,
            m.FunctionalPyramidDeclaration,
            tuple[m.FunctionalPyramidFinding, ...],
        ]
        | m.EvidenceSourceFailure
    ):
        if request.ranges:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid declaration sources must be whole documents"
            )
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            return result
        try:
            declaration, findings = _fp.decode_functional_pyramid_declaration(
                result.content,
                repository_id=repository_id,
                declaration_locator=request.locator,
            )
        except ValueError as exc:
            unsupported_version: int | None = None
            try:
                parsed = _json.loads(result.content)
                if isinstance(parsed, dict):
                    version = parsed.get("version")
                    if isinstance(version, int) and not isinstance(version, bool):
                        unsupported_version = version
            except _json.JSONDecodeError:
                pass
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid declaration violates the Version-3 contract",
                unsupported_version=unsupported_version,
            ) from exc
        return result.evidence_ref, declaration, findings


class _InstallationAuthorityResolver:
    def __init__(
        self,
        repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    ) -> None:
        self._repository_runtime = repository_runtime

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        return self._repository_runtime(repository_id).store.resolve_authority(
            repository_id, authority_ref
        )


@_contextlib.contextmanager
def open_functional_pyramid_service(
    data_dir: str | _pathlib.Path,
    *,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> _typing.Iterator[FunctionalPyramidService | None]:
    """Open existing installation state; never create or migrate it."""
    root = _pathlib.Path(data_dir)
    path = functional_pyramid_installation_path(root)
    if not path.is_file():
        yield None
        return

    with store_use_ownership(root):
        state = FunctionalPyramidInstallationStore(
            path,
            retention=DEFAULT_LIFECYCLE_RETENTION,
        )
        try:
            yield compose_functional_pyramid_service(
                state=state,
                policy=policy,
                repository_runtime=repository_runtime,
                registered_repository_ids=registered_repository_ids,
                repository_paths=lambda repository_ids: tuple(
                    (repository_id, str(root / f"{repository_id}.db"))
                    for repository_id in repository_ids
                ),
            )
        finally:
            state.close()


def compose_functional_pyramid_service(
    *,
    state: FunctionalPyramidStatePort,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
    repository_paths: _typing.Callable[[tuple[str, ...]], tuple[tuple[str, str], ...]],
    clock: _typing.Callable[[], _datetime.datetime] | None = None,
    new_context_id: _typing.Callable[[], str] | None = None,
    policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> FunctionalPyramidService:
    """Compose the one installation-wide Functional Pyramid service."""
    return FunctionalPyramidService(
        declarations=FilesystemFunctionalPyramidDeclarations(
            lambda repository_id: repository_runtime(repository_id).root
        ),
        authority=_InstallationAuthorityResolver(repository_runtime),
        state=state,
        policy=policy,
        registered_repository_ids=registered_repository_ids,
        repository_paths=repository_paths,
        repository_runtime=repository_runtime,
        clock=clock,
        new_context_id=new_context_id,
    )
