"""Graft structural provider (plan Phase 2.2, against §5.2 only).

Maps Graft's structural index (``graft/.graph/wiring.json``: nodes with
repo-relative ids, spans, signatures, body hashes; directed edges with
relations) onto the StructuralSource port. Structure-to-structure only:
no semantic interpretation, no authority, no meaning assignment. The
semantic model is not shaped around Graft (bootstrap §18); unknown
Graft node kinds or relations raise explicit typed errors instead of
being guessed into the canonical vocabulary.

Suitability record (plan Phase 2.1, license MIT verified Phase 0.4):

- generic-port fit: all five §5.2 operations served from wiring.json
  plus git (revision/dirty) plus target-repo file reads (fallback
  fingerprints);
- independence: separately installable npm package, no Pontivus code;
- build policy: this module never builds. ``ensure_graft_built`` runs
  ``graft build`` and is called only from explicit admin paths
  (structural-source factory used by initialization). Queries and hooks
  never trigger builds (I-27).
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import pathlib as _pathlib
import shutil as _shutil
import subprocess as _subprocess

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging
from span.shell.structural.memory import (
    evidence_kind_for_path,
    fingerprint_content,
)

__all__ = [
    "GraftUnavailableError",
    "GraftShapeError",
    "GraftVocabularyError",
    "GraftStructuralSource",
    "ensure_graft_built",
    "wiring_path_for",
    "NODE_SUBJECT_KIND",
    "RELATION_EDGE_KIND",
]


class GraftUnavailableError(Exception):
    """Graft CLI or its built index is unavailable (feeds §7 transport
    policy as provider-unavailable; never auto-remedied in queries)."""


class GraftShapeError(ValueError):
    """wiring.json does not match the expected structural contract."""


class GraftVocabularyError(ValueError):
    """A Graft node kind or edge relation has no closed mapping entry.
    Raised instead of guessing canonical semantics."""


#: Closed node-kind mapping (structural only). Files split by suffix
#: rule (shared with the deterministic source); symbols are code.
NODE_SUBJECT_KIND: dict[str, m.SubjectKind] = {
    "file": m.SubjectKind.COMPONENT,
    "function": m.SubjectKind.CODE_SYMBOL,
    "class": m.SubjectKind.CODE_SYMBOL,
    "method": m.SubjectKind.CODE_SYMBOL,
    "interface": m.SubjectKind.CODE_SYMBOL,
    "type": m.SubjectKind.CODE_SYMBOL,
}

#: Closed edge-relation mapping (structural only).
RELATION_EDGE_KIND: dict[str, m.StructuralEdgeKind] = {
    "contains": m.StructuralEdgeKind.DEFINES,
    "imports": m.StructuralEdgeKind.IMPORTS,
    "calls": m.StructuralEdgeKind.CALLS,
    "references": m.StructuralEdgeKind.REFERENCES,
    "depends_on": m.StructuralEdgeKind.DEPENDS_ON,
}

_DOCUMENT_SUFFIXES = (".md", ".rst", ".txt")


def wiring_path_for(repo_path: _pathlib.Path) -> _pathlib.Path:
    """Location of the built Graft structural index for a repository."""
    return repo_path / "graft" / ".graph" / "wiring.json"


def ensure_graft_built(repo_path: _pathlib.Path) -> None:
    """Run ``graft build`` in the target repo when no index exists.

    Explicit-admin-paths only (initialization factory). Never called
    from queries or hooks.
    """
    if wiring_path_for(repo_path).is_file():
        return
    if _shutil.which("graft") is None:
        raise GraftUnavailableError(
            f"graft CLI not found and no index at {wiring_path_for(repo_path)}"
        )
    completed = _subprocess.run(
        ["graft", "build"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0 or not wiring_path_for(repo_path).is_file():
        raise GraftUnavailableError(
            f"graft build failed in {repo_path}: "
            f"{completed.stderr.strip()[-500:]}"
        )


def _git_revision(repo_path: _pathlib.Path) -> tuple[str | None, bool]:
    try:
        head = _subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if head.returncode != 0:
            return None, False
        status = _subprocess.run(
            ["git", "-C", str(repo_path), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return head.stdout.strip(), bool(status.stdout.strip())
    except (OSError, _subprocess.SubprocessError):
        return None, False


class GraftStructuralSource:
    """StructuralSource over a built Graft index (read-only)."""

    def __init__(
        self,
        repository_id: str,
        repo_path: str | _pathlib.Path,
        wiring: dict | None = None,
    ) -> None:
        self._repository_id = repository_id
        self._repo_path = _pathlib.Path(repo_path)
        if wiring is None:
            path = wiring_path_for(self._repo_path)
            if not path.is_file():
                raise GraftUnavailableError(
                    f"no Graft index at {path}; build it explicitly "
                    f"(never auto-built in queries)"
                )
            try:
                wiring = _json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise GraftShapeError(f"cannot read wiring.json: {exc}") from exc
        self._nodes = self._parse_nodes(wiring)
        self._edges = self._parse_edges(wiring)

    # -- parsing ----------------------------------------------------------

    def _parse_nodes(self, wiring: dict) -> dict[str, dict]:
        try:
            raw_nodes = wiring["nodes"]
        except (KeyError, TypeError) as exc:
            raise GraftShapeError("wiring.json has no nodes list") from exc
        if not isinstance(raw_nodes, list):
            raise GraftShapeError("wiring.json nodes is not a list")
        nodes: dict[str, dict] = {}
        for node in raw_nodes:
            try:
                node_id = node["id"]
                kind = node["kind"]
                path = node["path"]
            except (KeyError, TypeError) as exc:
                raise GraftShapeError(
                    f"node missing id/kind/path: {node!r}"
                ) from exc
            if kind not in NODE_SUBJECT_KIND:
                raise GraftVocabularyError(f"unknown Graft node kind: {kind}")
            nodes[node_id] = node
        return nodes

    def _parse_edges(self, wiring: dict) -> list[tuple[str, str, str]]:
        raw_edges = wiring.get("edges", [])
        if not isinstance(raw_edges, list):
            raise GraftShapeError("wiring.json edges is not a list")
        edges: list[tuple[str, str, str]] = []
        for edge in raw_edges:
            try:
                source, target, relation = (
                    edge["source"],
                    edge["target"],
                    edge["relation"],
                )
            except (KeyError, TypeError) as exc:
                raise GraftShapeError(
                    f"edge missing source/target/relation: {edge!r}"
                ) from exc
            if relation not in RELATION_EDGE_KIND:
                raise GraftVocabularyError(
                    f"unknown Graft edge relation: {relation}"
                )
            edges.append((source, target, relation))
        return edges

    # -- mapping ------------------------------------------------------------

    def _subject_kind_of(self, node: dict) -> m.SubjectKind:
        if node["kind"] == "file" and str(node["path"]).endswith(
            _DOCUMENT_SUFFIXES
        ):
            return m.SubjectKind.DOCUMENT
        return NODE_SUBJECT_KIND[node["kind"]]

    def _subject_id_of(self, node_id: str) -> m.SubjectId:
        node = self._nodes[node_id]
        return m.SubjectId(
            repository_id=self._repository_id,
            subject_kind=self._subject_kind_of(node),
            canonical_locator=node_id,
        )

    def _to_subject(self, node_id: str) -> m.Subject:
        node = self._nodes[node_id]
        return m.Subject(
            subject_id=self._subject_id_of(node_id),
            display_name=str(node.get("name") or node_id),
            declared_kind=None,
        )

    def fingerprint_for(self, path: str, body_hash: str | None) -> str | None:
        """Body hash preferred; target file content fallback; None when
        neither is available (downstream classifies UNVERIFIABLE)."""
        if body_hash:
            return body_hash
        try:
            return fingerprint_content(
                (self._repo_path / path).read_text(encoding="utf-8")
            )
        except OSError:
            return None

    def _evidence_ref(self, node_id: str) -> m.EvidenceRef:
        node = self._nodes[node_id]
        path = str(node["path"])
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=evidence_kind_for_path(path),
            locator=path,
            revision_or_fingerprint=self.fingerprint_for(
                path,
                node.get("body_hash") if isinstance(node.get("body_hash"), str) else None,
            ),
            section_or_span=(
                str(node["span"]) if node.get("span") else None
            ),
        )

    def _to_edge(
        self, source: str, target: str, relation: str
    ) -> m.StructuralEdge:
        return m.StructuralEdge(
            source=self._subject_id_of(source),
            kind=RELATION_EDGE_KIND[relation],
            target=self._subject_id_of(target),
            evidence=self._evidence_ref(source),
        )

    def _state_fingerprint(self) -> str:
        parts = sorted(
            f"{node_id}:{node.get('body_hash') or ''}"
            for node_id, node in self._nodes.items()
        )
        return _hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    # -- StructuralSource port --------------------------------------------

    def repository_state(self, repository_id: str) -> m.RepositoryState:
        self._check_repository(repository_id)
        import datetime as _datetime

        revision, dirty = _git_revision(self._repo_path)
        return m.RepositoryState(
            repository_id=self._repository_id,
            revision_id=revision,
            dirty=dirty,
            state_fingerprint=self._state_fingerprint(),
            observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        )

    def resolve_subject(
        self,
        repository_id: str,
        selector: m.SubjectSelector,
        bounds: m.QueryBounds,
    ) -> m.SubjectResolution:
        self._check_repository(repository_id)
        if selector.exact_subject_id is not None:
            locator = selector.exact_subject_id.canonical_locator
            matches = [
                (locator, m.CandidateRankBasis.EXACT_LOCATOR)
                for locator in [locator]
                if locator in self._nodes
            ]
        else:
            matches = self._match_name(selector)
        order = {
            m.CandidateRankBasis.EXACT_LOCATOR: 0,
            m.CandidateRankBasis.EXACT_DECLARATION: 1,
            m.CandidateRankBasis.EXACT_NAME: 2,
            m.CandidateRankBasis.PARTIAL_NAME: 3,
            m.CandidateRankBasis.STRUCTURAL_PROXIMITY: 4,
        }
        matches.sort(key=lambda x: (order[x[1]], x[0]))
        candidates = tuple(
            m.SubjectCandidate(
                subject=self._to_subject(locator),
                structural_evidence=(),
                rank_basis=rank,
            )
            for locator, rank in matches
        )
        if not candidates:
            ambiguity = m.ResolutionAmbiguity.NOT_FOUND
        elif len(candidates) == 1:
            ambiguity = m.ResolutionAmbiguity.RESOLVED
        else:
            ambiguity = m.ResolutionAmbiguity.AMBIGUOUS
        kept = candidates[: bounds.max_subjects]
        return m.SubjectResolution(
            candidates=kept,
            ambiguity=ambiguity,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(candidates),
                truncated_category=(
                    "candidates" if len(kept) < len(candidates) else None
                ),
                continuation_token=None,
            ),
        )

    def _match_name(
        self, selector: m.SubjectSelector
    ) -> list[tuple[str, m.CandidateRankBasis]]:
        query = selector.name_or_locator
        if not query:
            return []
        # §4.2 identity: exact node id is identity, not a ranking input.
        exact = [
            (node_id, m.CandidateRankBasis.EXACT_LOCATOR)
            for node_id in self._nodes
            if query == node_id
        ]
        if exact:
            return exact
        matches: list[tuple[str, m.CandidateRankBasis]] = []
        for node_id, node in self._nodes.items():
            name = str(node.get("name") or "")
            if query == name and query:
                rank = (
                    m.CandidateRankBasis.EXACT_DECLARATION
                    if node["kind"] != "file"
                    else m.CandidateRankBasis.EXACT_NAME
                )
                matches.append((node_id, rank))
                continue
            basename = node_id.split("#")[-1].rsplit("/", 1)[-1]
            if query == basename:
                matches.append((node_id, m.CandidateRankBasis.EXACT_NAME))
            elif query in name or query in node_id:
                matches.append((node_id, m.CandidateRankBasis.PARTIAL_NAME))
        return matches

    def locations(
        self,
        repository_id: str,
        subject: m.SubjectId,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralLocationPage:
        self._check_repository(repository_id)
        node = self._nodes.get(subject.canonical_locator)
        items: tuple[m.StructuralLocation, ...] = ()
        if node is not None:
            items = (
                m.StructuralLocation(
                    subject=subject,
                    location=self._evidence_ref(subject.canonical_locator),
                ),
            )
        kept, bound_info = _paging.paginate(
            items, bounds.max_results, "locations", page_token
        )
        return m.StructuralLocationPage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )

    def edges(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralEdgePage:
        self._check_repository(repository_id)
        locator = subject.canonical_locator
        kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
        found: list[m.StructuralEdge] = []
        for source, target, relation in self._edges:
            edge = self._to_edge(source, target, relation)
            if edge.kind not in kinds:
                continue
            if direction in (
                StructuralDirection.DOWNSTREAM,
                StructuralDirection.BOTH,
            ) and source == locator:
                found.append(edge)
            elif direction in (
                StructuralDirection.UPSTREAM,
                StructuralDirection.BOTH,
            ) and target == locator:
                found.append(edge)
        found.sort(
            key=lambda e: (
                e.kind.value,
                e.source.canonical_locator,
                e.target.canonical_locator,
            )
        )
        kept, bound_info = _paging.paginate(
            tuple(found), bounds.max_results, "edges", page_token
        )
        return m.StructuralEdgePage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )

    def reach(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        max_depth: int,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralReachPage:
        self._check_repository(repository_id)
        limit = min(max_depth, bounds.max_depth)
        seen = {subject.canonical_locator}
        via: dict[str, m.StructuralEdge | None] = {
            subject.canonical_locator: None
        }
        frontier = [subject.canonical_locator]
        nodes: list[m.StructuralReachNode] = []
        for depth in range(1, limit + 1):
            nxt: list[str] = []
            for current in frontier:
                current_id = m.SubjectId(
                    repository_id=self._repository_id,
                    subject_kind=self._subject_kind_of(self._nodes[current]),
                    canonical_locator=current,
                )
                page = self.edges(
                    repository_id,
                    current_id,
                    edge_kinds,
                    direction,
                    bounds,
                )
                for edge in page.items:
                    other = (
                        edge.target.canonical_locator
                        if edge.source.canonical_locator == current
                        else edge.source.canonical_locator
                    )
                    if other not in seen and other in self._nodes:
                        seen.add(other)
                        via[other] = edge
                        nxt.append(other)
            nxt.sort()
            for locator in nxt:
                nodes.append(
                    m.StructuralReachNode(
                        subject=self._subject_id_of(locator),
                        depth=depth,
                        via=via[locator],
                    )
                )
            frontier = nxt
            if not frontier:
                break
        kept, bound_info = _paging.paginate(
            tuple(nodes), bounds.max_results, "reach", page_token,
            requested_max_depth=limit,
        )
        return m.StructuralReachPage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )
