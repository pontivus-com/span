"""Pure selected-status and verification decisions (FD-28)."""

from __future__ import annotations

from span.core import containment, model as m


def status_distribution(
    subject: m.StatusSubject,
    evaluations: tuple[m.UnderstandingSupport, ...],
    curated: frozenset[m.ConclusionRevisionRef],
    *,
    coverage: tuple[int, bool] | None = None,
    descendants: tuple[m.SurfaceStatusSummary, ...] = (),
) -> m.SurfaceStatus:
    current = 0
    pending: list[m.PendingConclusionRef] = []
    stale: list[m.StaleConclusionRef] = []
    for qualification in evaluations:
        for conclusion in qualification.conclusions:
            state = conclusion.evaluation.state
            if state is not m.SupportState.CURRENT:
                stale.append(
                    m.StaleConclusionRef(conclusion.ref, qualification.version, state)
                )
            elif conclusion.ref in curated:
                current += 1
            else:
                pending.append(
                    m.PendingConclusionRef(conclusion.ref, qualification.version)
                )
    return m.SurfaceStatus(
        subject=subject,
        current=current,
        pending=len(pending),
        pending_refs=tuple(pending),
        stale=len(stale),
        stale_refs=tuple(stale),
        unassessed=sum(not item.conclusions for item in evaluations),
        unexamined=None if coverage is None else coverage[0],
        unexamined_limited=None if coverage is None else coverage[1],
        descendants=descendants,
    )


def summarize_surface(status: m.SurfaceStatus) -> m.SurfaceStatusSummary:
    if status.unexamined is None or status.unexamined_limited is None:
        raise ValueError("only an ordinary surface has a child summary")
    return m.SurfaceStatusSummary(
        surface=status.subject.surface,
        current=status.current,
        pending=status.pending,
        stale=status.stale,
        unassessed=status.unassessed,
        unexamined=status.unexamined,
        unexamined_limited=status.unexamined_limited,
    )


def _strictly_contains(parent: m.Surface, child: m.Surface) -> bool:
    if (
        parent.key.repository_id != child.key.repository_id
        or parent.key == child.key
        or not parent.key.kind.is_declared
    ):
        return False
    if not child.key.kind.is_declared:
        return containment.surface_contains(parent, child.key)
    outer = m.EvidenceScope(paths=parent.boundary.paths + parent.boundary.symbols)
    inner = m.EvidenceScope(paths=child.boundary.paths + child.boundary.symbols)
    if not outer.paths or not inner.paths:
        return False
    return m.evidence_scope_contains(outer, inner) and (
        not m.evidence_scope_contains(inner, outer)
        or (
            parent.key.kind is m.SurfaceKind.DOMAIN
            and child.key.kind is m.SurfaceKind.SERVICE
        )
    )


def immediate_children(
    owner: m.SurfaceKey, surfaces: tuple[m.Surface, ...]
) -> tuple[m.SurfaceKey, ...]:
    parent = next((surface for surface in surfaces if surface.key == owner), None)
    if parent is None:
        return ()
    descendants = tuple(
        surface for surface in surfaces if _strictly_contains(parent, surface)
    )
    return containment.order_surfaces(
        child.key
        for child in descendants
        if not any(_strictly_contains(other, child) for other in descendants)
    )


def verification_covers(
    run: m.VerificationRun, repository_id: str, scope: m.EvidenceScope
) -> bool:
    if run.repository_id != repository_id:
        return False
    outer = run.scope.scope
    if any(ref.repository_id != repository_id for ref in outer.evidence_refs):
        return False
    if any(ref.repository_id != repository_id for ref in scope.evidence_refs):
        return False
    return m.evidence_scope_contains(outer, scope)


def _verification_group(
    view: m.VerificationView,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], str, str, str, tuple[str, ...]]:
    run = view.run
    refs = tuple(
        sorted(
            {
                (
                    ref.repository_id,
                    ref.evidence_id.value,
                    ref.source_kind.value,
                    ref.locator,
                    ref.revision_or_fingerprint or "",
                    ref.section_or_span or "",
                )
                for ref in run.scope.scope.evidence_refs
            }
        )
    )
    return (
        tuple(sorted(set(run.scope.scope.paths))),
        refs,
        run.scope.description,
        run.command or "",
        run.scenario or "",
        tuple(item.strip() for item in run.environment_limitations),
    )


def select_verification(
    candidates: tuple[m.VerificationView, ...],
) -> tuple[tuple[m.VerificationView, ...], tuple[m.VerificationView, ...]]:
    """Latest recorded and latest CURRENT per outcome, with ties and history."""
    groups: dict[
        tuple[tuple[str, ...], tuple[tuple[str, ...], ...], str, str, str, tuple[str, ...]],
        list[m.VerificationView],
    ] = {}
    for view in candidates:
        groups.setdefault(_verification_group(view), []).append(view)
    primary: list[m.VerificationView] = []
    history: list[m.VerificationView] = []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda item: item.run.run_id.value)
        ordered.sort(key=lambda item: item.run.observed_at, reverse=True)
        latest = ordered[0].run.observed_at
        current_times = {
            outcome: max(
                (
                    item.run.observed_at
                    for item in ordered
                    if item.run.outcome is outcome
                    and isinstance(item.qualification, m.VerificationQualification)
                    and item.qualification.state is m.SupportState.CURRENT
                ),
                default=None,
            )
            for outcome in m.VerificationOutcome
        }
        for item in ordered:
            current = (
                isinstance(item.qualification, m.VerificationQualification)
                and item.qualification.state is m.SupportState.CURRENT
                and item.run.observed_at == current_times[item.run.outcome]
            )
            destination = (
                primary if item.run.observed_at == latest or current else history
            )
            destination.append(item)
    return tuple(primary), tuple(history)
