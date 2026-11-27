"""One read-time surface status composer shared by ask and record (FD-60)."""

from __future__ import annotations

from dataclasses import replace as _replace

from span.core import model as m
from span.core import selection
from span.ports.lifecycle import LifecycleStorePort
from span.service.support import SupportService
from span.service.evidence import EvidenceService


def compose_surface_status(
    surface: m.SurfaceKey,
    *,
    store: LifecycleStorePort,
    support: SupportService,
    evidence: EvidenceService,
    selected: tuple[m.Understanding, ...] | None = None,
) -> m.SurfaceStatus:
    if selected is not None:
        return _distribution(surface, selected, store=store, support=support)
    all_understandings = tuple(store.list_understandings(surface.repository_id))
    own = tuple(item for item in all_understandings if item.surface == surface)
    examined = _examined_scopes(all_understandings, store=store)
    surfaces = store.list_surfaces(surface.repository_id)
    children = selection.immediate_children(surface, surfaces)
    summaries = tuple(
        _surface_distribution(
            child,
            tuple(item for item in all_understandings if item.surface == child),
            examined,
            store=store,
            support=support,
            evidence=evidence,
        )
        for child in children
    )
    return _surface_distribution(
        surface,
        own,
        examined,
        store=store,
        support=support,
        evidence=evidence,
        descendants=summaries,
    )


def _distribution(
    surface: m.SurfaceKey,
    understandings: tuple[m.Understanding, ...],
    *,
    store: LifecycleStorePort,
    support: SupportService,
) -> m.SurfaceStatus:
    evaluations = tuple(
        support.evaluate_version(
            understanding.understanding_id.value, understanding.current_version.value
        )
        for understanding in understandings
    )
    curated = frozenset(
        conclusion.ref
        for qualification in evaluations
        for conclusion in qualification.conclusions
        if conclusion.evaluation.state is m.SupportState.CURRENT
        and store.find_curation(
            conclusion.ref, as_of_version=qualification.version
        )
        is not None
    )
    return selection.status_distribution(surface, evaluations, curated)


def _surface_distribution(
    surface: m.SurfaceKey,
    understandings: tuple[m.Understanding, ...],
    examined: tuple[m.EvidenceScope, ...],
    *,
    store: LifecycleStorePort,
    support: SupportService,
    evidence: EvidenceService,
    descendants: tuple[m.SurfaceStatus, ...] = (),
) -> m.SurfaceStatus:
    distribution = _distribution(surface, understandings, store=store, support=support)
    unexamined, limited = _unexamined(
        surface, understandings, examined, store=store, evidence=evidence
    )
    return _replace(
        distribution,
        unexamined=unexamined,
        unexamined_limited=limited,
        descendants=descendants,
    )


def _examined_scopes(
    understandings: tuple[m.Understanding, ...], *, store: LifecycleStorePort
) -> tuple[m.EvidenceScope, ...]:
    """Retain complete semantic scopes for exact coverage checks (FD-59)."""
    scopes: list[m.EvidenceScope] = []
    for understanding in understandings:
        version = store.get_version(
            understanding.understanding_id.value,
            understanding.current_version.value,
        )
        revisions = {
            (item.conclusion_id.value, item.revision.value): item
            for item in store.get_conclusions(understanding.understanding_id.value)
        }
        for ref in version.conclusions:
            revision = revisions.get((ref.conclusion_id.value, ref.revision.value))
            content = None if revision is None else revision.content
            if isinstance(content, m.SupportedConclusion):
                scopes.append(content.scope)
    return tuple(scopes)


def _is_examined(locator: str, scopes: tuple[m.EvidenceScope, ...]) -> bool:
    member = m.EvidenceScope(paths=(locator,))
    return any(m.evidence_scope_contains(scope, member) for scope in scopes)


def _unexamined(
    surface: m.SurfaceKey,
    understandings: tuple[m.Understanding, ...],
    examined: tuple[m.EvidenceScope, ...],
    *,
    store: LifecycleStorePort,
    evidence: EvidenceService,
) -> tuple[int, bool]:
    """Boundary members with no understanding, and whether the count is bounded.

    A path or symbol surface is exactly one enumerable member. A declared
    surface can only enumerate the path and symbol surfaces the store has
    seen, so it reports the limit rather than claiming completeness
    (FD-8, scope.md "never as completeness").
    """
    if surface.kind in (m.SurfaceKind.FILE, m.SurfaceKind.SYMBOL):
        if _is_examined(surface.locator, examined):
            return 0, False
        return (0 if understandings else 1), False
    declared = store.find_surface(surface)
    if declared is None:
        return 0, True
    if not (declared.boundary.paths or declared.boundary.symbols):
        return 0, True
    unexamined = 0
    if declared.boundary.paths:
        for path in evidence.inventory_paths(
            surface.repository_id,
            m.EvidenceScope(paths=declared.boundary.paths),
        ):
            if not _is_examined(path, examined):
                unexamined += 1
    for symbol in declared.boundary.symbols:
        if not _is_examined(symbol, examined) and not any(
            item.surface.kind is m.SurfaceKind.SYMBOL and item.surface.locator == symbol
            for item in store.list_understandings(surface.repository_id)
        ):
            unexamined += 1
    return unexamined, True

