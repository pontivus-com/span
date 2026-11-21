"""External Functional Pyramid declaration source capability."""

from __future__ import annotations

import typing as _typing

from span.core import model as m


class FunctionalPyramidDeclarationInvalid(ValueError):
    """A named Functional Pyramid source exists but violates its strict contract."""


class FunctionalPyramidRepositoryUnavailable(OSError):
    """A declared Functional Pyramid member cannot currently be read."""


class FunctionalPyramidDeclarationPort(_typing.Protocol):
    """Read only exact Functional Pyramid bootstrap/declaration sources."""

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        """Return the conventional bootstrap, or None when it is absent."""

    def read_declaration(
        self, repository_id: str, request: m.EvidenceRequest
    ) -> (
        tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration]
        | m.EvidenceSourceFailure
    ):
        """Read and strict-decode one exact whole-document declaration source."""
