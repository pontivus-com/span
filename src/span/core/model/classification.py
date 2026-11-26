"""Flat Functional Pyramid classification (FD-88A).

One row is one canonical document's placement decision. The row carries only
what Span cannot derive: the owner's layer, directory scope, governing document
references and place/exclude decision. Sources, membership, placement identity,
ordering and the bootstrap are derived.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import enum as _enum

from span.core.model.functional_pyramid import (
    FunctionalDirectoryScope,
    FunctionalDocumentIdentity,
    FunctionalPyramidDeclaration,
    FunctionalPyramidLayer,
)
from span.core.model.primitives import _require_non_empty

__all__ = [
    "FunctionalPyramidClassification",
    "FunctionalPyramidClassificationDisposition",
    "FunctionalPyramidClassificationExclusion",
    "FunctionalPyramidClassificationRow",
    "FunctionalPyramidDerivation",
]


class FunctionalPyramidClassificationDisposition(_enum.Enum):
    PLACE = "place"
    EXCLUDE = "exclude"


@_dataclasses.dataclass(frozen=True)
class FunctionalPyramidClassificationRow:
    """One document's owner-decided placement."""

    repository_id: str
    document_ref: str
    disposition: FunctionalPyramidClassificationDisposition
    layer: FunctionalPyramidLayer | None = None
    scope: str | None = None
    governing_documents: tuple[FunctionalDocumentIdentity | str, ...] = ()
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        identity = FunctionalDocumentIdentity(self.repository_id, self.document_ref)
        if not isinstance(self.disposition, FunctionalPyramidClassificationDisposition):
            raise ValueError("row.disposition is not a classification disposition")
        if self.disposition is FunctionalPyramidClassificationDisposition.EXCLUDE:
            if (
                self.layer is not None
                or self.scope is not None
                or self.governing_documents
            ):
                raise ValueError(
                    "an exclude row carries no layer, scope or governing documents"
                )
            if not self.exclusion_reason:
                raise ValueError("an exclude row requires an exclusion reason")
            return
        if self.exclusion_reason is not None:
            raise ValueError("a place row carries no exclusion reason")
        if self.layer is None or self.scope is None:
            raise ValueError("a place row requires layer and scope")
        if not isinstance(self.layer, FunctionalPyramidLayer):
            raise ValueError("row.layer is not a Functional Pyramid layer")
        FunctionalDirectoryScope(self.scope)

        governing = self.governing_documents
        for parent in governing:
            if isinstance(parent, str):
                if parent != "ROOT":
                    raise ValueError("the only string governing terminal is ROOT")
            elif not isinstance(parent, FunctionalDocumentIdentity):
                raise ValueError("governing documents are document identities or ROOT")
            elif parent == identity:
                raise ValueError("a placement cannot govern itself")
        if len(set(governing)) != len(governing):
            raise ValueError("governing documents must be distinct")
        if self.layer is FunctionalPyramidLayer.P0:
            if governing not in ((), ("ROOT",)):
                raise ValueError("a P0 row is governed by ROOT, not a document")
        elif not governing:
            raise ValueError("a non-P0 row requires at least one governing document")
        elif "ROOT" in governing:
            raise ValueError("ROOT governs only P0 placements")


@_dataclasses.dataclass(frozen=True)
class FunctionalPyramidClassificationExclusion:
    """One explicit non-placement decision and its reason."""

    repository_id: str
    document_ref: str
    reason: str

    def __post_init__(self) -> None:
        FunctionalDocumentIdentity(self.repository_id, self.document_ref)
        _require_non_empty("exclusion.reason", self.reason)


@_dataclasses.dataclass(frozen=True)
class FunctionalPyramidDerivation:
    """The canonical Version-3 source set derived from one classification."""

    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...]
    exclusions: tuple[FunctionalPyramidClassificationExclusion, ...] = ()

    def __post_init__(self) -> None:
        if not self.declarations:
            raise ValueError("a derivation requires at least one declaration source")


@_dataclasses.dataclass(frozen=True)
class FunctionalPyramidClassification:
    """One approved flat classification."""

    rows: tuple[FunctionalPyramidClassificationRow, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError("classification.version must be 1")
        if not self.rows:
            raise ValueError("classification requires at least one row")
        identities = [(row.repository_id, row.document_ref) for row in self.rows]
        if len(set(identities)) != len(identities):
            raise ValueError("classification rows must be unique per document")
