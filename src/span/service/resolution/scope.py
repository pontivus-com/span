"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource


from span.service.resolution.selector import (
    _fallback_target_kind,
    _resolve_query_subject,
)


def _inventory_subjects(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> dict[tuple[m.SubjectKind, str], m.Subject]:
    """One subject per evidence-inventory item in the scope.

    Structural resolution first; a fallback subject when the provider knows the
    file but no semantic subject exists for it yet.
    """
    items: list[m.EvidenceInventoryItem] = []
    page_token: str | None = None
    while True:
        page = evidence.inventory_evidence(repository_id, scope, bounds, page_token)
        items.extend(page.items)
        next_token = page.bound_info.continuation_token
        if next_token is None:
            break
        if not page.items or next_token == page_token:
            raise ValueError("target evidence inventory did not advance")
        page_token = next_token
    found: dict[tuple[m.SubjectKind, str], m.Subject] = {}
    for item in items:
        locator = item.evidence_ref.locator
        resolution = structural.resolve_subject(
            repository_id,
            m.SubjectSelector(
                exact_subject_id=None,
                name_or_locator=locator,
                expected_kinds=(),
                retrieval_scope_hint=None,
            ),
            bounds,
        )
        subject = None
        if (
            resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED
            and len(resolution.candidates) == 1
            and resolution.candidates[0].subject.subject_id.canonical_locator == locator
        ):
            subject = resolution.candidates[0].subject
        if subject is None:
            subject = m.Subject(
                subject_id=m.SubjectId(
                    repository_id=repository_id,
                    subject_kind=_fallback_target_kind(item.evidence_ref),
                    canonical_locator=locator,
                ),
                display_name=locator.rsplit("/", 1)[-1],
                declared_kind=None,
            )
        found[(subject.subject_id.subject_kind, locator)] = subject
    return found


def _persisted_subjects_in_scope(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Every persisted subject in the scope, by keyset pages.

    This is the query that replaced the repository-wide subject scan: the
    store filters in SQL on the scope predicate.
    """
    subjects: list[m.Subject] = []
    after: tuple[str, str] | None = None
    while True:
        page = store.load_subjects_in_scope(repository_id, scope, bounds, after)
        subjects.extend(page.items)
        if not page.bound_info.truncated or not page.items:
            break
        last = page.items[-1].subject_id
        after = (last.canonical_locator, last.subject_kind.value)
    return tuple(subjects)


def _merged_scope_subjects(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """The scope frontier: persisted subjects plus evidence-derived ones.

    Persisted subjects win over a fallback for the same locator. Ordered by
    ``(locator, kind)`` so a page boundary is deterministic.
    """
    found = _inventory_subjects(
        repository_id, scope, structural=structural, evidence=evidence, bounds=bounds
    )
    for subject in _persisted_subjects_in_scope(
        repository_id, scope, store=store, bounds=bounds
    ):
        sid = subject.subject_id
        found[(sid.subject_kind, sid.canonical_locator)] = subject
    return tuple(
        found[key] for key in sorted(found, key=lambda pair: (pair[1], pair[0].value))
    )


def frontier_fingerprint(subjects: tuple[m.Subject, ...]) -> str:
    """Membership fingerprint binding a continuation to the exact frontier."""
    import hashlib as _hashlib

    payload = "\x00".join(
        f"{subject.subject_id.subject_kind.value}:"
        f"{subject.subject_id.canonical_locator}"
        for subject in subjects
    )
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def resolve_scope_frontier(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    offset: int = 0,
) -> tuple[tuple[m.Subject, ...], int, str]:
    """One frontier page plus the total and the membership fingerprint.

    ``offset`` is a position in the ordered frontier. The fingerprint lets the
    caller bind a continuation to the membership it was issued against, so a
    changed scope restarts instead of silently skipping.
    """
    if offset < 0:
        raise ValueError("scope offset must be non-negative")
    merged = _merged_scope_subjects(
        repository_id,
        scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    page = merged[offset : offset + bounds.max_subjects]
    return tuple(page), len(merged), frontier_fingerprint(merged)


def _resolve_target_subjects(
    repository_id: str,
    target: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Enumerate current structural/evidence candidates in the exact scope.

    Exhaustive by design: ``initialize_target`` needs the whole boundary. A
    scoped read uses ``resolve_scope_frontier`` instead, which pages it.
    """
    if not target.paths and not target.evidence_refs:
        raise ValueError("exact target scope must not be empty")
    return _merged_scope_subjects(
        repository_id,
        target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )


def _resolve_scope_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    evidence: EvidenceSource | None = None,
) -> tuple[tuple[m.Subject, ...], m.ResolutionAmbiguity]:
    if isinstance(target, m.EvidenceScope):
        if evidence is not None:
            return (
                _resolve_target_subjects(
                    repository_id,
                    target,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    bounds=bounds,
                ),
                m.ResolutionAmbiguity.RESOLVED,
            )
        subjects: list[m.Subject] = []
        paths = list(target.paths) + [ref.locator for ref in target.evidence_refs]
        for path in dict.fromkeys(paths):
            resolution = structural.resolve_subject(
                repository_id,
                m.SubjectSelector(
                    exact_subject_id=None,
                    name_or_locator=path,
                    expected_kinds=(),
                    retrieval_scope_hint=None,
                ),
                bounds,
            )
            subjects.extend(c.subject for c in resolution.candidates)
        seen: set[str] = set()
        unique = []
        for subject in subjects:
            key = subject.subject_id.canonical_locator
            if key not in seen:
                seen.add(key)
                unique.append(subject)
        return tuple(unique), m.ResolutionAmbiguity.RESOLVED
    resolution = _resolve_query_subject(
        repository_id,
        target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    return (
        tuple(c.subject for c in resolution.candidates),
        resolution.ambiguity,
    )
