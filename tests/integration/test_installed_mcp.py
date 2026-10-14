"""Installed MCP-process acceptance lane (Addendum I S9.3/S9.5/S9.8).

Builds an isolated virtualenv with a non-editable install of the
current source tree (plus a generated packaging-time ``BUILD_IDENTITY``)
and drives the S9.3 behavior matrix through the installed ``span-mcp``
console entrypoint over MCP stdio: tool/schema parity, observational
status, exact-path retrieval, schema-built submission, fresh-session
reuse, question-specific trace, authority separation, discriminated
impact, freshness mutation, refresh correction, and correction
isolation. A second server process over the same data directory proves
reuse without conversational memory.

The client path uses no ``span.*`` imports: request shapes come from
the server's own ``tools/list`` schemas and pending payloads, and all
assertions read wire JSON. A service-unit pass cannot substitute for
this gate. Requires ``uv`` and network access to build the isolated
environment; skips otherwise.
"""

import asyncio as _asyncio
import contextlib as _contextlib
import hashlib as _hashlib
import json as _json
import os as _os
import pathlib as _pathlib
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import unittest as _unittest

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
    "reissue_interpretation",
    "locate",
    "neighbors",
)

_REPO_FILES = {
    "README.md": "# synth\n\nSynthetic repository.\n",
    "src/alpha.py": "VALUE = 1\n",
    "src/beta.py": "OTHER = 2\n",
}

# Source set hashed into the packaging-time content digest. Mirrors
# the files the distribution is built from.
_SOURCE_SET = (
    "src",
    "pyproject.toml",
    "README.md",
)


def _tree_digest(root):
    """Content digest over the exact source bytes (sorted, deterministic).

    Dirty-tree-inclusive: two different working trees never share an
    identity even at one HEAD revision.
    """
    files = []
    for entry in _SOURCE_SET:
        path = root / entry
        if path.is_dir():
            for dirpath, dirnames, filenames in _os.walk(path):
                dirnames[:] = sorted(
                    d for d in dirnames if d != "__pycache__"
                )
                for name in sorted(filenames):
                    if name.endswith((".pyc", ".pyo")):
                        continue
                    files.append(_pathlib.Path(dirpath) / name)
        elif path.is_file():
            files.append(path)
    digest = _hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _tree_revision(root):
    try:
        head = _subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            capture_output=True, text=True, timeout=30,
        )
        dirty = _subprocess.run(
            ("git", "-C", str(root), "diff", "--quiet"),
            timeout=30,
        )
        if head.returncode != 0:
            return "unknown"
        return head.stdout.strip() + (
            "" if dirty.returncode == 0 else "-dirty"
        )
    except (OSError, _subprocess.SubprocessError):
        return "unknown"


def _ensure_isolated_exe(work):
    """Install the current tree non-editably into a fresh venv.

    Returns (exe path, identity dict). The install carries a generated
    packaging-time BUILD_IDENTITY; the source tree is never on the
    isolated interpreter's path.
    """
    if _shutil.which("uv") is None:
        raise AssertionError(
            "S9.8 BLOCKED: uv is unavailable, so the isolated "
            "install cannot be established; refusing to pass the "
            "installed gate without it"
        )
    repo_root = _pathlib.Path(__file__).resolve().parents[2]
    srctree = work / "srctree"
    _shutil.copytree(
        repo_root / "src", srctree / "src",
        ignore=_shutil.ignore_patterns("__pycache__"),
    )
    for name in ("pyproject.toml", "README.md"):
        _shutil.copy(repo_root / name, srctree / name)
    identity = {
        "source_revision": _tree_revision(repo_root),
        "source_digest": _tree_digest(repo_root),
    }
    (srctree / "src" / "span" / "BUILD_IDENTITY").write_text(
        _json.dumps(identity, sort_keys=True), encoding="utf-8"
    )
    venv = work / "iso-venv"
    _subprocess.run(
        ("uv", "venv", str(venv)), check=True, timeout=300,
        capture_output=True,
    )
    isolated_python = str(venv / "bin" / "python")
    _subprocess.run(
        ("uv", "pip", "install", "--python", isolated_python,
         str(srctree)),
        check=True, timeout=900, capture_output=True,
    )
    return str(venv / "bin" / "span-mcp"), isolated_python, identity


def _write_repo(work):
    for rel, content in _REPO_FILES.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # git identity for structural currency (mirrors the provision
    # path test).
    for args in (
        ("init", "-q"),
        ("add", "-A"),
        (
            "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "held-out",
        ),
    ):
        _subprocess.run(
            ("git", "-C", str(work), *args),
            check=True, timeout=60,
        )
    # Minimal explicitly-built wiring the test owns: the server never
    # builds the structural index.
    graph_dir = work / "graft" / ".graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    nodes = []
    for rel in ("README.md", "src/alpha.py", "src/beta.py"):
        body = (work / rel).read_text(encoding="utf-8")
        nodes.append({
            "id": rel,
            "name": _pathlib.Path(rel).name,
            "kind": "file",
            "path": rel,
            "body_hash": _hashlib.sha256(body.encode("utf-8")).hexdigest(),
        })
    (graph_dir / "wiring.json").write_text(
        _json.dumps({"nodes": nodes, "edges": []}), encoding="utf-8"
    )


def _selector(path):
    return {
        "$type": "SubjectSelector",
        "exact_subject_id": None,
        "name_or_locator": path,
        "expected_kinds": [],
        "retrieval_scope_hint": None,
    }


def _claim_for(subject, summary, ref):
    return {
        "$type": "CandidateSemanticClaim",
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
            "$type": "SemanticBasis",
            "derivation": "SEMANTIC_INTERPRETATION",
            "summary": "wire acceptance observes the file",
        },
    }


def _covering_result(pending, claim):
    question = pending["request"]["question"]
    coverage = {
        "$type": "InterpretationCoverage",
        "subjects": [question["subject"]],
        "question_slice": question["question_slice"],
        "evidence_scope": {
            "$type": "EvidenceScope", "paths": [], "evidence_refs": [],
        },
        "declared_complete": True,
        "question": question,
        "disposition": "ANSWERED",
        "result_refs": [],
        "resolution_requirements": [],
        "disposition_basis": "installed wire acceptance",
        "question_evidence": [],
    }
    return {
        "$type": "SemanticInterpretationResult",
        "claims": [claim],
        "relationships": [],
        "candidate_subjects": [],
        "candidate_conflicts": [],
        "proposed_question_coverages": [coverage],
        "candidate_withdrawals": [],
        "governing_source_refs": [],
        "diagnostics": [],
        "proposed_target_inventory_accounting": [],
        "proposed_target_questions": [],
    }


class _Wire:
    """Thin stdio client wrapper with a JSONL transcript."""

    def __init__(self, session, transcript):
        self._session = session
        self._transcript = transcript

    async def call(self, tool, args):
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


async def _lane(exe, work, data_dir, transcript):
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    env = {
        key: value for key, value in _os.environ.items()
        if key != "PYTHONPATH"
    }

    async def _session():
        params = StdioServerParameters(
            command=exe, args=["--data-dir", str(data_dir),
                               "--repo", str(work)], env=env,
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
        wire = _Wire(session, transcript)
        listed = await session.list_tools()
        names = [tool.name for tool in listed.tools]
        assert set(names) == set(_TOOL_NAMES), names
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
             "direction": "BOTH", "relationship_filter": None,
             "boundary_only": False},
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
             "target": _selector("src/alpha.py")},
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
             "change_kind": "BEHAVIOR",
             "change_description": "double the value",
             "affected_assertions": []},
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

        # Freshness: mutate the source, then read back stale.
        (work / "src" / "alpha.py").write_text(
            "VALUE = 1\n# touched\n", encoding="utf-8"
        )
        payload, is_error = await wire.call(
            "status",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "STALE" in _json.dumps(payload), payload

        # Refresh correction on alpha only.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _selector("src/alpha.py")},
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
             "target": _selector("src/beta.py")},
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
             "direction": "BOTH", "relationship_filter": None,
             "boundary_only": False},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        open_coverage = {
            "$type": "InterpretationCoverage",
            "subjects": [beta_subject],
            "question_slice": "beta second question",
            "evidence_scope": {
                "$type": "EvidenceScope", "paths": [],
                "evidence_refs": [],
            },
            "declared_complete": False,
            "question": {
                "$type": "SemanticQuestionScope",
                "scope_root": beta_subject,
                "subject": beta_subject,
                "question_class": "CQ_01",
                "question_slice": "beta second question",
                "materiality_basis": "wire acceptance second question",
            },
            "disposition": "OPEN",
            "result_refs": [],
            "resolution_requirements": [{
                "$type": "ResolutionRequirement",
                "kind": "MISSING_SEMANTIC_COVERAGE",
                "subject_or_claim": beta_subject,
                "description": "second gap stays open",
                "supporting_context": [],
            }],
            "disposition_basis": "wire acceptance open question",
            "question_evidence": [],
        }
        trace_question = payload["request"]["question"]
        trace_subject = payload["request"]["subjects"][0]["subject_id"]
        trace_ref = payload["request"]["evidence_units"][0]["evidence_ref"]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": payload["continuation"],
             "result": {
                 "$type": "SemanticInterpretationResult",
                 "claims": [_claim_for(
                     trace_subject, "beta trace look", trace_ref
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "proposed_question_coverages": [
                     {
                         "$type": "InterpretationCoverage",
                         "subjects": [trace_question["subject"]],
                         "question_slice":
                             trace_question["question_slice"],
                         "evidence_scope": {
                             "$type": "EvidenceScope", "paths": [],
                             "evidence_refs": [],
                         },
                         "declared_complete": True,
                         "question": trace_question,
                         "disposition": "ANSWERED",
                         "result_refs": [],
                         "resolution_requirements": [],
                         "disposition_basis": "wire acceptance",
                         "question_evidence": [],
                     },
                     open_coverage,
                 ],
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
             "target": _selector("src/beta.py")},
        )
        assert not is_error, payload
        assert "second gap stays open" in _json.dumps(payload), payload

        # Unchanged-source challenge: explicit refresh on unmutated
        # scope still suspends, submits, and answers; the consumed
        # continuation cannot be reused.
        payload, is_error = await wire.call(
            "refresh",
            {"repository_id": "synth",
             "target": _selector("src/beta.py"),
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
             "target": _selector("src/beta.py"),
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
             "target": _selector("src/beta.py")},
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
            "id": {"$type": "ClaimId", "value": beta_claim},
        }
        payload, is_error = await wire.call(
            "impact",
            {"repository_id": "synth",
             "target": _selector("src/beta.py"),
             "change_kind": "BEHAVIOR",
             "change_description": "wire test shared output",
             "affected_assertions": []},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        refresh_question = payload["request"]["question"]
        refresh_subject = payload["request"]["subjects"][0]["subject_id"]
        refresh_ref = payload["request"]["evidence_units"][0]["evidence_ref"]
        shared_coverage = {
            "$type": "InterpretationCoverage",
            "subjects": [refresh_subject],
            "question_slice": "beta depends on shared",
            "evidence_scope": {
                "$type": "EvidenceScope", "paths": [],
                "evidence_refs": [],
            },
            "declared_complete": True,
            "question": {
                "$type": "SemanticQuestionScope",
                "scope_root": refresh_subject,
                "subject": refresh_subject,
                "question_class": "CQ_01",
                "question_slice": "beta depends on shared",
                "materiality_basis": "wire acceptance shared output",
            },
            "disposition": "ANSWERED",
            "result_refs": [beta_ref],
            "resolution_requirements": [{
                "$type": "ResolutionRequirement",
                "kind": "MISSING_AUTHORITY",
                "subject_or_claim": refresh_subject,
                "description": "shared dependent original gap",
                "supporting_context": [],
            }],
            "disposition_basis": "wire acceptance shared output",
            "question_evidence": [],
        }
        answer, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": payload["continuation"],
             "result": {
                 "$type": "SemanticInterpretationResult",
                 "claims": [_claim_for(
                     refresh_subject, "beta refresh look", refresh_ref
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "proposed_question_coverages": [
                     {
                         "$type": "InterpretationCoverage",
                         "subjects": [refresh_question["subject"]],
                         "question_slice":
                             refresh_question["question_slice"],
                         "evidence_scope": {
                             "$type": "EvidenceScope", "paths": [],
                             "evidence_refs": [],
                         },
                         "declared_complete": True,
                         "question": refresh_question,
                         "disposition": "ANSWERED",
                         "result_refs": [],
                         "resolution_requirements": [],
                         "disposition_basis": "wire acceptance",
                         "question_evidence": [],
                     },
                     shared_coverage,
                 ],
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
            "refresh",
            {"repository_id": "synth",
             "target": _selector("src/beta.py"),
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
                 "$type": "SemanticInterpretationResult",
                 "claims": [_claim_for(
                     payload["request"]["subjects"][0]["subject_id"],
                     "beta withdraw look", withdraw_ref
                 )],
                 "relationships": [],
                 "candidate_subjects": [],
                 "candidate_conflicts": [],
                 "proposed_question_coverages": [
                     {
                         "$type": "InterpretationCoverage",
                         "subjects": [payload["request"]["subjects"][0][
                             "subject_id"]],
                         "question_slice": payload["request"][
                             "question"]["question_slice"],
                         "evidence_scope": {
                             "$type": "EvidenceScope", "paths": [],
                             "evidence_refs": [],
                         },
                         "declared_complete": True,
                         "question": payload["request"]["question"],
                         "disposition": "ANSWERED",
                         "result_refs": [],
                         "resolution_requirements": [],
                         "disposition_basis": "wire acceptance",
                         "question_evidence": [],
                     },
                 ],
                 "candidate_withdrawals": [{
                     "$type": "CandidateSemanticWithdrawal",
                     "target": beta_ref,
                     "basis": {
                         "$type": "SemanticBasis",
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
             "target": _selector("src/beta.py")},
        )
        assert not is_error, payload
        shared_views = [
            view for view in payload["content"].get("question_coverage", [])
            if view.get("question", {}).get("question_slice")
            == "beta depends on shared"
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
             "target": _selector("src/beta.py"),
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
    return alpha_claim, beta_claim


class InstalledMcpDriverTest(_unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = _pathlib.Path(
            _tempfile.mkdtemp(prefix="span-installed-mcp-")
        )
        cls.addClassCleanup(_shutil.rmtree, cls.tmp, True)
        cls.exe, cls.isolated_python, cls.identity = (
            _ensure_isolated_exe(cls.tmp / "gate")
        )
        proc = _subprocess.run(
            [cls.isolated_python, "-c",
             "import span, json, sys;"
             "print(span.__file__);"
             "print(sys.version.split()[0]);"
             "print(open(__import__('pathlib').Path(span.__file__)"
             ".resolve().parent / 'BUILD_IDENTITY').read())"],
            capture_output=True, text=True, timeout=120,
            cwd=str(cls.tmp),
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        if proc.returncode != 0:
            raise AssertionError(
                "S9.8 BLOCKED: isolated package identity unreadable: "
                + proc.stderr[-2000:]
            )
        location, interpreter, identity_json = (
            proc.stdout.strip().splitlines()
        )
        if "site-packages" not in location:
            raise AssertionError(
                "S9.8 BLOCKED: isolated install resolves inside the "
                f"source tree: {location}"
            )
        identity = _json.loads(identity_json)
        if identity.get("source_digest") != cls.identity["source_digest"]:
            raise AssertionError(
                "S9.8 BLOCKED: installed BUILD_IDENTITY digest mismatch"
            )
        cls.pkg_location = location
        cls.pkg_identity = identity
        cls.pkg_interpreter = interpreter
        cls.pkg_interpreter_path = cls.isolated_python

    def test_installed_entrypoint_resolved(self):
        proc = _subprocess.run(
            [self.exe, "--help"],
            capture_output=True, text=True, timeout=120,
            env={k: v for k, v in _os.environ.items()
                 if k != "PYTHONPATH"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        # Resolved in setUpClass: installed package outside any source
        # tree with matching packaging-time identity.
        self.assertIn("site-packages", self.pkg_location)
        self.assertEqual(
            self.pkg_identity["source_digest"],
            self.identity["source_digest"],
        )
        self.assertEqual(
            self.pkg_identity["source_revision"],
            self.identity["source_revision"],
        )

    def test_installed_mcp_acceptance(self):
        work = self.tmp / "synth"
        work.mkdir(parents=True, exist_ok=True)
        _write_repo(work)
        data_dir = self.tmp / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        transcript = []
        alpha_claim, beta_claim = _asyncio.run(
            _lane(self.exe, work, data_dir, transcript)
        )
        self.assertTrue(alpha_claim)
        self.assertTrue(beta_claim)
        self.assertNotEqual(alpha_claim, beta_claim)
        for entry in transcript:
            print(f"stdio: {_json.dumps(entry, sort_keys=True)}")
        print(f"installed MCP claims: {alpha_claim} {beta_claim}")
        record = {
            "program": "span-mcp-agent-usability (Addendum I, S0-S9)",
            "runner": (
                "local isolated virtualenv with a non-editable "
                "install; installed span-mcp driven over MCP stdio"
            ),
            "command": [
                self.exe, "--data-dir", "<tmp>/data",
                "--repo", "<tmp>/synth",
            ],
            "executable": self.exe,
            "package_location": type(self).pkg_location,
            "interpreter": self.pkg_interpreter,
            "interpreter_path": self.pkg_interpreter_path,
            "package_version": next(
                entry["server_version"] for entry in transcript
                if "server_version" in entry
            ),
            "source_revision": self.identity["source_revision"],
            "source_digest": self.identity["source_digest"],
            "schema_digest": next(
                entry["schema_digest"] for entry in transcript
                if "schema_digest" in entry
            ),
            "exit_code": 0,
            "transcript_path": (
                "span/.context/verification/stdio-transcript.jsonl"
            ),
            "transcript": transcript,
        }
        record_path = (
            _pathlib.Path(__file__).resolve().parents[2]
            / ".context" / "verification" / "record.json"
        )
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            _json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (record_path.parent / "stdio-transcript.jsonl").write_text(
            "\n".join(
                _json.dumps(entry, sort_keys=True)
                for entry in transcript
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    _unittest.main()
