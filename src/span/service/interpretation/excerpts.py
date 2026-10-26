"""Bounded excerpt projection for one task."""

from __future__ import annotations

import dataclasses as _dc
import json as _json

from span.core import model as m
from span.core import requirements as _requirements


def _range_meta(start: int, end: int, total: int) -> int:
    """Byte cost of the canonical range metadata for one delivered range."""
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


def _select_anchors(
    subject: m.Subject,
    question_terms: tuple[str, ...],
) -> tuple[str, ...]:
    """Anchors are literal substrings: the subject's names plus host terms."""
    default_anchors = (
        subject.display_name,
        subject.subject_id.canonical_locator.rsplit("/", 1)[-1],
    )
    return tuple(
        dict.fromkeys(
            anchor for anchor in (*default_anchors, *question_terms) if anchor
        )
    )


@_dc.dataclass
class _DeliveryRequirement:
    """The named requirement for evidence that could not be delivered."""

    subject_id: m.SubjectId

    def build(
        self,
        unit: m.EvidenceUnit,
        start: int,
        end: int,
        total: int,
    ) -> m.ResolutionRequirement:
        return _requirements.missing_evidence(
            subject_or_claim=self.subject_id,
            description=(
                f"evidence delivery: {unit.evidence_ref.locator} "
                f"lines {start}-{end} of {total} exceed the delivery "
                "budget; inspect the file directly and cite its "
                "canonical EvidenceRef"
            ),
            supporting_context=(unit.evidence_ref,),
        )


@_dc.dataclass
class _Projection:
    """Accumulated output and byte/omission accounting for one projection."""

    delivery_budget: int
    requirement: _DeliveryRequirement
    projected: list[m.EvidenceUnit] = _dc.field(default_factory=list)
    omissions: list[str] = _dc.field(default_factory=list)
    requirements: list[m.ResolutionRequirement] = _dc.field(default_factory=list)
    used: int = 0
    total_ranges: int = 0
    total_omitted_hits: int = 0

    def fits(self, size: int) -> bool:
        return self.used + size <= self.delivery_budget

    def deliver(
        self,
        unit: m.EvidenceUnit,
        text: str,
        start_line: int,
        end_line: int,
        total: int,
        size: int,
    ) -> None:
        self.projected.append(
            _dc.replace(
                unit,
                content=text,
                content_range=m.EvidenceLineRange(
                    start_line=start_line,
                    end_line=end_line,
                    total_lines=total,
                ),
            )
        )
        self.used += size

    def omit(
        self,
        unit: m.EvidenceUnit,
        first: int,
        last: int,
        total: int,
        hits: int,
    ) -> None:
        self.omissions.append(
            f"excerpt omitted {unit.evidence_ref.locator} lines "
            f"{first}-{last} of {total} ({hits} hits unexamined)"
        )
        self.total_ranges += 1
        self.total_omitted_hits += hits


def _anchor_hits(lines: list[str], anchors: tuple[str, ...]) -> list[int]:
    """Line numbers containing any anchor, matched literally as discovery does."""
    hits: list[int] = []
    for index, line in enumerate(lines, start=1):
        for anchor in anchors:
            if anchor and anchor in line:
                hits.append(index)
                break
    return hits


def _project_structural_span(
    projection: _Projection,
    unit: m.EvidenceUnit,
    content: str,
    lines: list[str],
    start: int,
    end: int,
) -> None:
    """Deliver an exact provider structural span, or name what it omitted."""
    total = len(lines)
    if start == 1 and end == total:
        size = len(content.encode("utf-8"))
        if projection.fits(size):
            projection.projected.append(unit)
            projection.used += size
            return
    excerpt_text = "\n".join(lines[start - 1 : end])
    if content.endswith("\n") and end == total:
        excerpt_text += "\n"
    size = len(excerpt_text.encode("utf-8")) + _range_meta(start, end, total)
    if projection.fits(size):
        projection.deliver(unit, excerpt_text, start, end, total, size)
        if start > 1:
            projection.omit(unit, 1, start - 1, total, 0)
        if end < total:
            projection.omit(unit, end + 1, total, total, 0)
        return
    first_line = lines[start - 1] + (
        "\n" if content.endswith("\n") and start == end == total else ""
    )
    if start == end or not projection.fits(
        len(first_line.encode("utf-8")) + _range_meta(start, start, total)
    ):
        projection.requirements.append(
            projection.requirement.build(unit, start, end, total)
        )
    projection.omit(unit, start, end, total, end - start + 1)


def _project_whole_unit(
    projection: _Projection,
    unit: m.EvidenceUnit,
    content: str,
) -> None:
    """Deliver an unhit unit whole when it fits; else name it as missing."""
    size = len(content.encode("utf-8"))
    if projection.fits(size):
        projection.projected.append(unit)
        projection.used += size
        return
    total = len(content.splitlines() or [""])
    projection.omit(unit, 1, total, total, 0)
    # Evidence omitted in full is still a named delivery requirement, even when
    # it has multiple lines and no grounded hit. It must not disappear from the
    # task.
    projection.requirements.append(projection.requirement.build(unit, 1, total, total))


def _project_enclosing_range(
    projection: _Projection,
    unit: m.EvidenceUnit,
    content: str,
    lines: list[str],
    hits: list[int],
) -> bool:
    """Deliver the one contiguous range enclosing every hit, if it fits."""
    total = len(lines)
    first, last = hits[0], hits[-1]
    excerpt_text = "\n".join(lines[first - 1 : last])
    if content.endswith("\n") and last == total:
        excerpt_text += "\n"
    size = len(excerpt_text.encode("utf-8")) + _range_meta(first, last, total)
    if not projection.fits(size):
        return False
    projection.deliver(unit, excerpt_text, first, last, total, size)
    if first > 1:
        projection.omit(unit, 1, first - 1, total, 0)
    if last < total:
        projection.omit(unit, last + 1, total, total, 0)
    return True


def _project_hit_prefix(
    projection: _Projection,
    unit: m.EvidenceUnit,
    content: str,
    lines: list[str],
    hits: list[int],
) -> None:
    """Deliver the maximal prefix of hits in line order that fits."""
    total = len(lines)
    first, last = hits[0], hits[-1]
    kept_last = first
    for hit in hits:
        trial = "\n".join(lines[first - 1 : hit])
        if content.endswith("\n") and hit == total:
            trial += "\n"
        trial_size = len(trial.encode("utf-8")) + _range_meta(first, hit, total)
        if not projection.fits(trial_size):
            break
        kept_last = hit
    excerpt_text = "\n".join(lines[first - 1 : kept_last])
    if content.endswith("\n") and kept_last == total:
        excerpt_text += "\n"
    size = len(excerpt_text.encode("utf-8")) + _range_meta(first, kept_last, total)
    if not excerpt_text or not projection.fits(size):
        first_line = lines[first - 1] + (
            "\n" if content.endswith("\n") and first == total else ""
        )
        if first == last or not projection.fits(
            len(first_line.encode("utf-8")) + _range_meta(first, first, total)
        ):
            projection.requirements.append(
                projection.requirement.build(unit, first, last, total)
            )
        projection.omit(unit, first, last, total, len(hits))
        return
    projection.deliver(unit, excerpt_text, first, kept_last, total, size)
    omitted = len([hit for hit in hits if hit > kept_last])
    if omitted or kept_last < last or first > 1 or last < total:
        projection.omit(unit, kept_last + 1, last, total, omitted)


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
    """Bounded excerpt delivery ([design note I](docs/design-references.md#i) S7 §5.7).

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
    anchors = _select_anchors(subject, question_terms)
    spans = structural_spans or {}
    projection = _Projection(
        delivery_budget=delivery_budget,
        requirement=_DeliveryRequirement(subject_id=subject.subject_id),
    )
    for unit in units:
        content = unit.content
        lines = content.splitlines() or [""]
        total = len(lines)
        span = spans.get(unit.evidence_ref.locator)
        start, end = (0, 0) if span is None else (max(1, span[0]), min(total, span[1]))
        if span is not None and start <= end:
            _project_structural_span(projection, unit, content, lines, start, end)
            continue
        hits = _anchor_hits(lines, anchors)
        if not hits:
            _project_whole_unit(projection, unit, content)
            continue
        if _project_enclosing_range(projection, unit, content, lines, hits):
            continue
        _project_hit_prefix(projection, unit, content, lines, hits)
    # Cap at 8 coalesced range lines plus one summary line.
    kept_omissions = projection.omissions[:8]
    truncated = len(projection.omissions) - len(kept_omissions)
    summary = (
        f"excerpt omissions: {projection.total_omitted_hits} hits in "
        f"{projection.total_ranges} ranges"
        + (f", +{truncated} further ranges truncated" if truncated else "")
    )
    if projection.omissions or not projection.projected:
        kept_omissions = (*kept_omissions, summary)
    return (
        tuple(projection.projected),
        tuple(kept_omissions),
        tuple(projection.requirements),
    )
