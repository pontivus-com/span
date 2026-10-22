"""Standalone black-box external MCP client (Addendum M §M-10).

This module is client-side test infrastructure only. It imports the
standard library and the MCP client SDK; it does not import Span or any
Span repository helper. Request shapes are constructed from the public
``tools/list`` schemas, tool descriptions, and returned pending data.
The client process enforces a meta-path guard against ``span`` imports.
"""

from __future__ import annotations

import asyncio as _asyncio
import contextlib as _contextlib
import json as _json
import os as _os
import pathlib as _pathlib


_TOOL_NAMES = (
    "initialize_repository",
    "initialize_target",
    "explain",
    "impact",
    "trace",
    "authority",
    "status",
    "refresh",
    "submit_interpretation",
    "locate",
    "neighbors",
)

def _selector(path):
    return {"name_or_locator": path}


def _tagged_selector(path):
    return {"$type": "SubjectSelector", "name_or_locator": path}


def _claim_for(subject, summary, ref):
    return {
        "candidate_key": "wire-1",
        "subject": subject,
        "kind": "PURPOSE",
        "value": {
            "$type": "PurposeValue",
            "summary": summary,
            "capability_refs": [],
        },
        "assertion_nature": "DESCRIPTIVE",
        "evidence": [ref],
        "candidate_authority": None,
        "basis": {
            "derivation": "SEMANTIC_INTERPRETATION",
            "summary": "wire acceptance observes the file",
        },
    }


def _covering_result(pending, claim):
    return {
        "claims": [claim],
        "relationships": [],
        "candidate_subjects": [],
        "candidate_conflicts": [],
        "question_decision": {
            "disposition": "ANSWERED",
            "evidence_scope": {"paths": [], "evidence_refs": []},
            "resolution_requirements": [],
            "disposition_basis": "installed wire acceptance",
        },
        "proposed_questions": [],
        "candidate_withdrawals": [],
        "governing_source_refs": [],
        "diagnostics": [],
        "proposed_target_inventory_accounting": [],
        "proposed_target_questions": [],
    }


class _Wire:
    """Thin stdio client wrapper with a JSONL transcript."""

    def __init__(self, session, transcript, schemas=None):
        self._session = session
        self._transcript = transcript
        self._schemas = schemas or {}

    async def call(self, tool, args, validate=True):
        # The client constructs public compact payloads directly; it has
        # no Span imports and no access to the internal wire projector.
        schema = self._schemas.get(tool)
        if validate and schema is not None and isinstance(args, dict):
            required = set(schema.get("required", []))
            allowed = set(schema.get("properties", {}))
            assert required <= set(args), (
                tool, "missing required", required - set(args)
            )
            assert set(args) <= allowed, (
                tool, "unknown arguments", set(args) - allowed
            )
        result = await self._session.call_tool(tool, args)
        texts = [
            block.text for block in result.content
            if getattr(block, "type", "") == "text"
        ]
        text = "".join(texts)
        try:
            payload = _json.loads(text)
        except ValueError:
            raise AssertionError(
                f"tool {tool} returned non-JSON payload: {text[:500]!r}"
            )
        # Full input/output transcript (S9.5): request arguments and
        # the complete returned JSON, not summaries.
        self._transcript.append({
            "tool": tool,
            "arguments": args,
            "error": bool(result.is_error),
            "response": payload,
        })
        return payload, bool(result.is_error)


async def lane(exe, work, data_dir, transcript):
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    env = {
        key: value for key, value in _os.environ.items()
        if key != "PYTHONPATH"
    }

    async def _session(register: bool = True):
        args = ["--data-dir", str(data_dir)]
        if register:
            args += ["--repo", str(work)]
        params = StdioServerParameters(
            command=exe, args=args, env=env,
        )
        stack = _contextlib.AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(
            ClientSession(read, write)
        )
        initialized = await session.initialize()
        return stack, session, initialized

    # -- phase 1: provisioned server ------------------------------------
    stack, session, initialized = await _session()
    try:
        server_version = initialized.server_info.version
        transcript.append({"server_version": server_version})
        listed = await session.list_tools()
        names = [tool.name for tool in listed.tools]
        assert set(names) == set(_TOOL_NAMES), names
        wire = _Wire(
            session,
            transcript,
            {tool.name: tool.input_schema for tool in listed.tools},
        )
        import hashlib as _hashlib

        transcript.append({
            "schema_digest": _hashlib.sha256(
                _json.dumps(
                    {tool.name: tool.input_schema
                     for tool in listed.tools},
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
        })
        by_name = {tool.name: tool for tool in listed.tools}
        assert "Registered repositories: synth." in (
            by_name["status"].description
        ), by_name["status"].description
        submit_schema = by_name["submit_interpretation"].input_schema
        assert "$defs" in submit_schema
        assert "SemanticInterpretationResult" in submit_schema["$defs"]
        assert set(submit_schema["required"]) >= {
            "continuation", "result", "repository_id",
        }

        async def _submit_covering(pending, locator, summary):
            subject = pending["request"]["subjects"][0]["subject_id"]
            assert subject["canonical_locator"] == locator
            ref = pending["request"]["evidence_units"][0]["evidence_ref"]
            claim = _claim_for(subject, summary, ref)
            result = _covering_result(pending, claim)
            payload, is_error = await wire.call(
                "submit_interpretation",
                {
                    "continuation": pending["continuation"],
                    "result": result,
                    "repository_id": "synth",
                },
            )
            assert not is_error, payload
            return payload, claim, result

        payload, is_error = await wire.call(
            "status", {"repository_id": "synth", "target": None}
        )
        assert not is_error, payload
        assert payload["content"].get("readiness") == "READY", payload

        # Exact-path explain -> pending -> schema-built submit -> answer.
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, alpha_claim_full, _ = await _submit_covering(
            payload, "src/alpha.py", "alpha computes the value"
        )
        alpha_claim = answer["content"]["claims"][0]["claim_id"]["value"]
        alpha_subject = alpha_claim_full["subject"]

        # Fresh readback recovers the same claim without resubmission.
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "continuation" not in payload, payload
        assert [
            c["claim_id"]["value"]
            for c in payload["content"]["claims"]
        ] == [alpha_claim]

        # Question-specific trace suspends, then answers after submit.
        payload, is_error = await wire.call(
            "trace",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py"),
             "direction": "BOTH"},
        )
        assert not is_error, payload
        if "continuation" in payload:
            answer, _, _ = await _submit_covering(
                payload, "src/alpha.py", "alpha computes the value"
            )
        else:
            answer = payload
        assert "content" in answer, answer

        # Authority separates normative ownership from observation:
        # the source-only claim stays unresolved without authority.
        payload, is_error = await wire.call(
            "authority",
            {"repository_id": "synth",
             "target": _tagged_selector("src/alpha.py")},
        )
        assert not is_error, payload
        if "continuation" in payload:
            answer, _, _ = await _submit_covering(
                payload, "src/alpha.py", "alpha computes the value"
            )
        else:
            answer = payload
        assert "UNRESOLVED" in _json.dumps(answer), answer

        # Discriminated impact: the pending slice carries kind and
        # description digest; submit then answers with conditions.
        payload, is_error = await wire.call(
            "impact",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py"),
             "change_kind": "BEHAVIOR"},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        pending_slice = payload["request"]["question"]["question_slice"]
        assert "|kind=BEHAVIOR|desc=" in pending_slice, pending_slice
        answer, _, _ = await _submit_covering(
            payload, "src/alpha.py", "alpha computes the value"
        )
        assert "change_conditions" in answer["content"], answer

        # Establish the second subject for the isolation check.
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": "synth",
             "target": _selector("src/beta.py")},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, beta_full, _ = await _submit_covering(
            payload, "src/beta.py", "beta holds the other value"
        )
        beta_claim = answer["content"]["claims"][0]["claim_id"]["value"]
        beta_subject = beta_full["subject"]
        beta_evidence = beta_full["evidence"][0]

        # Freshness: mutate the source, then read back stale.
        (work / "src" / "alpha.py").write_text(
            "VALUE = 1\n# touched\n", encoding="utf-8"
        )
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _tagged_selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "STALE" in _json.dumps(payload), payload

        # Refresh correction on alpha only.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _tagged_selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _, _ = await _submit_covering(
            payload, "src/alpha.py", "alpha computes the value"
        )
        assert "content" in answer, answer

        # Correction isolation: beta's coverage is still answered.
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py")},
        )
        assert not is_error, payload
        beta_views = payload["content"].get("question_coverage", [])
        assert any(
            view.get("effective_disposition") == "ANSWERED"
            for view in beta_views
        ), payload
        assert beta_claim in _json.dumps(payload), payload

        # Second OPEN question on the same subject: correcting one
        # question preserves the other's explicit gap reason (S8.2).
        # Asked through a pending trace task so the coverage lands in
        # the task's own subject scope.
        payload, is_error = await wire.call(
            "trace",
            {"repository_id": "synth",
             "target": _selector("src/beta.py"),
             "direction": "BOTH"},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        open_coverage = {
            "question": {
                "scope_root": beta_subject,
                "subject": beta_subject,
                "question_class": "CQ_01",
                "question_slice": "beta second question",
                "materiality_basis": "wire acceptance second question",
            },
            "decision": {
                "disposition": "OPEN",
                "evidence_scope": {"paths": [], "evidence_refs": []},
                "resolution_requirements": [{
                    "kind": "MISSING_SEMANTIC_COVERAGE",
                    "subject_or_claim": {"$type": "SubjectId", **beta_subject},
                    "description": "second gap stays open",
                    "supporting_context": [],
                }],
                "disposition_basis": "wire acceptance open question",
            },
        }
        trace_question = payload["request"]["question"]
        trace_subject = payload["request"]["subjects"][0]["subject_id"]
        trace_ref = payload["request"]["evidence_units"][0]["evidence_ref"]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": payload["continuation"],
             "result": {
                 "claims": [_claim_for(
                     trace_subject, "beta trace look", trace_ref
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "question_decision": {
                     "disposition": "ANSWERED",
                     "evidence_scope": {"paths": [], "evidence_refs": []},
                     "resolution_requirements": [],
                     "disposition_basis": "wire acceptance",
                 },
                 "proposed_questions": [open_coverage],
                 "candidate_withdrawals": [],
                 "governing_source_refs": [],
                 "diagnostics": [],
                 "proposed_target_inventory_accounting": [],
                 "proposed_target_questions": [],
             },
             "repository_id": "synth"},
        )
        assert not is_error, answer
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py")},
        )
        assert not is_error, payload
        assert "second gap stays open" in _json.dumps(payload), payload

        # Unchanged-source challenge: explicit refresh on unmutated
        # scope still suspends, submits, and answers; the consumed
        # continuation cannot be reused.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py"),
             "stale_only": False},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        refresh_token = payload["continuation"]
        answer, _, refresh_result = await _submit_covering(
            payload, "src/beta.py", "beta holds the other value"
        )
        assert "content" in answer, answer
        payload, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": refresh_token,
             "result": refresh_result,
             "repository_id": "synth"},
        )
        assert is_error, payload
        assert payload.get("error") == "unavailable", payload

        # Installed no-fallback case (S8.5): correcting beta's refreshed
        # question must not replace the second question's explicit gap
        # explanation with generic pending scaffolding.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py"),
             "stale_only": False},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _, _ = await _submit_covering(
            payload, "src/beta.py", "beta holds the other value"
        )
        assert "content" in answer, answer
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py")},
        )
        assert not is_error, payload
        second_views = [
            view for view in payload["content"].get("question_coverage", [])
            if view.get("question", {}).get("question_slice")
            == "beta second question"
        ]
        assert len(second_views) == 1, payload
        assert (
            second_views[0].get("effective_disposition") == "OPEN"
        ), payload
        assert [
            req.get("description")
            for req in second_views[0].get("resolution_requirements", [])
        ] == ["second gap stays open"], payload

        # Installed shared-withdrawal case (S8.5/S8.3): a dependent
        # coverage explicitly referencing beta's claim reopens with the
        # actual withdrawal reason when that claim is withdrawn. The
        # extra coverage rides a fresh impact task (refresh admits no
        # brand-new questions, only corrections of persisted ones).
        beta_ref = {
            "$type": "ClaimRef", "kind": "CLAIM",
            "id": {"value": beta_claim},
        }
        payload, is_error = await wire.call(
            "impact",
            {"repository_id": "synth",
             "target": _selector("src/beta.py"),
             "change_kind": "BEHAVIOR"},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        refresh_question = payload["request"]["question"]
        refresh_subject = payload["request"]["subjects"][0]["subject_id"]
        refresh_ref = payload["request"]["evidence_units"][0]["evidence_ref"]
        shared_requirement = {
            "kind": "MISSING_AUTHORITY",
            "subject_or_claim": {"$type": "SubjectId", **refresh_subject},
            "description": "shared dependent original gap",
            "supporting_context": [],
        }
        shared_slice = refresh_question["question_slice"]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": payload["continuation"],
             "result": {
                 "claims": [_claim_for(
                     beta_subject, "beta holds the other value",
                     beta_evidence
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "question_decision": {
                     "disposition": "ANSWERED",
                     "evidence_scope": {"paths": [], "evidence_refs": []},
                     "resolution_requirements": [shared_requirement],
                     "disposition_basis": "wire acceptance shared output",
                 },
                 "proposed_questions": [],
                 "candidate_withdrawals": [],
                 "governing_source_refs": [],
                 "diagnostics": [],
                 "proposed_target_inventory_accounting": [],
                 "proposed_target_questions": [],
             },
             "repository_id": "synth"},
        )
        assert not is_error, answer
        shared_claims = [
            claim for claim in answer["content"]["claims"]
            if claim["value"].get("summary") == "beta holds the other value"
        ]
        # Re-materializing the identical canonical claim content makes the
        # second answered question a co-owner of beta's exact claim id.
        assert shared_claims, answer
        assert (
            shared_claims[0]["claim_id"]["value"] == beta_claim
        ), shared_claims
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py"),
             "stale_only": False},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        withdraw_ref = payload["request"]["evidence_units"][0][
            "evidence_ref"]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": payload["continuation"],
             "result": {
                 "claims": [_claim_for(
                     payload["request"]["subjects"][0]["subject_id"],
                     "beta withdraw look", withdraw_ref
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "question_decision": {
                     "disposition": "ANSWERED",
                     "evidence_scope": {"paths": [], "evidence_refs": []},
                     "resolution_requirements": [],
                     "disposition_basis": "wire acceptance",
                 },
                 "proposed_questions": [],
                 "candidate_withdrawals": [{
                     "target": beta_ref,
                     "basis": {
                         "derivation": "SEMANTIC_INTERPRETATION",
                         "summary": (
                             "retracted: wire test withdraws "
                             "shared beta basis"
                         ),
                     },
                     "evidence": [withdraw_ref],
                 }],
                 "governing_source_refs": [],
                 "diagnostics": [],
                 "proposed_target_inventory_accounting": [],
                 "proposed_target_questions": [],
             },
             "repository_id": "synth"},
        )
        assert not is_error, answer
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py")},
        )
        assert not is_error, payload
        shared_views = [
            view for view in payload["content"].get("question_coverage", [])
            if view.get("question", {}).get("question_slice")
            == shared_slice
        ]
        assert len(shared_views) == 1, payload
        assert (
            shared_views[0].get("effective_disposition") == "PENDING"
        ), payload
        shared_reasons = [
            req.get("description")
            for req in shared_views[0].get("resolution_requirements", [])
        ]
        assert any(
            "retracted: wire test withdraws shared beta basis" in text
            for text in shared_reasons
        ), payload
        assert "shared dependent original gap" in shared_reasons, payload

        # Installed malformed-ingress case (S9.6): a submission
        # missing its required result is a deterministic ingress
        # error that retains the live continuation for correction.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _tagged_selector("src/beta.py"),
             "stale_only": False},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        malformed_pending = payload
        malformed_token = payload["continuation"]
        payload, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": malformed_token,
             "repository_id": "synth"},
            validate=False,
        )
        assert is_error, payload
        assert payload.get("error") == "ingress", payload
        assert "result" in payload.get("message", ""), payload
        answer, _, _ = await _submit_covering(
            malformed_pending, "src/beta.py", "beta holds the other value"
        )
        assert "content" in answer, answer
    finally:
        await stack.aclose()

    # -- phase 1b: untouched PENDING and semantic rejection recovery -----
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        selection = {
            "question_slice": "wire pending semantics",
            "materiality_basis": "wire acceptance pending semantics",
            "question_anchors": [],
        }
        pending, is_error = await wire.call(
            "explain",
            {
                "repository_id": "synth",
                "target": _selector("src/beta.py"),
                "question_selection": selection,
            },
        )
        assert not is_error, pending
        assert "continuation" in pending, pending
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": {
                    "question_decision": {"disposition": "PENDING"}
                },
                "repository_id": "synth",
            },
        )
        assert not is_error, answer
        assert "content" in answer, answer
        assert any(
            view.get("recorded_disposition") == "PENDING"
            for view in answer["content"].get("question_coverage", [])
        ), answer
        again, is_error = await wire.call(
            "explain",
            {
                "repository_id": "synth",
                "target": _selector("src/beta.py"),
                "question_selection": selection,
            },
        )
        assert not is_error, again
        if "content" in again:
            assert any(
                view.get("recorded_disposition") == "PENDING"
                for view in again["content"].get("question_coverage", [])
            ), again
        else:
            assert "continuation" in again, again
        transcript.append({"phase": "untouched-pending", "ok": True})

        # Semantic rejection keeps the same live continuation.
        selection = {
            "question_slice": "wire validation recovery",
            "materiality_basis": "wire acceptance validation recovery",
            "question_anchors": [],
        }
        pending, is_error = await wire.call(
            "explain",
            {
                "repository_id": "synth",
                "target": _selector("src/beta.py"),
                "question_selection": selection,
            },
        )
        assert not is_error, pending
        assert "continuation" in pending, pending
        subject = pending["request"]["subjects"][0]["subject_id"]
        ref = pending["request"]["evidence_units"][0]["evidence_ref"]
        bad = _claim_for(subject, "uncited", ref)
        bad["evidence"] = []
        rejected, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": {"claims": [bad]},
                "repository_id": "synth",
            },
        )
        assert is_error, rejected
        assert rejected.get("error") == "validation", rejected
        corrected, _, _ = await _submit_covering(
            pending, "src/beta.py", "beta holds the other value"
        )
        assert "content" in corrected, corrected
        transcript.append({"phase": "validation-recovery", "ok": True})
    finally:
        await stack.aclose()

    # -- phase 2: new server process, same store -------------------------
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "continuation" not in payload, payload
        # Fresh-session reuse: the original claim still resolves. The
        # refresh correction may have added a superseding claim citing
        # current evidence, so this asserts membership, not equality.
        assert alpha_claim in [
            c["claim_id"]["value"]
            for c in payload["content"]["claims"]
        ], payload
        transcript.append({"phase": "reuse-across-restart", "ok": True})
    finally:
        await stack.aclose()

    # The provider build must have produced the index in Span's data
    # directory, never in the target.
    assert not (work / "graft").exists(), (
        "target structural artifact was written"
    )
    assert (
        data_dir / "structural" / work.name / ".graph" / "wiring.json"
    ).is_file(), "provider index was not built into the data directory"

    # -- phase 3: unregistered setup call, one locator -------------------
    stack, session, _ = await _session(register=False)
    try:
        wire = _Wire(session, transcript)
        payload, is_error = await wire.call(
            "initialize_repository",
            {"repository_locator": str(work)},
        )
        assert not is_error, payload
        assert payload["readiness"] == "READY", payload
        assert payload["repository_id"] == work.name, payload
        transcript.append({"phase": "setup-one-locator", "ok": True})
    finally:
        await stack.aclose()

    # -- phase 4: multi-member target mapping and service-owned CQ-01 ----
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        payload, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": {"paths": ["src"], "evidence_refs": []},
                "objective": "wire target mapping",
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        items = payload["request"]["target_inventory_items"]
        bound_ids = [
            item["evidence_ref"]["evidence_id"]["value"] for item in items
        ]
        assert len(bound_ids) >= 2, payload
        template_rule = payload["request"]["brief"]["submission_rules"][-1]
        template = _json.loads(template_rule.split(": ", 1)[1])
        template_ids = [
            account["evidence_id"]["value"]
            for account in template["proposed_target_inventory_accounting"]
        ]
        assert template_ids == bound_ids, (template_ids, bound_ids)
        area = {
            "provisional_locator": "src",
            "kind": "COMPONENT",
            "display_name": "src",
            "evidence": [items[0]["evidence_ref"]],
            "basis": {
                "derivation": "SEMANTIC_INTERPRETATION",
                "summary": "wire acceptance maps the src area",
            },
        }
        area_id = {
            "repository_id": "synth",
            "subject_kind": "COMPONENT",
            "canonical_locator": "src",
        }
        result = {
            "candidate_subjects": [area],
            "proposed_target_inventory_accounting": [
                {
                    "evidence_id": {"value": evidence_id},
                    "assigned_area_subjects": [area_id],
                }
                for evidence_id in bound_ids
            ],
        }
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": payload["continuation"],
                "result": result,
                "repository_id": "synth",
            },
        )
        assert not is_error, answer
        # Re-enter the target frontier: the service-owned first-admission
        # CQ-01 must now be the pending unit for the admitted area.
        payload, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": {"paths": ["src"], "evidence_refs": []},
                "objective": "wire target mapping",
            },
        )
        assert not is_error, payload
        assert payload["request"]["question"]["question_class"] == "CQ_01", payload
        assert "service-owned first-admission" in (
            payload["request"]["question"]["materiality_basis"]
        ), payload
        seed_scope = payload["request"]["question"]
        transcript.append({
            "phase": "target-mapping-and-cq01-seed",
            "ok": True,
            "bound_ids": bound_ids,
        })
    finally:
        await stack.aclose()

    # -- phase 4a: existing target question reuse ------------------------
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        scope = {"paths": ["src/alpha.py"], "evidence_refs": []}
        pending, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": scope,
                "objective": "wire target question reuse",
            },
        )
        assert not is_error, pending
        assert pending["request"]["question"] is None, pending
        items = pending["request"]["target_inventory_items"]
        assert len(items) == 1, pending
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": {
                    "proposed_target_inventory_accounting": [{
                        "evidence_id": {
                            "value": items[0]["evidence_ref"][
                                "evidence_id"
                            ]["value"],
                        },
                        "assigned_area_subjects": [area_id],
                    }],
                    "proposed_target_questions": [seed_scope],
                },
                "repository_id": "synth",
            },
        )
        assert not is_error, answer
        again, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": scope,
                "objective": "wire target question reuse",
            },
        )
        assert not is_error, again
        assert again["request"]["question"]["question_slice"] == (
            seed_scope["question_slice"]
        ), again
        transcript.append({"phase": "target-question-reuse", "ok": True})
    finally:
        await stack.aclose()

    # -- phase 4b: unresolved mapping is accepted but non-progressing ----
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        scope = {"paths": ["src/beta.py"], "evidence_refs": []}
        pending, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": scope,
                "objective": "wire unresolved mapping",
            },
        )
        assert not is_error, pending
        assert pending["request"]["question"] is None, pending
        items = pending["request"]["target_inventory_items"]
        assert items, pending
        rules = " ".join(pending["request"]["brief"]["submission_rules"])
        assert "non-progressing" in rules, rules
        ids = [
            item["evidence_ref"]["evidence_id"]["value"] for item in items
        ]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": {
                    "proposed_target_inventory_accounting": [
                        {
                            "evidence_id": {"value": evidence_id},
                            "resolution_requirements": [{
                                "kind": "MISSING_SEMANTIC_COVERAGE",
                                "description": "wire unresolved mapping",
                            }],
                        }
                        for evidence_id in ids
                    ],
                },
                "repository_id": "synth",
            },
        )
        assert not is_error, answer
        again, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": "synth",
                "target": scope,
                "objective": "wire unresolved mapping",
            },
        )
        assert not is_error, again
        # The unresolved account is accepted without claiming target
        # completion; the frontier may move to the CQ-01 semantic unit.
        if "request" in again:
            assert again["request"]["question"] is None or (
                again["request"]["question"]["question_class"] == "CQ_01"
            ), again
        else:
            assert "content" in again, again
        transcript.append({"phase": "unresolved-mapping", "ok": True})
    finally:
        await stack.aclose()

    # -- phase 5: opaque pagination and cross-request rejection ----------
    stack, session, _ = await _session()
    try:
        wire = _Wire(session, transcript)
        small = {
            "max_results": 1, "max_depth": 5, "max_subjects": 1,
            "max_evidence_units": 24, "max_evidence_bytes": 96000,
            "max_candidate_claims": 64, "max_candidate_relationships": 64,
        }
        first, is_error = await wire.call(
            "status",
            {"repository_id": "synth", "target": None, "bounds": small},
        )
        assert not is_error, first
        token = first["bound_info"]["continuation_token"]
        assert token, first
        second, is_error = await wire.call(
            "status",
            {
                "repository_id": "synth", "target": None,
                "bounds": small, "page_token": token,
            },
        )
        assert not is_error, second
        changed = dict(small)
        changed["max_subjects"] = 2
        mismatched, is_error = await wire.call(
            "status",
            {
                "repository_id": "synth", "target": None,
                "bounds": changed, "page_token": token,
            },
        )
        assert is_error, mismatched
        assert "page token is invalid" in mismatched["message"], mismatched
        target_mismatch, target_error = await wire.call(
            "status",
            {
                "repository_id": "synth",
                "target": _tagged_selector("src/beta.py"),
                "bounds": small,
                "page_token": token,
            },
        )
        assert target_error, target_mismatch
        assert "page token is invalid" in target_mismatch["message"], target_mismatch
        located, locate_error = await wire.call(
            "locate",
            {
                "repository_id": "synth",
                "mode": "SYMBOL",
                "query": "src",
                "match": "CONTAINS",
                "bounds": small,
            },
        )
        if not locate_error:
            structural_token = located["bound_info"]["continuation_token"]
            if structural_token:
                page_two, page_error = await wire.call(
                    "locate",
                    {
                        "repository_id": "synth",
                        "mode": "SYMBOL",
                        "query": "src",
                        "match": "CONTAINS",
                        "bounds": small,
                        "page_token": structural_token,
                    },
                )
                assert not page_error, page_two
        transcript.append({"phase": "opaque-pagination", "ok": True})
    finally:
        await stack.aclose()
    return alpha_claim, beta_claim


