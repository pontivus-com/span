"""Offline PUB-07A conversion of retained schema-15 and installation-1 facts.

Only the administrative transition imports this module. It reads legacy
canonical JSON as data, not through the current runtime decoder. Staging
preserves every non-transformed SQLite cell and every legacy receipt key.
"""

from __future__ import annotations

import json as _json
import sqlite3 as _sqlite3
from collections.abc import Callable as _Callable
from pathlib import Path as _Path

from span.core import model as m
from span.shell.sqlite_store.functional_pyramid import SCHEMA2_DDL
from span.shell.store_transition import (
    TransitionError,
    TransitionPaths,
    _columns,
    _connect_read_only,
    _integrity,
    _table_names,
)


def _object(value: object, tag: str) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("$type") != tag:
        raise TransitionError(f"expected historical {tag}")
    if not all(isinstance(key, str) for key in value):
        raise TransitionError(f"invalid historical {tag} fields")
    return dict(value)


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TransitionError("historical collection is not an array")
    return value


def _factor(
    value: object, tag: str, component: str, fields: tuple[str, ...]
) -> dict[str, object]:
    """Move recorded fields without interpreting their values."""
    payload = _object(value, tag)
    if component in payload:
        raise TransitionError(f"{tag} is not a legacy record")
    try:
        payload[component] = {key: payload.pop(key) for key in fields}
    except KeyError as exc:
        raise TransitionError(f"{tag} lacks recorded field {exc}") from None
    return payload


def verification_payload(value: object) -> dict[str, object]:
    payload = _factor(
        value,
        "VerificationRun",
        "facts",
        (
            "run_id",
            "repository_id",
            "scope",
            "command",
            "scenario",
            "outcome",
            "observed_at",
            "observer",
            "provenance",
        ),
    )
    facts = payload["facts"]
    if not isinstance(facts, dict):
        raise TransitionError("verification facts are not an object")
    facts["$type"] = "VerificationRunFacts"
    return payload


def _resolution(value: object) -> dict[str, object]:
    payload = _factor(
        value,
        "ChallengeResolution",
        "facts",
        ("reasoning", "resulting_understanding_id", "resulting_version"),
    )
    facts = payload["facts"]
    if not isinstance(facts, dict):
        raise TransitionError("resolution facts are not an object")
    facts["$type"] = "ChallengeResolutionFacts"
    return payload


def _disposition(value: object) -> dict[str, object]:
    if isinstance(value, dict) and value.get("$type") == "UnresolvedChallengeRecord":
        return _object(value, "UnresolvedChallengeRecord")
    payload = _factor(
        value,
        "ResolvedChallengeRecord",
        "decision",
        ("challenge_revision", "recorded_at"),
    )
    decision = payload["decision"]
    if not isinstance(decision, dict):
        raise TransitionError("challenge decision is not an object")
    decision["$type"] = "ChallengeDispositionDecision"
    payload["resolution"] = _resolution(payload["resolution"])
    return payload


def challenge_payload(value: object) -> dict[str, object]:
    payload = _factor(
        value,
        "Challenge",
        "facts",
        (
            "challenge_id",
            "understanding_id",
            "target_version",
            "reason",
            "provenance",
            "challenge_revision",
            "state",
            "created_at",
        ),
    )
    facts = payload["facts"]
    if not isinstance(facts, dict):
        raise TransitionError("challenge facts are not an object")
    facts["$type"] = "ChallengeFacts"
    if payload.get("resolution") is not None:
        payload["resolution"] = _resolution(payload["resolution"])
    payload["dispositions"] = [
        _disposition(item) for item in _sequence(payload.get("dispositions", []))
    ]
    return payload


def _historical(
    *,
    understanding_versions: tuple[m.UnderstandingVersionRef, ...] = (),
    verification_run_ids: tuple[m.VerificationRunId, ...] = (),
    challenge_ids: tuple[m.ChallengeId, ...] = (),
    dependent_effect_refs: tuple[m.ConclusionRevisionRef, ...] = (),
) -> object:
    return m.to_canonical(
        m.HistoricalAcceptanceDetailUnavailable(
            understanding_versions=understanding_versions,
            verification_run_ids=verification_run_ids,
            challenge_ids=challenge_ids,
            dependent_effect_refs=dependent_effect_refs,
            reason="exact accepted detail was not retained by the historical schema",
            recovery="retrieve the named historical records; do not repeat the write",
        )
    )


def receipt_payload(value: object) -> dict[str, object]:
    payload = _object(value, "RecordReceipt")
    identity = _object(payload.pop("identity"), "RecordingIdentity")
    repository_id = identity["repository_id"]
    request_id = identity["request_id"]
    context_id = identity["context_id"]
    understanding_ids = tuple(
        m.from_canonical(m.UnderstandingId, item)
        for item in _sequence(payload.pop("accepted_understanding_ids", []))
    )
    versions = tuple(
        m.from_canonical(m.UnderstandingVersionNumber, item)
        for item in _sequence(payload.pop("accepted_understanding_versions", []))
    )
    runs = tuple(
        m.from_canonical(m.VerificationRunId, item)
        for item in _sequence(payload.pop("accepted_verification_run_ids", []))
    )
    challenges = tuple(
        m.from_canonical(m.ChallengeId, item)
        for item in _sequence(payload.pop("accepted_challenge_ids", []))
    )
    dependents = tuple(
        m.from_canonical(m.ConclusionRevisionRef, item)
        for item in _sequence(payload.pop("dependent_effects", []))
    )
    if len(understanding_ids) != len(versions):
        raise TransitionError(
            "historical receipt has unpaired understanding coordinates"
        )
    if not (understanding_ids or runs or challenges):
        raise TransitionError("historical receipt lacks accepted identity")
    effect: object
    if len(runs) == 1 and not (understanding_ids or challenges or dependents):
        effect = {
            "$type": "AcceptedVerificationEffect",
            "run_id": m.to_canonical(runs[0]),
        }
    else:
        effect = _historical(
            understanding_versions=tuple(
                m.UnderstandingVersionRef(identity, version)
                for identity, version in zip(understanding_ids, versions, strict=True)
            ),
            verification_run_ids=runs,
            challenge_ids=challenges,
            dependent_effect_refs=dependents,
        )
    payload.update(
        key={
            "$type": "RecordingKey",
            "repository_id": repository_id,
            "request_id": request_id,
        },
        original_addressing_repository_id=repository_id,
        context={
            "$type": "InvestigationContextRef",
            "repository_id": repository_id,
            "context_id": context_id,
        },
        accepted_effect=effect,
    )
    return payload


def installation_dependency_payload(value: object) -> object:
    refs = tuple(
        m.from_canonical(m.ConclusionRevisionRef, item) for item in _sequence(value)
    )
    if refs:
        return _historical(dependent_effect_refs=refs)
    return {"$type": "AcceptedDependencyEffects", "effects": []}


def _canonical_text(value: object) -> str:
    return _json.dumps(value, sort_keys=True, separators=(",", ":"))


def _replace_payloads(
    connection: _sqlite3.Connection,
    table: str,
    column: str,
    transform: _Callable[[object], object],
) -> None:
    for rowid, raw in connection.execute(
        f"SELECT rowid, {column} FROM {table}"
    ).fetchall():
        rewritten = _canonical_text(transform(_json.loads(raw)))
        connection.execute(
            f"UPDATE {table} SET {column}=? WHERE rowid=?", (rewritten, rowid)
        )


def upgrade_repository_payloads(connection: _sqlite3.Connection) -> None:
    """Convert all staged retained rows, including those mapped from 7–14."""
    for table, transform in (
        ("verification_runs", verification_payload),
        ("challenges", challenge_payload),
        ("record_receipts", receipt_payload),
    ):
        _replace_payloads(connection, table, "canonical_json", transform)
    connection.execute("UPDATE meta SET value='16' WHERE key='schema_version'")


def _backup(source: _Path, target: _Path) -> None:
    if target.exists():
        target.unlink()
    old = _connect_read_only(source)
    new = _sqlite3.connect(target)
    try:
        old.backup(new)
    finally:
        new.close()
        old.close()


def stage_schema15(paths: TransitionPaths) -> None:
    """Copy the complete archived SQLite database before changing its payloads."""
    _backup(paths.archive, paths.staging)
    connection = _sqlite3.connect(paths.staging)
    try:
        with connection:
            upgrade_repository_payloads(connection)
    finally:
        connection.close()
    verify_schema15_staging(paths)


def stage_installation_schema1(paths: TransitionPaths) -> None:
    """Preserve installation receipt/member facts and initialize empty v2 indexes."""
    _backup(paths.archive, paths.staging)
    connection = _sqlite3.connect(paths.staging)
    try:
        with connection:
            _replace_payloads(
                connection,
                "functional_pyramid_receipts",
                "dependent_effect_refs_json",
                installation_dependency_payload,
            )
            for statement in SCHEMA2_DDL:
                connection.execute(statement)
            connection.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    finally:
        connection.close()
    verify_installation_schema1_staging(paths)


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _verify_table(
    source: _sqlite3.Connection,
    staged: _sqlite3.Connection,
    table: str,
    *,
    version: str,
    transform: tuple[str, _Callable[[object], object]] | None = None,
) -> None:
    columns = _columns(source, table)
    if columns != _columns(staged, table):
        raise TransitionError(f"migration changed retained table columns: {table}")
    sql = f"SELECT * FROM {_quoted(table)} ORDER BY rowid"
    source_rows = source.execute(sql)
    staged_rows = staged.execute(sql)
    for old, new in zip(source_rows, staged_rows, strict=True):
        expected = list(old)
        if table == "meta" and old[columns.index("key")] == "schema_version":
            expected[columns.index("value")] = version
        if transform is not None:
            column, convert = transform
            position = columns.index(column)
            expected[position] = _canonical_text(
                convert(_json.loads(str(expected[position])))
            )
        if tuple(expected) != tuple(new):
            raise TransitionError(f"migration changed retained cells in {table}")


def _verify_copy(
    paths: TransitionPaths,
    version: str,
    transforms: dict[str, tuple[str, _Callable[[object], object]]],
    added_tables: frozenset[str],
) -> None:
    old = _connect_read_only(paths.archive)
    new = _connect_read_only(paths.staging)
    try:
        if _integrity(new) != "ok":
            raise TransitionError("staged database failed integrity check")
        original_tables = frozenset(_table_names(old))
        if frozenset(_table_names(new)) != original_tables | added_tables:
            raise TransitionError("migration changed retained table inventory")
        for table in sorted(original_tables):
            query = f"SELECT COUNT(*) FROM {_quoted(table)}"
            if old.execute(query).fetchone()[0] != new.execute(query).fetchone()[0]:
                raise TransitionError(f"migration changed row count: {table}")
            _verify_table(
                old, new, table, version=version, transform=transforms.get(table)
            )
        for table in added_tables:
            if new.execute(f"SELECT 1 FROM {_quoted(table)} LIMIT 1").fetchone():
                raise TransitionError(f"migration populated new index: {table}")
        if new.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise TransitionError("migration introduced broken foreign keys")
    finally:
        old.close()
        new.close()


def verify_schema15_staging(paths: TransitionPaths) -> None:
    _verify_copy(
        paths,
        "16",
        {
            "verification_runs": ("canonical_json", verification_payload),
            "challenges": ("canonical_json", challenge_payload),
            "record_receipts": ("canonical_json", receipt_payload),
        },
        frozenset(),
    )


def verify_installation_schema1_staging(paths: TransitionPaths) -> None:
    _verify_copy(
        paths,
        "2",
        {
            "functional_pyramid_receipts": (
                "dependent_effect_refs_json",
                installation_dependency_payload,
            )
        },
        frozenset({"delivery_selections", "delivery_cursors", "addressed_requests"}),
    )
