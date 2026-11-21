"""Filesystem-backed Functional Pyramid declaration source."""

from __future__ import annotations

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryUnavailable,
)
from span.ports.lifecycle import LifecycleStorePort
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_store.lifecycle import UnknownRepository


class FilesystemFunctionalPyramidDeclarations(FunctionalPyramidDeclarationPort):
    """Read strict declarations from roots already bound by the lifecycle store."""

    def __init__(self, store: LifecycleStorePort) -> None:
        self._store = store

    def _source(self, repository_id: str) -> FilesystemEvidenceSource:
        try:
            root = self._store.require_repository(repository_id)
        except UnknownRepository as exc:
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
                "Functional Pyramid bootstrap violates the Version-1 contract"
            ) from exc
        return result.evidence_ref, bootstrap

    def read_declaration(
        self, repository_id: str, request: m.EvidenceRequest
    ) -> (
        tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration]
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
            declaration = _fp.decode_functional_pyramid_declaration(result.content)
        except ValueError as exc:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid declaration violates the Version-1 contract"
            ) from exc
        return result.evidence_ref, declaration
