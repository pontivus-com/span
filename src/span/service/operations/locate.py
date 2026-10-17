"""Span service structural locate operation (Addendum F §4.1).

Read-only structural find/outline/member-listing over the existing
ports. No semantic interpretation, no persistence, no continuations:
every call returns a complete answer or a typed error. Arbitrary
content search stays out (agent grep); structure is exposed as
structure, never as semantic claims.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralSource
from span.service.bounds import resolve_bounds as _resolve_bounds
from span.service.discovery import enumerate_target_inventory
from span.service.repository import _is_initialized
from span.service.requests import SemanticStructuralLocateRequest
from span.shell import paging as _paging

__all__ = ["locate"]


def _listing_version(structural: StructuralSource, repository_id: str) -> str:
    """Listing version binding locate page tokens (Addendum F §4.3)."""
    return structural.repository_state(repository_id).state_fingerprint


def locate(
    request: SemanticStructuralLocateRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> m.StructuralLocateResult:
    """Execute one structural locate (read-only, no persistence)."""
    if not _is_initialized(request.repository_id, store=store):
        raise ValueError(
            f"repository not initialized: {request.repository_id}"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    mode = request.mode
    if mode is m.StructuralLocateMode.SYMBOL:
        if not request.query or not request.query.strip():
            raise ValueError("locate SYMBOL requires a non-empty query")
        if request.target is None:
            allowed = None
        else:
            allowed = request.target
        return _locate_symbol(
            request.repository_id, request.query, request.match,
            bounds, request.page_token, allowed, structural=structural,
        )
    if mode is m.StructuralLocateMode.FILE_OUTLINE:
        if not request.query or not request.query.strip():
            raise ValueError("locate FILE_OUTLINE requires a file locator")
        if request.target is not None:
            raise ValueError("locate FILE_OUTLINE takes no target scope")
        if request.match is not m.StructuralLocateMatch.EXACT:
            raise ValueError("locate match modes apply to SYMBOL only")
        return _locate_outline(
            request.repository_id, request.query, bounds,
            request.page_token, structural=structural,
        )
    if mode is m.StructuralLocateMode.TARGET_MEMBERS:
        if request.target is None:
            raise ValueError("locate TARGET_MEMBERS requires a target scope")
        if request.query is not None:
            raise ValueError("locate TARGET_MEMBERS takes no query")
        if request.match is not m.StructuralLocateMatch.EXACT:
            raise ValueError("locate match modes apply to SYMBOL only")
        return _locate_members(
            request.repository_id, request.target, bounds,
            request.page_token, structural=structural, evidence=evidence,
        )
    raise ValueError(f"unknown locate mode: {mode}")


def _locate_symbol(
    repository_id: str,
    query: str,
    match: m.StructuralLocateMatch,
    bounds: m.QueryBounds,
    page_token: str | None,
    scope: m.EvidenceScope | None,
    *,
    structural: StructuralSource,
) -> m.StructuralLocateResult:
    try:
        page = structural.search_symbols(
            repository_id, query, match, bounds, page_token, scope=scope
        )
    except StaleContinuationError:
        raise
    except ValueError as exc:
        raise ValueError(f"locate search failed: {exc}") from None
    entries: list[m.StructuralLocateEntry] = []
    for hit in page.items:
        subject = hit.candidate.subject.subject_id
        locator = subject.canonical_locator
        refs = structural.locations(
            repository_id, subject, bounds
        ).items
        if not refs:
            # Defensive: a search hit always has a location; without
            # evidence there is no entry to build, and inventing one is
            # worse than omitting it.
            continue
        ref = refs[0].location
        entries.append(
            m.StructuralLocateEntry(
                evidence_ref=ref,
                content_fingerprint=ref.revision_or_fingerprint or "",
                subject=subject,
                span_text=hit.span_text,
                signature_text=hit.signature_text,
            )
        )
    state = structural.repository_state(repository_id)
    return m.StructuralLocateResult(
        entries=tuple(entries),
        repository_state=state,
        bound_info=page.bound_info,
        stale_omitted=page.stale_omitted,
        coverage=page.coverage,
        coverage_detail=page.coverage_detail,
    )


def _locate_outline(
    repository_id: str,
    locator: str,
    bounds: m.QueryBounds,
    page_token: str | None,
    *,
    structural: StructuralSource,
) -> m.StructuralLocateResult:
    try:
        page = structural.file_outline(
            repository_id, locator, bounds, page_token
        )
    except StaleContinuationError:
        raise
    except ValueError as exc:
        raise ValueError(f"locate outline failed: {exc}") from None
    entries: list[m.StructuralLocateEntry] = []
    for member in page.items:
        subject = member.subject.subject_id
        refs = structural.locations(
            repository_id, subject, bounds
        ).items
        if not refs:
            continue
        ref = refs[0].location
        entries.append(
            m.StructuralLocateEntry(
                evidence_ref=ref,
                content_fingerprint=ref.revision_or_fingerprint or "",
                subject=subject,
                span_text=member.span_text,
                signature_text=member.signature_text,
            )
        )
    state = structural.repository_state(repository_id)
    return m.StructuralLocateResult(
        entries=tuple(entries),
        repository_state=state,
        bound_info=page.bound_info,
        stale_omitted=page.stale_omitted,
        coverage=page.coverage,
        coverage_detail=page.coverage_detail,
    )


def _locate_members(
    repository_id: str,
    scope: m.EvidenceScope,
    bounds: m.QueryBounds,
    page_token: str | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
) -> m.StructuralLocateResult:
    try:
        items = enumerate_target_inventory(
            repository_id, scope, evidence=evidence, bounds=bounds
        )
    except ValueError as exc:
        raise ValueError(f"target inventory unverifiable: {exc}") from None
    version = _listing_version(structural, repository_id)
    try:
        offset = _paging.parse_versioned_token(page_token, version=version)
    except ValueError as exc:
        if str(exc).startswith("stale listing continuation"):
            raise StaleContinuationError(str(exc)) from None
        raise ValueError(f"locate members failed: {exc}") from None
    window = items[offset:offset + bounds.max_results]
    remaining = len(items) - (offset + len(window))
    truncated = remaining > 0
    bound_info = m.BoundInfo(
        requested_max_results=bounds.max_results,
        requested_max_depth=0,
        returned_results=len(window),
        truncated=truncated,
        truncated_category="members" if truncated else None,
        continuation_token=(
            _paging.format_versioned_token(version, offset + len(window))
            if truncated else None
        ),
    )
    # One outline per distinct file: subject + transcribed span/signature
    # without inventing provider grammar at this layer. Outlines are
    # consumed to exhaustion — a first page alone could miss the file
    # node's own entry in a large file.
    outlines: dict[str, dict[str, m.StructuralOutlineEntry]] = {}
    for item in window:
        path = item.evidence_ref.locator
        if path not in outlines:
            collected: dict[str, m.StructuralOutlineEntry] = {}
            token: str | None = None
            seen_tokens: set[str | None] = {None}
            while True:
                try:
                    outline = structural.file_outline(
                        repository_id, path, bounds, token
                    )
                except StaleContinuationError:
                    raise
                except ValueError as exc:
                    raise ValueError(
                        f"locate members failed: {exc}"
                    ) from None
                for entry in outline.items:
                    collected.setdefault(
                        entry.subject.subject_id.canonical_locator, entry
                    )
                if not outline.bound_info.truncated:
                    break
                token = outline.bound_info.continuation_token
                if token in seen_tokens:
                    break
                seen_tokens.add(token)
            outlines[path] = collected
    report = structural.verify_files(
        repository_id,
        tuple(item.evidence_ref.locator for item in window),
    )
    stale_set = set(report.stale_files)
    entries: list[m.StructuralLocateEntry] = []
    stale_omitted = 0
    for item in window:
        loc = item.evidence_ref.locator
        if loc in stale_set:
            stale_omitted += 1
            continue
        member = outlines[loc].get(loc)
        entries.append(
            m.StructuralLocateEntry(
                evidence_ref=item.evidence_ref,
                content_fingerprint=item.content_fingerprint,
                subject=(
                    member.subject.subject_id if member is not None
                    else None
                ),
                span_text=member.span_text if member is not None else None,
                signature_text=(
                    member.signature_text if member is not None else None
                ),
            )
        )
    state = structural.repository_state(repository_id)
    return m.StructuralLocateResult(
        entries=tuple(entries),
        repository_state=state,
        bound_info=bound_info,
        stale_omitted=stale_omitted,
        coverage=report.coverage,
        coverage_detail=report.coverage_detail,
    )
