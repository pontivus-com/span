#!/usr/bin/env python3
"""Black-box installed Functional Pyramid governance journey.

Runs under the isolated installed interpreter, imports no span module and
drives only the public three-tool MCP surface. The fixture deliberately uses two
physical repository databases and cross-repository rule authority.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys


def _text(result) -> str:
    return "".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


async def _call(session, name, arguments):
    result = await session.call_tool(name, arguments)
    text = _text(result)
    try:
        payload = json.loads(text)
    except ValueError:
        payload = {"raw": text}
    return payload, bool(result.is_error)


def _value(value):
    return value.get("value") if isinstance(value, dict) and "value" in value else value


def _dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dicts(child)


def _has_route_support(value) -> bool:
    return any(
        "route_identity" in item and "semantic_scope" in item and "pyramid_id" in item
        for item in _dicts(value)
    )


def _authority_ids(value, repository_id):
    found = set()
    for item in _dicts(value):
        evidence = item.get("evidence_ref")
        if not isinstance(evidence, dict):
            continue
        if evidence.get("repository_id") != repository_id:
            continue
        evidence_id = _value(evidence.get("evidence_id"))
        if evidence_id:
            found.add(evidence_id)
    return sorted(found)


def _validation_reasons(candidate):
    return sorted(
        {
            item.get("reason")
            for item in candidate.get("validation_findings", [])
            if item.get("reason")
        }
    )


def _graph_reasons(candidate):
    return sorted(
        {
            item.get("reason")
            for item in candidate.get("graph_findings", [])
            if item.get("reason")
        }
    )


def _context_for(result, repository_id):
    return next(
        item
        for item in result.get("reestablishment_contexts", [])
        if item.get("repository_id") == repository_id
    )


def _surface_repositories(result):
    repositories = []
    for item in result.get("surfaces", []):
        surface = item.get("surface", {})
        repository_id = surface.get("repository_id")
        if repository_id:
            repositories.append(repository_id)
    return sorted(set(repositories))


async def _run(exe, repo_a, repo_b, data_dir, repo_a_id, repo_b_id):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    params = StdioServerParameters(
        command=exe,
        args=[
            "--data-dir",
            str(data_dir),
            "--repo",
            str(repo_a),
            "--repo",
            str(repo_b),
        ],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            unknown_repository, unknown_repository_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidSelector",
                        "repository_id": "repo-not-registered",
                    }
                },
            )
            unknown_pyramid, unknown_pyramid_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidSelector",
                        "pyramid_id": {"value": "fp-not-active"},
                    }
                },
            )

            mixed_candidate, mixed_candidate_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidCandidateSelector",
                        "action": "activate",
                        "members": [
                            {
                                "repository_id": repo_a_id,
                                "declaration_sources": [
                                    {
                                        "locator": "docs/invalid-functional-pyramid.json",
                                        "ranges": [],
                                    }
                                ],
                                "functional_scope": {
                                    "selectors": [{"kind": "PREFIX", "path": "src"}]
                                },
                                "coverage": "PARTIAL",
                            },
                            {
                                "repository_id": "repo-not-registered",
                                "declaration_sources": [
                                    {
                                        "locator": "docs/functional-pyramid.json",
                                        "ranges": [],
                                    }
                                ],
                                "functional_scope": {
                                    "selectors": [{"kind": "PREFIX", "path": "src"}]
                                },
                                "coverage": "PARTIAL",
                            },
                        ],
                    }
                },
            )

            members = [
                {
                    "repository_id": repo_a_id,
                    "declaration_sources": [
                        {"locator": "docs/functional-pyramid.json", "ranges": []}
                    ],
                    "functional_scope": {
                        "selectors": [{"kind": "PREFIX", "path": "src"}]
                    },
                    "coverage": "COMPLETE",
                },
                {
                    "repository_id": repo_b_id,
                    "declaration_sources": [
                        {"locator": "docs/functional-pyramid.json", "ranges": []}
                    ],
                    "functional_scope": {
                        "selectors": [
                            {"kind": "PATH", "path": "rules/p0-v1.md"},
                            {"kind": "PATH", "path": "rules/p0-v2.md"},
                        ]
                    },
                    "coverage": "PARTIAL",
                },
            ]
            candidate, candidate_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidCandidateSelector",
                        "action": "activate",
                        "members": members,
                    }
                },
            )
            pre_created, pre_created_error = await _call(
                session,
                "record",
                {
                    "repository_id": repo_a_id,
                    "request_id": "preactivation-normative-create",
                    "kind": "understanding",
                    "question": "What constrains alpha before adoption?",
                    "scope_paths": ["src/alpha.py"],
                    "conclusion": "Alpha has a normative pre-adoption constraint.",
                    "locator": "src/alpha.py",
                    "assertion_nature": "NORMATIVE",
                    "provenance": "installed preactivation probe",
                },
            )
            pre_understanding_id = _value(pre_created.get("understanding_id"))
            pre_version = _value(pre_created.get("version"))
            pre_affected = pre_created.get("affected_revisions", [])
            pre_conclusion_id = (
                _value(pre_affected[0].get("conclusion_id")) if pre_affected else None
            )

            activated, activated_error = await _call(
                session,
                "record",
                {
                    "request_id": "governed-activate",
                    "kind": "functional_pyramid",
                    "action": "activate",
                    "members": members,
                },
            )

            activation_receipt_before, activation_receipt_before_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidReceiptSelector",
                        "request_id": {"value": "governed-activate"},
                    }
                },
            )
            activation_replay_before, activation_replay_before_error = await _call(
                session,
                "record",
                {
                    "request_id": "governed-activate",
                    "kind": "functional_pyramid",
                    "action": "activate",
                    "members": members,
                },
            )
            activation_context_a = _context_for(activated, repo_a_id)
            pre_reestablished, pre_reestablished_error = await _call(
                session,
                "record",
                {
                    "request_id": "preactivation-normative-reestablish",
                    "context": activation_context_a,
                    "kind": "understanding",
                    "understanding_id": pre_understanding_id,
                    "expected_version": pre_version,
                    "actions": {
                        "confirm": [
                            {
                                "conclusion_id": pre_conclusion_id,
                                "locator": "src/alpha.py",
                            }
                        ]
                    },
                },
            )
            activation_receipt_after, activation_receipt_after_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidReceiptSelector",
                        "request_id": {"value": "governed-activate"},
                    }
                },
            )
            activation_replay_after, activation_replay_after_error = await _call(
                session,
                "record",
                {
                    "request_id": "governed-activate",
                    "kind": "functional_pyramid",
                    "action": "activate",
                    "members": members,
                },
            )

            ask_a, ask_a_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repo_a_id,
                    "reference": "src/alpha.py",
                },
            )
            owner_ask, owner_ask_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repo_b_id,
                    "reference": "rules/p0-v1.md",
                },
            )

            created, created_error = await _call(
                session,
                "record",
                {
                    "repository_id": repo_a_id,
                    "request_id": "governed-normative-create",
                    "kind": "understanding",
                    "question": "What governing rule constrains alpha?",
                    "scope_paths": ["src/alpha.py"],
                    "conclusion": "Alpha is governed by the cross-repository P0 rule.",
                    "locator": "src/alpha.py",
                    "assertion_nature": "NORMATIVE",
                    "provenance": "installed governed probe",
                },
            )
            understanding_id = _value(created.get("understanding_id"))
            version = _value(created.get("version"))
            affected = created.get("affected_revisions", [])
            conclusion_id = (
                _value(affected[0].get("conclusion_id")) if affected else None
            )
            snapshot_before, snapshot_before_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "UnderstandingSnapshotSelector",
                        "repository_id": repo_a_id,
                        "understanding_id": understanding_id,
                    }
                },
            )

            declaration_path = pathlib.Path(repo_b) / "docs/functional-pyramid.json"
            declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
            declaration["rules"][0]["owner"]["authority_ref"] = "authority-p0-v2"
            declaration_path.write_text(
                json.dumps(declaration, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            changed, changed_error = await _call(
                session,
                "reconsider",
                {
                    "repository_id": repo_b_id,
                    "changed_paths": ["docs/functional-pyramid.json"],
                },
            )
            context_a = _context_for(changed, repo_a_id)
            reestablished, reestablished_error = await _call(
                session,
                "record",
                {
                    "request_id": "governed-normative-reestablish",
                    "context": context_a,
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": version,
                    "actions": {
                        "confirm": [
                            {
                                "conclusion_id": conclusion_id,
                                "locator": "src/alpha.py",
                            }
                        ]
                    },
                },
            )
            snapshot_after, snapshot_after_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "UnderstandingSnapshotSelector",
                        "repository_id": repo_a_id,
                        "understanding_id": understanding_id,
                    }
                },
            )
            ask_after, ask_after_error = await _call(
                session,
                "ask",
                {
                    "repository_id": repo_a_id,
                    "reference": "src/alpha.py",
                },
            )

            fp_a = ask_a.get("functional_pyramid", {})
            owner_fp = owner_ask.get("functional_pyramid", {})
            owner_rules = owner_fp.get("rules", [])
            downstream_contexts = sorted(
                {
                    context_id
                    for rule in owner_rules
                    for context_id in rule.get("downstream_context_ids", [])
                }
            )
            return {
                "unknown_repository_error": unknown_repository_error,
                "unknown_repository_kind": unknown_repository.get("$type"),
                "unknown_pyramid_error": unknown_pyramid_error,
                "unknown_pyramid_kind": unknown_pyramid.get("$type"),
                "mixed_candidate_error": mixed_candidate_error,
                "mixed_validation_reasons": _validation_reasons(mixed_candidate),
                "mixed_graph_reasons": _graph_reasons(mixed_candidate),
                "candidate_error": candidate_error,
                "candidate_ready": candidate.get("activation_ready"),
                "activated_error": activated_error,
                "activated_kind": activated.get("$type"),
                "pre_created_error": pre_created_error,
                "pre_created_qualification": pre_created.get("qualification", {}).get(
                    "state"
                ),
                "activation_effect_repositories": _surface_repositories(
                    {"surfaces": activated.get("dependent_effects", [])}
                ),
                "activation_receipt_before_error": activation_receipt_before_error,
                "activation_receipt_before_refs": activation_receipt_before.get(
                    "dependent_effect_refs", []
                ),
                "activation_replay_before_error": activation_replay_before_error,
                "activation_replay_before_effect_repositories": _surface_repositories(
                    {"surfaces": activation_replay_before.get("dependent_effects", [])}
                ),
                "pre_reestablished_error": pre_reestablished_error,
                "pre_reestablished_qualification": pre_reestablished.get(
                    "qualification", {}
                ).get("state"),
                "activation_receipt_after_error": activation_receipt_after_error,
                "activation_receipt_after_refs": activation_receipt_after.get(
                    "dependent_effect_refs", []
                ),
                "activation_replay_after_error": activation_replay_after_error,
                "activation_replay_after_effect_count": len(
                    activation_replay_after.get("dependent_effects", [])
                ),
                "activation_replay_after_context_count": len(
                    activation_replay_after.get("reestablishment_contexts", [])
                ),
                "ask_a_error": ask_a_error,
                "ask_a_route_status": fp_a.get("status"),
                "ask_a_rule_authority_ids": _authority_ids(fp_a, repo_b_id),
                "owner_ask_error": owner_ask_error,
                "owner_scope_relation": owner_fp.get("scope_relation"),
                "owner_route_status": owner_fp.get("status"),
                "owner_downstream_contexts": downstream_contexts,
                "created_error": created_error,
                "created_qualification": created.get("qualification", {}).get("state"),
                "snapshot_before_error": snapshot_before_error,
                "snapshot_before_has_route": _has_route_support(snapshot_before),
                "snapshot_before_authority_ids": _authority_ids(
                    snapshot_before, repo_b_id
                ),
                "changed_error": changed_error,
                "changed_surface_repositories": _surface_repositories(changed),
                "changed_context_repository": context_a.get("repository_id"),
                "reestablished_error": reestablished_error,
                "reestablished_qualification": reestablished.get(
                    "qualification", {}
                ).get("state"),
                "snapshot_after_error": snapshot_after_error,
                "snapshot_after_has_route": _has_route_support(snapshot_after),
                "snapshot_after_authority_ids": _authority_ids(
                    snapshot_after, repo_b_id
                ),
                "ask_after_error": ask_after_error,
                "ask_after_kind": ask_after.get("$type"),
            }


def main(argv):
    if len(argv) != 7:
        print(
            "usage: functional_pyramid_governed_probe.py "
            "<span-mcp> <repo-a> <repo-b> <data-dir> <repo-a-id> <repo-b-id>",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            asyncio.run(
                _run(
                    argv[1],
                    argv[2],
                    argv[3],
                    argv[4],
                    argv[5],
                    argv[6],
                )
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
