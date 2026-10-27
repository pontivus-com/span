"""SQLite schema, DDL, and explicit migrations (plan §10.2, E5).

Schema version 9 is the only supported schema. Stores at any other version
fail closed; migration is explicit through ``migrate_store``.
"""

from __future__ import annotations

import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3

from span.shell.sqlite_store.mapping import _encode
from span.shell.sqlite_store.migrations.v0_8_0_to_v0_8_1 import (
    _count_legacy_question_coverages,
    _rewrite_question_coverages,
)

SCHEMA_VERSION = 9


SQLITE_BUSY_TIMEOUT_MS = 5_000


TARGET_RETENTION_DAYS = 90


_VERIFICATION_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS verification_records(
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  scope_fingerprint TEXT NOT NULL,
  command TEXT,
  exit_status INTEGER NOT NULL,
  observed_revision TEXT,
  observed_at TEXT NOT NULL,
  observer TEXT,
  PRIMARY KEY(
    repository_id, subject_locator, subject_kind, scope_fingerprint
  )
);
"""


_SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS repositories(
  repository_id TEXT PRIMARY KEY,
  revision_id TEXT,
  dirty INTEGER NOT NULL,
  state_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  authority_seeds_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subjects(
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, locator, kind)
);
CREATE TABLE IF NOT EXISTS claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships(
  relationship_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  source_locator TEXT NOT NULL,
  target_locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_dependencies(
  semantic_id TEXT NOT NULL,
  semantic_kind TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  observed_fingerprint TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(semantic_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS coverage_dependencies(
  repository_id TEXT NOT NULL,
  scope_locators TEXT NOT NULL,
  inventory_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_coverages(
  repository_id TEXT NOT NULL,
  scope_root_locator TEXT NOT NULL,
  scope_root_kind TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  question_class TEXT NOT NULL,
  question_slice TEXT NOT NULL,
  disposition TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(
    repository_id, scope_root_locator, scope_root_kind,
    subject_locator, subject_kind, question_class, question_slice
  )
);
CREATE TABLE IF NOT EXISTS premise_dependents(
  repository_id TEXT NOT NULL,
  premise_id TEXT NOT NULL,
  premise_kind TEXT NOT NULL,
  dependent_id TEXT NOT NULL,
  dependent_kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, premise_id, dependent_id)
);
CREATE TABLE IF NOT EXISTS question_result_refs(
  repository_id TEXT NOT NULL,
  scope_root_locator TEXT NOT NULL,
  scope_root_kind TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  question_class TEXT NOT NULL,
  question_slice TEXT NOT NULL,
  result_id TEXT NOT NULL,
  result_kind TEXT NOT NULL,
  PRIMARY KEY(
    repository_id, scope_root_locator, scope_root_kind,
    subject_locator, subject_kind, question_class, question_slice,
    result_id
  )
);
CREATE TABLE IF NOT EXISTS conflict_records(
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, subject_locator, left_id, right_id)
);
"""
    + _VERIFICATION_RECORDS_DDL
    + """
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS target_associations(
  repository_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  last_touched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, target_id)
);
CREATE INDEX IF NOT EXISTS idx_target_associations_repo
  ON target_associations(repository_id);
"""
)


def _rewrite_verification_claims(connection) -> int:
    """Rewrite stored verification values to the link-only shape (Step 17).

    A stored pass was never checkable, so it becomes an UNKNOWN
    attestation: the execution record is gone and inventing CANDIDATE
    would overstate what is known. Link-only payloads are left untouched,
    which makes the rewrite idempotent.
    """
    rewritten = 0
    rows = connection.execute(
        "SELECT claim_id, canonical_json FROM claims " "WHERE kind='VERIFICATION'"
    ).fetchall()
    for claim_id, payload in rows:
        data = _json.loads(payload)
        value = data.get("value")
        if not isinstance(value, dict) or value.get("$type") != "VerificationValue":
            continue
        if "currency" not in value and "observed_revision" not in value:
            continue
        data["value"] = {
            "$type": "VerificationValue",
            "verification_ref": value["verification_ref"],
            "kind": value["kind"],
            "attested_currency": "UNKNOWN",
        }
        connection.execute(
            "UPDATE claims SET canonical_json=? WHERE claim_id=?",
            (_encode(data), claim_id),
        )
        rewritten += 1
    return rewritten


def _rewrite_target_accounting(connection) -> tuple[int, int]:
    """Drop the mapping-era outcomes from persisted target accounts (step 8→9).

    The deterministic admission path always assigns an area, so
    ``exclusion_basis`` and ``resolution_requirements`` have no producer and
    no reader. Accounts that carry no assigned area are removed rather than
    fabricated into an area. Idempotent: already-compact payloads are left
    untouched.
    """
    rewritten = 0
    dropped = 0
    rows = connection.execute(
        "SELECT target_id, canonical_json FROM target_associations"
    ).fetchall()
    for target_id, payload in rows:
        data = _json.loads(payload)
        accounts = data.get("inventory_accounting")
        if not isinstance(accounts, list):
            continue
        changed = False
        compact: list[dict[str, object]] = []
        for account in accounts:
            if not isinstance(account, dict):
                changed = True
                continue
            had_legacy = (
                "exclusion_basis" in account or "resolution_requirements" in account
            )
            assigned = account.get("assigned_area_subjects") or []
            if not assigned:
                dropped += 1
                changed = True
                continue
            if had_legacy:
                account = {
                    key: value
                    for key, value in account.items()
                    if key not in ("exclusion_basis", "resolution_requirements")
                }
                changed = True
            compact.append(account)
        if not changed:
            continue
        data["inventory_accounting"] = compact
        connection.execute(
            "UPDATE target_associations SET canonical_json=? WHERE target_id=?",
            (_encode(data), target_id),
        )
        rewritten += 1
    return rewritten, dropped


def migrate_store(
    path: str | _pathlib.Path, *, dry_run: bool = False
) -> dict[str, object]:
    """Upgrade schema-7/8 stores and normalize 0.8.0 schema-9 stores.

    Never called at open. Refuses an unknown version rather than guessing,
    is idempotent at the current version, and performs every step in one
    transaction so a failure leaves the store untouched.
    """
    db_path = _pathlib.Path(path)
    if not db_path.is_file():
        raise ValueError(f"no Span store at {db_path}")
    connection = _sqlite3.connect(str(db_path))
    try:
        row = connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        version = int(row[0]) if row is not None else 0
        if version not in (7, 8, SCHEMA_VERSION):
            raise ValueError(
                "cannot migrate Span store schema version "
                f"{version}; only schema 7, 8, or 9 can be migrated to "
                f"{SCHEMA_VERSION}"
            )
        question_coverages = _count_legacy_question_coverages(connection)
        if dry_run:
            return {
                "path": str(db_path),
                "from": version,
                "to": SCHEMA_VERSION,
                "migrated": False,
                "rewritten_verifications": 0,
                "rewritten_target_accounts": 0,
                "dropped_target_accounts": 0,
                "rewritten_question_coverages": question_coverages,
            }
        with connection:
            rewritten_verifications = 0
            if version == 7:
                connection.execute(_VERIFICATION_RECORDS_DDL.strip().rstrip(";"))
                connection.execute("DROP TABLE IF EXISTS retired_claims")
                connection.execute("DROP TABLE IF EXISTS retired_relationships")
                rewritten_verifications = _rewrite_verification_claims(connection)
            rewritten_accounts, dropped_accounts = _rewrite_target_accounting(
                connection
            )
            rewritten_question_coverages = _rewrite_question_coverages(connection)
            connection.execute(
                "UPDATE meta SET value=? WHERE key='schema_version'",
                (str(SCHEMA_VERSION),),
            )
        return {
            "path": str(db_path),
            "from": version,
            "to": SCHEMA_VERSION,
            "migrated": bool(
                version != SCHEMA_VERSION
                or rewritten_verifications
                or rewritten_accounts
                or rewritten_question_coverages
            ),
            "rewritten_verifications": rewritten_verifications,
            "rewritten_target_accounts": rewritten_accounts,
            "dropped_target_accounts": dropped_accounts,
            "rewritten_question_coverages": rewritten_question_coverages,
        }
    finally:
        connection.close()
