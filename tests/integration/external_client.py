"""Standalone black-box external MCP client (Addendum M §M-10).

This module is client-side test infrastructure only. It imports the
standard library and the MCP client SDK; it does not import Span or any
Span repository helper. Every request payload is checked recursively
against the live ``tools/list`` schema obtained from the same server
before it is sent. Ordinary semantic submissions begin from the public
minimal template returned in ``PendingInterpretation.request.brief``.

The client process also installs a meta-path guard (in the runner) that
fails on any ``span``/``span.*`` import.
"""

from __future__ import annotations

import contextlib as _contextlib
import json as _json
import os as _os

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

#: Public markers for the returned minimal submission templates.
_TEMPLATE_MARKERS = (
    "Minimal submission template",
    "Minimal target-mapping submission template",
)


def _selector(value):
    """Minimal subject selector for schemas with no tagged union."""
    return {"name_or_locator": value}


def _tagged_subject_selector(value):
    """Subject selector for a schema whose advertised union requires $type."""
    return {"$type": "SubjectSelector", "name_or_locator": value}


def _phase(transcript, name, ok=True, **extra):
    """Record one named acceptance phase and require it to be successful."""
    assert ok, (name, extra)
    transcript.append({"phase": name, "ok": True, **extra})


def _discover_repository_id(tools):
    """Read the canonical registered repository ID from public metadata."""
    marker = "Registered repositories: "
    found = []
    for tool in tools:
        text = tool.description or ""
        if marker not in text:
            continue
        tail = text.split(marker, 1)[1]
        listing = tail.split(".", 1)[0]
        found = [part.strip() for part in listing.split(",") if part.strip()]
        break
    assert len(found) == 1, (
        "expected exactly one registered repository in public tool "
        f"metadata, found {found!r}"
    )
    return found[0]


def submission_template_from_pending(pending):
    """Return the public minimal result template for a pending task.

    The template is the JSON payload carried by the returned
    ``request.brief.submission_rules`` entry that begins with the
    documented marker. Nothing here is reconstructed from Span source.
    """
    rules = pending.get("request", {}).get("brief", {}).get("submission_rules", [])
    for rule in rules:
        if not isinstance(rule, str):
            continue
        if not rule.startswith(_TEMPLATE_MARKERS):
            continue
        _prefix, encoded = rule.split(": ", 1)
        template = _json.loads(encoded)
        assert isinstance(template, dict), template
        return template
    raise AssertionError(
        "pending task did not return a minimal submission template: " f"{rules!r}"
    )


class _SchemaViolation(AssertionError):
    """Raised before sending a payload that violates the live schema."""


class _SchemaValidator:
    """Small recursive validator for the JSON Schema Span emits.

    Supports exactly the constructs present in ``tools/list``
    inputSchema values: ``type``, ``properties``, ``required``,
    ``items``, ``enum``, ``const``, local ``$ref`` to ``#/$defs/*``,
    ``anyOf``/``oneOf`` for tagged public unions, ``allOf`` with
    ``if``/``then`` as emitted for claim kind/value agreement, and
    ``additionalProperties: false``. No production dependency and no
    duplicate carrier model.
    """

    def __init__(self, schemas):
        self._schemas = schemas

    def validate_call(self, tool, value):
        schema = self._schemas.get(tool)
        if schema is None:
            raise _SchemaViolation(f"no advertised schema for tool {tool}")
        self._validate(value, schema, schema, "$")

    def validate_definition(self, tool, name, value):
        schema = self._schemas.get(tool)
        if schema is None:
            raise _SchemaViolation(f"no advertised schema for tool {tool}")
        defs = schema.get("$defs", {})
        if name not in defs:
            raise _SchemaViolation(
                f"advertised schema for {tool} has no {name} definition"
            )
        self._validate(
            value,
            {"$ref": f"#/$defs/{name}"},
            schema,
            f"$<{name}>",
        )

    def _matches(self, value, schema, root):
        try:
            self._validate(value, schema, root, "$?")
        except _SchemaViolation:
            return False
        return True

    def _resolve(self, ref, root):
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            raise _SchemaViolation(f"unsupported schema ref: {ref!r}")
        name = ref.rsplit("/", 1)[-1]
        defs = root.get("$defs", {})
        if name not in defs:
            raise _SchemaViolation(f"missing schema definition: {name}")
        return defs[name]

    def _validate(self, value, schema, root, path):
        if not isinstance(schema, dict):
            return
        if "$ref" in schema:
            self._validate(value, self._resolve(schema["$ref"], root), root, path)
            return
        if "const" in schema and value != schema["const"]:
            raise _SchemaViolation(
                f"{path}: expected const {schema['const']!r}, " f"got {value!r}"
            )
        if "enum" in schema and value not in schema["enum"]:
            raise _SchemaViolation(f"{path}: {value!r} not in enum {schema['enum']!r}")
        if "allOf" in schema:
            for branch in schema["allOf"]:
                self._validate(value, branch, root, path)
        if "if" in schema:
            if self._matches(value, schema["if"], root):
                if "then" in schema:
                    self._validate(value, schema["then"], root, path)
            elif "else" in schema:
                self._validate(value, schema["else"], root, path)
        if "anyOf" in schema:
            if not any(
                self._matches(value, branch, root) for branch in schema["anyOf"]
            ):
                raise _SchemaViolation(f"{path}: no anyOf branch matched: {value!r}")
        if "oneOf" in schema:
            matched = sum(
                1 for branch in schema["oneOf"] if self._matches(value, branch, root)
            )
            if matched != 1:
                raise _SchemaViolation(
                    f"{path}: expected exactly one oneOf branch, "
                    f"matched {matched}: {value!r}"
                )
        declared = schema.get("type")
        if declared is not None:
            types = declared if isinstance(declared, list) else [declared]
            if not any(self._type_matches(value, name) for name in types):
                raise _SchemaViolation(
                    f"{path}: expected type {types!r}, " f"got {type(value).__name__}"
                )
        if isinstance(value, dict):
            properties = schema.get("properties")
            if properties is not None:
                for required in schema.get("required", []):
                    if required not in value:
                        raise _SchemaViolation(
                            f"{path}: missing required field " f"{required!r}"
                        )
                if schema.get("additionalProperties") is False:
                    extra = set(value) - set(properties)
                    if extra:
                        raise _SchemaViolation(
                            f"{path}: unknown fields {sorted(extra)!r}"
                        )
                for key, item in value.items():
                    if key in properties:
                        self._validate(
                            item,
                            properties[key],
                            root,
                            f"{path}.{key}",
                        )
        if isinstance(value, list) and "items" in schema:
            for index, item in enumerate(value):
                self._validate(item, schema["items"], root, f"{path}[{index}]")

    @staticmethod
    def _type_matches(value, name):
        if name == "object":
            return isinstance(value, dict)
        if name == "array":
            return isinstance(value, list)
        if name == "string":
            return isinstance(value, str)
        if name == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if name == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if name == "boolean":
            return isinstance(value, bool)
        if name == "null":
            return value is None
        raise _SchemaViolation(f"unsupported schema type: {name!r}")


class _Wire:
    """Thin stdio client wrapper with live schema validation."""

    def __init__(self, session, transcript, schemas):
        self._session = session
        self._transcript = transcript
        self._validator = _SchemaValidator(schemas)

    def validate_definition(self, tool, name, value):
        self._validator.validate_definition(tool, name, value)

    def claim(self, subject, summary, ref):
        """Build one public PURPOSE claim and validate its live shape."""
        claim = {
            "candidate_key": "wire-1",
            "subject": subject,
            "kind": "PURPOSE",
            "value": {
                "$type": "PurposeValue",
                "summary": summary,
            },
            "assertion_nature": "DESCRIPTIVE",
            "evidence": [ref],
            "basis": {
                "derivation": "SEMANTIC_INTERPRETATION",
                "summary": "wire acceptance observes the file",
            },
        }
        self.validate_definition(
            "submit_interpretation", "CandidateSemanticClaim", claim
        )
        return claim

    async def call(self, tool, args, validate=True):
        # Every ordinary payload is checked recursively against the
        # schema advertised by this same server before transmission.
        # Only the deliberate malformed-ingress probe opts out.
        if validate:
            self._validator.validate_call(tool, args)
        result = await self._session.call_tool(tool, args)
        texts = [
            block.text
            for block in result.content
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
        self._transcript.append(
            {
                "tool": tool,
                "arguments": args,
                "error": bool(result.is_error),
                "response": payload,
            }
        )
        return payload, bool(result.is_error)


def _pending_subject(pending):
    return pending["request"]["subjects"][0]["subject_id"]


def _pending_evidence_ref(pending):
    return pending["request"]["evidence_units"][0]["evidence_ref"]


async def _submit_answered(
    wire,
    pending,
    repo_id,
    summary=None,
    *,
    disposition_basis="installed wire acceptance",
    claims=None,
    **updates,
):
    """Answer a pending task from its returned minimal template.

    Only the semantic fields the scenario needs are added; the template
    supplies the question decision and the client never initializes
    every optional collection.
    """
    result = submission_template_from_pending(pending)
    decision = result.setdefault("question_decision", {})
    decision["disposition"] = "ANSWERED"
    decision["disposition_basis"] = disposition_basis
    if "resolution_requirements" in updates:
        decision["resolution_requirements"] = updates.pop("resolution_requirements")
    if claims is not None:
        result["claims"] = list(claims)
    elif summary is not None:
        result["claims"] = [
            wire.claim(
                _pending_subject(pending),
                summary,
                _pending_evidence_ref(pending),
            )
        ]
    for key, value in updates.items():
        result[key] = value
    payload, is_error = await wire.call(
        "submit_interpretation",
        {
            "continuation": pending["continuation"],
            "result": result,
            "repository_id": repo_id,
        },
    )
    assert not is_error, payload
    return payload, result


async def lane(exe, work, data_dir, transcript):
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    env = {key: value for key, value in _os.environ.items() if key != "PYTHONPATH"}

    async def _session(register: bool = True):
        args = ["--data-dir", str(data_dir)]
        if register:
            args += ["--repo", str(work)]
        params = StdioServerParameters(
            command=exe,
            args=args,
            env=env,
        )
        stack = _contextlib.AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        initialized = await session.initialize()
        listed = await session.list_tools()
        return stack, session, initialized, listed

    def _wire(session, listed):
        schemas = {tool.name: tool.input_schema for tool in listed.tools}
        return _Wire(session, transcript, schemas)

    # -- phase 1: provisioned server ------------------------------------
    stack, session, initialized, listed = await _session()
    try:
        server_version = initialized.server_info.version
        transcript.append({"server_version": server_version})
        names = [tool.name for tool in listed.tools]
        assert len(names) == 11, names
        assert names == list(_TOOL_NAMES), names
        assert "reissue_interpretation" not in names, names
        _phase(transcript, "EC-01", tools=names)

        import hashlib as _hashlib

        transcript.append(
            {
                "schema_digest": _hashlib.sha256(
                    _json.dumps(
                        {tool.name: tool.input_schema for tool in listed.tools},
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )

        repo_id = _discover_repository_id(listed.tools)
        assert repo_id, "registered repository ID was not discoverable"
        _phase(transcript, "EC-02", repository_id=repo_id)

        wire = _wire(session, listed)
        by_name = {tool.name: tool for tool in listed.tools}
        # MCP process startup registers repository identity only. This
        # fresh fixture therefore performs the explicit setup the normal
        # installed flow completes during install verification before
        # ordinary semantic work begins.
        setup, is_error = await wire.call(
            "initialize_repository",
            {"repository_locator": str(work)},
        )
        assert not is_error, setup
        assert setup["readiness"] == "READY", setup
        assert setup["repository_id"] == repo_id, setup
        submit_schema = by_name["submit_interpretation"].input_schema
        assert "$defs" in submit_schema
        assert "SemanticInterpretationResult" in submit_schema["$defs"]
        assert set(submit_schema["required"]) >= {
            "continuation",
            "result",
            "repository_id",
        }

        # EC-04: direct semantic entry, no status preflight, bounded
        # task returned.
        assert not any(
            entry.get("tool") == "status" for entry in transcript
        ), "status preflight preceded the first semantic call"
        alpha_pending, is_error = await wire.call(
            "explain",
            {"repository_id": repo_id, "target": _selector("src/alpha.py")},
        )
        assert not is_error, alpha_pending
        assert "continuation" in alpha_pending, alpha_pending
        assert submission_template_from_pending(alpha_pending) == {
            "question_decision": {"disposition": "PENDING"},
        }
        _phase(
            transcript,
            "EC-04",
            question_class=alpha_pending["request"]["question"]["question_class"],
        )

        alpha_token = alpha_pending["continuation"]
        answer, alpha_result = await _submit_answered(
            wire,
            alpha_pending,
            repo_id,
            "alpha computes the value",
        )
        alpha_claim = answer["content"]["claims"][0]["claim_id"]["value"]

        # EC-08: a consumed continuation is unavailable, and re-entering
        # the original operation recovers the persisted result.
        consumed, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": alpha_token,
                "result": alpha_result,
                "repository_id": repo_id,
            },
        )
        assert is_error, consumed
        assert consumed.get("error") == "unavailable", consumed
        reentry, is_error = await wire.call(
            "explain",
            {"repository_id": repo_id, "target": _selector("src/alpha.py")},
        )
        assert not is_error, reentry
        assert "continuation" not in reentry, reentry
        assert [
            claim["claim_id"]["value"] for claim in reentry["content"]["claims"]
        ] == [alpha_claim], reentry
        _phase(transcript, "EC-08", claim_id=alpha_claim)

        # EC-03: an established question now returns its persisted answer
        # directly, still without a status preflight.
        _phase(transcript, "EC-03", claim_id=alpha_claim)

        payload, is_error = await wire.call(
            "status", {"repository_id": repo_id, "target": None}
        )
        assert not is_error, payload
        assert payload["content"].get("readiness") == "READY", payload

        # EC-09: trace with only required arguments (defaults omitted).
        payload, is_error = await wire.call(
            "trace",
            {
                "repository_id": repo_id,
                "target": _selector("src/alpha.py"),
                "direction": "BOTH",
            },
        )
        assert not is_error, payload
        if "continuation" in payload:
            answer, _ = await _submit_answered(
                wire, payload, repo_id, "alpha computes the value"
            )
        else:
            answer = payload
        assert "content" in answer, answer
        _phase(transcript, "EC-09")

        # EC-11: authority is a direct entry point.
        payload, is_error = await wire.call(
            "authority",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/alpha.py"),
            },
        )
        assert not is_error, payload
        if "continuation" in payload:
            answer, _ = await _submit_answered(
                wire, payload, repo_id, "alpha computes the value"
            )
        else:
            answer = payload
        assert "UNRESOLVED" in _json.dumps(answer), answer
        _phase(transcript, "EC-11")

        # EC-10: impact without an optional change_description.
        payload, is_error = await wire.call(
            "impact",
            {
                "repository_id": repo_id,
                "target": _selector("src/alpha.py"),
                "change_kind": "BEHAVIOR",
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        pending_slice = payload["request"]["question"]["question_slice"]
        assert "|kind=BEHAVIOR|desc=" in pending_slice, pending_slice
        answer, _ = await _submit_answered(
            wire, payload, repo_id, "alpha computes the value"
        )
        assert "change_conditions" in answer["content"], answer
        _phase(transcript, "EC-10")

        # Establish the second subject for the isolation check.
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": repo_id, "target": _selector("src/beta.py")},
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _ = await _submit_answered(
            wire, payload, repo_id, "beta holds the other value"
        )
        beta_claim = answer["content"]["claims"][0]["claim_id"]["value"]
        beta_subject = _pending_subject(payload)

        # EC-16: changing supporting evidence makes alpha noncurrent.
        (work / "src" / "alpha.py").write_text(
            "VALUE = 1\n# touched\n", encoding="utf-8"
        )
        payload, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/alpha.py"),
            },
        )
        assert not is_error, payload
        assert "STALE" in _json.dumps(payload), payload
        _phase(transcript, "EC-16")

        # EC-17: scoped refresh answers only the affected scope.
        payload, is_error = await wire.call(
            "refresh",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/alpha.py"),
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _ = await _submit_answered(
            wire, payload, repo_id, "alpha computes the value"
        )
        assert "content" in answer, answer
        _phase(transcript, "EC-17")

        # EC-18: unrelated established knowledge is still reusable.
        payload, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
            },
        )
        assert not is_error, payload
        beta_views = payload["content"].get("question_coverage", [])
        assert any(
            view.get("effective_disposition") == "ANSWERED" for view in beta_views
        ), payload
        assert beta_claim in _json.dumps(payload), payload
        _phase(transcript, "EC-18")

        # Second OPEN question on the same subject: correcting one
        # question preserves the other's explicit gap reason (S8.2).
        payload, is_error = await wire.call(
            "trace",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "direction": "BOTH",
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        trace_subject = _pending_subject(payload)
        trace_ref = _pending_evidence_ref(payload)
        assert trace_subject == beta_subject, (trace_subject, beta_subject)
        open_coverage = {
            "question": {
                "scope_root": trace_subject,
                "subject": trace_subject,
                "question_class": "CQ_01",
                "question_slice": "beta second question",
                "materiality_basis": "wire acceptance second question",
            },
            "decision": {
                "disposition": "OPEN",
                "evidence_scope": {"paths": [], "evidence_refs": []},
                "resolution_requirements": [
                    {
                        "kind": "MISSING_SEMANTIC_COVERAGE",
                        "subject_or_claim": {
                            "$type": "SubjectId",
                            **trace_subject,
                        },
                        "description": "second gap stays open",
                        "supporting_context": [],
                    }
                ],
                "disposition_basis": "wire acceptance open question",
            },
        }
        answer, _ = await _submit_answered(
            wire,
            payload,
            repo_id,
            claims=[wire.claim(trace_subject, "beta trace look", trace_ref)],
            proposed_questions=[open_coverage],
        )
        payload, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
            },
        )
        assert not is_error, payload
        assert "second gap stays open" in _json.dumps(payload), payload

        # EC-19: correction of a current exact subject.
        payload, is_error = await wire.call(
            "refresh",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
                "stale_only": False,
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _ = await _submit_answered(
            wire, payload, repo_id, "beta holds the other value"
        )
        assert "content" in answer, answer
        _phase(transcript, "EC-19")

        # Installed no-fallback case (S8.5): correcting beta's refreshed
        # question must not replace the second question's explicit gap
        # explanation with generic pending scaffolding.
        payload, is_error = await wire.call(
            "refresh",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
                "stale_only": False,
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        answer, _ = await _submit_answered(
            wire, payload, repo_id, "beta holds the other value"
        )
        assert "content" in answer, answer
        payload, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
            },
        )
        assert not is_error, payload
        second_views = [
            view
            for view in payload["content"].get("question_coverage", [])
            if view.get("question", {}).get("question_slice") == "beta second question"
        ]
        assert len(second_views) == 1, payload
        assert second_views[0].get("effective_disposition") == "OPEN", payload
        assert [
            req.get("description")
            for req in second_views[0].get("resolution_requirements", [])
        ] == ["second gap stays open"], payload

        # Installed shared-withdrawal case (S8.5/S8.3): a dependent
        # coverage explicitly referencing beta's claim reopens with the
        # actual withdrawal reason when that claim is withdrawn.
        beta_ref = {
            "$type": "ClaimRef",
            "kind": "CLAIM",
            "id": {"value": beta_claim},
        }
        payload, is_error = await wire.call(
            "impact",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "change_kind": "BEHAVIOR",
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        refresh_question = payload["request"]["question"]
        refresh_subject = _pending_subject(payload)
        shared_requirement = {
            "kind": "MISSING_AUTHORITY",
            "subject_or_claim": {
                "$type": "SubjectId",
                **refresh_subject,
            },
            "description": "shared dependent original gap",
            "supporting_context": [],
        }
        shared_slice = refresh_question["question_slice"]
        answer, _ = await _submit_answered(
            wire,
            payload,
            repo_id,
            "beta holds the other value",
            resolution_requirements=[shared_requirement],
            disposition_basis="wire acceptance shared output",
        )
        shared_claims = [
            claim
            for claim in answer["content"]["claims"]
            if claim["value"].get("summary") == "beta holds the other value"
        ]
        # Re-materializing the identical canonical claim content makes the
        # second answered question a co-owner of beta's exact claim id.
        assert shared_claims, answer
        assert shared_claims[0]["claim_id"]["value"] == beta_claim, shared_claims

        payload, is_error = await wire.call(
            "refresh",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
                "stale_only": False,
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        withdraw_subject = _pending_subject(payload)
        withdraw_ref = _pending_evidence_ref(payload)
        answer, _ = await _submit_answered(
            wire,
            payload,
            repo_id,
            claims=[wire.claim(withdraw_subject, "beta withdraw look", withdraw_ref)],
            candidate_withdrawals=[
                {
                    "target": beta_ref,
                    "basis": {
                        "derivation": "SEMANTIC_INTERPRETATION",
                        "summary": (
                            "retracted: wire test withdraws " "shared beta basis"
                        ),
                    },
                    "evidence": [withdraw_ref],
                }
            ],
        )
        payload, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
            },
        )
        assert not is_error, payload
        shared_views = [
            view
            for view in payload["content"].get("question_coverage", [])
            if view.get("question", {}).get("question_slice") == shared_slice
        ]
        assert len(shared_views) == 1, payload
        assert shared_views[0].get("effective_disposition") == "PENDING", payload
        shared_reasons = [
            req.get("description")
            for req in shared_views[0].get("resolution_requirements", [])
        ]
        assert any(
            "retracted: wire test withdraws shared beta basis" in text
            for text in shared_reasons
        ), payload
        assert "shared dependent original gap" in shared_reasons, payload

        # EC-06: malformed ingress retains the live continuation.
        payload, is_error = await wire.call(
            "refresh",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
                "stale_only": False,
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        malformed_pending = payload
        malformed_token = payload["continuation"]
        payload, is_error = await wire.call(
            "submit_interpretation",
            {"continuation": malformed_token, "repository_id": repo_id},
            validate=False,
        )
        assert is_error, payload
        assert payload.get("error") == "ingress", payload
        assert "result" in payload.get("message", ""), payload
        answer, _ = await _submit_answered(
            wire, malformed_pending, repo_id, "beta holds the other value"
        )
        assert "content" in answer, answer
        _phase(transcript, "EC-06")
    finally:
        await stack.aclose()

    # -- phase 1b: untouched PENDING and semantic rejection recovery -----
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        # EC-05: submit exactly the returned PENDING template.
        selection = {
            "question_slice": "wire pending semantics",
            "materiality_basis": "wire acceptance pending semantics",
            "question_anchors": [],
        }
        pending, is_error = await wire.call(
            "explain",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "question_selection": selection,
            },
        )
        assert not is_error, pending
        assert "continuation" in pending, pending
        pending_template = submission_template_from_pending(pending)
        assert pending_template == {
            "question_decision": {"disposition": "PENDING"},
        }, pending_template
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": pending_template,
                "repository_id": repo_id,
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
                "repository_id": repo_id,
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
        _phase(transcript, "EC-05")

        # EC-07: schema-valid but semantically invalid material is
        # rejected; the same continuation accepts the correction.
        selection = {
            "question_slice": "wire validation recovery",
            "materiality_basis": "wire acceptance validation recovery",
            "question_anchors": [],
        }
        pending, is_error = await wire.call(
            "explain",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "question_selection": selection,
            },
        )
        assert not is_error, pending
        assert "continuation" in pending, pending
        subject = _pending_subject(pending)
        ref = _pending_evidence_ref(pending)
        bad = wire.claim(subject, "uncited", ref)
        bad["evidence"] = []
        rejected, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": {"claims": [bad]},
                "repository_id": repo_id,
            },
        )
        assert is_error, rejected
        assert rejected.get("error") == "validation", rejected
        corrected, _ = await _submit_answered(
            wire, pending, repo_id, "beta holds the other value"
        )
        assert "content" in corrected, corrected
        _phase(transcript, "EC-07")
    finally:
        await stack.aclose()

    # -- phase 2: new server process, same store -------------------------
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        payload, is_error = await wire.call(
            "explain",
            {"repository_id": repo_id, "target": _selector("src/alpha.py")},
        )
        assert not is_error, payload
        assert "continuation" not in payload, payload
        # Fresh-session reuse: the original claim still resolves. The
        # refresh correction may have added a superseding claim citing
        # current evidence, so this asserts membership, not equality.
        assert alpha_claim in [
            claim["claim_id"]["value"] for claim in payload["content"]["claims"]
        ], payload
        _phase(transcript, "EC-20", claim_id=alpha_claim)
    finally:
        await stack.aclose()

    # EC-22: the provider built its index into Span's data directory,
    # never into the target repository.
    for artifact in ("graft", ".graph"):
        assert not (
            work / artifact
        ).exists(), f"target structural artifact was written: {artifact}"
    assert not any(
        path.name == "wiring.json" for path in work.rglob("wiring.json")
    ), "provider index was written into the target repository"
    assert (
        data_dir / "structural" / repo_id / ".graph" / "wiring.json"
    ).is_file(), "provider index was not built into the data directory"
    _phase(
        transcript,
        "EC-22",
        index=str(data_dir / "structural" / repo_id / ".graph" / "wiring.json"),
    )

    # -- phase 3: unregistered setup call, one locator -------------------
    stack, session, _initialized, listed = await _session(register=False)
    try:
        wire = _wire(session, listed)
        # EC-21: one repository locator, no structural-provider config.
        payload, is_error = await wire.call(
            "initialize_repository",
            {"repository_locator": str(work)},
        )
        assert not is_error, payload
        assert payload["readiness"] == "READY", payload
        assert payload["repository_id"] == repo_id, payload
        _phase(transcript, "EC-21", repository_id=repo_id)
    finally:
        await stack.aclose()

    # -- phase 4: multi-member target mapping and service-owned CQ-01 ----
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        payload, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
                "target": {"paths": ["src"], "evidence_refs": []},
                "objective": "wire target mapping",
            },
        )
        assert not is_error, payload
        assert "continuation" in payload, payload
        items = payload["request"]["target_inventory_items"]
        bound_ids = [item["evidence_ref"]["evidence_id"]["value"] for item in items]
        assert len(bound_ids) >= 2, payload
        template = submission_template_from_pending(payload)
        template_ids = [
            account["evidence_id"]["value"]
            for account in template["proposed_target_inventory_accounting"]
        ]
        assert template_ids == bound_ids, (template_ids, bound_ids)
        _phase(
            transcript,
            "EC-23",
            bound_ids=bound_ids,
            template_ids=template_ids,
        )

        # EC-25: evidence-supported area assignment. The client does not
        # manufacture the default CQ-01.
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
            "repository_id": repo_id,
            "subject_kind": "COMPONENT",
            "canonical_locator": "src",
        }
        result = template
        for account in result["proposed_target_inventory_accounting"]:
            account.pop("resolution_requirements", None)
            account["assigned_area_subjects"] = [area_id]
        result["candidate_subjects"] = [area]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": payload["continuation"],
                "result": result,
                "repository_id": repo_id,
            },
        )
        assert not is_error, answer
        payload, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
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
        _phase(transcript, "EC-25", question_class="CQ_01")
    finally:
        await stack.aclose()

    # -- phase 4a: existing target question reuse ------------------------
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        scope = {"paths": ["src/alpha.py"], "evidence_refs": []}
        pending, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
                "target": scope,
                "objective": "wire target question reuse",
            },
        )
        assert not is_error, pending
        # EC-27: the persisted CQ-01 exists, but it is not attached to a
        # new target merely because it exists. Materiality is explicit.
        assert pending["request"]["question"] is None, pending
        items = pending["request"]["target_inventory_items"]
        assert len(items) == 1, pending
        result = submission_template_from_pending(pending)
        accounts = result["proposed_target_inventory_accounting"]
        assert len(accounts) == 1, result
        accounts[0].pop("resolution_requirements", None)
        accounts[0]["assigned_area_subjects"] = [area_id]
        # EC-26: reuse the identical already-persisted target question.
        result["proposed_target_questions"] = [seed_scope]
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": result,
                "repository_id": repo_id,
            },
        )
        assert not is_error, answer
        again, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
                "target": scope,
                "objective": "wire target question reuse",
            },
        )
        assert not is_error, again
        assert again["request"]["question"]["question_slice"] == (
            seed_scope["question_slice"]
        ), again
        _phase(transcript, "EC-26", question_slice=seed_scope["question_slice"])
        _phase(transcript, "EC-27")
    finally:
        await stack.aclose()

    # -- phase 4b: unresolved mapping is accepted but non-progressing ----
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        scope = {"paths": ["src/beta.py"], "evidence_refs": []}
        pending, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
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
        template = submission_template_from_pending(pending)
        ids = [item["evidence_ref"]["evidence_id"]["value"] for item in items]
        template_ids = [
            account["evidence_id"]["value"]
            for account in template["proposed_target_inventory_accounting"]
        ]
        assert template_ids == ids, (template_ids, ids)
        # EC-24: submit the returned unresolved template unchanged.
        answer, is_error = await wire.call(
            "submit_interpretation",
            {
                "continuation": pending["continuation"],
                "result": template,
                "repository_id": repo_id,
            },
        )
        assert not is_error, answer
        again, is_error = await wire.call(
            "initialize_target",
            {
                "repository_id": repo_id,
                "target": scope,
                "objective": "wire unresolved mapping",
            },
        )
        assert not is_error, again
        # Unresolved members keep the target incomplete: the frontier
        # returns outstanding work or an explicitly incomplete target,
        # never a falsely completed target.
        if "request" in again:
            assert again["request"]["question"] is None or (
                again["request"]["question"]["question_class"] == "CQ_01"
            ), again
        else:
            assert "content" in again, again
            assert again["content"].get("target_disposition") != "CURRENT", again
            assert again["content"].get("unresolved"), again
        _phase(transcript, "EC-24", non_progressing=True)
    finally:
        await stack.aclose()

    # -- phase 5: opaque pagination and cross-request rejection ----------
    stack, session, _initialized, listed = await _session()
    try:
        wire = _wire(session, listed)
        small = {
            "max_results": 1,
            "max_depth": 5,
            "max_subjects": 1,
            "max_evidence_units": 24,
            "max_evidence_bytes": 96000,
            "max_candidate_claims": 64,
            "max_candidate_relationships": 64,
        }
        first, is_error = await wire.call(
            "status",
            {"repository_id": repo_id, "target": None, "bounds": small},
        )
        assert not is_error, first
        token = first["bound_info"]["continuation_token"]
        assert token, first
        second, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": None,
                "bounds": small,
                "page_token": token,
            },
        )
        assert not is_error, second
        assert (
            second["content"] != first["content"]
        ), "the redeemed page repeated the first page"
        _phase(transcript, "EC-12", page_token_opaque=True)

        opaque_errors = []

        def _assert_opaque(payload):
            message = payload.get("message", "")
            assert "page token is invalid" in message, payload
            for forbidden in ("pgq:", "pgv:", "pgn:"):
                assert forbidden not in message, payload
            lowered = message.lower()
            for forbidden in ("digest", "offset", token):
                assert forbidden not in lowered, payload
            opaque_errors.append(message)

        # EC-13: bounds mutation rejects the old token.
        changed = dict(small)
        changed["max_subjects"] = 2
        mismatched, is_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": None,
                "bounds": changed,
                "page_token": token,
            },
        )
        assert is_error, mismatched
        _assert_opaque(mismatched)

        # EC-13: target mutation rejects the old token.
        target_mismatch, target_error = await wire.call(
            "status",
            {
                "repository_id": repo_id,
                "target": _tagged_subject_selector("src/beta.py"),
                "bounds": small,
                "page_token": token,
            },
        )
        assert target_error, target_mismatch
        _assert_opaque(target_mismatch)

        # EC-13: question-selection mutation. Bind a service token to a
        # persisted narrowed question, then redeem it against a different
        # persisted question: the digest must reject the old token.
        question_bounds = dict(small)
        question_bounds["max_results"] = 1
        selected = {
            "question_slice": "wire validation recovery",
            "materiality_basis": "wire acceptance validation recovery",
            "question_anchors": [],
        }
        q_first, q_error = await wire.call(
            "explain",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "bounds": question_bounds,
                "question_selection": selected,
            },
        )
        assert not q_error, q_first
        assert "content" in q_first, q_first
        q_token = q_first.get("bound_info", {}).get("continuation_token")
        assert q_token, q_first
        mutated = {
            "question_slice": "beta second question",
            "materiality_basis": "wire acceptance second question",
            "question_anchors": [],
        }
        q_mismatch, q_selection_error = await wire.call(
            "explain",
            {
                "repository_id": repo_id,
                "target": _selector("src/beta.py"),
                "bounds": question_bounds,
                "page_token": q_token,
                "question_selection": mutated,
            },
        )
        assert q_selection_error, q_mismatch
        _assert_opaque(q_mismatch)
        question_mutation = "rejected"
        _phase(
            transcript,
            "EC-13",
            bounds_mutation="rejected",
            target_mutation="rejected",
            question_selection_mutation=question_mutation,
        )
        _phase(transcript, "EC-14", opaque_errors=len(opaque_errors))

        # EC-15: structural pagination token, passed unchanged.
        located, locate_error = await wire.call(
            "locate",
            {
                "repository_id": repo_id,
                "mode": "SYMBOL",
                "query": "src",
                "match": "CONTAINS",
                "bounds": small,
            },
        )
        assert not locate_error, located
        structural_token = located["bound_info"]["continuation_token"]
        assert structural_token, located
        page_two, page_error = await wire.call(
            "locate",
            {
                "repository_id": repo_id,
                "mode": "SYMBOL",
                "query": "src",
                "match": "CONTAINS",
                "bounds": small,
                "page_token": structural_token,
            },
        )
        assert not page_error, page_two
        _phase(transcript, "EC-15", page_token_opaque=True)
    finally:
        await stack.aclose()
    return alpha_claim, beta_claim
