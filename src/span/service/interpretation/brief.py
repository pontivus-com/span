"""Task brief: the uniform quality card for one admitted task."""

from __future__ import annotations

from span.core import model as m


def _submission_template(
    bound_question: m.SemanticQuestionScope | None,
) -> str:
    if bound_question is None:
        return ""
    import json as _json

    # Smallest strict-decodable unfinished shape ([design note M](docs/design-references.md#m) §M-05.1).
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
            "A disposition is your decision: a claim supported by cited file "
            "evidence is a complete assertion. Missing governing authority is "
            "recorded as a resolution requirement on the claim, not a reason "
            "to withhold the assertion or leave the question OPEN."
        ),
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
            authority_guidance,
            evidence_authority,
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
