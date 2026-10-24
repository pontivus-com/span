"""Span service interpretation exchange (plan §11.12, §8.3; v0.6 §14 Amendment A-01).

Bounded task framing for the invoking agent, strict-ingress validation
context, candidate admission, unit materialization, and suspension.
Span never invokes a model or provider: insufficient semantics suspend
with PendingInterpretation; the agent submits the typed result.
Question evidence is derived per question (Addendum L). Otherwise
verbatim from span.service_operations.
"""

from __future__ import annotations

import dataclasses as _dataclasses
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource
from span.shell.agent_exchange.continuations import (
    ContinuationStore,
    SuspendedOperation,
)
from span.service.discovery import (
    _read_units_within_bytes,
    discover_evidence,
)
from span.service.questions import _question_class_for_intent
from span.service.refs import _item_ref, _ref_value
from span.service.resolution import (
    _load_all_coverages_or_defer,
    _load_subject_state,
)

__all__ = [
    "InterpretationTask",
    "prepare_interpretation_task",
    "_validation_context_for",
    "_assign_candidate_keys",
    "_admit_cited_evidence",
    "_derive_question_evidence",
    "_materialize_unit",
    "_next_baseline_pending",
    "_suspend_baseline_pending",
    "_suspend",
]


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


def _project_excerpts(
    units: tuple[m.EvidenceUnit, ...],
    question_terms: tuple[str, ...],
    subject: m.Subject,
    delivery_budget: int,
    structural_spans: dict[str, tuple[int, int]] | None = None,
) -> tuple[
    tuple[m.EvidenceUnit, ...],
    tuple[str, ...],
    tuple[m.ResolutionRequirement, ...],
]:
    """Bounded excerpt delivery (Addendum I S7 §5.7).

    Keeps canonical envelope and item shapes. Full-source
    identity/fingerprint versus delivered range. Anchors are literal
    substrings matched exactly as discovery does; no tokenization or
    expansion. Exact provider structural spans (1-based inclusive line
    ranges keyed by evidence locator), when supplied, select the
    delivered range directly; no current provider supplies typed spans,
    so the literal-substring path below is the ordinary one. Delivers
    one contiguous enclosing line range for selected hits if it fits;
    else maximal prefix of hits in line order. Reports omissions
    deterministically in scope_boundaries strings with at most
    8 coalesced range lines plus one summary line. Never silently cuts
    prose and labels it complete. Byte accounting is exact UTF-8 bytes
    of delivered content plus the canonical range metadata. With no
    grounded range, retains full fitting unit or reports missing
    bounded evidence via omission lines. A single line that cannot fit
    produces a named evidence-delivery requirement instead of a silent
    cut.
    """
    import dataclasses as _dc
    import json as _json

    def _range_meta(start: int, end: int, total: int) -> int:
        return len(
            _json.dumps(
                m.to_canonical(
                    m.EvidenceLineRange(
                        start_line=start,
                        end_line=end,
                        total_lines=total,
                    )
                ),
                sort_keys=True,
            ).encode("utf-8")
        )

    def _delivery_requirement(
        unit: m.EvidenceUnit, start: int, end: int, total: int
    ) -> m.ResolutionRequirement:
        return m.ResolutionRequirement(
            kind=m.ResolutionKind.MISSING_EVIDENCE,
            subject_or_claim=subject.subject_id,
            description=(
                f"evidence delivery: {unit.evidence_ref.locator} "
                f"lines {start}-{end} of {total} exceed the delivery "
                "budget; inspect the file directly and cite its "
                "canonical EvidenceRef"
            ),
            supporting_context=(unit.evidence_ref,),
        )

    # Default anchors plus verbatim host anchors.
    default_anchors = (
        subject.display_name,
        subject.subject_id.canonical_locator.rsplit("/", 1)[-1],
    )
    anchors = tuple(dict.fromkeys(a for a in (*default_anchors, *question_terms) if a))
    spans = structural_spans or {}
    projected: list[m.EvidenceUnit] = []
    omissions: list[str] = []
    requirements: list[m.ResolutionRequirement] = []
    total_ranges = 0
    total_omitted_hits = 0
    used = 0
    for unit in units:
        content = unit.content
        lines = content.splitlines() or [""]
        total = len(lines)
        span = spans.get(unit.evidence_ref.locator)
        if span is not None:
            start, end = span
            start = max(1, start)
            end = min(total, end)
        else:
            start, end = 0, 0
        if span is None or start > end:
            hits: list[int] = []
            for idx, line in enumerate(lines, start=1):
                for anchor in anchors:
                    if anchor and anchor in line:
                        hits.append(idx)
                        break
        else:
            hits = []
        if span is not None and start <= end:
            # Exact provider structural span: deliver those lines with
            # explicit range metadata, or report omission/requirement.
            if start == 1 and end == total:
                size = len(content.encode("utf-8"))
                if used + size <= delivery_budget:
                    projected.append(unit)
                    used += size
                    continue
            excerpt_text = "\n".join(lines[start - 1 : end])
            if content.endswith("\n") and end == total:
                excerpt_text += "\n"
            size = len(excerpt_text.encode("utf-8")) + _range_meta(start, end, total)
            if used + size <= delivery_budget:
                projected.append(
                    _dc.replace(
                        unit,
                        content=excerpt_text,
                        content_range=m.EvidenceLineRange(
                            start_line=start,
                            end_line=end,
                            total_lines=total,
                        ),
                    )
                )
                used += size
                if start > 1 or end < total:
                    if start > 1:
                        omissions.append(
                            f"excerpt omitted {unit.evidence_ref.locator} "
                            f"lines 1-{start - 1} of {total} "
                            f"(0 hits unexamined)"
                        )
                        total_ranges += 1
                    if end < total:
                        omissions.append(
                            f"excerpt omitted {unit.evidence_ref.locator} "
                            f"lines {end + 1}-{total} of {total} "
                            f"(0 hits unexamined)"
                        )
                        total_ranges += 1
                continue
            first_line = lines[start - 1] + (
                "\n" if content.endswith("\n") and start == end == total else ""
            )
            if (
                start == end
                or used
                + len(first_line.encode("utf-8"))
                + _range_meta(start, start, total)
                > delivery_budget
            ):
                requirements.append(_delivery_requirement(unit, start, end, total))
            omissions.append(
                f"excerpt omitted {unit.evidence_ref.locator} lines "
                f"{start}-{end} of {total} "
                f"({end - start + 1} hits unexamined)"
            )
            total_ranges += 1
            total_omitted_hits += end - start + 1
            continue
        if not hits:
            size = len(content.encode("utf-8"))
            if used + size <= delivery_budget:
                projected.append(unit)
                used += size
            else:
                omissions.append(
                    f"excerpt omitted {unit.evidence_ref.locator} lines "
                    f"1-{total} of {total} (0 hits unexamined)"
                )
                total_ranges += 1
                if total == 1:
                    # A single ungrounded line that cannot fit is still
                    # a named delivery requirement, not silent omission.
                    requirements.append(_delivery_requirement(unit, 1, total, total))
            continue
        first, last = hits[0], hits[-1]
        # Contiguous enclosing range.
        excerpt_lines = lines[first - 1 : last]
        excerpt_text = "\n".join(excerpt_lines)
        # Preserve trailing newline semantics minimally.
        if content.endswith("\n") and last == total:
            excerpt_text += "\n"
        size = len(excerpt_text.encode("utf-8")) + _range_meta(first, last, total)
        if used + size <= delivery_budget:
            projected.append(
                _dc.replace(
                    unit,
                    content=excerpt_text,
                    content_range=m.EvidenceLineRange(
                        start_line=first,
                        end_line=last,
                        total_lines=total,
                    ),
                )
            )
            used += size
            # Report non-delivered outside ranges as omitted when sparse.
            if first > 1 or last < total:
                # Coalesce to at most one range line per unit here; the
                # caller caps total lines at 8.
                if first > 1:
                    omissions.append(
                        f"excerpt omitted {unit.evidence_ref.locator} "
                        f"lines 1-{first - 1} of {total} "
                        f"(0 hits unexamined)"
                    )
                    total_ranges += 1
                if last < total:
                    omissions.append(
                        f"excerpt omitted {unit.evidence_ref.locator} "
                        f"lines {last + 1}-{total} of {total} "
                        f"(0 hits unexamined)"
                    )
                    total_ranges += 1
            continue
        # Maximal prefix of hits in line order that fits.
        kept_last = first
        for h in hits:
            trial = "\n".join(lines[first - 1 : h])
            if content.endswith("\n") and h == total:
                trial += "\n"
            trial_size = len(trial.encode("utf-8")) + _range_meta(first, h, total)
            if used + trial_size <= delivery_budget:
                kept_last = h
            else:
                break
        excerpt_text = "\n".join(lines[first - 1 : kept_last])
        if content.endswith("\n") and kept_last == total:
            excerpt_text += "\n"
        size = len(excerpt_text.encode("utf-8")) + _range_meta(first, kept_last, total)
        if not excerpt_text or used + size > delivery_budget:
            first_line = lines[first - 1] + (
                "\n" if content.endswith("\n") and first == total else ""
            )
            if (
                first == last
                or used
                + len(first_line.encode("utf-8"))
                + _range_meta(first, first, total)
                > delivery_budget
            ):
                requirements.append(_delivery_requirement(unit, first, last, total))
            omissions.append(
                f"excerpt omitted {unit.evidence_ref.locator} lines "
                f"{first}-{last} of {total} "
                f"({len(hits)} hits unexamined)"
            )
            total_ranges += 1
            total_omitted_hits += len(hits)
            continue
        projected.append(
            _dc.replace(
                unit,
                content=excerpt_text,
                content_range=m.EvidenceLineRange(
                    start_line=first,
                    end_line=kept_last,
                    total_lines=total,
                ),
            )
        )
        used += size
        omitted = len([h for h in hits if h > kept_last])
        if omitted or kept_last < last or first > 1 or last < total:
            omissions.append(
                f"excerpt omitted {unit.evidence_ref.locator} lines "
                f"{kept_last + 1}-{last} of {total} "
                f"({omitted} hits unexamined)"
            )
            total_ranges += 1
            total_omitted_hits += omitted
    # Cap at 8 coalesced range lines plus one summary line.
    kept_omissions = omissions[:8]
    truncated = len(omissions) - len(kept_omissions)
    summary = (
        f"excerpt omissions: {total_omitted_hits} hits in "
        f"{total_ranges} ranges"
        + (f", +{truncated} further ranges truncated" if truncated else "")
    )
    if omissions or not projected:
        kept_omissions = (*kept_omissions, summary)
    return tuple(projected), tuple(kept_omissions), tuple(requirements)


def _submission_template(
    bound_question: m.SemanticQuestionScope | None,
) -> str:
    if bound_question is None:
        return ""
    import json as _json

    # Smallest strict-decodable unfinished shape (Addendum M §M-05.1).
    # Every omitted collection is a canonical default; printing empty
    # campaign fields only teaches protocol ceremony.
    example = {
        "question_decision": {
            "disposition": "PENDING",
        },
    }
    return (
        "Minimal submission template (unfinished, PENDING; replace "
        "PENDING with the actual disposition when the examination reaches "
        "one, add claims/relationships only when supported semantic "
        "material exists, and add optional fields only when materially "
        "applicable): " + _json.dumps(example, sort_keys=True)
    )


def _mapping_submission_template(
    target_inventory_items: tuple[m.EvidenceInventoryItem, ...],
) -> str:
    """Valid compact command shape for a target-mapping task.

    Mapping is not a semantic question: no ``question_decision`` is
    shown because the agent is not answering a bound question. The
    template carries exactly one accounting candidate for every bound
    inventory member in deterministic bound order (Addendum M §M-05.2).
    """
    import json as _json

    accounts = [
        {
            "evidence_id": {
                "value": item.evidence_ref.evidence_id.value,
            },
            "resolution_requirements": [
                {
                    "kind": "MISSING_SEMANTIC_COVERAGE",
                    "description": (
                        "map this member to an admitted area, record an "
                        "evidence-backed exclusion, or state the unresolved "
                        "mapping"
                    ),
                }
            ],
        }
        for item in target_inventory_items
    ]
    example = {"proposed_target_inventory_accounting": accounts}
    return (
        "Minimal target-mapping submission template (unfinished; submit "
        "exactly one accounting outcome for every bound member; the "
        "unresolved example is valid but non-progressing): "
        + _json.dumps(example, sort_keys=True)
    )


def _build_task_brief(
    *,
    resolved_slice: str,
    resolved_class: m.SemanticQuestionClass,
    root: m.SubjectId,
    subject: m.Subject,
    selected_refs: tuple[m.EvidenceRef, ...],
    authority_seeds: tuple[m.EvidenceRef, ...],
    open_requirements: tuple[m.ResolutionRequirement, ...],
    target_scope: m.EvidenceScope,
    objective: str = "",
    excerpt_omissions: tuple[str, ...] = (),
    bound_question: m.SemanticQuestionScope | None = None,
) -> m.TaskBrief:
    """Project one admitted task into the uniform quality card."""
    evidence_authority = (
        ("Evidence examined: " + ", ".join(ref.locator for ref in selected_refs))
        if selected_refs
        else "Evidence examined: none recorded; do not assert unsupported facts."
    )
    authority_guidance = (
        (
            "Governing authority references: "
            + ", ".join(ref.locator for ref in authority_seeds)
        )
        if authority_seeds
        else "Governing authority: none recorded; missing authority stays unresolved."
    )
    target_boundaries = tuple(
        [f"target path: {path}" for path in target_scope.paths]
        + [f"target evidence: {ref.locator}" for ref in target_scope.evidence_refs]
    )
    scope_boundaries = (
        target_boundaries
        + (
            f"scope root: {root.canonical_locator}",
            f"structural anchor: {subject.subject_id.canonical_locator}",
        )
        + tuple(excerpt_omissions)
    )
    # S3.4 task-bound submission example: minimal shape populated with
    # bound question and immutable identities, PENDING + missing
    # examination, not a fabricated answer. Agents supply validated
    # candidates and disposition. No parallel template carrier.
    submission_example = _submission_template(bound_question)
    submission_rules = m.TASK_BRIEF_SUBMISSION_RULES + (
        (
            submission_example
            if submission_example
            else "Submit one strict canonical result with an explicit "
            "question disposition."
        ),
    )
    return m.TaskBrief(
        objective=(
            (
                objective.strip() + " — "
                if objective.strip()
                else "Support the admitted engineering question: "
            )
            + resolved_slice
        ),
        material_aspects=m.QUESTION_CLASS_ASPECTS.get(resolved_class, ()),
        scope_boundaries=scope_boundaries,
        evidence_authority=(
            evidence_authority,
            authority_guidance,
            "Distinguish observed behavior from governing intent; "
            "preserve absent or conflicting authority explicitly.",
            "Missing evidence: obtain current EvidenceRefs via locate "
            "(TARGET_MEMBERS, FILE_OUTLINE, or SYMBOL) before "
            "submitting claims.",
        ),
        material_path=m.TASK_BRIEF_MATERIAL_PATH,
        semantic_result=m.TASK_BRIEF_SEMANTIC_RESULT,
        adversarial_checks=m.TASK_BRIEF_ADVERSARIAL_CHECKS,
        readback=m.TASK_BRIEF_READBACK,
        open_requirements=open_requirements,
        open_handling=m.TASK_BRIEF_OPEN_HANDLING,
        submission_rules=submission_rules,
    )


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
    target_inventory_items: tuple[m.EvidenceInventoryItem, ...] = (),
    mapping_mode: bool = False,
    required_evidence_refs: tuple[m.EvidenceRef, ...] = (),
    question_terms: tuple[str, ...] = (),
) -> InterpretationTask:
    """Build the bounded task for the invoking agent (§8.3/§11.12).

    Addendum B: constructs the immutable question scope, loads bounded
    prior canonical items, and attaches service-owned SA obligations.
    Addendum I S4: question_terms are verbatim host anchors forwarded
    into bounded discovery; the service performs no tokenization or
    semantic expansion. Addendum I S7: excerpt projection applies after
    bounded read with omission reporting; full-source validation stays
    in admission.
    """
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
    units = _read_units_within_bytes(evidence, selection.selected_refs, bounds)
    # S7 §5.7 excerpt projection: service-owned, after bounded read.
    # Full-source identity/fingerprint versus delivered range; omissions
    # in scope_boundaries; byte accounting UTF-8 against delivery ceiling.
    from span.service.bounds import (
        DEFAULT_SERVICE_BOUNDS_POLICY as _default_policy,
    )

    _delivery_ceiling = _default_policy.max_delivered_evidence_bytes
    _delivery_budget = min(_delivery_ceiling, bounds.max_evidence_bytes)
    units, _excerpt_omissions, _excerpt_requirements = _project_excerpts(
        tuple(units), question_terms, subject, _delivery_budget
    )
    fingerprints = tuple(
        (unit.evidence_ref.evidence_id.value, unit.content_fingerprint)
        for unit in units
    )
    known_subjects = (
        (sid,)
        + tuple(
            obs.target_subject for obs in observations if obs.target_subject is not None
        )
        + tuple(obs.source_subject for obs in observations)
    )
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
    root = scope_root or sid
    question = m.SemanticQuestionScope(
        scope_root=root,
        subject=sid,
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
    prior_claims: tuple[m.SemanticClaim, ...] = ()
    prior_relationships: tuple[m.SemanticRelationship, ...] = ()
    if store is not None:
        try:
            claim_page = store.load_claims(repository_id, (sid,), (), bounds, None)
            prior_claims = tuple(claim_page.items)[: bounds.max_results]
        except Exception:
            prior_claims = ()
        try:
            from span.ports.structural import StructuralDirection as _Dir

            rel_page = store.load_relationships(
                repository_id, (sid,), (), _Dir.BOTH, bounds, None
            )
            prior_relationships = tuple(rel_page.items)[: bounds.max_results]
        except Exception:
            prior_relationships = ()
    # Slice-instance brief content (F-02): recorded OPEN/PENDING
    # requirements for this EXACT admitted question identity
    # (scope root, subject, class, slice) — quoted from store, never
    # inferred. Sibling slices stay out: narrow stays narrow.
    # Deterministic order; absent without a store.
    open_requirements: list[m.ResolutionRequirement] = []
    if store is not None:
        try:
            scoped = store.load_question_coverages(
                repository_id,
                root,
                (sid,),
                bounds,
            )
        except Exception:
            scoped = ()
        for cov in scoped:
            if cov.question is None:
                continue
            if cov.question.scope_root != root:
                continue
            if cov.question.subject != sid:
                continue
            if cov.question.question_class != resolved_class:
                continue
            if cov.question.question_slice != resolved_slice:
                continue
            if cov.disposition not in (
                m.SemanticQuestionDisposition.OPEN,
                m.SemanticQuestionDisposition.PENDING,
            ):
                continue
            open_requirements.extend(cov.resolution_requirements)
    open_requirements.extend(_excerpt_requirements)
    open_requirements.sort(key=lambda req: req.description)
    units_list = list(units)
    fingerprints_list = list(fingerprints)
    item_unreadable_notes: list[str] = []
    if mapping_mode and target_inventory_items:
        # S5.2: deliver every bound member's canonical EvidenceRef,
        # inserting in batch order; an unreadable member is reported, not
        # dropped — the agent records an unresolved mapping requirement.
        for item in reversed(target_inventory_items):
            item_ref = item.evidence_ref
            if all(
                u.evidence_ref.evidence_id.value != item_ref.evidence_id.value
                for u in units_list
            ):
                try:
                    item_units = evidence.read_evidence((item_ref,), bounds)
                except Exception as exc:
                    item_unreadable_notes.append(
                        f"current inventory item evidence unreadable: "
                        f"{item_ref.locator} ({exc}); record an unresolved "
                        f"mapping requirement, do not skip this item"
                    )
                else:
                    for iu in item_units:
                        units_list.insert(0, iu)
                        fingerprints_list.insert(
                            0,
                            (
                                iu.evidence_ref.evidence_id.value,
                                iu.content_fingerprint,
                            ),
                        )
    if required_evidence_refs:
        present = {u.evidence_ref.evidence_id.value for u in units_list}
        missing = [
            ref
            for ref in required_evidence_refs
            if ref.evidence_id.value not in present
        ]
        if missing:
            try:
                extra_units = evidence.read_evidence(tuple(missing), bounds)
            except Exception as exc:
                raise _validation.InterpretationUnitRejected(
                    (f"required task evidence unreadable: {exc}",)
                )
            for iu in extra_units:
                units_list.append(iu)
                fingerprints_list.append(
                    (iu.evidence_ref.evidence_id.value, iu.content_fingerprint)
                )
    if mapping_mode and target_inventory_items:
        present_ids = {u.evidence_ref.evidence_id.value for u in units_list}
        if any(
            item.evidence_ref.evidence_id.value not in present_ids
            and not any(
                item.evidence_ref.locator in note for note in item_unreadable_notes
            )
            for item in target_inventory_items
        ):
            raise _validation.InterpretationUnitRejected(
                ("mapping item evidence missing from task",)
            )
    if mapping_mode:
        item_locators = (
            ", ".join(item.evidence_ref.locator for item in target_inventory_items)
            or sid.canonical_locator
        )
        mapping_slice = (
            f"Account for inventory member(s) {item_locators} in target: "
            f"assign to admitted area(s), record an evidence-backed "
            f"exclusion, or record an unresolved mapping requirement for "
            f"each."
        )
        mapping_brief = m.TaskBrief(
            objective=((objective.strip() + " — ") if objective.strip() else "")
            + mapping_slice,
            scope_boundaries=tuple(
                [f"target path: {p}" for p in target_scope.paths]
                + [f"target evidence: {r.locator}" for r in target_scope.evidence_refs]
                + [
                    f"current inventory item: {item.evidence_ref.locator}"
                    for item in target_inventory_items
                ]
                + list(item_unreadable_notes)
            ),
            evidence_authority=(
                (
                    (
                        "Evidence examined: "
                        + ", ".join(r.locator for r in selection.selected_refs)
                    )
                    if selection.selected_refs
                    else "Evidence examined: none recorded."
                ),
                "Include the current inventory item's EvidenceRef before supplementary evidence.",
                "Distinguish observed behavior from governing intent.",
            ),
            material_path=m.TASK_BRIEF_MATERIAL_PATH,
            semantic_result=m.TASK_BRIEF_SEMANTIC_RESULT,
            adversarial_checks=m.TASK_BRIEF_ADVERSARIAL_CHECKS,
            readback=m.TASK_BRIEF_READBACK,
            open_requirements=tuple(open_requirements),
            open_handling=m.TASK_BRIEF_OPEN_HANDLING,
            submission_rules=m.TASK_BRIEF_SUBMISSION_RULES
            + (
                "Submit exactly one CandidateTargetInventoryAccount for "
                "every inventory member bound in this mapping task; every "
                "returned bound EvidenceId must appear exactly once. The "
                "unresolved example is valid but non-progressing: replace "
                "it with an evidence-supported assignment or exclusion "
                "whenever the investigation permits progress, and leaving "
                "a member unresolved keeps target completion incomplete. "
                "No completed claim payload is required.",
                "A newly admitted area receives exactly one service-owned "
                "PENDING CQ-01 seed; do not manufacture a target question "
                "for a new area. Use proposed_target_questions only to "
                "reuse existing current coverage whose scope root and "
                "subject are already persisted.",
                "The anchor subject is discovery input, not an admitted "
                "semantic area. If an anchor question is needed, establish "
                "it first through question-local examination (explain), "
                "then reuse it; mapping tasks cannot co-admit non-area "
                "subjects under the orphan rule.",
            )
            + (
                (
                    "The anchor subject is a synthetic structural fallback "
                    "(OTHER kind): it is discovery input only, not an "
                    "admitted semantic area and not an ownership assertion. "
                    "subject: null means the structural index has no "
                    "subject for this member; it does not mean the "
                    "member is unmappable. "
                    "Propose the coherent area via CandidateSubject.",
                )
                if subject.subject_id.subject_kind is m.SubjectKind.OTHER
                else (
                    "The anchor subject is structural input only: assign "
                    "the item to an admitted or newly proposed coherent area, "
                    "never to the anchor itself unless the anchor is that area.",
                )
            )
            + (_mapping_submission_template(target_inventory_items),),
        )
    request = m.SemanticInterpretationRequest(
        repository_id=repository_id,
        subjects=(subject,),
        evidence_units=tuple(units_list),
        structural_observations=tuple(observations),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(sid,),
        operation_intent=operation_intent,
        question_slice=mapping_slice if mapping_mode else resolved_slice,
        proposed_change=proposed_change,
        bounds=bounds,
        question=None if mapping_mode else question,
        prior_claims=prior_claims,
        prior_relationships=prior_relationships,
        analysis_obligations=m.SA_ANALYSIS_OBLIGATIONS,
        brief=(
            mapping_brief
            if mapping_mode
            else _build_task_brief(
                resolved_slice=resolved_slice,
                resolved_class=resolved_class,
                root=root,
                subject=subject,
                selected_refs=selection.selected_refs,
                authority_seeds=authority_seeds,
                open_requirements=tuple(open_requirements),
                target_scope=target_scope,
                objective=objective,
                excerpt_omissions=_excerpt_omissions,
                bound_question=question,
            )
        ),
        target_scope=target_scope,
        target_id=target_id,
        target_inventory_items=target_inventory_items,
        discovery_scope=selection.discovery_scope,
    )
    if len(request.subjects) > bounds.max_subjects:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_subjects",)
        )
    return InterpretationTask(
        request=request,
        fingerprints=tuple(fingerprints_list),
        known_subject_ids=known_subjects,
        observations=tuple(observations),
    )


def _validation_context_for(
    task: InterpretationTask,
    extra_known: tuple[m.SubjectId, ...] = (),
) -> _validation.ValidationContext:
    return _validation.ValidationContext(
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        known_evidence_ids=frozenset(eid for eid, _ in task.fingerprints),
        known_subject_ids=task.known_subject_ids + extra_known,
        evidence_fingerprints=dict(task.fingerprints),
        evidence_contents={
            unit.evidence_ref.evidence_id.value: unit.content
            for unit in task.request.evidence_units
        },
        evidence_refs={
            unit.evidence_ref.evidence_id.value: unit.evidence_ref
            for unit in task.request.evidence_units
        },
    )


def _assign_candidate_keys(
    result: m.SemanticInterpretationResult,
) -> m.SemanticInterpretationResult:
    """Deterministic key assignment (plan §4.11 discipline).

    Explicit keys link conflict proposals; empty keys receive
    deterministic `auto:<index>` values so every result carries unique
    non-empty keys. Explicit duplicates reject the unit.
    """
    keys = [c.candidate_key for c in result.claims] + [
        r.candidate_key for r in result.relationships
    ]
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for index, key in enumerate(keys):
        if not key:
            continue
        if key in seen:
            for dup_index in (seen[key], index):
                member = (
                    f"claims[{dup_index}]"
                    if dup_index < len(result.claims)
                    else f"relationships[{dup_index - len(result.claims)}]"
                )
                duplicates.append(f"{member} (key={key})")
        else:
            seen[key] = index
    if duplicates:
        raise _validation.InterpretationUnitRejected(
            tuple(
                f"{label}: duplicate candidate_key in interpretation result"
                for label in duplicates
            )
        )
    if all(keys):
        return result
    claims = tuple(
        (
            c
            if c.candidate_key
            else m.CandidateSemanticClaim(
                candidate_key=f"auto-{n}",
                subject=c.subject,
                kind=c.kind,
                value=c.value,
                assertion_nature=c.assertion_nature,
                evidence=c.evidence,
                candidate_authority=c.candidate_authority,
                basis=c.basis,
            )
        )
        for n, c in enumerate(result.claims)
    )
    relationships = tuple(
        (
            r
            if r.candidate_key
            else m.CandidateSemanticRelationship(
                candidate_key=f"auto-c{len(result.claims) + n}",
                source=r.source,
                kind=r.kind,
                target=r.target,
                assertion_nature=r.assertion_nature,
                evidence=r.evidence,
                candidate_authority=r.candidate_authority,
                basis=r.basis,
            )
        )
        for n, r in enumerate(result.relationships)
    )
    return m.SemanticInterpretationResult(
        claims=claims,
        relationships=relationships,
        governing_source_refs=result.governing_source_refs,
        diagnostics=result.diagnostics,
        candidate_subjects=result.candidate_subjects,
        candidate_conflicts=result.candidate_conflicts,
        question_decision=result.question_decision,
        proposed_questions=result.proposed_questions,
        candidate_withdrawals=result.candidate_withdrawals,
        proposed_target_inventory_accounting=result.proposed_target_inventory_accounting,
        proposed_target_questions=result.proposed_target_questions,
    )


def _normalize_cited_ref(
    cited: m.EvidenceRef,
    canonical: m.EvidenceRef,
    observed_fingerprint: str,
) -> m.EvidenceRef:
    """Project one agent-supplied ref onto its canonical observation.

    Base identity is already verified equal by the caller. The
    observation fingerprint always comes from the provider; the span
    survives only when it equals the canonical span, else it strips to
    None (file-level citation, location unasserted).
    """
    return m.EvidenceRef(
        evidence_id=cited.evidence_id,
        repository_id=canonical.repository_id,
        source_kind=canonical.source_kind,
        locator=canonical.locator,
        revision_or_fingerprint=observed_fingerprint,
        section_or_span=(
            cited.section_or_span
            if cited.section_or_span == canonical.section_or_span
            else None
        ),
    )


def _admit_cited_evidence(
    repository_id: str,
    result: m.SemanticInterpretationResult,
    ctx: _validation.ValidationContext,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[
    _validation.ValidationContext,
    m.SemanticInterpretationResult,
    list[str],
]:
    """Admit cited evidence against the canonical provider (Addendum H §5).

    Every agent-supplied ``EvidenceRef`` unknown to the task is resolved
    to the provider-canonical identity; base-identity mismatch,
    unknown identity, or unreadable bytes come back as problems — never
    silently admitted. Recorded history never gates admission: a
    fingerprint that differs from recorded observations admits the
    current bytes (old rows keep old fingerprints and go stale through
    existing freshness). Returns the extended context, the normalized
    submission (same carrier; normalized before validation so
    deterministic ids derive from persisted refs), and problems.
    """
    cited_by_id: dict[str, list[m.EvidenceRef]] = {}

    def _note(ref: m.EvidenceRef) -> None:
        cited_by_id.setdefault(ref.evidence_id.value, []).append(ref)

    def _note_nested_basis(basis: m.SemanticBasis) -> None:
        # Basis input refs persist inside claims, relationships, and
        # recorded conflicts: unverifiable nested provenance must not
        # reach canonical state, so nested evidence goes through the
        # same provider admission as primary citations.
        for input_ref in basis.input_refs:
            if isinstance(input_ref, m.EvidenceRef):
                _note(input_ref)

    def _note_nested_requirements(
        requirements: tuple[m.ResolutionRequirement, ...],
    ) -> None:
        # Requirement supporting context persists inside coverages and
        # target accounts: same admission rule as basis input refs.
        for requirement in requirements:
            for context_ref in requirement.supporting_context:
                if isinstance(context_ref, m.EvidenceRef):
                    _note(context_ref)

    def _note_decision(decision: m.SemanticQuestionDecision) -> None:
        # The agent owns only its selected support scope and typed
        # requirements; those are the only command-shaped citations.
        for ref in decision.evidence_scope.evidence_refs:
            _note(ref)
        _note_nested_requirements(decision.resolution_requirements)

    for candidate in (*result.claims, *result.relationships):
        for ref in candidate.evidence:
            _note(ref)
        authority = candidate.candidate_authority
        if authority is not None:
            _note(authority.binding.evidence_ref)
        _note_nested_basis(candidate.basis)
    for proposed in result.candidate_subjects:
        for ref in proposed.evidence:
            _note(ref)
        _note_nested_basis(proposed.basis)
    for withdrawal in result.candidate_withdrawals:
        for ref in withdrawal.evidence:
            _note(ref)
        _note_nested_basis(withdrawal.basis)
    for conflict in result.candidate_conflicts:
        _note_nested_basis(conflict.basis)
        if conflict.candidate_precedence is not None:
            for ref in conflict.candidate_precedence.overrides:
                _note(ref)
    if result.question_decision is not None:
        _note_decision(result.question_decision)
    for proposed in result.proposed_questions:
        _note_decision(proposed.decision)
    for account in result.proposed_target_inventory_accounting:
        if account.exclusion_basis is not None:
            _note_nested_basis(account.exclusion_basis)
        _note_nested_requirements(account.resolution_requirements)
    wanted = sorted(i for i in cited_by_id if i not in ctx.known_evidence_ids)
    fingerprints = dict(ctx.evidence_fingerprints)
    contents = dict(ctx.evidence_contents)
    canonical_refs = dict(ctx.evidence_refs)
    problems: list[str] = []
    if wanted:
        try:
            page = evidence.inventory_evidence(
                repository_id,
                m.EvidenceScope(
                    paths=(),
                    evidence_refs=tuple(
                        ref for eid in wanted for ref in cited_by_id[eid]
                    ),
                ),
                bounds,
            )
        except ValueError as exc:
            return ctx, result, [f"cited evidence inventory unavailable: {exc}"]
        try:
            from span.service.discovery import check_inventory_identity

            items = check_inventory_identity(tuple(page.items))
        except ValueError as exc:
            return ctx, result, [f"cited evidence {exc}"]
        by_id = {item.evidence_ref.evidence_id.value: item for item in items}
        for eid in wanted:
            item = by_id.get(eid)
            if item is None:
                problems.append(f"unknown evidence identity: {eid}")
                continue
            canonical = item.evidence_ref
            occurrences = cited_by_id[eid]
            if any(
                ref.repository_id != repository_id
                or ref.locator != canonical.locator
                or ref.source_kind != canonical.source_kind
                for ref in occurrences
            ):
                problems.append(
                    "cited evidence identity does not match "
                    f"provider snapshot: {eid}"
                )
                continue
            try:
                units = evidence.read_evidence((canonical,), bounds)
            except ValueError:
                problems.append(f"cited evidence is unreadable: {eid}")
                continue
            if len(units) != 1:
                problems.append(f"cited evidence is unreadable: {eid}")
                continue
            (unit,) = units
            fingerprints[eid] = unit.content_fingerprint
            contents[eid] = unit.content
            canonical_refs[eid] = m.EvidenceRef(
                evidence_id=canonical.evidence_id,
                repository_id=canonical.repository_id,
                source_kind=canonical.source_kind,
                locator=canonical.locator,
                revision_or_fingerprint=unit.content_fingerprint,
                section_or_span=canonical.section_or_span,
            )
    known = ctx.known_evidence_ids | frozenset(fingerprints)

    def _normalize(ref: m.EvidenceRef) -> m.EvidenceRef:
        canonical = canonical_refs.get(ref.evidence_id.value)
        if canonical is None:
            return ref
        return _normalize_cited_ref(ref, canonical, fingerprints[ref.evidence_id.value])

    def _normalize_basis(basis: m.SemanticBasis) -> m.SemanticBasis:
        return _dataclasses.replace(
            basis,
            input_refs=tuple(
                (
                    _normalize(input_ref)
                    if isinstance(input_ref, m.EvidenceRef)
                    else input_ref
                )
                for input_ref in basis.input_refs
            ),
        )

    def _normalize_requirement(
        requirement: m.ResolutionRequirement,
    ) -> m.ResolutionRequirement:
        return _dataclasses.replace(
            requirement,
            supporting_context=tuple(
                (
                    _normalize(context_ref)
                    if isinstance(context_ref, m.EvidenceRef)
                    else context_ref
                )
                for context_ref in requirement.supporting_context
            ),
        )

    def _normalize_precedence(
        precedence: m.DeclaredPrecedence | None,
    ) -> m.DeclaredPrecedence | None:
        if precedence is None:
            return None
        return _dataclasses.replace(
            precedence,
            overrides=tuple(_normalize(ref) for ref in precedence.overrides),
        )

    def _normalize_authority(
        authority: m.CandidateAuthority | None,
    ) -> m.CandidateAuthority | None:
        if authority is None:
            return None
        return _dataclasses.replace(
            authority,
            binding=_dataclasses.replace(
                authority.binding,
                evidence_ref=_normalize(authority.binding.evidence_ref),
            ),
        )

    claims = tuple(
        _dataclasses.replace(
            candidate,
            evidence=tuple(_normalize(ref) for ref in candidate.evidence),
            candidate_authority=_normalize_authority(candidate.candidate_authority),
            basis=_normalize_basis(candidate.basis),
        )
        for candidate in result.claims
    )
    relationships = tuple(
        _dataclasses.replace(
            candidate,
            evidence=tuple(_normalize(ref) for ref in candidate.evidence),
            candidate_authority=_normalize_authority(candidate.candidate_authority),
            basis=_normalize_basis(candidate.basis),
        )
        for candidate in result.relationships
    )
    subjects = tuple(
        _dataclasses.replace(
            proposed,
            evidence=tuple(_normalize(ref) for ref in proposed.evidence),
            basis=_normalize_basis(proposed.basis),
        )
        for proposed in result.candidate_subjects
    )
    conflicts = tuple(
        _dataclasses.replace(
            conflict,
            candidate_precedence=_normalize_precedence(conflict.candidate_precedence),
            basis=_normalize_basis(conflict.basis),
        )
        for conflict in result.candidate_conflicts
    )
    withdrawals = tuple(
        _dataclasses.replace(
            withdrawal,
            evidence=tuple(_normalize(ref) for ref in withdrawal.evidence),
            basis=_normalize_basis(withdrawal.basis),
        )
        for withdrawal in result.candidate_withdrawals
    )

    def _normalize_decision(
        decision: m.SemanticQuestionDecision,
    ) -> m.SemanticQuestionDecision:
        return _dataclasses.replace(
            decision,
            evidence_scope=_dataclasses.replace(
                decision.evidence_scope,
                evidence_refs=tuple(
                    _normalize(ref) if ref.evidence_id.value in canonical_refs else ref
                    for ref in decision.evidence_scope.evidence_refs
                ),
            ),
            resolution_requirements=tuple(
                _normalize_requirement(requirement)
                for requirement in decision.resolution_requirements
            ),
        )

    accounts = tuple(
        _dataclasses.replace(
            account,
            exclusion_basis=(
                None
                if account.exclusion_basis is None
                else _dataclasses.replace(
                    account.exclusion_basis,
                    input_refs=tuple(
                        (
                            _normalize(input_ref)
                            if isinstance(input_ref, m.EvidenceRef)
                            else input_ref
                        )
                        for input_ref in account.exclusion_basis.input_refs
                    ),
                )
            ),
            resolution_requirements=tuple(
                _normalize_requirement(requirement)
                for requirement in account.resolution_requirements
            ),
        )
        for account in result.proposed_target_inventory_accounting
    )
    normalized = m.SemanticInterpretationResult(
        claims=claims,
        relationships=relationships,
        governing_source_refs=tuple(
            _normalize(ref) if ref.evidence_id.value in canonical_refs else ref
            for ref in result.governing_source_refs
        ),
        diagnostics=result.diagnostics,
        candidate_subjects=subjects,
        candidate_conflicts=conflicts,
        question_decision=(
            None
            if result.question_decision is None
            else _normalize_decision(result.question_decision)
        ),
        proposed_questions=tuple(
            _dataclasses.replace(
                proposed,
                decision=_normalize_decision(proposed.decision),
            )
            for proposed in result.proposed_questions
        ),
        candidate_withdrawals=withdrawals,
        proposed_target_inventory_accounting=accounts,
        proposed_target_questions=result.proposed_target_questions,
    )
    return (
        _validation.ValidationContext(
            allowed_claim_kinds=ctx.allowed_claim_kinds,
            allowed_relationship_kinds=ctx.allowed_relationship_kinds,
            known_evidence_ids=known,
            known_subject_ids=ctx.known_subject_ids,
            evidence_fingerprints=fingerprints,
            evidence_contents=contents,
            evidence_refs=canonical_refs,
        ),
        normalized,
        problems,
    )


def _material_result_refs(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
    return tuple(m.ClaimRef(id=c.claim_id) for c in claims) + tuple(
        m.RelationshipRef(id=r.relationship_id) for r in relationships
    )


def _material_evidence_refs(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.EvidenceRef, ...]:
    """Evidence actually cited by this unit's materialized result."""
    refs: list[m.EvidenceRef] = []
    for item in (*claims, *relationships):
        refs.extend(item.evidence)
        if item.authority is not None:
            refs.append(item.authority.evidence_ref)
    return tuple(refs)


def _load_prior_question_coverage(
    repository_id: str,
    question: m.SemanticQuestionScope,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.InterpretationCoverage | None:
    """Load the exact persisted row for one canonical question identity."""
    try:
        rows = store.load_all_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
        )
    except Exception:
        try:
            rows = store.load_question_coverages(
                repository_id,
                question.scope_root,
                (question.subject,),
                bounds,
            )
        except Exception:
            rows = ()
    for row in rows:
        if row.question is not None and row.question == question:
            return row
    return None


def _ordered_result_refs(
    prior: tuple[m.ClaimRef | m.RelationshipRef, ...],
    new: tuple[m.ClaimRef | m.RelationshipRef, ...],
    withdrawn: frozenset[str],
) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
    """Stable prior-then-new union, minus explicitly withdrawn ids."""
    seen: set[str] = set()
    ordered: list[m.ClaimRef | m.RelationshipRef] = []
    for ref in (*prior, *new):
        rid = ref.id.value
        if rid in withdrawn or rid in seen:
            continue
        seen.add(rid)
        ordered.append(ref)
    return tuple(ordered)


def _derive_question_evidence(
    decision: m.SemanticQuestionDecision,
    *,
    canonical_refs: dict[str, m.EvidenceRef],
    fingerprints: dict[str, str],
    material_evidence: tuple[m.EvidenceRef, ...] = (),
    prior_evidence: tuple[m.QuestionEvidenceObservation, ...] = (),
) -> tuple[m.QuestionEvidenceObservation, ...]:
    """Derive one question's exact direct support.

    Only the agent's selected ``evidence_scope`` and (for ANSWERED/OPEN)
    evidence actually cited by this unit's materialized results are used.
    PENDING/OPEN retain prior direct support; NOT_APPLICABLE never
    manufactures direct evidence from task delivery.
    """
    disposition = decision.disposition
    selected = decision.evidence_scope.evidence_refs
    if disposition is m.SemanticQuestionDisposition.ANSWERED:
        ordered_refs = tuple(material_evidence) + tuple(selected)
        prior: tuple[m.QuestionEvidenceObservation, ...] = ()
    elif disposition is m.SemanticQuestionDisposition.OPEN:
        ordered_refs = tuple(selected) + tuple(material_evidence)
        prior = prior_evidence
    elif disposition is m.SemanticQuestionDisposition.PENDING:
        ordered_refs = tuple(selected)
        prior = prior_evidence
    else:  # NOT_APPLICABLE
        ordered_refs = tuple(selected)
        prior = ()

    seen: set[str] = set()
    observations: list[m.QuestionEvidenceObservation] = []

    def _add_ref(ref: m.EvidenceRef) -> None:
        eid = ref.evidence_id.value
        canonical = canonical_refs.get(eid)
        fingerprint = fingerprints.get(eid)
        if canonical is None or fingerprint is None or eid in seen:
            return
        seen.add(eid)
        observations.append(
            m.QuestionEvidenceObservation(
                evidence_ref=canonical,
                observed_fingerprint=fingerprint,
            )
        )

    def _add_prior(observation: m.QuestionEvidenceObservation) -> None:
        eid = observation.evidence_ref.evidence_id.value
        if eid in seen:
            return
        seen.add(eid)
        canonical = canonical_refs.get(eid)
        fingerprint = fingerprints.get(eid)
        if canonical is not None and fingerprint is not None:
            observations.append(
                m.QuestionEvidenceObservation(
                    evidence_ref=canonical,
                    observed_fingerprint=fingerprint,
                )
            )
        else:
            observations.append(observation)

    for ref in ordered_refs:
        _add_ref(ref)
    for observation in prior:
        _add_prior(observation)
    return tuple(observations)


def _decision_coverage(
    question: m.SemanticQuestionScope,
    decision: m.SemanticQuestionDecision,
    *,
    subjects: tuple[m.SubjectId, ...],
) -> m.InterpretationCoverage:
    """Project one agent decision into the canonical coverage record.

    Only the agent-owned decision crosses the boundary: disposition,
    selected support scope, typed requirements, and basis. Identity,
    slice, completion, result refs, and evidence observations are
    Span-owned and filled by the materializer (Addendum L).
    """
    return m.InterpretationCoverage(
        subjects=subjects,
        question_slice=question.question_slice,
        evidence_scope=decision.evidence_scope,
        declared_complete=(
            decision.disposition is m.SemanticQuestionDisposition.ANSWERED
        ),
        question=question,
        disposition=decision.disposition,
        result_refs=(),
        resolution_requirements=decision.resolution_requirements,
        disposition_basis=decision.disposition_basis,
        question_evidence=(),
    )


def _retire_replaced_outputs(
    repository_id: str,
    question: m.SemanticQuestionScope,
    new_refs: set[str],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    retires_claims: list[m.ClaimRef],
    retires_relationships: list[m.RelationshipRef],
) -> None:
    """Retire prior unshared outputs replaced by a complete ANSWERED
    rewrite (Addendum C C-05).

    PENDING/OPEN/NOT_APPLICABLE never authorize omission-based
    retirement; explicit withdrawals retire through the validated
    path. Shared outputs are preserved (their other owners reopen via
    withdrawal fanout); enumeration overflow defers via
    ``_load_all_coverages_or_defer`` instead of retiring blind.
    """
    try:
        prior_qcovs = store.load_all_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
        )
    except Exception:
        try:
            prior_qcovs = store.load_question_coverages(
                repository_id,
                question.scope_root,
                (question.subject,),
                bounds,
            )
        except Exception:
            prior_qcovs = ()
    old_refs: set[str] = set()
    for qc in prior_qcovs:
        if qc.question == question:
            old_refs.update(r.id.value for r in qc.result_refs)
    for oid in old_refs - new_refs:
        # Shared-output check across ALL questions (unbounded: a
        # bounded read could hide an owner and cause an unsafe
        # retirement). Deferral propagates: never retire with an
        # incomplete owner set.
        all_qcovs = _load_all_coverages_or_defer(
            repository_id,
            None,
            (),
            store=store,
            bounds=bounds,
            purpose="shared-output retirement check",
        )
        shared = False
        for other in all_qcovs:
            if other.question == question:
                continue
            if oid in {r.id.value for r in other.result_refs}:
                shared = True
                break
        if shared:
            continue
        # Unshared: retire.
        try:
            (old_item,) = store.load_by_refs(
                repository_id,
                (m.ClaimRef(id=m.ClaimId(oid)),),
            )
            if isinstance(old_item, m.SemanticClaim):
                retires_claims.append(m.ClaimRef(id=m.ClaimId(oid)))
            else:
                retires_relationships.append(
                    m.RelationshipRef(id=m.RelationshipId(oid))
                )
        except Exception:
            try:
                store.load_by_refs(
                    repository_id,
                    (m.RelationshipRef(id=m.RelationshipId(oid)),),
                )
                retires_relationships.append(
                    m.RelationshipRef(id=m.RelationshipId(oid))
                )
            except Exception:
                continue


def _materialize_unit(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    state: m.RepositoryState,
    extra_known_subjects: tuple[m.SubjectId, ...] = (),
    coverage: m.CoverageDependency,
    declared_complete: bool,
    retire_scope: tuple[m.SubjectId, ...],
    target_id: m.TargetId | None = None,
    target_inventory_items: tuple[m.EvidenceInventoryItem, ...] = (),
    target_association: m.TargetAssociation | None = None,
    current_inventory_ids: frozenset[str] = frozenset(),
    current_inventory_snapshot: dict[str, m.EvidenceRef] | None = None,
    correction_question: m.SemanticQuestionScope | None = None,
) -> None:
    """Validate and atomically materialize one submitted unit (§7.5, I-37).

    Addendum B: exact-question completion/retirement with shared-output
    safety, unassigned-output preservation, explicit withdrawals and
    entire-unit atomicity. Subject-wide omission is truncation, never
    withdrawal, for question-scoped writes.

    Addendum H §6: when ``correction_question`` names the one nominated
    already-persisted original question of a fallback refresh unit, its
    explicit ANSWERED coverage derives/retires exactly like the bound
    question; otherwise non-bound coverages persist as submitted. The
    fallback bound question itself — which has no persisted row — is
    orchestration scaffolding only: it neither synthesizes nor persists
    its own coverage, so a successful correction leaves no synthetic
    pending question behind.
    """
    if len(result.claims) > task.request.bounds.max_candidate_claims:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_claims",)
        )
    if len(result.relationships) > task.request.bounds.max_candidate_relationships:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_relationships",)
        )
    result = _assign_candidate_keys(result)
    ctx = _validation_context_for(task, extra_known_subjects)
    # S7 §5.7 full-source validation: excerpt-bearing task units must
    # load canonical full units before quote or content validation, even
    # when the ID is already in task fingerprints. Reuses per-submission
    # map to avoid duplicate reads. Fingerprints stay complete source.
    # A full unit that cannot be loaded is an actionable rejection with
    # a live continuation; an excerpt never substitutes for it.
    _full_contents = dict(ctx.evidence_contents)
    _full_refs = dict(ctx.evidence_refs)
    _reload_failures: list[str] = []
    for _unit in task.request.evidence_units:
        if _unit.content_range is None:
            continue
        _eid = _unit.evidence_ref.evidence_id.value
        _canonical_ref = _full_refs.get(_eid, _unit.evidence_ref)
        try:
            _full_units = evidence.read_evidence((_canonical_ref,), task.request.bounds)
        except ValueError as exc:
            _reload_failures.append(
                f"excerpt full-source reload failed for {_eid}: {exc}; "
                "re-check the source range and resubmit under the same "
                "continuation"
            )
            continue
        if len(_full_units) != 1:
            _reload_failures.append(
                f"excerpt full-source reload failed for {_eid}: "
                "unreadable; re-check the source range and resubmit "
                "under the same continuation"
            )
            continue
        _full_contents[_eid] = _full_units[0].content
    if _reload_failures:
        raise _validation.InterpretationUnitRejected(tuple(_reload_failures))
    ctx = _validation.ValidationContext(
        allowed_claim_kinds=ctx.allowed_claim_kinds,
        allowed_relationship_kinds=ctx.allowed_relationship_kinds,
        known_evidence_ids=ctx.known_evidence_ids,
        known_subject_ids=ctx.known_subject_ids,
        evidence_fingerprints=dict(ctx.evidence_fingerprints),
        evidence_contents=_full_contents,
        evidence_refs=_full_refs,
    )
    ctx, result, evidence_problems = _admit_cited_evidence(
        task.request.repository_id,
        result,
        ctx,
        evidence=evidence,
        bounds=task.request.bounds,
    )
    failures: list[str] = []
    failures.extend(evidence_problems)
    new_subjects: list[m.Subject] = []
    new_subject_ids: list[m.SubjectId] = []
    for index, proposed in enumerate(result.candidate_subjects):
        validation = _validation.validate_candidate_subject(proposed, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "candidate_subjects",
                    index,
                    proposed.provisional_locator or None,
                    validation.diagnostics,
                )
            )
            continue
        sid = m.SubjectId(
            repository_id=task.request.repository_id,
            subject_kind=proposed.kind,
            canonical_locator=proposed.provisional_locator,
        )
        existing = store.load_subjects(task.request.repository_id, (sid,))
        if existing:
            new_subjects.append(existing[0])
        else:
            new_subjects.append(
                m.Subject(
                    subject_id=sid,
                    display_name=proposed.display_name,
                    declared_kind=proposed.declared_kind,
                )
            )
        new_subject_ids.append(sid)
    if new_subject_ids:
        ctx = _validation.ValidationContext(
            allowed_claim_kinds=ctx.allowed_claim_kinds,
            allowed_relationship_kinds=ctx.allowed_relationship_kinds,
            known_evidence_ids=ctx.known_evidence_ids,
            known_subject_ids=(ctx.known_subject_ids + tuple(new_subject_ids)),
            evidence_fingerprints=ctx.evidence_fingerprints,
            evidence_contents=ctx.evidence_contents,
            evidence_refs=ctx.evidence_refs,
        )
    claims: list[m.SemanticClaim] = []
    for index, candidate in enumerate(result.claims):
        validation = _validation.validate_candidate_claim(candidate, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "claims",
                    index,
                    candidate.candidate_key or None,
                    validation.diagnostics,
                )
            )
            continue
        claims.append(_validation.materialize_claim(candidate, validation, state))
    relationships: list[m.SemanticRelationship] = []
    for index, candidate in enumerate(result.relationships):
        validation = _validation.validate_candidate_relationship(candidate, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "relationships",
                    index,
                    candidate.candidate_key or None,
                    validation.diagnostics,
                )
            )
            continue
        relationships.append(
            _validation.materialize_relationship(candidate, validation, state)
        )
    # B-03: duplicate substantive candidates fail; reordering is stable.
    seen_ids: set[str] = set()
    for item in (*claims, *relationships):
        iid = (
            item.claim_id.value
            if isinstance(item, m.SemanticClaim)
            else item.relationship_id.value
        )
        if iid in seen_ids:
            failures.append(f"duplicate substantive candidate: {iid}")
        seen_ids.add(iid)
    # B-05: premise refs must resolve to active same-repo items; stale
    # premises cannot support newly current conclusions; no self-refs/cycles.
    try:
        active_items = {
            _ref_value(r): r
            for r in (
                tuple(m.ClaimRef(id=c.claim_id) for c in claims)
                + tuple(m.RelationshipRef(id=r.relationship_id) for r in relationships)
            )
        }
        for item in (*claims, *relationships):
            for pref in item.basis.input_refs:
                if not isinstance(pref, (m.ClaimRef, m.RelationshipRef)):
                    continue
                pid = pref.id.value
                if pid in active_items and pid == (
                    item.claim_id.value
                    if isinstance(item, m.SemanticClaim)
                    else item.relationship_id.value
                ):
                    failures.append("semantic premise self-dependency")
                    continue
                if pid in seen_ids:
                    # Within-unit cycle: new items referencing each other.
                    failures.append(f"semantic premise cycle within unit: {pid}")
                    continue
                try:
                    (prior,) = store.load_by_refs(task.request.repository_id, (pref,))
                except ValueError:
                    failures.append(f"semantic premise does not resolve: {pid}")
                    continue
                if prior.freshness.state is not m.FreshnessState.CURRENT:
                    failures.append(
                        f"stale premise cannot support current conclusion: {pid}"
                    )
    except Exception as exc:
        # Port-conformance failure fails the unit closed: validation
        # never proceeds on unverified premises.
        failures.append(f"premise validation unavailable: {exc}")
    keys_in_result = frozenset(
        [c.candidate_key for c in result.claims]
        + [r.candidate_key for r in result.relationships]
    )
    key_to_ref: dict[str, m.ClaimRef | m.RelationshipRef] = {}
    for candidate, item in zip(result.claims, claims):
        key_to_ref[candidate.candidate_key] = m.ClaimRef(id=item.claim_id)
    for candidate, item in zip(result.relationships, relationships):
        key_to_ref[candidate.candidate_key] = m.RelationshipRef(id=item.relationship_id)
    recorded: list[m.RecordedConflict] = []
    for index, proposed in enumerate(result.candidate_conflicts):
        validation = _validation.validate_candidate_conflict(
            proposed, keys_in_result, ctx
        )
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "conflicts",
                    index,
                    f"{proposed.left_key}/{proposed.right_key}",
                    validation.diagnostics,
                )
            )
            continue
        left = key_to_ref[proposed.left_key]
        right = key_to_ref[proposed.right_key]
        left_item = next(
            item for item in (*claims, *relationships) if _item_ref(item) == left
        )
        recorded.append(
            m.RecordedConflict(
                subject=(
                    left_item.subject
                    if isinstance(left_item, m.SemanticClaim)
                    else left_item.source
                ),
                left=left,
                right=right,
                declared_precedence=proposed.candidate_precedence,
                basis=proposed.basis,
            )
        )
    if failures:
        raise _validation.InterpretationUnitRejected(tuple(failures))
    # ctx fingerprints include addendum-A/F2 admitted established
    # evidence alongside task fingerprints.
    fingerprints = dict(ctx.evidence_fingerprints)
    is_mapping_write = task.request.question is None and bool(
        task.request.target_inventory_items
    )
    if is_mapping_write:
        # Mapping anchors are discovery inputs, never semantic areas:
        # only newly admitted area subjects persist from mapping units.
        subjects = tuple(new_subjects)
    else:
        subjects = tuple(task.request.subjects) + tuple(new_subjects)
    known_ids = {c.claim_id.value for c in claims} | {
        r.relationship_id.value for r in relationships
    }
    # Explicit withdrawals (B-03): validated, source-grounded, never omission.
    all_result_ids = frozenset(known_ids)
    try:
        prior_refs_for_withdrawal: set[str] = set()
        if task.request.question is not None:
            bq = task.request.question
            try:
                existing_qcovs = store.load_all_question_coverages(
                    task.request.repository_id,
                    bq.scope_root,
                    (bq.subject,),
                )
            except Exception:
                try:
                    existing_qcovs = store.load_question_coverages(
                        task.request.repository_id,
                        bq.scope_root,
                        (bq.subject,),
                        task.request.bounds,
                    )
                except Exception:
                    existing_qcovs = ()
            for qc in existing_qcovs:
                if qc.question is None:
                    continue
                q = qc.question
                if (
                    q.scope_root == bq.scope_root
                    and q.subject == bq.subject
                    and q.question_class == bq.question_class
                    and q.question_slice == bq.question_slice
                ):
                    prior_refs_for_withdrawal.update(r.id.value for r in qc.result_refs)
        else:
            for sid in retire_scope:
                try:
                    lc, lr, _, _ = _load_subject_state(
                        task.request.repository_id,
                        sid,
                        store=store,
                        bounds=task.request.bounds,
                    )
                except Exception:
                    continue
                prior_refs_for_withdrawal.update(c.claim_id.value for c in lc)
                prior_refs_for_withdrawal.update(r.relationship_id.value for r in lr)
    except Exception:
        prior_refs_for_withdrawal = set()
    if correction_question is not None:
        # Addendum H §6: the one nominated original question contributes
        # its prior outputs to withdrawal scope alongside the bound
        # question. New-unit ids are already in all_result_ids.
        try:
            nominated_qcovs = store.load_all_question_coverages(
                task.request.repository_id,
                correction_question.scope_root,
                (correction_question.subject,),
            )
        except Exception:
            nominated_qcovs = ()
        for qc in nominated_qcovs:
            if qc.question is None:
                continue
            if qc.question == correction_question:
                prior_refs_for_withdrawal.update(r.id.value for r in qc.result_refs)
    known_for_withdrawal = frozenset(all_result_ids | prior_refs_for_withdrawal)
    validated_withdrawals: list[m.CandidateSemanticWithdrawal] = []
    for index, withdrawal in enumerate(result.candidate_withdrawals):
        withdrawal_key = withdrawal.target.id.value
        problem = _validation.validate_candidate_withdrawal(
            withdrawal,
            ctx,
            known_for_withdrawal,
            "withdrawal",
        )
        if problem is not None:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "withdrawals",
                        index,
                        withdrawal_key,
                        (problem,),
                    )
                )
            )
        # Must name active item in bound question or shared-output set.
        # Local name is withdrawal-scoped: it must not shadow the
        # target-campaign `target_id` parameter used below.
        withdrawal_target_id = withdrawal.target.id.value
        try:
            store.load_by_refs(task.request.repository_id, (withdrawal.target,))
        except ValueError:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "withdrawals",
                        index,
                        withdrawal_target_id,
                        (f"withdrawal target unknown: " f"{withdrawal_target_id}",),
                    )
                )
            )
        validated_withdrawals.append(withdrawal)
    retires_claims: list[m.ClaimRef] = []
    retires_relationships: list[m.RelationshipRef] = []
    for withdrawal in validated_withdrawals:
        if isinstance(withdrawal.target, m.ClaimRef):
            retires_claims.append(withdrawal.target)
        else:
            retires_relationships.append(withdrawal.target)
    # Question-scoped retirement: only exact bound question outputs retire,
    # and only when unshared. A bound question with no submitted coverages
    # synthesizes its own current-question coverage below so that every
    # materialization leaves durable question state (no silent unassessed
    # writes); PENDING-only synthesis claims no completion. Addendum H §6
    # exception: in a correction-fallback unit (correction_question names
    # the one nominated original question while the bound question has no
    # persisted row and is therefore orchestration scaffolding), the
    # fallback bound question neither synthesizes nor persists its own
    # coverage — only the nominated original question persists.
    bound_question = task.request.question
    if bound_question is None and result.question_decision is not None:
        raise _validation.InterpretationUnitRejected(
            (
                "question_decision requires a bound question; mapping "
                "tasks submit additional questions through "
                "proposed_questions",
            )
        )
    if bound_question is not None:
        for index, proposed in enumerate(result.proposed_questions):
            if proposed.question == bound_question:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "proposed_questions",
                            index,
                            bound_question.question_slice or None,
                            (
                                "the already-bound question must be answered "
                                "through question_decision; "
                                "proposed_questions is only for additional "
                                "questions or the explicit refresh-correction "
                                "nomination case",
                            ),
                        )
                    )
                )
    for index, proposed in enumerate(result.proposed_questions):
        if (
            proposed.decision.disposition is m.SemanticQuestionDisposition.ANSWERED
            and proposed.question != correction_question
        ):
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "proposed_questions",
                        index,
                        proposed.question.question_slice or None,
                        (
                            "additional questions may be introduced as "
                            "PENDING, OPEN, or NOT_APPLICABLE; only the "
                            "currently bound question may be newly ANSWERED "
                            "in this interpretation unit",
                        ),
                    )
                )
            )
    bound_is_fallback_scaffolding = False
    if correction_question is not None and bound_question is not None:
        try:
            bound_existing = store.load_all_question_coverages(
                task.request.repository_id,
                bound_question.scope_root,
                (bound_question.subject,),
            )
        except Exception:
            bound_existing = ()
        bound_is_fallback_scaffolding = not any(
            cov.question is not None and cov.question == bound_question
            for cov in bound_existing
        )
    question_coverages_to_persist: list[m.InterpretationCoverage] = []
    reopened_coverages: list[m.InterpretationCoverage] = []
    # Span derives the canonical persisted coverage from the compact
    # command. Identity, subjects, slice, completion, result refs, and
    # question evidence are never agent-supplied (Addendum L).
    submitted_coverages: list[m.InterpretationCoverage] = []
    if (
        bound_question is not None
        and not bound_is_fallback_scaffolding
        and result.question_decision is not None
    ):
        submitted_coverages.append(
            _decision_coverage(
                bound_question,
                result.question_decision,
                subjects=tuple(s.subject_id for s in subjects),
            )
        )
    for proposed in result.proposed_questions:
        submitted_coverages.append(
            _decision_coverage(
                proposed.question,
                proposed.decision,
                subjects=(proposed.question.subject,),
            )
        )
    if bound_question is not None or submitted_coverages:
        # Validate submitted coverages; derive refs/evidence from validated
        # candidates and expressly selected support refs.
        seen_qidentities: set[tuple[str, ...]] = set()
        for qindex, submitted in enumerate(submitted_coverages):
            if submitted.question is None:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "question_coverages",
                            qindex,
                            None,
                            ("question coverage without question scope",),
                        )
                    )
                )
            q = submitted.question
            ident = (
                q.scope_root.repository_id,
                q.scope_root.canonical_locator,
                q.scope_root.subject_kind.value,
                q.subject.canonical_locator,
                q.subject.subject_kind.value,
                q.question_class.value,
                q.question_slice,
            )
            if ident in seen_qidentities:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "question_coverages",
                            qindex,
                            q.question_slice or None,
                            ("duplicate question identity in submission",),
                        )
                    )
                )
            seen_qidentities.add(ident)
            problem = _validation.validate_question_coverage(
                submitted,
                ctx,
                "question coverage",
            )
            if problem is not None:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "question_coverages",
                            qindex,
                            q.question_slice or None,
                            (problem,),
                        )
                    )
                )
            if q.question_slice != submitted.question_slice:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "question_coverages",
                            qindex,
                            q.question_slice or None,
                            ("question_slice mismatch in coverage",),
                        )
                    )
                )
        # Current-question coverage: Addendum C C-05 eliminates implied
        # completion. An explicit submitted disposition for the bound
        # question is required for ANSWERED/NOT_APPLICABLE. Missing
        # explicit coverage always synthesizes PENDING, never completion,
        # so claims without a completion claim stay unassigned output.
        # Addendum H §6 correction-fallback case: the fallback bound
        # question is scaffolding only — it neither adopts an explicitly
        # submitted bound coverage nor synthesizes PENDING.
        # Span-derived support: one question's direct evidence is only its
        # selected support plus (for ANSWERED/OPEN) evidence cited by the
        # materialized results that question owns. Task delivery alone is
        # never a direct question dependency.
        material_evidence = _material_evidence_refs(claims, relationships)
        new_result_refs = _material_result_refs(claims, relationships)
        withdrawn_ids = frozenset(
            withdrawal.target.id.value for withdrawal in validated_withdrawals
        )
        prior_cache: dict[m.SemanticQuestionScope, m.InterpretationCoverage | None] = {}

        def _prior(
            question: m.SemanticQuestionScope,
        ) -> m.InterpretationCoverage | None:
            if question not in prior_cache:
                prior_cache[question] = _load_prior_question_coverage(
                    task.request.repository_id,
                    question,
                    store=store,
                    bounds=task.request.bounds,
                )
            return prior_cache[question]

        def _finalize(
            submitted: m.InterpretationCoverage,
            *,
            owns_material: bool,
        ) -> m.InterpretationCoverage:
            prior = _prior(submitted.question)
            prior_refs = () if prior is None else prior.result_refs
            prior_evidence = () if prior is None else prior.question_evidence
            decision = m.SemanticQuestionDecision(
                disposition=submitted.disposition,
                evidence_scope=submitted.evidence_scope,
                resolution_requirements=submitted.resolution_requirements,
                disposition_basis=submitted.disposition_basis,
            )
            disposition = submitted.disposition
            if disposition is m.SemanticQuestionDisposition.ANSWERED:
                result_refs = new_result_refs
                question_evidence = _derive_question_evidence(
                    decision,
                    canonical_refs=ctx.evidence_refs,
                    fingerprints=fingerprints,
                    material_evidence=(material_evidence if owns_material else ()),
                )
            elif disposition is m.SemanticQuestionDisposition.OPEN:
                result_refs = _ordered_result_refs(
                    prior_refs,
                    new_result_refs if owns_material else (),
                    withdrawn_ids,
                )
                question_evidence = _derive_question_evidence(
                    decision,
                    canonical_refs=ctx.evidence_refs,
                    fingerprints=fingerprints,
                    material_evidence=(material_evidence if owns_material else ()),
                    prior_evidence=prior_evidence,
                )
            elif disposition is m.SemanticQuestionDisposition.PENDING:
                result_refs = _ordered_result_refs(
                    prior_refs,
                    (),
                    withdrawn_ids,
                )
                question_evidence = _derive_question_evidence(
                    decision,
                    canonical_refs=ctx.evidence_refs,
                    fingerprints=fingerprints,
                    prior_evidence=prior_evidence,
                )
            else:  # NOT_APPLICABLE never owns semantic result refs.
                result_refs = ()
                question_evidence = _derive_question_evidence(
                    decision,
                    canonical_refs=ctx.evidence_refs,
                    fingerprints=fingerprints,
                )
            return _dataclasses.replace(
                submitted,
                result_refs=result_refs,
                question_evidence=question_evidence,
                declared_complete=(
                    disposition is m.SemanticQuestionDisposition.ANSWERED
                ),
            )

        current_qcov: m.InterpretationCoverage | None = None
        if bound_question is not None and not bound_is_fallback_scaffolding:
            is_current = [
                c
                for c in submitted_coverages
                if c.question is not None and c.question == bound_question
            ]
            if is_current:
                current_qcov = is_current[0]
                if (
                    current_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED
                ) and not (claims or relationships):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "question_coverages",
                                0,
                                bound_question.question_slice or None,
                                (
                                    "explicit ANSWERED with zero "
                                    "validated material; submit "
                                    "PENDING/OPEN or add supported "
                                    "candidates",
                                ),
                            )
                        )
                    )
                current_qcov = _finalize(current_qcov, owns_material=True)
            else:
                # Addendum C C-05: no explicit current coverage means no
                # completion claim. Always synthesize PENDING (admitted but
                # unexamined) so the unit still leaves durable question
                # state; submitted claims persist as unassigned output.
                prior = _prior(bound_question)
                current_qcov = m.InterpretationCoverage(
                    subjects=tuple(s.subject_id for s in subjects),
                    question_slice=bound_question.question_slice,
                    evidence_scope=m.EvidenceScope(
                        paths=(),
                        evidence_refs=tuple(
                            unit.evidence_ref for unit in task.request.evidence_units
                        ),
                    ),
                    declared_complete=False,
                    question=bound_question,
                    disposition=m.SemanticQuestionDisposition.PENDING,
                    result_refs=_ordered_result_refs(
                        () if prior is None else prior.result_refs,
                        (),
                        withdrawn_ids,
                    ),
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=(m.ResolutionKind.MISSING_SEMANTIC_COVERAGE),
                            subject_or_claim=bound_question.subject,
                            description=(
                                "question submitted without explicit "
                                "completion; examination pending"
                            ),
                            supporting_context=(),
                        ),
                    ),
                    disposition_basis=(
                        "synthesized pending: no explicit completion submitted"
                    ),
                    question_evidence=(
                        () if prior is None else prior.question_evidence
                    ),
                )
            if current_qcov is not None and (
                current_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED
            ):
                # Addendum C C-05: only a complete replacement retires
                # prior unshared outputs. PENDING/OPEN/NOT_APPLICABLE never
                # authorize omission-based retirement; explicit withdrawals
                # retire through the validated-withdrawal path above.
                _retire_replaced_outputs(
                    task.request.repository_id,
                    bound_question,
                    {r.id.value for r in current_qcov.result_refs},
                    store=store,
                    bounds=task.request.bounds,
                    retires_claims=retires_claims,
                    retires_relationships=retires_relationships,
                )
        # Addendum H §6: the one nominated original question of a
        # fallback refresh unit derives/retires exactly like the bound
        # question. Any other non-bound coverage persists as submitted.
        nominated_qcov: m.InterpretationCoverage | None = None
        if correction_question is not None:
            is_nominated = [
                c
                for c in submitted_coverages
                if c.question is not None and c.question == correction_question
            ]
            if is_nominated:
                nominated_qcov = is_nominated[0]
                if (
                    nominated_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED
                ) and not (claims or relationships):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "question_coverages",
                                0,
                                correction_question.question_slice or None,
                                (
                                    "explicit ANSWERED with zero "
                                    "validated material; submit "
                                    "PENDING/OPEN or add supported "
                                    "candidates",
                                ),
                            )
                        )
                    )
                nominated_qcov = _finalize(nominated_qcov, owns_material=True)
                if nominated_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED:
                    _retire_replaced_outputs(
                        task.request.repository_id,
                        correction_question,
                        {r.id.value for r in nominated_qcov.result_refs},
                        store=store,
                        bounds=task.request.bounds,
                        retires_claims=retires_claims,
                        retires_relationships=retires_relationships,
                    )
        # Addendum C C-05: the bound question persists exactly once, as
        # the derived/synthesized current coverage — never the submitted
        # original (whose empty refs are intent, not examined output).
        # The nominated correction question likewise persists exactly
        # once as its derived coverage. Addendum H §6 correction-fallback
        # case: the fallback bound question persists zero times —
        # current_qcov above stays None and explicitly submitted
        # bound-matching entries are excluded from the bucket below.
        question_coverages_to_persist = [
            _finalize(c, owns_material=False)
            for c in submitted_coverages
            if c.question is None
            or (
                (bound_question is None or c.question != bound_question)
                and (correction_question is None or c.question != correction_question)
            )
        ]
        if current_qcov is not None:
            question_coverages_to_persist.append(current_qcov)
        if nominated_qcov is not None:
            question_coverages_to_persist.append(nominated_qcov)
        # Explicit withdrawal fanout: reopen all other referencing questions.
        # Enumeration is unbounded; overflow defers (raises, no partial
        # write) instead of retiring with an incomplete fanout.
        if validated_withdrawals:
            all_qcovs = _load_all_coverages_or_defer(
                task.request.repository_id,
                None,
                (),
                store=store,
                bounds=task.request.bounds,
                purpose="withdrawal fanout",
            )
            withdrawn_ids = {w.target.id.value for w in validated_withdrawals}
            withdrawn_reasons: dict[str, str] = {}
            for w in validated_withdrawals:
                withdrawn_reasons.setdefault(w.target.id.value, w.basis.summary)
            for other in all_qcovs:
                if other.question is None:
                    continue
                if bound_question is not None and other.question == bound_question:
                    continue
                if (
                    correction_question is not None
                    and other.question == correction_question
                ):
                    # Addendum H §6: the nominated original question is
                    # answered by this same unit; its prior row is
                    # superseded by the derived ANSWERED coverage above,
                    # not reopened.
                    continue
                other_ref_ids = {r.id.value for r in other.result_refs}
                if withdrawn_ids & other_ref_ids:
                    # S8.3: reopen with the actual withdrawal reason
                    # while preserving the dependent question's useful
                    # original requirements.
                    reasons = sorted(
                        {
                            withdrawn_reasons[rid]
                            for rid in other_ref_ids
                            if rid in withdrawn_reasons
                        }
                    )
                    reason = (
                        "; ".join(reasons) if reasons else "shared output withdrawn"
                    )
                    reopened_coverages.append(
                        m.InterpretationCoverage(
                            subjects=other.subjects,
                            question_slice=other.question_slice,
                            evidence_scope=other.evidence_scope,
                            declared_complete=False,
                            question=other.question,
                            disposition=m.SemanticQuestionDisposition.PENDING,
                            result_refs=other.result_refs,
                            resolution_requirements=(
                                tuple(other.resolution_requirements)
                                + (
                                    m.ResolutionRequirement(
                                        kind=(m.ResolutionKind.STALE_EVIDENCE),
                                        subject_or_claim=(other.question.subject),
                                        description=(
                                            "shared output withdrawn "
                                            f"({reason}); reassessment "
                                            "required"
                                        ),
                                        supporting_context=tuple(
                                            w.target
                                            for w in validated_withdrawals
                                            if w.target.id.value in other_ref_ids
                                        ),
                                    ),
                                )
                            ),
                            disposition_basis=(
                                "reopened by explicit withdrawal in bound question"
                            ),
                            question_evidence=other.question_evidence,
                        )
                    )
            # Bound check: if fanout exceeds bounds, fail without partial.
            if len(reopened_coverages) > task.request.bounds.max_results:
                raise _validation.InterpretationUnitRejected(
                    ("withdrawal fanout exceeds bounds; deferred",)
                )
    dependencies = tuple(
        m.EvidenceDependency(
            semantic_id=_item_ref(item),
            evidence_ref=ref,
            observed_fingerprint=fingerprints[ref.evidence_id.value],
        )
        for item in (*claims, *relationships)
        for ref in item.evidence
    )
    all_coverages = tuple(question_coverages_to_persist) + tuple(reopened_coverages)
    # Addendum E target accounting (same atomic batch). Pure validation
    # here; persistence joins the single CanonicalIndexBatch below.
    updated_associations: tuple[m.TargetAssociation, ...] = ()
    has_target_proposals = bool(
        result.proposed_target_inventory_accounting or result.proposed_target_questions
    )
    effective_target_id = target_id if target_id is not None else task.request.target_id
    if has_target_proposals and effective_target_id is None:
        raise _validation.InterpretationUnitRejected(
            tuple(
                _member_diagnostics(
                    "target_accounts",
                    0,
                    None,
                    ("target proposals without target mode",),
                )
            )
        )
    bound_items = target_inventory_items or task.request.target_inventory_items
    # J-6/S5: a mapping batch is correlated strictly by stable EvidenceId,
    # never by position in the submitted list. The map is built once from
    # the bound batch so every later check names the exact member.
    bound_by_id = {item.evidence_ref.evidence_id.value: item for item in bound_items}
    is_mapping_task = task.request.question is None and bool(bound_items)
    if is_mapping_task and not result.proposed_target_inventory_accounting:
        raise _validation.InterpretationUnitRejected(
            tuple(
                diagnostic
                for index, item in enumerate(bound_items)
                for diagnostic in _member_diagnostics(
                    "bound_items",
                    index,
                    item.evidence_ref.evidence_id.value,
                    ("bound mapping item has no accounting candidate",),
                )
            )
        )
    if effective_target_id is not None:
        if target_association is None or (
            target_association.target_id != effective_target_id
        ):
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "target_accounts",
                        0,
                        None,
                        ("target association does not resolve",),
                    )
                )
            )
        if result.proposed_target_inventory_accounting:
            seen_ids: set[str] = set()
            for tindex, acc in enumerate(result.proposed_target_inventory_accounting):
                eid = acc.evidence_id.value
                if eid in seen_ids:
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_accounts",
                                tindex,
                                eid,
                                (f"duplicate target account: {eid}",),
                            )
                        )
                    )
                seen_ids.add(eid)
            expected_ids = {item.evidence_ref.evidence_id.value for item in bound_items}
            if expected_ids:
                for tindex, acc in enumerate(
                    result.proposed_target_inventory_accounting
                ):
                    eid = acc.evidence_id.value
                    if eid not in bound_by_id:
                        raise _validation.InterpretationUnitRejected(
                            tuple(
                                _member_diagnostics(
                                    "target_accounts",
                                    tindex,
                                    eid,
                                    (
                                        "target account is outside the bound "
                                        "mapping batch",
                                    ),
                                )
                            )
                        )
            admitted_existing = tuple(target_association.area_subjects)
            new_ids = tuple(new_subject_ids)
            snapshot = current_inventory_snapshot or {}
            for tindex, acc in enumerate(result.proposed_target_inventory_accounting):
                validation = _validation.validate_target_inventory_account(
                    acc,
                    ctx,
                    current_inventory_ids=current_inventory_ids,
                    expected_evidence_id=None,
                    admitted_area_ids=admitted_existing,
                    new_area_ids=new_ids,
                )
                if not validation.ok:
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_accounts",
                                tindex,
                                acc.evidence_id.value,
                                tuple(validation.diagnostics),
                            )
                        )
                    )
                # J-4/S4.2: the accounted member's canonical current ref is
                # a provider fact, never agent-supplied. It must resolve in
                # the provider snapshot.
                if snapshot.get(acc.evidence_id.value) is None:
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_accounts",
                                tindex,
                                acc.evidence_id.value,
                                (
                                    "target account not in provider "
                                    f"snapshot: {acc.evidence_id.value}",
                                ),
                            )
                        )
                    )
            if expected_ids:
                missing_ids = expected_ids - seen_ids
                if missing_ids:
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            diagnostic
                            for index, item in enumerate(bound_items)
                            if item.evidence_ref.evidence_id.value in missing_ids
                            for diagnostic in _member_diagnostics(
                                "bound_items",
                                index,
                                item.evidence_ref.evidence_id.value,
                                ("bound mapping item has no accounting " "candidate",),
                            )
                        )
                    )
                # Orphan prohibition: every new subject from a mapping task
                # must be referenced by at least one bound assignment.
                assigned_any = {
                    sid
                    for acc in result.proposed_target_inventory_accounting
                    for sid in acc.assigned_area_subjects
                }
                for sid in new_subject_ids:
                    if sid not in assigned_any:
                        raise _validation.InterpretationUnitRejected(
                            tuple(
                                _member_diagnostics(
                                    "target_accounts",
                                    0,
                                    None,
                                    ("orphan target-mapping subject",),
                                )
                            )
                        )
                assigned = tuple(assigned_any)
                fresh_areas = [
                    sid for sid in assigned if sid not in set(admitted_existing)
                ]
                if fresh_areas:
                    new_roots = {
                        cov.question.scope_root
                        for cov in question_coverages_to_persist
                        if cov.question is not None
                        and cov.disposition is m.SemanticQuestionDisposition.PENDING
                    }
                    reuse_roots = {
                        qq.scope_root for qq in result.proposed_target_questions
                    }
                    satisfying = new_roots | reuse_roots
                    area_member_refs = {
                        sid: tuple(
                            snapshot[acc.evidence_id.value]
                            for acc in result.proposed_target_inventory_accounting
                            if sid in acc.assigned_area_subjects
                            and snapshot.get(acc.evidence_id.value) is not None
                        )
                        for sid in fresh_areas
                    }
                    for sid in fresh_areas:
                        if sid in satisfying:
                            continue
                        # J-5/S4.4: exactly one service-owned PENDING CQ-01
                        # seed for a newly admitted area with no reusable
                        # current target question. The agent is never
                        # required to manufacture it. The seed asserts no
                        # area meaning; its discovery support is the
                        # canonical mapping member(s) assigned to the area.
                        seed_slice = m.QUESTION_CLASS_DEFAULT_SLICE[
                            m.SemanticQuestionClass.CQ_01
                        ]
                        seed_question = m.SemanticQuestionScope(
                            scope_root=sid,
                            subject=sid,
                            question_class=m.SemanticQuestionClass.CQ_01,
                            question_slice=seed_slice,
                            materiality_basis=(
                                "service-owned first-admission target seed"
                            ),
                        )
                        question_coverages_to_persist.append(
                            m.InterpretationCoverage(
                                subjects=(sid,),
                                question_slice=seed_slice,
                                evidence_scope=m.EvidenceScope(
                                    evidence_refs=area_member_refs.get(sid, ())
                                ),
                                declared_complete=False,
                                question=seed_question,
                                disposition=(m.SemanticQuestionDisposition.PENDING),
                                result_refs=(),
                                resolution_requirements=(
                                    m.ResolutionRequirement(
                                        kind=(
                                            m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
                                        ),
                                        subject_or_claim=sid,
                                        description=(
                                            "service-owned first-admission "
                                            "target seed: establish this "
                                            "admitted area's purpose and "
                                            "material questions for the "
                                            "selected target."
                                        ),
                                        supporting_context=(),
                                    ),
                                ),
                                disposition_basis=(
                                    "service-owned first-admission " "target seed"
                                ),
                                question_evidence=(),
                            )
                        )
                    # The persisted coverage set changed: recompute before
                    # it is consumed by the atomic batch.
                    all_coverages = tuple(question_coverages_to_persist) + tuple(
                        reopened_coverages
                    )
            else:
                # Semantic-phase revisions are task-evidence-bounded: a
                # revised member must be present in this task's evidence.
                in_task = {
                    u.evidence_ref.evidence_id.value
                    for u in task.request.evidence_units
                }
                for tindex, acc in enumerate(
                    result.proposed_target_inventory_accounting
                ):
                    if acc.evidence_id.value not in in_task:
                        raise _validation.InterpretationUnitRejected(
                            tuple(
                                _member_diagnostics(
                                    "target_accounts",
                                    tindex,
                                    acc.evidence_id.value,
                                    (
                                        "target revision outside task "
                                        "evidence: "
                                        f"{acc.evidence_id.value}",
                                    ),
                                )
                            )
                        )
        if result.proposed_target_questions:
            admitted_all = tuple(target_association.area_subjects) + tuple(
                new_subject_ids
            )
            # Assignments in this same unit admit areas before question check.
            for acc in result.proposed_target_inventory_accounting:
                for sid in acc.assigned_area_subjects:
                    if sid not in admitted_all:
                        admitted_all = admitted_all + (sid,)
            validation_q = _validation.validate_target_questions(
                tuple(result.proposed_target_questions),
                admitted_area_ids=tuple(admitted_all),
            )
            if not validation_q.ok:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "target_questions",
                            0,
                            None,
                            tuple(validation_q.diagnostics),
                        )
                    )
                )
            # Reuse is strict: each proposed question must already be
            # persisted canonically. New questions enter only through
            # proposed_questions in the same unit (which
            # auto-contribute their scopes below), never through this
            # reuse field.
            for qq_index, qq in enumerate(result.proposed_target_questions):
                try:
                    persisted = store.load_all_question_coverages(
                        task.request.repository_id,
                        qq.scope_root,
                        (qq.subject,),
                    )
                except Exception:
                    persisted = ()
                if not any(
                    cov.question is not None
                    and cov.question.scope_root == qq.scope_root
                    and cov.question.subject == qq.subject
                    and cov.question.question_class == qq.question_class
                    and cov.question.question_slice == qq.question_slice
                    for cov in persisted
                ):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_questions",
                                qq_index,
                                qq.question_slice or None,
                                (
                                    "target question does not resolve to "
                                    "persisted coverage; use "
                                    "proposed_questions to "
                                    "create new PENDING coverage",
                                ),
                            )
                        )
                    )
                if not store.load_subjects(task.request.repository_id, (qq.subject,)):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_questions",
                                qq_index,
                                qq.subject.canonical_locator,
                                ("target question subject does not " "resolve",),
                            )
                        )
                    )
        # Upsert accounting by EvidenceId (membership only, §§4C.6B/4C.6E).
        # No content fingerprint is stamped here: content freshness remains
        # owned by the existing evidence/question/claim/relationship
        # dependency machinery.
        merged: dict[str, m.TargetInventoryAccount] = {
            acc.evidence_ref.evidence_id.value: acc
            for acc in target_association.inventory_accounting
        }
        snapshot_map = current_inventory_snapshot or {}
        for acc in result.proposed_target_inventory_accounting:
            eid = acc.evidence_id.value
            canonical_ref = snapshot_map.get(eid)
            if canonical_ref is None:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "target_accounts",
                            0,
                            eid,
                            ("target account not in provider " f"snapshot: {eid}",),
                        )
                    )
                )
            merged[eid] = m.TargetInventoryAccount(
                evidence_ref=canonical_ref,
                assigned_area_subjects=acc.assigned_area_subjects,
                exclusion_basis=acc.exclusion_basis,
                resolution_requirements=acc.resolution_requirements,
            )
        new_area_union = tuple(
            dict.fromkeys(
                sid for acc in merged.values() for sid in acc.assigned_area_subjects
            )
        )
        admitted_set = set(new_area_union)
        kept_questions = tuple(
            q
            for q in target_association.target_questions
            if q.scope_root in admitted_set
        )
        added_scopes: list[m.SemanticQuestionScope] = []
        for cov_index, cov in enumerate(question_coverages_to_persist):
            if cov.question is not None:
                if cov.question.scope_root not in admitted_set:
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "question_coverages",
                                cov_index,
                                cov.question.question_slice or None,
                                (
                                    "question scope root is not an admitted "
                                    "target area",
                                ),
                            )
                        )
                    )
                # §4C.6D amendment (answerability, 2026-10-11): a new
                # question anchored to nothing can never suspend or
                # answer — same fail-closed as the reuse path below.
                # Unit-co-admitted subjects count, mirroring admitted_all.
                if cov.question.subject not in new_subject_ids:
                    if not store.load_subjects(
                        task.request.repository_id, (cov.question.subject,)
                    ):
                        raise _validation.InterpretationUnitRejected(
                            tuple(
                                _member_diagnostics(
                                    "question_coverages",
                                    cov_index,
                                    cov.question.subject.canonical_locator,
                                    ("target question subject does not " "resolve",),
                                )
                            )
                        )
                added_scopes.append(cov.question)
        for qq_index, qq in enumerate(result.proposed_target_questions):
            if qq.scope_root not in admitted_set:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "target_questions",
                            qq_index,
                            qq.question_slice or None,
                            ("question scope root is not an admitted " "target area",),
                        )
                    )
                )
        added_scopes.extend(result.proposed_target_questions)
        combined = tuple(kept_questions) + tuple(added_scopes)
        # Deduplicate question identities deterministically (full
        # SubjectId identity: repository, locator, and kind).
        seen_q: set[tuple[str, str, str, str, str, str, str, str]] = set()
        deduped: list[m.SemanticQuestionScope] = []
        for q in combined:
            key = (
                q.scope_root.repository_id,
                q.scope_root.canonical_locator,
                q.scope_root.subject_kind.value,
                q.subject.repository_id,
                q.subject.canonical_locator,
                q.subject.subject_kind.value,
                q.question_class.value,
                q.question_slice,
            )
            if key not in seen_q:
                seen_q.add(key)
                deduped.append(q)
        updated = m.TargetAssociation(
            target_id=target_association.target_id,
            repository_id=target_association.repository_id,
            target_scope=target_association.target_scope,
            objective=target_association.objective,
            area_subjects=new_area_union,
            target_questions=tuple(deduped),
            inventory_accounting=tuple(merged[k] for k in sorted(merged)),
            inventory_fingerprint=target_association.inventory_fingerprint,
            observed_repository_state_fingerprint=(
                target_association.observed_repository_state_fingerprint
            ),
        )
        # Every accepted target-mode submission refreshes TTL: persist the
        # reconciled association in the same batch even without new
        # proposals (store write refreshes last_touched_at/expires_at).
        updated_associations = (updated,)
    # Deduplicate retirements: an explicit withdrawal and complete
    # replacement may name the same item; retiring twice must not
    # fail the batch on the second (already-moved) lookup.
    seen_retire_claims: set[str] = set()
    unique_retire_claims: list[m.ClaimRef] = []
    for ref in retires_claims:
        if ref.id.value not in seen_retire_claims:
            seen_retire_claims.add(ref.id.value)
            unique_retire_claims.append(ref)
    seen_retire_rels: set[str] = set()
    unique_retire_rels: list[m.RelationshipRef] = []
    for ref in retires_relationships:
        if ref.id.value not in seen_retire_rels:
            seen_retire_rels.add(ref.id.value)
            unique_retire_rels.append(ref)
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=subjects,
            claims=tuple(claims),
            relationships=tuple(relationships),
            evidence_dependencies=dependencies,
            coverage_dependencies=(
                ()
                if (is_mapping_write and not claims and not relationships)
                else (coverage,)
            ),
            coverage=all_coverages,
            retires_claims=tuple(unique_retire_claims),
            retires_relationships=tuple(unique_retire_rels),
            conflicts=tuple(recorded),
            target_associations=updated_associations,
        )
    )


def _next_baseline_pending(
    repository_id: str,
    root: m.Subject,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.InterpretationCoverage | None:
    """First admitted PENDING question under a baseline root, if any.

    Deterministic order (CQ class, subject, slice). Used both when a
    baseline resumes after submit and when the baseline operation is
    re-entered after a lost continuation: persisted coverage — never
    prompt wording — determines remaining work, so the audit is never
    restarted while admitted work exists.
    """
    try:
        pending = store.load_all_question_coverages(
            repository_id,
            root.subject_id,
            (root.subject_id,),
        )
    except Exception:
        try:
            pending = store.load_question_coverages(
                repository_id,
                root.subject_id,
                (root.subject_id,),
                bounds,
            )
        except Exception:
            pending = ()
    next_pending = [
        cov
        for cov in pending
        if cov.disposition is m.SemanticQuestionDisposition.PENDING
        and cov.question is not None
    ]
    next_pending.sort(
        key=lambda c: (
            c.question.question_class.value,  # type: ignore[union-attr]
            c.question.subject.canonical_locator,  # type: ignore[union-attr]
            c.question.question_slice,  # type: ignore[union-attr]
        )
    )
    return next_pending[0] if next_pending else None


def _suspend_baseline_pending(
    repository_id: str,
    root: m.Subject,
    coverage: m.InterpretationCoverage,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    seeds: tuple[m.EvidenceRef, ...],
    resolution: m.SubjectResolution | None,
    continuations: ContinuationStore,
    op: str = "explain",
    scope: tuple[m.Subject, ...] = (),
    remaining: tuple[m.Subject, ...] = (),
    objective: str = "",
    target_scope: m.EvidenceScope = m.EvidenceScope(),
    target_id: m.TargetId | None = None,
) -> PendingInterpretation:
    """Suspend the next admitted baseline question under its persisted
    identity (no regenerated wording, no restarted audit)."""
    assert coverage.question is not None
    try:
        loaded = store.load_subjects(repository_id, (coverage.question.subject,))
        nxt_subject = (
            m.Subject(
                subject_id=loaded[0].subject_id,
                display_name=loaded[0].display_name,
                declared_kind=loaded[0].declared_kind,
            )
            if loaded
            else root
        )
    except Exception:
        nxt_subject = root
    nxt_task = prepare_interpretation_task(
        repository_id,
        nxt_subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=seeds,
        operation_intent=m.SemanticIntent.EXPLAIN,
        question_slice=coverage.question.question_slice,
        store=store,
        scope_root=coverage.question.scope_root,
        question_class=coverage.question.question_class,
        materiality_basis=coverage.question.materiality_basis,
        establish_baseline=False,
        objective=objective,
        target_scope=target_scope,
        target_id=target_id,
    )
    return _suspend(
        op=op,
        repository_id=repository_id,
        subject=nxt_subject,
        task=nxt_task,
        seeds=seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        scope=scope,
        remaining=remaining,
        continuations=continuations,
        operation_intent="EXPLAIN",
        question_slice=coverage.question.question_slice,
        establish_baseline=True,
        objective=objective,
        target_scope=target_scope,
        target_id=target_id,
    )


def _suspend(
    *,
    op: str,
    repository_id: str,
    subject: m.Subject,
    task: InterpretationTask,
    seeds: tuple[m.EvidenceRef, ...],
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    resolution: m.SubjectResolution | None,
    scope: tuple[m.Subject, ...] = (),
    remaining: tuple[m.Subject, ...] = (),
    changed: tuple[m.EvidenceDependency, ...] = (),
    suspended: tuple[m.SubjectId, ...] = (),
    change_kind: str | None = None,
    change_description: str | None = None,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    operation_intent: str = "EXPLAIN",
    question_slice: str = "",
    declared_complete: bool = False,
    trace_direction: str | None = None,
    trace_filter: tuple[m.RelationshipKind, ...] = (),
    trace_filter_set: bool = False,
    trace_boundary: bool = False,
    continuations: ContinuationStore,
    establish_baseline: bool = False,
    objective: str = "",
    target_scope: m.EvidenceScope = m.EvidenceScope(),
    target_id: m.TargetId | None = None,
    root_question: m.SemanticQuestionScope | None = None,
    question_selection: m.SemanticQuestionSelection | None = None,
) -> PendingInterpretation:
    token = continuations.pend(
        SuspendedOperation(
            op=op,
            repository_id=repository_id,
            subject=subject,
            scope=scope,
            remaining=remaining,
            changed=changed,
            resolution=resolution,
            request=task.request,
            fingerprints=task.fingerprints,
            known_subject_ids=task.known_subject_ids,
            seeds=seeds,
            bounds=bounds,
            state=state,
            suspended=suspended,
            change_kind=change_kind,
            change_description=change_description,
            affected_assertions=affected_assertions,
            operation_intent=operation_intent,
            objective=objective,
            question_slice=question_slice,
            declared_complete=declared_complete,
            trace_direction=trace_direction,
            trace_filter=trace_filter,
            trace_filter_set=trace_filter_set,
            trace_boundary=trace_boundary,
            establish_baseline=establish_baseline,
            target_scope=target_scope,
            target_id=target_id,
            root_question=root_question,
            question_selection=question_selection,
        )
    )
    return PendingInterpretation(continuation=token, request=task.request)
