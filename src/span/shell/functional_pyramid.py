"""Filesystem-backed Functional Pyramid declaration source."""

from __future__ import annotations

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.ports.functional_pyramid import FunctionalPyramidDeclarationPort
from span.ports.lifecycle import LifecycleStorePort
from span.shell.filesystem_evidence import FilesystemEvidenceSource


class FilesystemFunctionalPyramidDeclarations(FunctionalPyramidDeclarationPort):
    """Read strict declarations from roots already bound by the lifecycle store."""

    def __init__(self, store: LifecycleStorePort) -> None:
        self._store = store

    def _source(self, repository_id: str) -> FilesystemEvidenceSource:
        root = self._store.require_repository(repository_id)
        return FilesystemEvidenceSource(repository_id, root)

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        request = m.EvidenceRequest(".span/functional-pyramid.json")
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            if result.kind is m.EvidenceSourceFailureKind.MISSING:
                return None
            raise ValueError(result.reason)
        return (
            result.evidence_ref,
            _fp.decode_functional_pyramid_bootstrap(result.content),
        )

    def read_declaration(
        self, repository_id: str, request: m.EvidenceRequest
    ) -> (
        tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration]
        | m.EvidenceSourceFailure
    ):
        if request.ranges:
            raise ValueError(
                "Functional Pyramid declaration sources must be whole documents"
            )
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            return result
        return (
            result.evidence_ref,
            _fp.decode_functional_pyramid_declaration(result.content),
        )
