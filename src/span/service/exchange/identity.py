"""Canonical question identity and composed-answer keys."""

from __future__ import annotations

from span.core import model as m


def _format_question_identity(question: m.SemanticQuestionScope) -> str:
    """Render the complete canonical question identity for diagnostics.

    Pure formatting over the same identity fields used by
    ``_question_identity``: no hashing, normalization, or paraphrase
    equivalence.
    """
    return (
        "("
        f"scope_root.repository_id={question.scope_root.repository_id}, "
        f"scope_root.subject_kind={question.scope_root.subject_kind.value}, "
        f"scope_root.canonical_locator="
        f"{question.scope_root.canonical_locator}, "
        f"subject.repository_id={question.subject.repository_id}, "
        f"subject.subject_kind={question.subject.subject_kind.value}, "
        f"subject.canonical_locator={question.subject.canonical_locator}, "
        f"question_class={question.question_class.value}, "
        f"question_slice={question.question_slice}"
        ")"
    )


def _question_identity(
    question: m.SemanticQuestionScope,
) -> tuple[str, ...]:
    """Canonical identity of one question scope, in comparison order."""
    return (
        question.scope_root.repository_id,
        question.scope_root.subject_kind.value,
        question.scope_root.canonical_locator,
        question.subject.subject_kind.value,
        question.subject.canonical_locator,
        question.question_class.value,
        question.question_slice,
    )


def _question_key(question: m.SemanticQuestionScope | None) -> str:
    """The composed answer's question key: class plus slice, or empty."""
    if question is None:
        return ""
    return f"{question.question_class.value}:{question.question_slice}"
