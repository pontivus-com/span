"""EvidenceSource port (plan §5.3).

Generic retrieval mechanics only. Evidence selection may use links,
structural references, names/identifiers as retrieval anchors, authority
seeds, and text search — but filename, path, keyword, or similarity
score never establish semantic authority (plan §5.3/§6.2).
"""

import typing as _typing

from span.core.model import (
    EvidenceRef,
    EvidenceInventoryPage,
    EvidenceScope,
    EvidenceSelection,
    EvidenceUnit,
    QueryBounds,
    StructuralObservation,
    SubjectId,
)


@_typing.runtime_checkable
class EvidenceSource(_typing.Protocol):
    def inventory_evidence(
        self,
        repository_id: str,
        scope: EvidenceScope,
        bounds: QueryBounds,
    ) -> EvidenceInventoryPage:
        """Bounded evidence inventory (fingerprints, not judgments)."""
        ...

    def select_evidence(
        self,
        repository_id: str,
        subject: SubjectId,
        structural_context: tuple[StructuralObservation, ...],
        known_authority_seeds: tuple[EvidenceRef, ...],
        bounds: QueryBounds,
    ) -> EvidenceSelection:
        """Bounded evidence selection; relevance only, never authority."""
        ...

    def read_evidence(
        self,
        refs: tuple[EvidenceRef, ...],
        bounds: QueryBounds,
    ) -> tuple[EvidenceUnit, ...]:
        """Read bounded evidence units for the given references."""
        ...
