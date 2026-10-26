"""Task construction and the slice-derived brief."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.core import requirements as _requirements
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource
from span.service.discovery import (
    _read_units_within_bytes,
    discover_evidence,
)
from span.service.questions import _question_class_for_intent

from span.service.interpretation.brief import _build_task_brief
from span.service.interpretation.excerpts import (
    _project_excerpts,
)


def _member_diagnostics(
    collection: str,
    index: int,
    key: str | None,
    diagnostics: tuple[str, ...] | list[str],
) -> list[str]:
    """Prefix validation diagnostics with member identity (G §4.3).

    Format is always `collection[index] (key=...)`: collection plus
    zero-based index are always present so duplicate or missing keys
    stay distinguishable. Atomic rejection is unchanged; only identity
    improves.
    """
    label = f"{collection}[{index}]"
    if key:
        label += f" (key={key})"
    else:
        label += " (key=?)"
    return [f"{label}: {text}" for text in diagnostics]


@_dataclass(frozen=True)
class InterpretationTask:
    """Prepared bounded interpretation task (Span side, pre-suspension)."""

    request: m.SemanticInterpretationRequest
    fingerprints: tuple[tuple[str, str], ...]
    known_subject_ids: tuple[m.SubjectId, ...]
    observations: tuple[m.StructuralObservation, ...]


@_dataclass
class _StructuralContext:
    """The bounded structural neighbourhood one task is built from."""

    observations: tuple[m.StructuralObservation, ...]
    known_subject_ids: tuple[m.SubjectId, ...]


def _structural_context(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> _StructuralContext:
    """Load bounded edges and locations as observations for the task."""
    sid = subject.subject_id
    edges = structural.edges(repository_id, sid, (), StructuralDirection.BOTH, bounds)
    observations = [
        m.StructuralObservation(
            source_subject=edge.source,
            edge_kind=edge.kind,
            target_subject=edge.target,
            location=None,
            repository_state=state,
        )
        for edge in edges.items
    ]
    locations = structural.locations(repository_id, sid, bounds).items
    observations.extend(
        m.StructuralObservation(
            source_subject=sid,
            edge_kind=None,
            target_subject=None,
            location=loc.location,
            repository_state=state,
        )
        for loc in locations
    )
    known_subject_ids = (
        (sid,)
        + tuple(
            observation.target_subject
            for observation in observations
            if observation.target_subject is not None
        )
        + tuple(observation.source_subject for observation in observations)
    )
    return _StructuralContext(
        observations=tuple(observations),
        known_subject_ids=known_subject_ids,
    )


def _unique_bodies(
    units: tuple[m.EvidenceUnit, ...],
) -> tuple[tuple[m.EvidenceUnit, ...], tuple[str, ...]]:
    """Keep the first unit for each evidence body.

    One body can be selected under different evidence identities (a host-cited
    ref plus the provider-canonical ref, for example). Delivering it twice
    spends the byte budget twice and shows the agent the same bytes twice, so
    the first occurrence is delivered and every duplicate is named.
    """
    kept: list[m.EvidenceUnit] = []
    first_by_body: dict[tuple[str, str], m.EvidenceRef] = {}
    duplicates: list[str] = []
    for unit in units:
        body = (unit.evidence_ref.locator, unit.content_fingerprint)
        first = first_by_body.get(body)
        if first is None:
            first_by_body[body] = unit.evidence_ref
            kept.append(unit)
            continue
        duplicates.append(
            "evidence body delivered once: "
            f"{unit.evidence_ref.locator} "
            f"({unit.evidence_ref.evidence_id.value}) "
            f"duplicates {first.evidence_id.value}"
        )
    return tuple(kept), tuple(duplicates)


@_dataclass
class _TaskEvidence:
    """Bounded evidence actually delivered for one task."""

    units: tuple[m.EvidenceUnit, ...]
    fingerprints: tuple[tuple[str, str], ...]
    omissions: tuple[str, ...]
    requirements: tuple[m.ResolutionRequirement, ...]
    selected_refs: tuple[m.EvidenceRef, ...]
    discovery_scope: m.EvidenceScope


def _select_task_evidence(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
    question_terms: tuple[str, ...],
    target_scope: m.EvidenceScope,
    required_evidence_refs: tuple[m.EvidenceRef, ...],
) -> _TaskEvidence:
    """Select, read, and project the bounded evidence one task delivers.

    Host anchors are forwarded verbatim; excerpt projection applies after the
    bounded read with omission reporting, and full-source validation stays in
    admission.
    """
    selection = discover_evidence(
        repository_id,
        subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        question_terms=question_terms,
        target_scope=target_scope,
    )
    # All evidence classes share the same bounded read and delivery pass.
    # Mapping and required refs have priority because they are explicit
    # task inputs; ordinary discovery refs fill the remaining bounded set.
    mandatory_refs: list[m.EvidenceRef] = []
    mandatory_ids: set[str] = set()
    for ref in required_evidence_refs:
        if ref.evidence_id.value in mandatory_ids:
            continue
        mandatory_ids.add(ref.evidence_id.value)
        mandatory_refs.append(ref)
    combined_refs: list[m.EvidenceRef] = []
    seen_ref_ids: set[str] = set()
    for ref in (*mandatory_refs, *selection.selected_refs):
        evidence_id = ref.evidence_id.value
        if evidence_id in seen_ref_ids:
            continue
        seen_ref_ids.add(evidence_id)
        combined_refs.append(ref)
    try:
        units = _read_units_within_bytes(evidence, tuple(combined_refs), bounds)
    except ValueError:
        if not mandatory_refs:
            raise
        units = ()
    retained_ids = {unit.evidence_ref.evidence_id.value for unit in units}
    source_bound_requirements = tuple(
        _requirements.missing_evidence(
            subject_or_claim=subject.subject_id,
            description=(
                f"mandatory evidence source read omitted {ref.locator} "
                "before delivery projection because the bounded evidence "
                "unit, byte limit, or source read failure prevented delivery; "
                "narrow the target or cite its canonical EvidenceRef"
            ),
            supporting_context=(ref,),
        )
        for ref in mandatory_refs
        if ref.evidence_id.value not in retained_ids
    )
    units, duplicate_omissions = _unique_bodies(units)
    # S7 §5.7 excerpt projection: service-owned, after bounded read.
    # Full-source identity/fingerprint versus delivered range; omissions
    # in scope_boundaries; byte accounting UTF-8 against delivery ceiling.
    from span.service.bounds import (
        DEFAULT_SERVICE_BOUNDS_POLICY as _default_policy,
    )

    delivery_budget = min(
        _default_policy.max_delivered_evidence_bytes,
        bounds.max_evidence_bytes,
    )
    units, omissions, requirements = _project_excerpts(
        tuple(units), question_terms, subject, delivery_budget
    )
    return _TaskEvidence(
        units=units,
        fingerprints=tuple(
            (unit.evidence_ref.evidence_id.value, unit.content_fingerprint)
            for unit in units
        ),
        omissions=(*duplicate_omissions, *omissions),
        requirements=(*source_bound_requirements, *requirements),
        selected_refs=tuple(unit.evidence_ref for unit in units),
        discovery_scope=selection.discovery_scope,
    )


@_dataclass
class _ResolvedQuestion:
    """The exact admitted question identity one task is built around."""

    question: m.SemanticQuestionScope
    question_class: m.SemanticQuestionClass
    question_slice: str
    scope_root: m.SubjectId


def _resolve_question(
    subject: m.Subject,
    *,
    operation_intent: m.SemanticIntent,
    question_class: m.SemanticQuestionClass | None,
    question_slice: str,
    materiality_basis: str,
    establish_baseline: bool,
    scope_root: m.SubjectId | None,
) -> _ResolvedQuestion:
    """Resolve the bounded question scope the host asked for."""
    resolved_class = question_class or _question_class_for_intent(
        operation_intent, establish_baseline
    )
    # J-3/S3.2: never use a subject locator as the question slice. When the
    # host supplied no selection, use the canonical operation/CQ default.
    resolved_slice = question_slice or m.QUESTION_CLASS_DEFAULT_SLICE[resolved_class]
    if establish_baseline and not question_slice:
        resolved_slice = (
            "Establish the selected root's purpose, principal participants, "
            "and material CQ-01–CQ-09 questions for this bounded scope."
        )
    root = scope_root or subject.subject_id
    question = m.SemanticQuestionScope(
        scope_root=root,
        subject=subject.subject_id,
        question_class=resolved_class,
        question_slice=resolved_slice,
        materiality_basis=(
            materiality_basis
            or (
                "user-requested bounded baseline"
                if establish_baseline
                else f"{operation_intent.value} question-local"
            )
        ),
    )
    return _ResolvedQuestion(
        question=question,
        question_class=resolved_class,
        question_slice=resolved_slice,
        scope_root=root,
    )


@_dataclass
class _PriorContext:
    """Bounded prior canonical items the task attaches."""

    claims: tuple[m.SemanticClaim, ...]
    relationships: tuple[m.SemanticRelationship, ...]


def _load_prior_context(
    repository_id: str,
    subject_id: m.SubjectId,
    *,
    store: SemanticStore | None,
    bounds: m.QueryBounds,
) -> _PriorContext:
    """Load bounded prior claims and relationships for the subject."""
    if store is None:
        return _PriorContext(claims=(), relationships=())
    try:
        claim_page = store.load_claims(repository_id, (subject_id,), (), bounds, None)
        prior_claims = tuple(claim_page.items)[: bounds.max_results]
    except Exception:
        prior_claims = ()
    try:
        from span.ports.structural import StructuralDirection as _Dir

        rel_page = store.load_relationships(
            repository_id, (subject_id,), (), _Dir.BOTH, bounds, None
        )
        prior_relationships = tuple(rel_page.items)[: bounds.max_results]
    except Exception:
        prior_relationships = ()
    return _PriorContext(
        claims=prior_claims,
        relationships=prior_relationships,
    )


def _load_open_requirements(
    repository_id: str,
    *,
    store: SemanticStore | None,
    question: m.SemanticQuestionScope,
    bounds: m.QueryBounds,
) -> list[m.ResolutionRequirement]:
    """Quote recorded OPEN/PENDING requirements for this exact question.

    Slice-instance brief content (F-02): the identity is the admitted question
    (scope root, subject, class, slice) — never inferred. Sibling slices stay
    out: narrow stays narrow. Deterministic order; absent without a store.
    """
    if store is None:
        return []
    try:
        scoped = store.load_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
            bounds,
        )
    except Exception:
        scoped = ()
    open_requirements: list[m.ResolutionRequirement] = []
    for coverage in scoped:
        if coverage.question is None:
            continue
        if coverage.question.scope_root != question.scope_root:
            continue
        if coverage.question.subject != question.subject:
            continue
        if coverage.question.question_class != question.question_class:
            continue
        if coverage.question.question_slice != question.question_slice:
            continue
        if coverage.disposition not in (
            m.SemanticQuestionDisposition.OPEN,
            m.SemanticQuestionDisposition.PENDING,
        ):
            continue
        open_requirements.extend(coverage.resolution_requirements)
    return open_requirements


def prepare_interpretation_task(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
    operation_intent: m.SemanticIntent = m.SemanticIntent.EXPLAIN,
    question_slice: str = "",
    proposed_change: m.ProposedChange | None = None,
    store: SemanticStore | None = None,
    scope_root: m.SubjectId | None = None,
    question_class: m.SemanticQuestionClass | None = None,
    materiality_basis: str = "",
    establish_baseline: bool = False,
    objective: str = "",
    target_scope: m.EvidenceScope = m.EvidenceScope(),
    target_id: m.TargetId | None = None,
    required_evidence_refs: tuple[m.EvidenceRef, ...] = (),
    question_terms: tuple[str, ...] = (),
) -> InterpretationTask:
    """Build the bounded task for the invoking agent (§8.3/§11.12).

    [design note B](docs/design-references.md#b): constructs the immutable question scope, loads bounded
    prior canonical items, and attaches service-owned SA obligations.
    [design note I](docs/design-references.md#i) S4: question_terms are verbatim host anchors forwarded
    into bounded discovery; the service performs no tokenization or
    semantic expansion. [design note I](docs/design-references.md#i) S7: excerpt projection applies after
    bounded read with omission reporting; full-source validation stays
    in admission.
    """
    context = _structural_context(
        repository_id,
        subject,
        structural=structural,
        bounds=bounds,
        state=state,
    )
    task_evidence = _select_task_evidence(
        repository_id,
        subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        question_terms=question_terms,
        target_scope=target_scope,
        required_evidence_refs=required_evidence_refs,
    )
    resolved = _resolve_question(
        subject,
        operation_intent=operation_intent,
        question_class=question_class,
        question_slice=question_slice,
        materiality_basis=materiality_basis,
        establish_baseline=establish_baseline,
        scope_root=scope_root,
    )
    prior = _load_prior_context(
        repository_id,
        subject.subject_id,
        store=store,
        bounds=bounds,
    )
    open_requirements = _load_open_requirements(
        repository_id,
        store=store,
        question=resolved.question,
        bounds=bounds,
    )
    open_requirements.extend(task_evidence.requirements)
    open_requirements.sort(key=lambda requirement: requirement.description)
    request = m.SemanticInterpretationRequest(
        repository_id=repository_id,
        subjects=(subject,),
        task_evidence=m.TaskEvidence(
            evidence_units=task_evidence.units,
            structural_observations=context.observations,
            identity_bindings=(subject.subject_id,),
        ),
        allowed_kinds=m.AllowedKinds(
            claim_kinds=tuple(m.ClaimKind),
            relationship_kinds=tuple(m.RelationshipKind),
        ),
        operation_intent=operation_intent,
        question_slice=resolved.question_slice,
        proposed_change=proposed_change,
        bounds=bounds,
        question=resolved.question,
        prior_context=m.PriorContext(
            claims=prior.claims,
            relationships=prior.relationships,
        ),
        analysis_obligations=m.SA_ANALYSIS_OBLIGATIONS,
        brief=_build_task_brief(
            resolved_slice=resolved.question_slice,
            resolved_class=resolved.question_class,
            root=resolved.scope_root,
            subject=subject,
            selected_refs=task_evidence.selected_refs,
            authority_seeds=authority_seeds,
            open_requirements=tuple(open_requirements),
            target_scope=target_scope,
            objective=objective,
            excerpt_omissions=task_evidence.omissions,
            bound_question=resolved.question,
        ),
        target_scope=target_scope,
        target_id=target_id,
        discovery_scope=task_evidence.discovery_scope,
    )
    if len(request.subjects) > bounds.max_subjects:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_subjects",)
        )
    return InterpretationTask(
        request=request,
        fingerprints=task_evidence.fingerprints,
        known_subject_ids=context.known_subject_ids,
        observations=context.observations,
    )
