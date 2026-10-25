"""Answer-boundary conformance gate (remediation plan Step 02, report mode).

Every answer-producing tool is driven through the shared exchange harness and
its envelope is checked against the invariants the release promises. The gate
fails in both directions: an unexplained violation, or a listed violation that
no longer reproduces. ``KNOWN_VIOLATIONS`` is empty, so any regression fails,
and the empty table itself is asserted — a stale entry cannot linger.

The counter here is deliberately independent of the service. It counts every
tuple-valued leaf on the content plus the envelope's resolution requirements,
so it cannot agree with the service by construction. It must never import a
service helper that computes the number it is checking.
"""

import dataclasses as _dataclasses
import typing as _typing
import unittest

from span.core import model as m
from span.ports.structural import StructuralDirection
from span.shell import mcp
from span.shell.mcp import McpAdapter
from span.shell.mcp_server import handle_list_tools
from span import service as ops
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _establish,
    _exchange,
    _harness,
)

#: Fields that are tuples but are not independent leaves.
#: ``StatusContent.unresolved`` repeats ``answer.resolution_requirements``;
#: counting both would double-count the same requirement. ``coverage_report``
#: is an object, counted through its entries.
_NON_LEAF = {
    ("StatusContent", "unresolved"),
    ("StatusContent", "freshness_items"),
}

INVARIANTS = (
    "count_matches_payload",
    "returned_within_ceiling",
    "truncated_iff_token",
    "entries_within_subject_bound",
    "cursor_states_its_lifespan",
)

#: Violations observed on the tree before the structural steps land.
#: Keyed by ``(tool, scenario)``. Must shrink to nothing at Step 09.
KNOWN_VIOLATIONS: dict[tuple[str, str], frozenset[str]] = {
    # Empty as of Step 06: counting is truthful (Step 05), the scoped frontier
    # is bounded and resumable (Step 06), and repository leaf accounting is the
    # only remaining production bound (Step 07). The table fails in both
    # directions, so anything new — or anything that stops reproducing — must
    # be explained rather than tolerated.
}


def _leaf_count(answer: m.SemanticAnswer) -> int:
    """Independently count the leaves the answer carries."""
    content = answer.content
    count = len(answer.resolution_requirements)
    hints = _typing.get_type_hints(type(content))
    for field in _dataclasses.fields(content):
        if (type(content).__name__, field.name) in _NON_LEAF:
            continue
        if field.name in {"freshness_items"}:
            continue
        if _typing.get_origin(hints[field.name]) is tuple:
            count += len(getattr(content, field.name) or ())
    return count


def _violations(answer: m.SemanticAnswer, requested: m.QueryBounds) -> set[str]:
    found: set[str] = set()
    bound = answer.bound_info

    if bound.returned_results != _leaf_count(answer):
        found.add("count_matches_payload")

    if bound.returned_results > bound.requested_max_results:
        # Declared exception (D1): one atomic unit — an item with its own
        # requirements — is always emitted whole. Only a page that admitted
        # exactly one coverage entry can exceed the ceiling this way.
        report = getattr(answer.content, "coverage_report", None)
        page = getattr(report, "page", None)
        entries = getattr(page, "entries", ())
        if len(entries) != 1:
            found.add("returned_within_ceiling")

    if bound.truncated != (bound.continuation_token is not None):
        found.add("truncated_iff_token")

    if bound.lifespan != m.CURSOR_LIFESPAN:
        found.add("cursor_states_its_lifespan")

    report = getattr(answer.content, "coverage_report", None)
    page = getattr(report, "page", None)
    entries = getattr(page, "entries", None)
    if entries is not None and len(entries) > requested.max_subjects:
        found.add("entries_within_subject_bound")

    return found


def _scenarios():
    """(tool, scenario, request_factory, scoped, populate)."""
    selector = m.SubjectSelector(None, "src/flow.py", (), None)
    return (
        (
            "explain",
            "selector",
            lambda: ops.SemanticExplainRequest(
                repository_id=REPO, target=selector, bounds=_bounds()
            ),
            True,
            False,
        ),
        (
            "impact",
            "selector",
            lambda: ops.SemanticImpactRequest(
                repository_id=REPO,
                target=selector,
                change_kind=ops.ChangeKind.BEHAVIOR,
                change_description=None,
                bounds=_bounds(),
                affected_assertions=(),
            ),
            True,
            False,
        ),
        (
            "trace",
            "selector",
            lambda: ops.SemanticTraceRequest(
                repository_id=REPO,
                target=selector,
                direction=StructuralDirection.BOTH,
                relationship_filter=None,
                boundary_only=False,
                bounds=_bounds(),
            ),
            True,
            False,
        ),
        (
            "authority",
            "selector",
            lambda: ops.SemanticAuthorityRequest(
                repository_id=REPO, target=selector, bounds=_bounds()
            ),
            True,
            False,
        ),
        (
            "status",
            "scope",
            lambda: ops.SemanticStatusRequest(
                repository_id=REPO,
                target=m.EvidenceScope(paths=("src",), evidence_refs=()),
                bounds=_bounds(max_subjects=1, max_results=2),
            ),
            True,
            True,
        ),
        (
            "status",
            "repository",
            lambda: ops.SemanticStatusRequest(
                repository_id=REPO,
                target=None,
                bounds=_bounds(max_subjects=2, max_results=2),
            ),
            False,
            True,
        ),
        (
            "initialize_target",
            "scope",
            lambda: ops.SemanticInitializeTargetRequest(
                repository_id=REPO,
                target=m.EvidenceScope(paths=("src",), evidence_refs=()),
                objective="Establish the src area from direct evidence.",
                bounds=_bounds(),
            ),
            True,
            False,
        ),
        (
            "refresh",
            "selector",
            lambda: ops.SemanticRefreshRequest(
                repository_id=REPO, target=selector, bounds=_bounds()
            ),
            True,
            True,
        ),
    )


_OPERATION = {
    "initialize_target": ops.initialize_target,
    "explain": ops.explain,
    "impact": ops.impact,
    "trace": ops.trace,
    "authority": ops.authority,
    "status": ops.status,
    "refresh": ops.refresh,
}

#: Tools that answer, but only as the return leg of another call.
_ENTRY_LEG = {"submit_interpretation": "driven by every suspending scenario"}

#: Answer-producing tools the shared fixture agent cannot drive. Empty:
#: every answer-producing tool is enrolled through the shared exchange.
_EXEMPT: dict[str, str] = {}

#: Tools whose result is not an answer envelope, with the reason they are out.
_NON_ANSWER = {
    "initialize_repository": "returns SemanticInitializeRepositoryResult",
    "locate": "returns a structural result, not an answer",
    "neighbors": "returns a structural result, not an answer",
}


def _answer_tools() -> set[str]:
    """Tools whose declared output union contains SemanticAnswer."""
    answer: set[str] = set()
    for tool, output in mcp.TOOL_OUTPUT_TYPES.items():
        if any(arg is m.SemanticAnswer for arg in _typing.get_args(output)):
            answer.add(tool)
    return answer


def _answer(tool: str, request: object, populate: bool) -> m.SemanticAnswer:
    structural, evidence, store, agent = _harness()
    try:
        if populate:
            _establish(structural, evidence, store, agent)
        result = _exchange(
            request, _OPERATION[tool], structural, evidence, store, agent
        )
    finally:
        store.close()
    assert isinstance(result, m.SemanticAnswer), type(result)
    return result


class AnswerConformanceTest(unittest.TestCase):
    def test_every_public_tool_is_enrolled(self):
        listed = {spec["name"] for spec in handle_list_tools(McpAdapter())}
        self.assertEqual(listed, set(mcp.TOOL_NAMES))

        answers = _answer_tools()
        driven = {tool for tool, _, _, _, _ in _scenarios()} | set(_ENTRY_LEG)
        self.assertEqual(
            answers - driven,
            set(_EXEMPT),
            "an answer-producing tool is neither driven nor exempted with a reason",
        )
        self.assertEqual(
            set(_EXEMPT) - answers,
            set(),
            "an exemption names a tool that no longer produces answers",
        )
        self.assertEqual(
            listed - answers,
            set(_NON_ANSWER),
            "a non-answer tool is not declared",
        )
        self.assertTrue(all(_EXEMPT.values()), "every exemption states a reason")

    def test_scoped_report_has_no_repository_global_field(self):
        report_fields = {f.name for f in _dataclasses.fields(m.ScopedCoverageReport)}
        self.assertNotIn("repository", report_fields)
        scope_fields = {f.name for f in _dataclasses.fields(m.ScopeTotals)}
        self.assertEqual(scope_fields, {"persisted_subject_count"})
        for field in (
            "pending_question_count",
            "open_question_count",
            "active_target_association_count",
            "persisted_target_accounted_count",
            "persisted_target_unresolved_count",
            "bounded_live_target_unaccounted_count",
        ):
            self.assertNotIn(field, report_fields | scope_fields)

    def test_known_violations_is_empty(self):
        self.assertEqual(
            KNOWN_VIOLATIONS,
            {},
            "the ratchet must stay empty; fix the boundary, not the table",
        )

    def test_invariants(self):
        observed: dict[tuple[str, str], set[str]] = {}
        for tool, scenario, make_request, _scoped, populate in _scenarios():
            request = make_request()
            answer = _answer(tool, request, populate)
            found = _violations(answer, request.bounds or _bounds())
            if found:
                observed[(tool, scenario)] = found

        unexplained = {
            key: value - KNOWN_VIOLATIONS.get(key, frozenset())
            for key, value in observed.items()
            if value - KNOWN_VIOLATIONS.get(key, frozenset())
        }
        stale = {
            key: set(value) - observed.get(key, set())
            for key, value in KNOWN_VIOLATIONS.items()
            if set(value) - observed.get(key, set())
        }
        self.assertEqual(unexplained, {}, "new boundary violations")
        self.assertEqual(stale, {}, "listed violations no longer reproduce")


if __name__ == "__main__":
    unittest.main()
