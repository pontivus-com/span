"""Bounded discovery of saved understanding (plan §4.1).

Discovery returns candidate identities and explicit match reasons. It never
asserts applicability, merges identities, or claims repository-wide absence.
Scope association and lexical overlap are retrieval signals only. Traversal is
paged so one call never loads the whole repository: the continuation token is
the next deterministic scan position, and the explicit bound reports whether
unscanned rows remain.
"""

from __future__ import annotations

import re as _re

from span.core import model as m
from span.ports.lifecycle import LifecycleStorePort

__all__ = ["DiscoveryService"]

_TOKEN = _re.compile(r"[a-z0-9_]{2,}")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _scope_associated(requested: m.EvidenceScope, candidate: m.EvidenceScope) -> bool:
    if not (requested.paths or requested.evidence_refs):
        return False
    if not (candidate.paths or candidate.evidence_refs):
        return False
    for ref in requested.evidence_refs:
        if any(item.locator == ref.locator for item in candidate.evidence_refs):
            return True
        if m.evidence_scope_allows(ref.locator, candidate):
            return True
    for ref in candidate.evidence_refs:
        if m.evidence_scope_allows(ref.locator, requested):
            return True
    for path in candidate.paths:
        if m.evidence_scope_allows(path, requested):
            return True
    for path in requested.paths:
        if m.evidence_scope_allows(path, candidate):
            return True
    return False


def _statement(content: m.ConclusionContent) -> str:
    if isinstance(content, m.SupportedConclusion):
        return content.statement
    return ""


def _decode_token(token: str | None) -> int:
    if token is None:
        return 0
    prefix = "dsp:"
    if not token.startswith(prefix):
        raise ValueError("invalid discovery page token")
    try:
        offset = int(token[len(prefix) :])
    except ValueError:
        raise ValueError("invalid discovery page token") from None
    if offset < 0:
        raise ValueError("invalid discovery page token")
    return offset


def _encode_token(offset: int) -> str:
    return f"dsp:{offset}"


class DiscoveryService:
    """Find saved understanding by exact scope association or wording."""

    def __init__(self, *, store: LifecycleStorePort) -> None:
        self._store = store

    def discover(
        self,
        repository_id: str,
        scope: m.EvidenceScope,
        question: str | None,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.UnderstandingDiscovery:
        self._store.require_repository(repository_id)
        question_tokens = _tokens(question or "")
        limit = bounds.max_results
        page_size = max(limit, 1)
        offset = _decode_token(page_token)
        candidates: list[m.UnderstandingCandidate] = []
        truncated = False
        next_token: str | None = None
        scanned = 0
        while True:
            page = self._store.list_understandings(
                repository_id, limit=page_size, offset=offset
            )
            if not page:
                break
            stop = False
            for index, understanding in enumerate(page):
                scanned += 1
                version = self._store.get_version(
                    understanding.understanding_id.value,
                    understanding.current_version.value,
                )
                current = self._store.get_version_conclusions(
                    understanding.understanding_id.value,
                    understanding.current_version.value,
                )
                associated = _scope_associated(scope, understanding.scope)
                text = " ".join(
                    [version.question] + [_statement(item.content) for item in current]
                )
                overlap = question_tokens & _tokens(text)
                if not associated and not overlap:
                    continue
                matched = tuple(
                    m.ConclusionRevisionRef(
                        understanding_id=item.understanding_id,
                        conclusion_id=item.conclusion_id,
                        revision=item.revision,
                    )
                    for item in current
                    if question_tokens & _tokens(_statement(item.content))
                )
                if associated and not matched:
                    matched = version.conclusions
                reasons: list[str] = []
                if associated:
                    reasons.append("scope-associated")
                if overlap:
                    reasons.append("terms: " + ", ".join(sorted(overlap)))
                candidates.append(
                    m.UnderstandingCandidate(
                        understanding_id=understanding.understanding_id,
                        current_version=understanding.current_version,
                        question=version.question,
                        scope=understanding.scope,
                        matched_conclusions=matched,
                        match_reasons=tuple(reasons),
                        lexical_overlap=len(overlap),
                        scope_associated=associated,
                    )
                )
                if len(candidates) >= limit:
                    stop = True
                    next_offset = offset + index + 1
                    break
            if stop:
                truncated = True
                next_token = _encode_token(next_offset)
                break
            if len(page) < page_size:
                break
            offset += len(page)
            if scanned and len(candidates) == 0 and offset == 0:
                break
        kept = tuple(candidates[:limit])
        if not kept:
            if not (scope.paths or scope.evidence_refs):
                limit_reason = (
                    "no saved understanding matched this wording; provide a "
                    "concrete scope to search associations; no "
                    "repository-wide absence is claimed"
                )
            elif question:
                limit_reason = (
                    "no saved understanding is associated with this scope or "
                    "wording; the repository was not judged absent"
                )
            else:
                limit_reason = (
                    "provide a concrete scope or question; no "
                    "repository-wide absence is claimed"
                )
        elif truncated:
            limit_reason = "result bound reached; continue with the page token"
        else:
            limit_reason = None
        return m.UnderstandingDiscovery(
            candidates=kept,
            bound_info=m.BoundInfo(
                requested_max_results=limit,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=truncated,
                truncated_category="discovery" if truncated else None,
                continuation_token=next_token,
            ),
            limit_reason=limit_reason,
        )
