"""Bounded transitive premise freshness walk (plan §9.2).

Separated from the query and projection paths: this is the one walk that
expands staleness across premise dependents, and it is long enough to own a
module rather than crowd the classifiers beside it.
"""

from __future__ import annotations


from span.core import model as m
from span.ports.store import SemanticStore


def _premise_preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    max_depth: int = 6,
    live_states: dict[str, m.FreshnessState] | None = None,
) -> tuple[m.FreshnessUpdate, ...]:
    """Bounded transitive premise walk with path-based cycle detection.

    A cycle is reported only when a premise chain leads back to an
    item already on the CURRENT traversal path (true circularity).
    Merely visiting the same premise from two roots (diamond or
    sibling order) is not a cycle. Truncation yields UNVERIFIABLE,
    never silent green.

    ``live_states`` carries per-call live classifications for reached
    premise evidence (S2 §5.2): premises with live direct evidence use
    the live state, not stored freshness. A source can change before
    any other operation marks its premise stale.
    """
    updates: dict[str, m.FreshnessUpdate] = {}
    clean: set[str] = set()

    def _mark(
        rid: str,
        ref: m.ClaimRef | m.RelationshipRef,
        state: m.FreshnessState,
        reason: str,
    ) -> None:
        updates.setdefault(
            rid,
            m.FreshnessUpdate(
                semantic_id=ref, freshness=m.Freshness(state, reason=reason)
            ),
        )

    def _premise_update_state(pid: str) -> m.FreshnessState | None:
        update = updates.get(pid)
        return update.freshness.state if update is not None else None

    def _visit(
        ref: m.ClaimRef | m.RelationshipRef,
        path: tuple[str, ...],
        depth: int,
    ) -> bool:
        """Walk one subtree; True iff fully explored (no truncation)."""
        rid = ref.id.value
        if rid in clean or rid in updates:
            return True
        if depth >= max_depth:
            return False
        try:
            (item,) = store.load_by_refs(repository_id, (ref,))
        except ValueError:
            _mark(
                rid,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise unknown/retired; reassessment required",
            )
            return True
        premises = [
            pref
            for pref in item.basis.input_refs
            if isinstance(pref, (m.ClaimRef, m.RelationshipRef))
        ]
        if not premises:
            clean.add(rid)
            return True
        complete = True
        for pref in premises:
            pid = pref.id.value
            if pid == rid or pid in path:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.UNVERIFIABLE,
                    "premise cycle; unverifiable until reconciled",
                )
                continue
            if not _visit(pref, path + (rid,), depth + 1):
                complete = False
                continue
            state = _premise_update_state(pid)
            if state is None and live_states is not None:
                state = live_states.get(pid)
            if state is None:
                try:
                    (premise,) = store.load_by_refs(repository_id, (pref,))
                except ValueError:
                    _mark(
                        rid,
                        ref,
                        m.FreshnessState.STALE,
                        "premise retired/unknown; dependent reassessment " "required",
                    )
                    continue
                state = premise.freshness.state
            if state is m.FreshnessState.UNVERIFIABLE:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.UNVERIFIABLE,
                    "upstream premise unverifiable; dependent " "reassessment required",
                )
            elif state is not m.FreshnessState.CURRENT:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.STALE,
                    "upstream premise noncurrent; dependent reassessment " "required",
                )
        if complete and rid not in updates:
            clean.add(rid)
        return complete

    for ref in semantic_ids:
        if not _visit(ref, (), 0):
            _mark(
                ref.id.value,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
        if len(clean) + len(updates) > bounds.max_results * 4 + len(semantic_ids):
            _mark(
                ref.id.value,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
            break
    return tuple(updates.values())
