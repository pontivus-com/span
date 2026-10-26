"""Static contract checks for the advertised tool surface.

Each test here fails on a contract the decoder enforces but the schema (or the
codec) does not state. They are intentionally independent of the service: the
model must be able to construct a request from the schema alone.
"""

from __future__ import annotations

import dataclasses
import unittest

from span.core.schema.wire import from_wire
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.requests import SemanticExplainRequest
from span.shell.mcp.schemas import TOOL_SCHEMAS


def _tag_members(schema: object) -> list[str]:
    """Carrier names advertised by one tagged-union projection."""
    names: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.endswith("__tag"):
                names.append(ref.rsplit("/", 1)[-1][: -len("__tag")])
            for key in ("anyOf", "oneOf"):
                for branch in node.get(key, []) or []:
                    walk(branch)

    walk(schema)
    return list(dict.fromkeys(names))


class SchemaContractTest(unittest.TestCase):
    def test_every_multi_tag_property_states_its_tags(self):
        """A property the model must discriminate must say so."""
        missing: list[str] = []
        for tool, schema in TOOL_SCHEMAS.items():
            for name, prop in (schema.get("properties") or {}).items():
                if len(_tag_members(prop)) >= 2 and not prop.get("description"):
                    missing.append(f"{tool}.{name}")
        self.assertEqual(
            missing,
            [],
            "multi-tag properties without $type guidance: " + ", ".join(missing),
        )

    def test_bounds_advertise_the_enforced_maximum(self):
        """Every bound rejects above a maximum; the schema must state it."""
        maximum = dataclasses.asdict(DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds)
        missing: list[str] = []
        for tool, schema in TOOL_SCHEMAS.items():
            bounds = (schema.get("$defs") or {}).get("QueryBounds")
            if not isinstance(bounds, dict):
                continue
            for name, limit in maximum.items():
                prop = (bounds.get("properties") or {}).get(name)
                if not isinstance(prop, dict) or prop.get("maximum") != limit:
                    missing.append(f"{tool}.QueryBounds.{name}")
        self.assertEqual(
            missing,
            [],
            "bounds without their enforced maximum: " + ", ".join(missing),
        )

    def test_paths_state_the_repository_relative_rule(self):
        seen = 0
        for tool, schema in TOOL_SCHEMAS.items():
            scope = (schema.get("$defs") or {}).get("EvidenceScope")
            if not isinstance(scope, dict):
                continue
            seen += 1
            description = (
                scope["properties"]["paths"].get("description") or ""
            ).lower()
            self.assertIn("repository-relative", description, f"{tool}.EvidenceScope")
        self.assertGreater(seen, 0, "no tool schema defines EvidenceScope")


class WireTagTest(unittest.TestCase):
    def test_redundant_tag_naming_the_only_carrier_is_accepted(self):
        """A tag that cannot be ambiguous carries no risk; do not fail on it."""
        request = from_wire(
            SemanticExplainRequest,
            {
                "repository_id": "repo",
                "target": {
                    "$type": "SubjectSelector",
                    "name_or_locator": "src/module.py",
                },
            },
        )
        self.assertEqual(request.target.name_or_locator, "src/module.py")

    def test_tag_naming_another_carrier_is_rejected(self):
        with self.assertRaises(ValueError):
            from_wire(
                SemanticExplainRequest,
                {
                    "repository_id": "repo",
                    "target": {"$type": "EvidenceScope", "paths": ["src"]},
                },
            )


class RefreshContractTest(unittest.TestCase):
    def test_refresh_never_returns_a_partial_answer(self):
        from span.service.operations.refresh.answer import _refuse_truncated_refresh
        from span.service.requests import RefreshScopeError, SemanticRefreshRequest

        _refuse_truncated_refresh(False, 50)
        with self.assertRaises(RefreshScopeError):
            _refuse_truncated_refresh(True, 50)
        names = {field.name for field in dataclasses.fields(SemanticRefreshRequest)}
        self.assertNotIn("page_token", names)


if __name__ == "__main__":
    unittest.main()
