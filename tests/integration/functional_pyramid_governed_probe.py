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
import subprocess
import sys
import traceback


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


def _authority_locators(value, repository_id):
    found = set()
    for item in _dicts(value):
        evidence = item.get("evidence_ref")
        if not isinstance(evidence, dict):
            continue
        if evidence.get("repository_id") != repository_id:
            continue
        locator = evidence.get("locator")
        if locator:
            found.add(locator)
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


def _install(command, data_dir, repository_id):
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError("governed install failed: " + (result.stderr or result.stdout)[-8000:])
    receipt = json.loads((pathlib.Path(data_dir) / "install.json").read_text())
    return receipt["governed_initialization"][repository_id]["participation_results"][-1]


async def _run(exe, repo_a, repo_b, data_dir, repo_a_id, repo_b_id, command):
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

            pre_status, pre_status_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidSelector",
                        "repository_id": repo_a_id,
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
                            },
                            {
                                "repository_id": "repo-not-registered",
                                "declaration_sources": [
                                    {
                                        "locator": "docs/functional-pyramid.json",
                                        "ranges": [],
                                    }
                                ],
                            },
                        ],
                    }
                },
            )

            manual_activation, _ = await _call(
                session, "record", {
                    "request_id": "manual-activation-forbidden",
                    "kind": "functional_pyramid",
                    "action": "activate",
                    "members": [{
                        "repository_id": repo_a_id,
                        "declaration_sources": [{"locator": "docs/invalid-functional-pyramid.json", "ranges": []}],
                    }],
                }
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

            activated = _install(command, data_dir, repo_a_id)
            activated_error = False
            activation_id = _value(activated["receipt_selector"]["request_id"])
            members = [
                {
                    "repository_id": member["repository_id"],
                    "declaration_sources": [
                        {"locator": ref["locator"], "ranges": []}
                        for ref in member["declaration_refs"]
                    ],
                }
                for member in activated["members"]
            ]
            candidate, candidate_error = await _call(
                session, "ask", {
                    "selector": {
                        "$type": "FunctionalPyramidCandidateSelector",
                        "action": "revise",
                        "members": members,
                        "pyramid_id": activated["pyramid_id"],
                        "expected_version": activated["version"],
                    }
                }
            )

            activation_receipt_before, activation_receipt_before_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidReceiptSelector",
                        "request_id": {"value": activation_id},
                    }
                },
            )
            activation_replay_before, activation_replay_before_error = await _call(
                session,
                "record",
                {
                    "request_id": activation_id,
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
                        "request_id": {"value": activation_id},
                    }
                },
            )
            activation_replay_after, activation_replay_after_error = await _call(
                session,
                "record",
                {
                    "request_id": activation_id,
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
                    "reference": "rules/p2s.md",
                },
            )

            directory_src, directory_src_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidDirectorySelector",
                        "repository_id": repo_a_id,
                        "directory": "src",
                    }
                },
            )
            directory_root, directory_root_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "FunctionalPyramidDirectorySelector",
                        "repository_id": repo_a_id,
                        "directory": ".",
                    }
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
            captured_ask, captured_ask_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "CurrentUnderstandingSelector",
                        "repository_id": repo_a_id,
                        "understanding_id": understanding_id,
                    }
                },
            )
            pending, pending_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "PendingCurationSelector",
                        "repository_id": repo_a_id,
                    }
                },
            )
            pending_contains_created = any(
                _value(item.get("ref", {}).get("understanding_id")) == understanding_id
                and _value(item.get("ref", {}).get("conclusion_id")) == conclusion_id
                for item in pending.get("items", [])
            )

            curated, curated_error = await _call(
                session,
                "record",
                {
                    "repository_id": repo_a_id,
                    "request_id": "governed-normative-curate",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": version,
                    "actions": {
                        "curate": [
                            {
                                "conclusion_id": conclusion_id,
                                "reasoning": (
                                    "reviewed cross-repository normative conclusion"
                                ),
                            }
                        ]
                    },
                    "provenance": "installed governed reviewer",
                },
            )
            version = _value(curated.get("version"))
            async with stdio_client(params) as (fresh_read, fresh_write):
                async with ClientSession(fresh_read, fresh_write) as fresh_session:
                    await fresh_session.initialize()
                    fresh_reuse, fresh_reuse_error = await _call(
                        fresh_session,
                        "ask",
                        {
                            "selector": {
                                "$type": "CurrentUnderstandingSelector",
                                "repository_id": repo_a_id,
                                "understanding_id": understanding_id,
                            }
                        },
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

            # Change the repository-owned classification, never a generated source.
            for repository in (repo_a, repo_b):
                classification_path = pathlib.Path(repository) / "docs/classification.json"
                classification = json.loads(classification_path.read_text())
                for row in classification["rows"]:
                    locator = row["document_ref"]
                    if locator == "rules/p0-v1.md":
                        row["document_ref"] = "rules/p0-v2.md"
                    elif locator == "rules/p0-v2.md":
                        row["document_ref"] = "rules/p0-v1.md"
                    for parent in row.get("governing_documents", []):
                        if isinstance(parent, dict) and parent["document_ref"] == "rules/p0-v1.md":
                            parent["document_ref"] = "rules/p0-v2.md"
                classification_path.write_text(json.dumps(classification, sort_keys=True) + "\n")
            revision_result = _install(command, data_dir, repo_a_id)
            changed = {
                "surfaces": revision_result["dependent_effects"],
                "reestablishment_contexts": revision_result["reestablishment_contexts"],
            }
            changed_error = False
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

            version = _value(reestablished.get("version"))
            corrected, corrected_error = await _call(
                session,
                "record",
                {
                    "repository_id": repo_a_id,
                    "request_id": "governed-normative-correct",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": version,
                    "actions": {
                        "correct": [
                            {
                                "conclusion_id": conclusion_id,
                                "conclusion": (
                                    "Alpha is governed by the corrected cross-repository "
                                    "P0 rule."
                                ),
                                "locator": "src/alpha.py",
                            }
                        ]
                    },
                    "provenance": "installed governed correction",
                },
            )
            corrected_version = _value(corrected.get("version"))
            corrected_affected = corrected.get("affected_revisions", [])
            corrected_conclusion_id = (
                _value(corrected_affected[0].get("conclusion_id"))
                if corrected_affected
                else conclusion_id
            )
            corrected_ask, corrected_ask_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "CurrentUnderstandingSelector",
                        "repository_id": repo_a_id,
                        "understanding_id": understanding_id,
                    }
                },
            )
            corrected_pending, corrected_pending_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "PendingCurationSelector",
                        "repository_id": repo_a_id,
                    }
                },
            )
            corrected_pending_contains_target = any(
                _value(item.get("ref", {}).get("understanding_id")) == understanding_id
                and _value(item.get("ref", {}).get("conclusion_id"))
                == corrected_conclusion_id
                for item in corrected_pending.get("items", [])
            )
            recurated, recurated_error = await _call(
                session,
                "record",
                {
                    "repository_id": repo_a_id,
                    "request_id": "governed-normative-recurate",
                    "kind": "understanding",
                    "understanding_id": understanding_id,
                    "expected_version": corrected_version,
                    "actions": {
                        "curate": [
                            {
                                "conclusion_id": corrected_conclusion_id,
                                "reasoning": "reviewed corrected governed meaning",
                            }
                        ]
                    },
                    "provenance": "installed governed reviewer",
                },
            )
            final_ask, final_ask_error = await _call(
                session,
                "ask",
                {
                    "selector": {
                        "$type": "CurrentUnderstandingSelector",
                        "repository_id": repo_a_id,
                        "understanding_id": understanding_id,
                    }
                },
            )

            fp_a = ask_a.get("functional_pyramid", {})
            owner_fp = owner_ask.get("functional_pyramid", {})
            read_exposes_internal = {
                key: key in owner_fp for key in ("routes", "provenance", "health")
            }
            directory_src_fp = directory_src
            directory_root_fp = directory_root
            return {
                "unknown_repository_error": unknown_repository_error,
                "unknown_repository_kind": unknown_repository.get("$type"),
                "unknown_pyramid_error": unknown_pyramid_error,
                "unknown_pyramid_kind": unknown_pyramid.get("$type"),
                "pre_status_error": pre_status_error,
                "pre_status_state": pre_status.get("state"),
                "mixed_candidate_error": mixed_candidate_error,
                "mixed_validation_reasons": _validation_reasons(mixed_candidate),
                "mixed_graph_reasons": _graph_reasons(mixed_candidate),
                "manual_activation_kind": manual_activation.get("$type"),
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
                "ask_a_documents": [
                    placement.get("document", {}).get("document_ref")
                    for placement in fp_a.get("placements", [])
                ],
                "directory_src_error": directory_src_error,
                "directory_src_route_status": directory_src_fp.get("status"),
                "directory_src_documents": [
                    placement.get("document", {}).get("document_ref")
                    for placement in directory_src_fp.get("placements", [])
                ],
                "directory_root_error": directory_root_error,
                "directory_root_documents": [
                    placement.get("document", {}).get("document_ref")
                    for placement in directory_root_fp.get("placements", [])
                ],
                "read_exposes_internal": read_exposes_internal,
                "owner_ask_error": owner_ask_error,
                "owner_route_status": owner_fp.get("status"),
                "created_error": created_error,
                "created_qualification": created.get("qualification", {}).get("state"),
                "captured_ask_error": captured_ask_error,
                "captured_ask_kind": captured_ask.get("$type"),
                "captured_gap_reason": captured_ask.get("reason"),
                "pending_error": pending_error,
                "pending_kind": pending.get("$type"),
                "pending_contains_created": pending_contains_created,
                "curated_error": curated_error,
                "curated_kind": curated.get("$type"),
                "fresh_reuse_error": fresh_reuse_error,
                "fresh_reuse_kind": fresh_reuse.get("$type"),
                "snapshot_before_error": snapshot_before_error,
                "snapshot_before_has_route": _has_route_support(snapshot_before),
                "snapshot_before_authority_locators": _authority_locators(
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
                "snapshot_after_authority_locators": _authority_locators(
                    snapshot_after, repo_b_id
                ),
                "ask_after_error": ask_after_error,
                "ask_after_kind": ask_after.get("$type"),
                "corrected_error": corrected_error,
                "corrected_kind": corrected.get("$type"),
                "corrected_ask_error": corrected_ask_error,
                "corrected_ask_kind": corrected_ask.get("$type"),
                "corrected_gap_reason": corrected_ask.get("reason"),
                "corrected_pending_error": corrected_pending_error,
                "corrected_pending_contains_target": corrected_pending_contains_target,
                "recurated_error": recurated_error,
                "recurated_kind": recurated.get("$type"),
                "final_ask_error": final_ask_error,
                "final_ask_kind": final_ask.get("$type"),
            }


def _print_exception_tree(error):
    children = getattr(error, "exceptions", ())
    if children:
        for child in children:
            _print_exception_tree(child)
        return
    traceback.print_tb(error.__traceback__, file=sys.stderr)
    message = str(error)
    if len(message) > 2000:
        message = message[:2000] + "...<truncated>"
    print(f"{type(error).__name__}: {message}", file=sys.stderr)


def main(argv):
    if len(argv) != 8:
        print(
            "usage: functional_pyramid_governed_probe.py "
            "<span-mcp> <repo-a> <repo-b> <data-dir> <repo-a-id> <repo-b-id>",
            file=sys.stderr,
        )
        return 2
    try:
        result = asyncio.run(
            _run(
                argv[1],
                argv[2],
                argv[3],
                argv[4],
                argv[5],
                argv[6],
                json.loads(argv[7]),
            )
        )
    except BaseException as exc:
        _print_exception_tree(exc)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
