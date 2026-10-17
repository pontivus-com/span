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
        page_token: str | None = None,
    ) -> EvidenceInventoryPage:
        """Bounded evidence inventory (fingerprints, not judgments).

        Stable-identity contract (Addendum E §4C.6B): for one logical
        inventory member in one repository, EvidenceId is stable across
        repeated calls, restarts, and content changes. A rename/move may
        legitimately appear as removal of the old identity and admission
        of a new identity. Content fingerprints are per-read observations,
        never identity. Services deduplicate identical identity and fail
        closed on conflicting identity for one EvidenceId.
        """
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

    def list_inventory_entries(
        self,
        repository_id: str,
        scope: EvidenceScope,
        fingerprint_locators: tuple[str, ...] = (),
    ) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
        """Membership-only inventory listing plus targeted fingerprints.

        Returns ((locator, evidence_id value) pairs in deterministic
        order, {locator: content fingerprint} for the requested
        locators present). Membership is restricted to ``scope``; an
        empty ``scope`` (no paths and no refs) preserves repository-wide
        membership (migrated legacy coverage). Requested fingerprints
        may resolve outside the scope for explicit authority seeds and
        never enlarge membership. Non-requested content is neither read
        nor hashed. Retrieval mechanics only — never authority.
        """
        ...
