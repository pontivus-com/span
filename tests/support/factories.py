"""Canonical test factories: one definition per concept (plan §1.3, D7).

Tests describe the fixture they need; they do not re-implement it. Each
factory here is the single definition of one test concept, so a change to a
fixture shape happens once. Test modules import these (optionally through
``functools.partial`` for their repository or file map) instead of defining
per-file copies.
"""

from __future__ import annotations

from span.core import model as m
from span.shell.structural.memory import fingerprint_content

__all__ = [
    "query_bounds",
    "subject_id",
    "evidence_ref",
]

REPOSITORY_ID = "repo-1"

_DOCUMENT_SUFFIXES = (".md", ".rst", ".txt", ".yaml", ".yml")


def query_bounds(**overrides: object) -> m.QueryBounds:
    """The standard bounded query, with named overrides."""
    base: dict[str, object] = {
        "max_results": 50,
        "max_depth": 5,
        "max_subjects": 8,
        "max_evidence_units": 24,
        "max_evidence_bytes": 96_000,
        "max_candidate_claims": 64,
        "max_candidate_relationships": 64,
    }
    base.update(overrides)
    return m.QueryBounds(**base)  # type: ignore[arg-type]


def subject_id(
    locator: str = "src/a.py",
    kind: m.SubjectKind = m.SubjectKind.COMPONENT,
    *,
    repository_id: str = REPOSITORY_ID,
) -> m.SubjectId:
    """One canonical subject identity."""
    return m.SubjectId(
        repository_id=repository_id,
        subject_kind=kind,
        canonical_locator=locator,
    )


def evidence_ref(
    path: str = "src/a.py",
    *,
    repository_id: str = REPOSITORY_ID,
    files: dict[str, str] | None = None,
    fingerprint: str | None = None,
    span: str | None = None,
    evidence_id: str | None = None,
    source_kind: m.EvidenceSourceKind | None = None,
) -> m.EvidenceRef:
    """One canonical evidence reference.

    Fingerprints come from the file map when supplied; otherwise the stable
    ``fp-1`` marker keeps tests that do not exercise freshness independent of
    fixture text.
    """
    if evidence_id is None:
        evidence_id = f"ev-{path}"
    if fingerprint is None:
        fingerprint = (
            fingerprint_content(files[path])
            if files is not None and path in files
            else "fp-1"
        )
    if source_kind is None:
        source_kind = (
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(_DOCUMENT_SUFFIXES)
            else m.EvidenceSourceKind.SOURCE_CODE
        )
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(evidence_id),
        repository_id=repository_id,
        source_kind=source_kind,
        locator=path,
        revision_or_fingerprint=fingerprint,
        section_or_span=span,
    )
