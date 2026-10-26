"""Target identity, membership, and canonicalization.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
from dataclasses import dataclass as _dataclass

from span.core.model.primitives import (
    EvidenceRef,
    EvidenceScope,
    SubjectId,
    _require_non_empty,
)
from span.core.model.canonical import (
    to_canonical,
)
from span.core.model.semantics import (
    SemanticQuestionScope,
)
from span.core.model.repository import (
    EvidenceInventoryItem,
)


@_dataclass(frozen=True)
class TargetId:
    """Nominal non-empty opaque target-campaign identifier ([design note E](docs/design-references.md#e))."""

    value: str

    def __post_init__(self) -> None:
        _require_non_empty("TargetId", self.value)


@_dataclass(frozen=True)
class TargetInventoryAccount:
    """One durable target-membership entry ([design note E](docs/design-references.md#e) §4C.2).

    Membership only: the member and the area subjects it belongs to. No
    semantic meaning, and no content fingerprint. Membership is computed at
    admission, so there is no agent-proposed counterpart to this carrier.
    """

    evidence_ref: EvidenceRef
    assigned_area_subjects: tuple[SubjectId, ...] = ()

    def __post_init__(self) -> None:
        if not self.assigned_area_subjects:
            raise ValueError(
                "TargetInventoryAccount requires at least one area subject"
            )


@_dataclass(frozen=True)
class TargetAssociation:
    """Durable target-accounting state ([design note E](docs/design-references.md#e) §§4C.2/4C.6A–6C).

    Accounting only; area meaning stays in claims/relationships, question
    state stays in InterpretationCoverage.
    """

    target_id: TargetId
    repository_id: str
    target_scope: EvidenceScope
    objective: str
    area_subjects: tuple[SubjectId, ...] = ()
    target_questions: tuple[SemanticQuestionScope, ...] = ()
    inventory_accounting: tuple[TargetInventoryAccount, ...] = ()
    inventory_fingerprint: str = ""
    observed_repository_state_fingerprint: str = ""
    #: Retention deadline for this handle, as stored. None on a carrier built
    #: before a write assigns it.
    expires_at: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("repository_id", self.repository_id)
        _require_non_empty("objective", self.objective)


def _canonicalize_path(path: str) -> str:
    if not path or path.startswith("/") or path == "":
        raise ValueError(f"invalid target path: {path!r}")
    parts = path.split("/")
    out: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"path escapes repository: {path!r}")
        if part == "":
            raise ValueError(f"invalid target path: {path!r}")
        out.append(part)
    if not out:
        return "."
    return "/".join(out)


def canonicalize_target_scope(
    repository_id: str, scope: EvidenceScope, objective: str
) -> tuple[EvidenceScope, str]:
    """Canonicalize scope/objective per [design note E](docs/design-references.md#e) §4C.6A (deterministic)."""
    canonical_objective = objective.strip()
    if not canonical_objective:
        raise ValueError("objective is empty after strip")
    if not scope.paths and not scope.evidence_refs:
        raise ValueError("target scope is empty: no paths or evidence_refs")
    canonical_paths: list[str] = []
    for raw in scope.paths:
        if not raw:
            raise ValueError("empty path member")
        canonical_paths.append(_canonicalize_path(raw))
    canonical_paths = sorted(set(canonical_paths))
    canonical_refs: list[EvidenceRef] = []
    for ref in scope.evidence_refs:
        if ref.repository_id != repository_id:
            raise ValueError("evidence_ref repository mismatch")
        if ref.section_or_span is not None:
            raise ValueError("section-scoped refs are not inventory members")
        canonical_refs.append(
            EvidenceRef(
                evidence_id=ref.evidence_id,
                repository_id=ref.repository_id,
                source_kind=ref.source_kind,
                locator=_canonicalize_path(ref.locator),
                revision_or_fingerprint=None,
                section_or_span=None,
            )
        )
    canonical_refs.sort(
        key=lambda r: (
            r.evidence_id.value,
            r.source_kind.value,
            r.locator,
        )
    )
    seen: dict[str, EvidenceRef] = {}
    for ref in canonical_refs:
        key = ref.evidence_id.value
        if key in seen:
            prev = seen[key]
            if prev.locator != ref.locator or prev.source_kind != ref.source_kind:
                raise ValueError(f"conflicting provider identity for {key!r}")
            continue
        seen[key] = ref
    canonical_scope = EvidenceScope(
        paths=tuple(canonical_paths),
        evidence_refs=tuple(seen[k] for k in sorted(seen)),
    )
    return canonical_scope, canonical_objective


def derive_target_id(
    repository_id: str, canonical_scope: EvidenceScope, canonical_objective: str
) -> TargetId:
    """Derive tgt- ID from canonical identity only (no revision/content)."""
    payload = to_canonical(canonical_scope)
    canonical_json = _json.dumps(
        [repository_id, payload, canonical_objective],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = _hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
    return TargetId(value=f"tgt-{digest}")


def target_inventory_fingerprint(
    items: tuple[EvidenceInventoryItem, ...],
) -> str:
    """Membership fingerprint over sorted stable identity tuples."""
    members = sorted(
        (
            item.evidence_ref.evidence_id.value,
            item.evidence_ref.locator,
            item.evidence_ref.source_kind.value,
        )
        for item in items
    )
    payload = _json.dumps(
        [list(m) for m in members],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()
