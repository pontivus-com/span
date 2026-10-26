"""Span questions: identity projection, slice derivation, and frontier."""

from __future__ import annotations


from span.core import model as m


def _question_identity_key(
    question: m.SemanticQuestionScope,
) -> tuple[str, ...]:
    return (
        "q",
        question.scope_root.repository_id,
        question.scope_root.subject_kind.value,
        question.scope_root.canonical_locator,
        question.subject.repository_id,
        question.subject.subject_kind.value,
        question.subject.canonical_locator,
        question.question_class.value,
        question.question_slice,
    )


def effective_trace_slice(
    host_slice: str,
    direction: object,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
) -> str:
    """Persisted effective slice for TRACE (S4 §5.4 discriminator).

    Appends ``|dir=<UPSTREAM|DOWNSTREAM|BOTH>|filter=<ALL|NONE|sorted
    kind names>|boundary=<0|1>``. A None filter encodes as ALL and an
    explicitly empty tuple encodes as NONE, so different traversal
    parameters never share one persisted identity.
    """
    direction_value = direction.value if hasattr(direction, "value") else str(direction)
    if relationship_filter is None:
        filter_part = "ALL"
    elif not relationship_filter:
        filter_part = "NONE"
    else:
        filter_part = ",".join(
            sorted(
                k.value if hasattr(k, "value") else str(k) for k in relationship_filter
            )
        )
    boundary_part = "1" if boundary_only else "0"
    return (
        f"{host_slice}|dir={direction_value}"
        f"|filter={filter_part}|boundary={boundary_part}"
    )


def effective_impact_slice(
    host_slice: str,
    change_kind: object,
    change_description: str | None,
    affected_assertions: tuple[object, ...] = (),
) -> str:
    """Persisted effective slice for IMPACT (S4 §5.4 discriminator).

    Appends ``|kind=<name>|desc=<sha16 hex of exact UTF-8 bytes of the
    description, - when None or empty>|affected=<sorted ref values or ->``.
    Different change proposals never share one persisted identity.
    """
    import hashlib as _hashlib

    kind_value = (
        change_kind.value if hasattr(change_kind, "value") else str(change_kind)
    )
    if change_description:
        desc_part = _hashlib.sha256(change_description.encode("utf-8")).hexdigest()[:16]
    else:
        desc_part = "-"
    ref_values: list[str] = []
    for ref in affected_assertions:
        ref_id = getattr(getattr(ref, "id", None), "value", None)
        if ref_id:
            ref_values.append(str(ref_id))
    affected_part = ",".join(sorted(ref_values)) if ref_values else "-"
    return (
        f"{host_slice}|kind={kind_value}" f"|desc={desc_part}|affected={affected_part}"
    )


def derive_service_question(
    *,
    subject: m.Subject,
    scope_root: m.SubjectId,
    question_class: m.SemanticQuestionClass,
    selection: m.SemanticQuestionSelection | None,
    default_slice: str,
    default_basis: str,
) -> tuple[m.SemanticQuestionScope, tuple[str, ...]]:
    """Build the service-owned full scope from host selection (S4 §5.4).

    Returns (scope, anchors). The service derives scope_root, subject,
    and question_class; the host supplies only slice/basis/anchors.
    Missing basis fills with the operation-derived default so the
    required non-empty invariant holds. Slice canonicalized verbatim
    (no paraphrase equivalence). Anchors passed verbatim as
    question_terms into bounded discovery.
    """
    if selection is not None:
        host_slice = selection.question_slice
        basis = selection.materiality_basis or default_basis
        anchors = tuple(selection.question_anchors)
    else:
        host_slice = default_slice
        basis = default_basis
        anchors = ()
    if not host_slice:
        raise ValueError("question slice must be nonempty")
    if not basis:
        raise ValueError("materiality basis must be nonempty")
    scope = m.SemanticQuestionScope(
        scope_root=scope_root,
        subject=subject.subject_id,
        question_class=question_class,
        question_slice=host_slice,
        materiality_basis=basis,
    )
    return scope, anchors
