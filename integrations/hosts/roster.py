"""Host-side structural territory proposals (addendum D §9, ROSTER-D-01).

Orientation candidates for setup sessions: bounded structural
neighborhoods expanded from caller-supplied seeds, merged on shared
members, presented WITHOUT ranking, scores, or importance. The host
agent selects scopes using evidence and objectives; centrality never
decides importance (D §16 non-decision); there is no fixed-count
roster invariant.

Boundaries (row ROSTER-D-01):

- structural port only: ``reach`` reads, nothing else;
- no semantic output persisted — this module writes nothing anywhere;
- no whole-repository crawl: expansion starts from explicit seeds and
  is bounded by ``bounds.max_depth`` (canonical bounds, no new
  number); empty seeds yield an empty roster, never a hunt;
- no meaning inferred: members, entry points (proven indegree-zero
  within the territory via exact upstream reads), and observed edge
  kinds are topological facts; no filename, keyword, adjacency, or
  degree judgment;
- deterministic order (member locator), never size- or degree-ordered.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core import model as m
from span.ports.structural import StructuralDirection, StructuralSource

__all__ = [
    "Territory",
    "Roster",
    "propose_territories",
]


@_dataclass(frozen=True)
class Territory:
    """One candidate territory: topological facts, no judgment."""

    members: tuple[m.SubjectId, ...] = ()
    entry_points: tuple[m.SubjectId, ...] = ()
    edge_kinds: tuple[m.StructuralEdgeKind, ...] = ()

    def __post_init__(self) -> None:
        entered = {e.canonical_locator for e in self.entry_points}
        membered = {s.canonical_locator for s in self.members}
        if not entered <= membered:
            raise ValueError("entry points must be territory members")


@_dataclass
class _UnionFind:
    parent: dict[str, str] = _field(default_factory=dict)

    def find(self, key: str) -> str:
        root = self.parent.setdefault(key, key)
        while self.parent[root] != root:
            self.parent[root] = self.parent[self.parent[root]]
            root = self.parent[root]
        return root

    def union(self, left: str, right: str) -> None:
        self.parent[self.find(left)] = self.find(right)


@_dataclass(frozen=True)
class Roster:
    """Proposed territories in deterministic locator order."""

    territories: tuple[Territory, ...] = ()


def propose_territories(
    repository_id: str,
    seeds: tuple[m.SubjectId, ...],
    *,
    structural: StructuralSource,
    bounds: m.QueryBounds,
    edge_kinds: tuple[m.StructuralEdgeKind, ...] = (),
) -> Roster:
    """Expand bounded neighborhoods around seeds; merge on shared members.

    Seeds resolving to no subject are skipped (documented, not an
    error: roster output is advisory). Provider errors propagate.
    """
    reached: dict[str, m.SubjectId] = {}
    kinds: dict[str, set[m.StructuralEdgeKind]] = {}
    unions = _UnionFind()
    for seed in seeds:
        resolution = structural.resolve_subject(
            repository_id,
            m.SubjectSelector(
                exact_subject_id=seed,
                name_or_locator=None,
                expected_kinds=(),
                retrieval_scope_hint=None,
            ),
            bounds,
        )
        if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
            continue
        reached.setdefault(seed.canonical_locator, seed)
        unions.union(seed.canonical_locator, seed.canonical_locator)
        page = structural.reach(
            repository_id,
            seed,
            edge_kinds,
            StructuralDirection.BOTH,
            bounds.max_depth,
            bounds,
        )
        for node in page.items:
            key = node.subject.canonical_locator
            reached.setdefault(key, node.subject)
            unions.union(seed.canonical_locator, key)
            if node.via is not None:
                via = node.via
                src = via.source.canonical_locator
                dst = via.target.canonical_locator
                reached.setdefault(src, via.source)
                reached.setdefault(dst, via.target)
                unions.union(src, dst)
                kinds.setdefault(dst, set()).add(via.kind)
                kinds.setdefault(src, set()).add(via.kind)
    groups: dict[str, set[str]] = {}
    for key in reached:
        groups.setdefault(unions.find(key), set()).add(key)
    territories: list[Territory] = []
    for group in groups.values():
        members = tuple(reached[key] for key in sorted(group))
        # Exact territory-internal entries: one upstream read per
        # member. Entry is claimed only when proven — a truncated
        # incoming page cannot prove entry, so that member is not
        # listed (documented, never guessed).
        internal_incoming: dict[str, set[str]] = {}
        proven: set[str] = set()
        for key in sorted(group):
            page = structural.edges(
                repository_id,
                reached[key],
                (),
                StructuralDirection.UPSTREAM,
                bounds,
            )
            if page.bound_info.truncated:
                continue
            proven.add(key)
            internal_incoming[key] = {
                e.source.canonical_locator
                for e in page.items
                if e.source.canonical_locator in group
            }
            for edge in page.items:
                kinds.setdefault(key, set()).add(edge.kind)
                kinds.setdefault(edge.source.canonical_locator, set()).add(edge.kind)
        entries = tuple(
            reached[key]
            for key in sorted(group)
            if key in proven and not internal_incoming[key]
        )
        group_kinds = sorted(
            {k for key in group for k in kinds.get(key, ())},
            key=lambda kind: kind.value,
        )
        territories.append(
            Territory(
                members=members,
                entry_points=entries,
                edge_kinds=tuple(group_kinds),
            )
        )
    territories.sort(key=lambda t: t.members[0].canonical_locator if t.members else "")
    return Roster(territories=tuple(territories))
