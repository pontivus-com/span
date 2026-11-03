"""Raw schema-10 -> schema-11 semantic staging for the offline transition.

The mapping is external to the runtime: it reads the archived schema-10 bytes,
assigns one file surface per recorded single-file scope (O-4), preserves every
history row, and records source and target identities, counts, hashes, and the
provenance of each mapping in ``mapping.json``. Unresolved rows stay in the
archive with a named reason; they are never silently downgraded.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib as _hashlib
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3
import typing as _typing

from span.core import model as m
from span.shell.store_transition import (
    TARGET_SCHEMA,
    TransitionConfig,
    TransitionError,
    TransitionPaths,
    _connect_read_only,
    _table_names,
)

__all__ = ["stage_schema10", "verify_schema10_staging"]


_SCHEMA10_TABLES = (
    "source_observations",
    "discovery_observations",
    "investigation_contexts",
    "context_evidence",
    "context_discovery_evidence",
    "understandings",
    "understanding_versions",
    "conclusions",
    "support_dependencies",
    "understanding_membership",
    "challenges",
    "verification_runs",
    "verification_observations",
    "record_receipts",
)


def _sha256_text(value: str) -> str:
    return _hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: object, field: str) -> str:
    """Validate one archived schema-10 text field; never coerce."""
    if not isinstance(value, str):
        raise TypeError(f"schema 10 archive field {field!r} is not text")
    return value


def _items(payload: dict[str, object], key: str) -> list[object]:
    """Validate one archived schema-10 list field; never coerce."""
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"schema 10 archive field {key!r} is not a list")
    return value


def _mapping(
    records: list[dict[str, object]],
    *,
    source_table: str,
    source_id: str,
    target_table: str,
    target_id: str,
    classification: str,
    source_payload: str = "",
    target_payload: str = "",
    reason: str = "",
) -> None:
    records.append(
        {
            "source_table": source_table,
            "source_id": source_id,
            "target_table": target_table,
            "target_id": target_id,
            "classification": classification,
            "reason": reason,
            "source_sha256": _sha256_text(source_payload),
            "target_sha256": _sha256_text(target_payload),
        }
    )


def _file_surface(
    repository_id: str, scope: m.EvidenceScope, root: _pathlib.Path
) -> tuple[m.SurfaceKey | None, str]:
    if len(scope.paths) != 1:
        return None, "scope does not identify one file surface"
    locator = scope.paths[0]
    candidate = root / locator
    if not candidate.is_file():
        return None, "scope does not identify one file surface"
    return (
        m.SurfaceKey(
            repository_id=repository_id,
            kind=m.SurfaceKind.FILE,
            locator=locator,
        ),
        "",
    )


def _insert_schema10_rows(
    connection: _sqlite3.Connection,
    *,
    config: TransitionConfig,
    root: str,
    records: list[dict[str, object]],
    limitations: list[str],
) -> None:
    archive = _connect_read_only(
        TransitionPaths(config.data_dir, config.repository_id).archive
    )
    try:
        tables = set(_table_names(archive))
        missing = [name for name in _SCHEMA10_TABLES if name not in tables]
        if missing:
            raise TransitionError(
                "schema-10 source is missing required tables: "
                + ", ".join(sorted(missing))
                + "; nothing was imported"
            )
        contexts = _import_contexts(connection, archive, records, config.repository_id)
        _import_source_observations(connection, archive, records, config.repository_id)
        _import_discovery_observations(
            connection, archive, records, config.repository_id
        )
        _import_context_links(connection, archive, records, config)
        _import_understandings(
            connection,
            archive,
            records,
            limitations,
            config=config,
            root=root,
        )
        _import_challenges(
            connection, archive, records, config.repository_id, limitations
        )
        _import_verifications(connection, archive, records, config)
        _import_receipts(
            connection,
            archive,
            records,
            limitations,
            config=config,
            contexts=contexts,
        )
    finally:
        archive.close()


def _import_contexts(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    repository_id: str,
) -> dict[str, m.InvestigationContext]:
    contexts: dict[str, m.InvestigationContext] = {}
    for row in archive.execute(
        "SELECT context_id, canonical_json FROM investigation_contexts"
        " WHERE repository_id=?",
        (repository_id,),
    ).fetchall():
        context = m.from_canonical(m.InvestigationContext, _json.loads(row[1]))
        contexts[row[0]] = context
        connection.execute(
            "INSERT OR REPLACE INTO investigation_contexts"
            "(context_id, repository_id, request_id, request_digest,"
            " canonical_json, expires_at) VALUES(?,?,?,?,?,?)",
            (
                context.context_id.value,
                context.repository_id,
                context.request_id.value,
                context.request_digest.value,
                row[1],
                (
                    context.expires_at.astimezone(_datetime.timezone.utc).isoformat()
                    if context.expires_at
                    else None
                ),
            ),
        )
        _mapping(
            records,
            source_table="investigation_contexts",
            source_id=context.context_id.value,
            target_table="investigation_contexts",
            target_id=context.context_id.value,
            classification="preserved",
            source_payload=row[1],
            target_payload=row[1],
        )
    return contexts


def _import_source_observations(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    repository_id: str,
) -> None:
    for row in archive.execute(
        "SELECT observation_id, repository_id, evidence_id, locator,"
        " content_digest, captured_at, total_lines, delivered_ranges_json,"
        " whole_file, excerpt, canonical_json FROM source_observations"
        " WHERE repository_id=?",
        (repository_id,),
    ).fetchall():
        observation = m.SourceObservation(
            observation_id=m.SourceObservationId(row[0]),
            repository_id=row[1],
            evidence=m.from_canonical(m.EvidenceRef, _json.loads(row[10])),
            content_digest=m.ContentDigest(row[4]),
            captured_at=_datetime.datetime.fromisoformat(row[5]),
            total_lines=int(row[6]),
            delivered_ranges=tuple(
                m.from_canonical(m.SourceRange, item) for item in _json.loads(row[7])
            ),
            whole_file=bool(row[8]),
            excerpt=row[9],
        )
        connection.execute(
            "INSERT OR REPLACE INTO source_observations"
            "(observation_id, repository_id, evidence_id, locator,"
            " content_digest, captured_at, total_lines, delivered_ranges_json,"
            " whole_file, excerpt, canonical_json)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                observation.observation_id.value,
                observation.repository_id,
                observation.evidence.evidence_id.value,
                observation.evidence.locator,
                observation.content_digest.value,
                observation.captured_at.astimezone(_datetime.timezone.utc).isoformat(),
                observation.total_lines,
                _json.dumps(
                    [m.to_canonical(item) for item in observation.delivered_ranges],
                    sort_keys=True,
                ),
                int(observation.whole_file),
                observation.excerpt,
                row[10],
            ),
        )
        _mapping(
            records,
            source_table="source_observations",
            source_id=observation.observation_id.value,
            target_table="source_observations",
            target_id=observation.observation_id.value,
            classification="preserved",
            source_payload=row[10],
            target_payload=row[10],
        )


def _import_discovery_observations(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    repository_id: str,
) -> None:
    for row in archive.execute(
        "SELECT observation_id, canonical_json FROM discovery_observations"
        " WHERE repository_id=?",
        (repository_id,),
    ).fetchall():
        observation = m.from_canonical(m.DiscoveryObservation, _json.loads(row[1]))
        connection.execute(
            "INSERT OR REPLACE INTO discovery_observations"
            "(observation_id, repository_id, canonical_json) VALUES(?,?,?)",
            (observation.observation_id.value, observation.repository_id, row[1]),
        )
        _mapping(
            records,
            source_table="discovery_observations",
            source_id=observation.observation_id.value,
            target_table="discovery_observations",
            target_id=observation.observation_id.value,
            classification="preserved",
            source_payload=row[1],
            target_payload=row[1],
        )


def _import_context_links(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    config: TransitionConfig,
) -> None:
    for source_table, target_table in (
        ("context_evidence", "context_evidence"),
        ("context_discovery_evidence", "context_discovery_evidence"),
    ):
        for row in archive.execute(
            "SELECT links.context_id, links.observation_id"
            f" FROM {source_table} AS links"
            " JOIN investigation_contexts AS contexts"
            " ON contexts.context_id = links.context_id"
            " WHERE contexts.repository_id=?",
            (config.repository_id,),
        ).fetchall():
            connection.execute(
                f"INSERT OR REPLACE INTO {target_table}"
                "(repository_id, context_id, observation_id) VALUES(?,?,?)",
                (config.repository_id, row[0], row[1]),
            )
            _mapping(
                records,
                source_table=source_table,
                source_id=f"{row[0]}/{row[1]}",
                target_table=target_table,
                target_id=f"{row[0]}/{row[1]}",
                classification="preserved",
            )


def _import_understandings(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    limitations: list[str],
    *,
    config: TransitionConfig,
    root: str,
) -> None:
    surface_keys: set[tuple[str, str]] = set()
    occupied: set[tuple[str, str, str]] = set()
    rows = archive.execute(
        "SELECT understanding_id, question, scope_json, current_version,"
        " canonical_json FROM understandings WHERE repository_id=?"
        " ORDER BY understanding_id",
        (config.repository_id,),
    ).fetchall()
    for source in rows:
        _import_one_understanding(
            connection,
            archive,
            records,
            limitations,
            config=config,
            root=root,
            source=source,
            surface_keys=surface_keys,
            occupied=occupied,
        )


def _import_one_understanding(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    limitations: list[str],
    *,
    config: TransitionConfig,
    root: str,
    source: tuple[object, ...],
    surface_keys: set[tuple[str, str]],
    occupied: set[tuple[str, str, str]],
) -> None:
    from span.core.identity import payload_digest

    source_id = str(source[0])
    payload = _json.loads(_text(source[4], "understandings.payload"))
    scope = m.from_canonical(
        m.EvidenceScope, _json.loads(_text(source[2], "understandings.scope"))
    )
    surface, reason = _file_surface(config.repository_id, scope, _pathlib.Path(root))
    if surface is None:
        _unresolved(
            records,
            limitations,
            "understandings",
            source_id,
            _text(source[4], "understandings.payload"),
            reason,
        )
        return
    key = (surface.kind.value, surface.locator, str(source[1]))
    if key in occupied:
        reason = "mapped surface and question are already occupied"
        _unresolved(
            records,
            limitations,
            "understandings",
            source_id,
            _text(source[4], "understandings.payload"),
            reason,
        )
        return
    occupied.add(key)
    _ensure_surface(connection, records, source, surface, surface_keys, payload_digest)
    understanding_payload = dict(payload)
    understanding_payload["surface"] = m.to_canonical(surface)
    understanding = m.from_canonical(m.Understanding, understanding_payload)
    understanding_canonical = _json.dumps(m.to_canonical(understanding), sort_keys=True)
    connection.execute(
        "INSERT OR REPLACE INTO understandings"
        "(understanding_id, repository_id, surface_kind, surface_locator,"
        " question, scope_json, current_version, canonical_json)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (
            understanding.understanding_id.value,
            understanding.repository_id,
            understanding.surface.kind.value,
            understanding.surface.locator,
            understanding.question,
            _json.dumps(m.to_canonical(understanding.scope), sort_keys=True),
            understanding.current_version.value,
            understanding_canonical,
        ),
    )
    _mapping(
        records,
        source_table="understandings",
        source_id=source_id,
        target_table="understandings",
        target_id=understanding.understanding_id.value,
        classification="transformed",
        source_payload=_text(source[4], "understandings.payload"),
        target_payload=understanding_canonical,
        reason="surface assigned from the recorded scope (O-4)",
    )
    _import_versions(connection, archive, records, source_id)
    _import_conclusions(connection, archive, records, source_id)


def _ensure_surface(
    connection: _sqlite3.Connection,
    records: list[dict[str, object]],
    source: tuple[object, ...],
    surface: m.SurfaceKey,
    surface_keys: set[tuple[str, str]],
    payload_digest: _typing.Callable[[object], m.ContentDigest],
) -> None:
    key = (surface.kind.value, surface.locator)
    if key in surface_keys:
        return
    declared = m.Surface(key=surface)
    canonical = _json.dumps(m.to_canonical(declared), sort_keys=True)
    connection.execute(
        "INSERT OR IGNORE INTO surfaces(repository_id, kind, locator,"
        " parent_kind, parent_locator, boundary_version, canonical_json)"
        " VALUES(?,?,?,?,?,?,?)",
        (
            surface.repository_id,
            surface.kind.value,
            surface.locator,
            None,
            None,
            declared.boundary_version,
            canonical,
        ),
    )
    connection.execute(
        "INSERT OR IGNORE INTO surface_boundary_versions"
        "(repository_id, kind, locator, boundary_version,"
        " boundary_digest, canonical_json) VALUES(?,?,?,?,?,?)",
        (
            surface.repository_id,
            surface.kind.value,
            surface.locator,
            declared.boundary_version,
            payload_digest(m.to_canonical(declared.boundary)).value,
            canonical,
        ),
    )
    surface_keys.add(key)
    _mapping(
        records,
        source_table="understandings",
        source_id=str(source[0]),
        target_table="surfaces",
        target_id=surface.locator,
        classification="transformed",
        source_payload=_text(source[4], "understandings.payload"),
        target_payload=canonical,
        reason="path surface derived from the recorded scope",
    )


def _import_versions(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    source_id: str,
) -> None:
    for version_row in archive.execute(
        "SELECT version, canonical_json FROM understanding_versions"
        " WHERE understanding_id=? ORDER BY version",
        (source_id,),
    ).fetchall():
        version_payload = _json.loads(version_row[1])
        version_payload["surface_boundary_version"] = 1
        version_payload["gaps"] = [
            {**gap, "$type": "RecordedQuestionGap"}
            for gap in version_payload.get("gaps", [])
        ]
        version = m.from_canonical(m.UnderstandingVersion, version_payload)
        version_canonical = _json.dumps(m.to_canonical(version), sort_keys=True)
        connection.execute(
            "INSERT OR REPLACE INTO understanding_versions"
            "(understanding_id, version, canonical_json) VALUES(?,?,?)",
            (
                version.understanding_id.value,
                version.version.value,
                version_canonical,
            ),
        )
        _mapping(
            records,
            source_table="understanding_versions",
            source_id=f"{source_id}@{version_row[0]}",
            target_table="understanding_versions",
            target_id=f"{source_id}@{version.version.value}",
            classification="transformed",
            source_payload=version_row[1],
            target_payload=version_canonical,
            reason="surface boundary version recorded; persisted Gap tag renamed",
        )
        for ref in version.conclusions:
            connection.execute(
                "INSERT OR REPLACE INTO understanding_membership"
                "(understanding_id, version, conclusion_id, revision)"
                " VALUES(?,?,?,?)",
                (
                    version.understanding_id.value,
                    version.version.value,
                    ref.conclusion_id.value,
                    ref.revision.value,
                ),
            )


def _import_conclusions(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    source_id: str,
) -> None:
    from span.shell.sqlite_store.lifecycle import _support_rows

    for row in archive.execute(
        "SELECT conclusion_id, revision, canonical_json FROM conclusions"
        " WHERE understanding_id=? ORDER BY conclusion_id, revision",
        (source_id,),
    ).fetchall():
        revision = m.from_canonical(m.ConclusionRevision, _json.loads(row[2]))
        revision_canonical = _json.dumps(m.to_canonical(revision), sort_keys=True)
        connection.execute(
            "INSERT OR REPLACE INTO conclusions"
            "(understanding_id, conclusion_id, revision, canonical_json)"
            " VALUES(?,?,?,?)",
            (
                revision.understanding_id.value,
                revision.conclusion_id.value,
                revision.revision.value,
                revision_canonical,
            ),
        )
        for dependency_kind, dependency_ref in _support_rows(revision):
            connection.execute(
                "INSERT OR REPLACE INTO support_dependencies"
                "(understanding_id, conclusion_id, revision,"
                " dependency_kind, dependency_ref) VALUES(?,?,?,?,?)",
                (
                    revision.understanding_id.value,
                    revision.conclusion_id.value,
                    revision.revision.value,
                    dependency_kind,
                    dependency_ref,
                ),
            )
        _mapping(
            records,
            source_table="conclusions",
            source_id=f"{source_id}/{row[0]}@{row[1]}",
            target_table="conclusions",
            target_id=(
                f"{revision.understanding_id.value}/"
                f"{revision.conclusion_id.value}@{revision.revision.value}"
            ),
            classification="preserved",
            source_payload=row[2],
            target_payload=revision_canonical,
        )


def _import_challenges(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    repository_id: str,
    limitations: list[str],
) -> None:
    for row in archive.execute(
        "SELECT challenges.challenge_id, challenges.canonical_json"
        " FROM challenges JOIN understandings"
        " ON understandings.understanding_id = challenges.understanding_id"
        " WHERE understandings.repository_id=?",
        (repository_id,),
    ).fetchall():
        challenge = m.from_canonical(m.Challenge, _json.loads(row[1]))
        if (
            connection.execute(
                "SELECT 1 FROM understandings WHERE understanding_id=?",
                (challenge.understanding_id.value,),
            ).fetchone()
            is None
        ):
            _unresolved(
                records,
                limitations,
                "challenges",
                challenge.challenge_id.value,
                row[1],
                "owning understanding is unresolved",
            )
            continue
        connection.execute(
            "INSERT OR REPLACE INTO challenges"
            "(challenge_id, understanding_id, canonical_json) VALUES(?,?,?)",
            (challenge.challenge_id.value, challenge.understanding_id.value, row[1]),
        )
        _mapping(
            records,
            source_table="challenges",
            source_id=challenge.challenge_id.value,
            target_table="challenges",
            target_id=challenge.challenge_id.value,
            classification="preserved",
            source_payload=row[1],
            target_payload=row[1],
        )


def _import_verifications(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    config: TransitionConfig,
) -> None:
    for row in archive.execute(
        "SELECT run_id, canonical_json FROM verification_runs" " WHERE repository_id=?",
        (config.repository_id,),
    ).fetchall():
        run = m.from_canonical(m.VerificationRun, _json.loads(row[1]))
        connection.execute(
            "INSERT OR REPLACE INTO verification_runs"
            "(run_id, repository_id, canonical_json) VALUES(?,?,?)",
            (run.run_id.value, run.repository_id, row[1]),
        )
        _mapping(
            records,
            source_table="verification_runs",
            source_id=run.run_id.value,
            target_table="verification_runs",
            target_id=run.run_id.value,
            classification="preserved",
            source_payload=row[1],
            target_payload=row[1],
        )
    for row in archive.execute(
        "SELECT observations.run_id, observations.observation_id"
        " FROM verification_observations AS observations"
        " JOIN verification_runs AS runs"
        " ON runs.run_id = observations.run_id"
        " WHERE runs.repository_id=?",
        (config.repository_id,),
    ).fetchall():
        connection.execute(
            "INSERT OR REPLACE INTO verification_observations"
            "(repository_id, run_id, observation_id) VALUES(?,?,?)",
            (config.repository_id, row[0], row[1]),
        )
        _mapping(
            records,
            source_table="verification_observations",
            source_id=f"{row[0]}/{row[1]}",
            target_table="verification_observations",
            target_id=f"{row[0]}/{row[1]}",
            classification="preserved",
        )


def _import_receipts(
    connection: _sqlite3.Connection,
    archive: _sqlite3.Connection,
    records: list[dict[str, object]],
    limitations: list[str],
    *,
    config: TransitionConfig,
    contexts: dict[str, m.InvestigationContext],
) -> None:
    receipt_keys: set[tuple[str, str]] = set()
    for row in archive.execute(
        "SELECT repository_id, context_id, submission_id, canonical_json"
        " FROM record_receipts WHERE repository_id=?"
        " ORDER BY context_id, submission_id",
        (config.repository_id,),
    ).fetchall():
        receipt_payload = _json.loads(row[3])
        context = contexts.get(str(row[1]))
        if context is None:
            _unresolved(
                records,
                limitations,
                "record_receipts",
                f"{row[1]}/{row[2]}",
                row[3],
                "receipt context is gone",
            )
            continue
        key = (str(row[0]), context.request_id.value)
        if key in receipt_keys:
            _unresolved(
                records,
                limitations,
                "record_receipts",
                f"{row[1]}/{row[2]}",
                row[3],
                "request identity is already mapped from another receipt",
            )
            continue
        receipt_keys.add(key)
        receipt = _receipt_from_schema10(payload=receipt_payload, context=context)
        missing = _missing_receipt_effects(connection, receipt)
        if missing:
            _unresolved(
                records,
                limitations,
                "record_receipts",
                f"{row[1]}/{row[2]}",
                row[3],
                "receipt effect is unresolved: " + ", ".join(missing),
            )
            continue
        receipt_canonical = _json.dumps(m.to_canonical(receipt), sort_keys=True)
        connection.execute(
            "INSERT OR REPLACE INTO record_receipts"
            "(repository_id, request_id, content_digest, canonical_json,"
            " replay_expires_at) VALUES(?,?,?,?,?)",
            (
                receipt.identity.repository_id,
                receipt.identity.request_id.value,
                receipt.content_digest.value,
                receipt_canonical,
                (
                    receipt.replay_expires_at.astimezone(
                        _datetime.timezone.utc
                    ).isoformat()
                    if receipt.replay_expires_at
                    else None
                ),
            ),
        )
        _mapping(
            records,
            source_table="record_receipts",
            source_id=f"{row[1]}/{row[2]}",
            target_table="record_receipts",
            target_id=f"{row[0]}/{context.request_id.value}",
            classification="transformed",
            source_payload=row[3],
            target_payload=receipt_canonical,
            reason="receipt identity mapped through the context request identity",
        )


def _missing_receipt_effects(
    connection: _sqlite3.Connection, receipt: m.RecordReceipt
) -> tuple[str, ...]:
    missing: list[str] = []
    for understanding_id in receipt.accepted_understanding_ids:
        if (
            connection.execute(
                "SELECT 1 FROM understandings WHERE understanding_id=?",
                (understanding_id.value,),
            ).fetchone()
            is None
        ):
            missing.append(f"understanding {understanding_id.value}")
    for run_id in receipt.accepted_verification_run_ids:
        if (
            connection.execute(
                "SELECT 1 FROM verification_runs WHERE run_id=?", (run_id.value,)
            ).fetchone()
            is None
        ):
            missing.append(f"verification run {run_id.value}")
    for challenge_id in receipt.accepted_challenge_ids:
        if (
            connection.execute(
                "SELECT 1 FROM challenges WHERE challenge_id=?",
                (challenge_id.value,),
            ).fetchone()
            is None
        ):
            missing.append(f"challenge {challenge_id.value}")
    return tuple(missing)


def _unresolved(
    records: list[dict[str, object]],
    limitations: list[str],
    source_table: str,
    source_id: str,
    source_payload: str,
    reason: str,
) -> None:
    _mapping(
        records,
        source_table=source_table,
        source_id=source_id,
        target_table="",
        target_id="",
        classification="unresolved",
        source_payload=source_payload,
        reason=reason,
    )
    limitations.append(f"{source_table} {source_id} is unresolved: {reason}")


def _receipt_from_schema10(
    *, payload: dict[str, object], context: m.InvestigationContext
) -> m.RecordReceipt:
    identity = m.RecordingIdentity(
        repository_id=context.repository_id,
        request_id=context.request_id,
        context_id=context.context_id,
    )
    return m.RecordReceipt(
        identity=identity,
        content_digest=m.from_canonical(m.ContentDigest, payload["content_digest"]),
        committed_at=_datetime.datetime.fromisoformat(str(payload["committed_at"])),
        accepted_understanding_ids=tuple(
            m.from_canonical(m.UnderstandingId, item)
            for item in _items(payload, "accepted_understanding_ids")
        ),
        accepted_understanding_versions=tuple(
            m.from_canonical(m.UnderstandingVersionNumber, item)
            for item in _items(payload, "accepted_understanding_versions")
        ),
        accepted_verification_run_ids=tuple(
            m.from_canonical(m.VerificationRunId, item)
            for item in _items(payload, "accepted_verification_run_ids")
        ),
        accepted_challenge_ids=tuple(
            m.from_canonical(m.ChallengeId, item)
            for item in _items(payload, "accepted_challenge_ids")
        ),
        replay_expires_at=(
            _datetime.datetime.fromisoformat(str(payload["replay_expires_at"]))
            if payload.get("replay_expires_at")
            else None
        ),
    )


def verify_schema10_staging(paths: TransitionPaths, config: TransitionConfig) -> None:
    """Verify per-table counts and every preserved cross-table reference."""
    if not paths.mapping.is_file():
        raise TransitionError("schema-10 mapping artifact is missing")
    payload = _json.loads(paths.mapping.read_text(encoding="utf-8"))
    expected: dict[str, int] = {}
    for record in payload["records"]:
        table = str(record["target_table"])
        if table:
            expected[table] = expected.get(table, 0) + 1
    connection = _connect_read_only(paths.staging)
    try:
        for table, count in expected.items():
            actual = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            if actual != count:
                raise TransitionError(
                    f"staged {table} holds {actual} rows, mapping expects {count}"
                )
        for kind, ref in connection.execute(
            "SELECT dependency_kind, dependency_ref FROM support_dependencies"
        ).fetchall():
            if (
                kind == "SOURCE"
                and connection.execute(
                    "SELECT 1 FROM source_observations WHERE observation_id=?", (ref,)
                ).fetchone()
                is None
            ):
                raise TransitionError(
                    f"source dependency {ref} does not resolve in the staged store"
                )
            if (
                kind == "DISCOVERY"
                and connection.execute(
                    "SELECT 1 FROM discovery_observations WHERE observation_id=?",
                    (ref,),
                ).fetchone()
                is None
            ):
                raise TransitionError(
                    f"discovery dependency {ref} does not resolve in the staged store"
                )
            if kind == "PREMISE":
                understanding_id, rest = ref.split("/", 1)
                conclusion_id, revision = rest.rsplit("@", 1)
                if (
                    connection.execute(
                        "SELECT 1 FROM conclusions WHERE understanding_id=?"
                        " AND conclusion_id=? AND revision=?",
                        (understanding_id, conclusion_id, int(revision)),
                    ).fetchone()
                    is None
                ):
                    raise TransitionError(
                        f"premise dependency {ref} does not resolve in the staged store"
                    )
        for row in connection.execute(
            "SELECT canonical_json FROM record_receipts"
        ).fetchall():
            receipt = m.from_canonical(m.RecordReceipt, _json.loads(row[0]))
            if receipt.identity.repository_id != config.repository_id:
                raise TransitionError(
                    "a mapped receipt names another repository: "
                    f"{receipt.identity.repository_id}"
                )
            for understanding_id in receipt.accepted_understanding_ids:
                if (
                    connection.execute(
                        "SELECT 1 FROM understandings WHERE understanding_id=?",
                        (understanding_id.value,),
                    ).fetchone()
                    is None
                ):
                    raise TransitionError(
                        "a mapped receipt names a missing understanding: "
                        f"{understanding_id.value}"
                    )
            for run_id in receipt.accepted_verification_run_ids:
                if (
                    connection.execute(
                        "SELECT 1 FROM verification_runs WHERE run_id=?",
                        (run_id.value,),
                    ).fetchone()
                    is None
                ):
                    raise TransitionError(
                        f"a mapped receipt names a missing verification run: "
                        f"{run_id.value}"
                    )
            for challenge_id in receipt.accepted_challenge_ids:
                if (
                    connection.execute(
                        "SELECT 1 FROM challenges WHERE challenge_id=?",
                        (challenge_id.value,),
                    ).fetchone()
                    is None
                ):
                    raise TransitionError(
                        f"a mapped receipt names a missing challenge: "
                        f"{challenge_id.value}"
                    )
    finally:
        connection.close()
    return


def stage_schema10(
    paths: TransitionPaths,
    config: TransitionConfig,
    root: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    records: list[dict[str, object]] = []
    limitations: list[str] = []
    connection = _sqlite3.connect(paths.staging)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _insert_schema10_rows(
            connection,
            config=config,
            root=root,
            records=records,
            limitations=limitations,
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    unresolved = [item for item in records if item["classification"] == "unresolved"]
    payload = {
        "source_schema": 10,
        "target_schema": TARGET_SCHEMA,
        "repository_id": config.repository_id,
        "records": records,
        "counts": {
            "preserved": sum(
                1 for item in records if item["classification"] == "preserved"
            ),
            "transformed": sum(
                1 for item in records if item["classification"] == "transformed"
            ),
            "unresolved": len(unresolved),
        },
        "unresolved": unresolved,
    }
    paths.mapping.write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (
        tuple(limitations)
        + (
            f"schema-10 mapping wrote {len(records)} records "
            f"({len(unresolved)} unresolved) to {paths.mapping}",
        ),
        payload,
    )
