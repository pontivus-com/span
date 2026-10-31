"""Candidate schema-10 lifecycle store.

This is the replacement store boundary for the 0.9.0 lifecycle: canonical
contexts, understanding versions, conclusion revisions, challenges,
verification runs, and recording receipts in one SQLite transaction.

It is a candidate module for WP-02 and is not wired into the current MCP
server. The old schema-9 store remains the running release until the
coordinated cutover.
"""

from __future__ import annotations

import contextlib as _contextlib
import dataclasses as _dataclasses
import datetime as _datetime
import json as _json
import pathlib as _pathlib
import sqlite3 as _sqlite3
import typing as _typing

from span.core import model as m
from span.core.identity import challenge_identity, record_content_digest
from span.core.recording import (
    ChallengeEffect,
    RecordingConflict,
    RecordingValidationError,
    UnderstandingTransition,
    apply_update,
    build_receipt,
    create_challenge as build_challenge,
    create_understanding,
    receipt_decision,
)

__all__ = [
    "LifecycleStore",
    "LifecycleStoreError",
    "SchemaVersionError",
    "SourceObservationRecord",
]

SCHEMA_VERSION = 10


class LifecycleStoreError(ValueError):
    """The store cannot satisfy this operation."""


class SchemaVersionError(LifecycleStoreError):
    """The store is not the supported schema version."""


_DDL = (
    """
    CREATE TABLE IF NOT EXISTS meta(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repositories(
        repository_id TEXT PRIMARY KEY,
        root TEXT NOT NULL,
        authority_seeds_json TEXT NOT NULL DEFAULT '[]',
        authority_bindings_json TEXT NOT NULL DEFAULT '[]'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_observations(
        observation_id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        evidence_id TEXT NOT NULL,
        locator TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        total_lines INTEGER NOT NULL DEFAULT 0,
        delivered_ranges_json TEXT NOT NULL DEFAULT '[]',
        whole_file INTEGER NOT NULL DEFAULT 0,
        excerpt TEXT NOT NULL DEFAULT '',
        canonical_json TEXT NOT NULL,
        UNIQUE(repository_id, observation_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS source_observations_evidence
    ON source_observations(evidence_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS source_observations_locator
    ON source_observations(repository_id, locator)
    """,
    """
    CREATE TABLE IF NOT EXISTS discovery_observations(
        observation_id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        canonical_json TEXT NOT NULL,
        UNIQUE(repository_id, observation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investigation_contexts(
        context_id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        request_id TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        expires_at TEXT,
        UNIQUE(repository_id, request_id),
        UNIQUE(repository_id, context_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS context_evidence(
        repository_id TEXT NOT NULL,
        context_id TEXT NOT NULL,
        observation_id TEXT NOT NULL,
        PRIMARY KEY(repository_id, context_id, observation_id),
        FOREIGN KEY(repository_id, context_id)
            REFERENCES investigation_contexts(repository_id, context_id)
            ON DELETE CASCADE,
        FOREIGN KEY(repository_id, observation_id)
            REFERENCES source_observations(repository_id, observation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS context_discovery_evidence(
        repository_id TEXT NOT NULL,
        context_id TEXT NOT NULL,
        observation_id TEXT NOT NULL,
        PRIMARY KEY(repository_id, context_id, observation_id),
        FOREIGN KEY(repository_id, context_id)
            REFERENCES investigation_contexts(repository_id, context_id)
            ON DELETE CASCADE,
        FOREIGN KEY(repository_id, observation_id)
            REFERENCES discovery_observations(repository_id, observation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS understandings(
        understanding_id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        question TEXT NOT NULL,
        scope_json TEXT NOT NULL,
        current_version INTEGER NOT NULL,
        canonical_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS understanding_versions(
        understanding_id TEXT NOT NULL
            REFERENCES understandings(understanding_id),
        version INTEGER NOT NULL,
        canonical_json TEXT NOT NULL,
        PRIMARY KEY(understanding_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conclusions(
        understanding_id TEXT NOT NULL
            REFERENCES understandings(understanding_id),
        conclusion_id TEXT NOT NULL,
        revision INTEGER NOT NULL,
        canonical_json TEXT NOT NULL,
        PRIMARY KEY(understanding_id, conclusion_id, revision)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS support_dependencies(
        understanding_id TEXT NOT NULL,
        conclusion_id TEXT NOT NULL,
        revision INTEGER NOT NULL,
        dependency_kind TEXT NOT NULL,
        dependency_ref TEXT NOT NULL,
        PRIMARY KEY(
            understanding_id, conclusion_id, revision,
            dependency_kind, dependency_ref
        ),
        FOREIGN KEY(understanding_id, conclusion_id, revision)
            REFERENCES conclusions(understanding_id, conclusion_id, revision)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS support_dependencies_ref
    ON support_dependencies(dependency_kind, dependency_ref)
    """,
    """
    CREATE TABLE IF NOT EXISTS understanding_membership(
        understanding_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        conclusion_id TEXT NOT NULL,
        revision INTEGER NOT NULL,
        PRIMARY KEY(understanding_id, version, conclusion_id),
        FOREIGN KEY(understanding_id, version)
            REFERENCES understanding_versions(understanding_id, version),
        FOREIGN KEY(understanding_id, conclusion_id, revision)
            REFERENCES conclusions(understanding_id, conclusion_id, revision)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS challenges(
        challenge_id TEXT PRIMARY KEY,
        understanding_id TEXT NOT NULL
            REFERENCES understandings(understanding_id),
        canonical_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_runs(
        run_id TEXT PRIMARY KEY,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        canonical_json TEXT NOT NULL,
        UNIQUE(repository_id, run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_observations(
        repository_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        observation_id TEXT NOT NULL,
        PRIMARY KEY(repository_id, run_id, observation_id),
        FOREIGN KEY(repository_id, run_id)
            REFERENCES verification_runs(repository_id, run_id)
            ON DELETE CASCADE,
        FOREIGN KEY(repository_id, observation_id)
            REFERENCES source_observations(repository_id, observation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_receipts(
        repository_id TEXT NOT NULL,
        context_id TEXT NOT NULL,
        submission_id TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        replay_expires_at TEXT,
        PRIMARY KEY(repository_id, context_id, submission_id)
    )
    """,
)


SourceObservationRecord = m.SourceObservation


def _now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _timestamp(value: _datetime.datetime) -> str:
    """Store one aware timestamp in canonical UTC ISO form."""
    return value.astimezone(_datetime.timezone.utc).isoformat()


class LifecycleStore:
    """One candidate SQLite store with atomic lifecycle acceptance."""

    def __init__(
        self,
        path: str | _pathlib.Path,
        *,
        retention: m.LifecycleRetention,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
    ) -> None:
        self.path = _pathlib.Path(path)
        self.retention = retention
        self._clock = clock or _now
        self._connection = _sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = _sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    @_contextlib.contextmanager
    def _transaction(self) -> _typing.Iterator[_sqlite3.Connection]:
        """Serialize one write decision with its effects.

        ``BEGIN IMMEDIATE`` acquires the write lock before any receipt or
        expected-version read, so two writers cannot both accept against a
        stale snapshot.
        """
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except BaseException:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()

    def _initialize_schema(self) -> None:
        tables = {
            str(row["name"])
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master"
                " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if "meta" not in tables and tables:
            raise SchemaVersionError(
                "existing store has no schema version marker; refusing to open"
            )
        if "meta" in tables:
            row = self._connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                raise SchemaVersionError(
                    "existing store has no schema version; refusing to open"
                )
            if int(row["value"]) != SCHEMA_VERSION:
                raise SchemaVersionError(
                    f"unsupported lifecycle store schema {row['value']}; "
                    f"expected {SCHEMA_VERSION}"
                )
        with self._transaction() as connection:
            for statement in _DDL:
                connection.execute(statement)
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )

    # -- repository binding ------------------------------------------------

    def register_repository(
        self,
        repository_id: str,
        root: str,
        *,
        authority_seeds: tuple[m.EvidenceRef, ...] = (),
        authority_bindings: tuple[m.AuthorityBinding, ...] | None = None,
    ) -> None:
        """Register one repository root without silent rebinding.

        ``authority_bindings=None`` preserves the configured bindings; an empty
        tuple clears them; a non-empty tuple replaces them.
        """
        if not repository_id:
            raise LifecycleStoreError("repository_id is required")
        if not root:
            raise LifecycleStoreError("repository root is required")
        seeds = _json.dumps(
            [m.to_canonical(item) for item in authority_seeds],
            sort_keys=True,
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT root, authority_bindings_json FROM repositories"
                " WHERE repository_id=?",
                (repository_id,),
            ).fetchone()
            if authority_bindings is None:
                bindings = row["authority_bindings_json"] if row is not None else "[]"
            else:
                bindings = _json.dumps(
                    [m.to_canonical(item) for item in authority_bindings],
                    sort_keys=True,
                )
            if row is None:
                connection.execute(
                    "INSERT INTO repositories"
                    "(repository_id, root, authority_seeds_json,"
                    " authority_bindings_json) VALUES(?,?,?,?)",
                    (repository_id, root, seeds, bindings),
                )
                return
            if row["root"] != root:
                raise LifecycleStoreError(
                    f"repository {repository_id} is bound to {row['root']!r}, "
                    f"not {root!r}"
                )
            connection.execute(
                "UPDATE repositories SET authority_seeds_json=?,"
                " authority_bindings_json=? WHERE repository_id=?",
                (seeds, bindings, repository_id),
            )

    def load_authority_seeds(self, repository_id: str) -> tuple[m.EvidenceRef, ...]:
        """Return the declared authority seeds for one repository.

        Missing repository or malformed stored seeds fail closed; they never
        fall back to an empty configuration.
        """
        row = self._connection.execute(
            "SELECT authority_seeds_json FROM repositories" " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return ()
        try:
            payload = _json.loads(row["authority_seeds_json"])
            if not isinstance(payload, list):
                raise ValueError("authority seeds are not a list")
            seeds = tuple(m.from_canonical(m.EvidenceRef, item) for item in payload)
        except (TypeError, ValueError) as exc:
            raise LifecycleStoreError(
                f"authority seeds for {repository_id} are not canonical: {exc}"
            ) from None
        for seed in seeds:
            if seed.repository_id != repository_id:
                raise LifecycleStoreError(
                    f"authority seed for {repository_id} belongs to "
                    f"{seed.repository_id}"
                )
        return seeds

    def load_authority_bindings(
        self, repository_id: str
    ) -> tuple[m.AuthorityBinding, ...]:
        """Return the declared authority bindings; malformed data fails closed."""
        row = self._connection.execute(
            "SELECT authority_bindings_json FROM repositories" " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return ()
        try:
            payload = _json.loads(row["authority_bindings_json"])
            if not isinstance(payload, list):
                raise ValueError("authority bindings are not a list")
            bindings = tuple(
                m.from_canonical(m.AuthorityBinding, item) for item in payload
            )
        except (TypeError, ValueError) as exc:
            raise LifecycleStoreError(
                f"authority bindings for {repository_id} are not canonical: {exc}"
            ) from None
        for binding in bindings:
            if binding.evidence_ref.repository_id != repository_id:
                raise LifecycleStoreError(
                    f"authority binding for {repository_id} belongs to "
                    f"{binding.evidence_ref.repository_id}"
                )
        return bindings

    def find_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding | None:
        """Find one declared authority binding, or return None."""
        row = self._connection.execute(
            "SELECT authority_bindings_json FROM repositories" " WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return None
        for item in _json.loads(row["authority_bindings_json"]):
            binding = m.from_canonical(m.AuthorityBinding, item)
            if binding.evidence_ref.evidence_id.value == authority_ref:
                return binding
        return None

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        binding = self.find_authority(repository_id, authority_ref)
        if binding is None:
            raise RecordingValidationError(
                f"unknown authority reference: {authority_ref}"
            )
        return binding

    def schema_version(self) -> int:
        """Return the active lifecycle schema version."""
        return SCHEMA_VERSION

    def require_repository(self, repository_id: str) -> str:
        """Return the registered root or reject an unknown repository."""
        row = self._connection.execute(
            "SELECT root FROM repositories WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(
                f"unknown repository: {repository_id}; "
                "initialize it before recording"
            )
        return str(row["root"])

    # -- evidence observations --------------------------------------------

    def put_source_observation(self, record: SourceObservationRecord) -> None:
        """Insert one immutable observation; an identity conflict rejects."""
        with self._transaction() as connection:
            ranges = _ranges_json(record.delivered_ranges)
            row = connection.execute(
                "SELECT repository_id, evidence_id, locator, content_digest,"
                " captured_at, total_lines, delivered_ranges_json, whole_file,"
                " excerpt FROM source_observations WHERE observation_id=?",
                (record.observation_id.value,),
            ).fetchone()
            if row is not None:
                observed = (
                    row["repository_id"],
                    row["evidence_id"],
                    row["locator"],
                    row["content_digest"],
                    row["captured_at"],
                    int(row["total_lines"]),
                    row["delivered_ranges_json"],
                    int(row["whole_file"]),
                    row["excerpt"],
                )
                proposed = (
                    record.repository_id,
                    record.evidence.evidence_id.value,
                    record.evidence.locator,
                    record.content_digest.value,
                    _timestamp(record.captured_at),
                    record.total_lines,
                    ranges,
                    int(record.whole_file),
                    record.excerpt,
                )
                if observed != proposed:
                    raise LifecycleStoreError(
                        "source observation is immutable: "
                        f"{record.observation_id.value} already exists with "
                        "different content"
                    )
                return
            connection.execute(
                "INSERT INTO source_observations"
                "(observation_id, repository_id, evidence_id, locator,"
                " content_digest, captured_at, total_lines,"
                " delivered_ranges_json, whole_file, excerpt, canonical_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.observation_id.value,
                    record.repository_id,
                    record.evidence.evidence_id.value,
                    record.evidence.locator,
                    record.content_digest.value,
                    _timestamp(record.captured_at),
                    record.total_lines,
                    ranges,
                    int(record.whole_file),
                    record.excerpt,
                    _json.dumps(m.to_canonical(record.evidence), sort_keys=True),
                ),
            )

    def put_discovery_observation(self, observation: m.DiscoveryObservation) -> None:
        """Insert one immutable discovery observation, rejecting drift."""
        encoded = _json.dumps(m.to_canonical(observation), sort_keys=True)
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT canonical_json FROM discovery_observations"
                " WHERE observation_id=?",
                (observation.observation_id.value,),
            ).fetchone()
            if row is not None:
                if row["canonical_json"] != encoded:
                    raise LifecycleStoreError(
                        "discovery observation is immutable: "
                        f"{observation.observation_id.value} already exists "
                        "with different content"
                    )
                return
            connection.execute(
                "INSERT INTO discovery_observations"
                "(observation_id, repository_id, canonical_json)"
                " VALUES(?,?,?)",
                (
                    observation.observation_id.value,
                    observation.repository_id,
                    encoded,
                ),
            )

    def has_source_observation(self, observation_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM source_observations WHERE observation_id=?",
            (observation_id,),
        ).fetchone()
        return row is not None

    def source_observation_ids_for_locator(
        self, repository_id: str, locator: str
    ) -> tuple[str, ...]:
        """Return observations captured from one repository locator."""
        rows = self._connection.execute(
            "SELECT observation_id FROM source_observations"
            " WHERE repository_id=? AND locator=? ORDER BY observation_id",
            (repository_id, locator),
        ).fetchall()
        return tuple(str(row["observation_id"]) for row in rows)

    def find_source_observation(
        self, observation_id: str
    ) -> SourceObservationRecord | None:
        row = self._connection.execute(
            "SELECT observation_id, repository_id, evidence_id, locator,"
            " content_digest, captured_at, total_lines,"
            " delivered_ranges_json, whole_file, excerpt, canonical_json"
            " FROM source_observations WHERE observation_id=?",
            (observation_id,),
        ).fetchone()
        return None if row is None else _observation_from_row(row)

    def get_source_observation(self, observation_id: str) -> SourceObservationRecord:
        record = self.find_source_observation(observation_id)
        if record is None:
            raise LifecycleStoreError(f"unknown source observation: {observation_id}")
        return record

    def list_context_evidence(
        self, context_id: str
    ) -> tuple[SourceObservationRecord, ...]:
        rows = self._connection.execute(
            "SELECT o.observation_id, o.repository_id, o.evidence_id,"
            " o.locator, o.content_digest, o.captured_at, o.total_lines,"
            " o.delivered_ranges_json, o.whole_file, o.excerpt,"
            " o.canonical_json"
            " FROM context_evidence ce"
            " JOIN source_observations o"
            " ON o.observation_id = ce.observation_id"
            " AND o.repository_id = ce.repository_id"
            " WHERE ce.context_id=?"
            " ORDER BY o.observation_id",
            (context_id,),
        ).fetchall()
        return tuple(_observation_from_row(row) for row in rows)

    def find_discovery_observation(
        self, observation_id: str
    ) -> m.DiscoveryObservation | None:
        row = self._connection.execute(
            "SELECT canonical_json FROM discovery_observations"
            " WHERE observation_id=?",
            (observation_id,),
        ).fetchone()
        if row is None:
            return None
        return m.from_canonical(
            m.DiscoveryObservation, _json.loads(row["canonical_json"])
        )

    def get_discovery_observation(self, observation_id: str) -> m.DiscoveryObservation:
        observation = self.find_discovery_observation(observation_id)
        if observation is None:
            raise LifecycleStoreError(
                f"unknown discovery observation: {observation_id}"
            )
        return observation

    def find_admitted_evidence(
        self, context_id: str, reference: str
    ) -> m.EvidenceRef | None:
        """Resolve one admitted observation/evidence reference by identity."""
        row = self._connection.execute(
            "SELECT o.canonical_json FROM context_evidence ce"
            " JOIN source_observations o"
            " ON o.observation_id = ce.observation_id"
            " AND o.repository_id = ce.repository_id"
            " WHERE ce.context_id=?"
            " AND (o.observation_id=? OR o.evidence_id=?)"
            " ORDER BY o.observation_id LIMIT 1",
            (context_id, reference, reference),
        ).fetchone()
        if row is None:
            return None
        return m.from_canonical(m.EvidenceRef, _json.loads(row["canonical_json"]))

    def has_admitted_observation(self, context_id: str, observation_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM context_evidence ce"
            " JOIN source_observations o"
            " ON o.observation_id = ce.observation_id"
            " AND o.repository_id = ce.repository_id"
            " WHERE ce.context_id=? AND ce.observation_id=?",
            (context_id, observation_id),
        ).fetchone()
        return row is not None

    def _context_repository(
        self, connection: _sqlite3.Connection, context_id: str
    ) -> str:
        row = connection.execute(
            "SELECT repository_id FROM investigation_contexts WHERE context_id=?",
            (context_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(f"unknown context: {context_id}")
        return str(row["repository_id"])

    def add_context_evidence(self, context_id: str, observation_id: str) -> None:
        with self._transaction() as connection:
            repository_id = self._context_repository(connection, context_id)
            connection.execute(
                "INSERT OR IGNORE INTO context_evidence"
                "(repository_id, context_id, observation_id) VALUES(?,?,?)",
                (repository_id, context_id, observation_id),
            )

    def add_context_discovery_evidence(
        self, context_id: str, observation_id: str
    ) -> None:
        with self._transaction() as connection:
            repository_id = self._context_repository(connection, context_id)
            connection.execute(
                "INSERT OR IGNORE INTO context_discovery_evidence"
                "(repository_id, context_id, observation_id) VALUES(?,?,?)",
                (repository_id, context_id, observation_id),
            )

    def has_admitted_discovery(self, context_id: str, observation_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM context_discovery_evidence ce"
            " JOIN discovery_observations o"
            " ON o.observation_id = ce.observation_id"
            " AND o.repository_id = ce.repository_id"
            " WHERE ce.context_id=? AND ce.observation_id=?",
            (context_id, observation_id),
        ).fetchone()
        return row is not None

    # -- investigation contexts -------------------------------------------

    def resolve_context(
        self,
        repository_id: str,
        request_id: m.RequestId,
        request_digest: m.ContentDigest,
        factory: _typing.Callable[[], m.InvestigationContext],
    ) -> m.InvestigationContext:
        """Return the context bound to this request, or create exactly one.

        The request binding and creation commit in one write transaction, so
        concurrent first calls cannot issue two contexts for one identity.
        """
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT request_digest, canonical_json"
                " FROM investigation_contexts"
                " WHERE repository_id=? AND request_id=?",
                (repository_id, request_id.value),
            ).fetchone()
            if row is not None:
                if row["request_digest"] != request_digest.value:
                    raise RecordingConflict(
                        "this request identity is already bound to "
                        "different context content"
                    )
                existing = _context_from_json(row["canonical_json"])
                if existing.state is not m.ContextState.LIVE:
                    raise RecordingValidationError(
                        "the bound request context is no longer live; "
                        "start a new request identity"
                    )
                if (
                    existing.expires_at is not None
                    and existing.expires_at < self._clock()
                ):
                    raise RecordingValidationError(
                        "the bound request context has expired; "
                        "start a new request identity"
                    )
                return existing
            context = factory()
            if (
                context.repository_id != repository_id
                or context.request_id != request_id
                or context.request_digest != request_digest
            ):
                raise LifecycleStoreError(
                    "the created context does not match its request binding"
                )
            self._insert_context(connection, context)
            return context

    def put_context(self, context: m.InvestigationContext) -> None:
        with self._transaction() as connection:
            self._insert_context(connection, context)

    def _insert_context(
        self,
        connection: _sqlite3.Connection,
        context: m.InvestigationContext,
    ) -> None:
        connection.execute(
            "INSERT INTO investigation_contexts"
            "(context_id, repository_id, request_id, request_digest,"
            " canonical_json, expires_at) VALUES(?,?,?,?,?,?)",
            (
                context.context_id.value,
                context.repository_id,
                context.request_id.value,
                context.request_digest.value,
                _json.dumps(m.to_canonical(context), sort_keys=True),
                _timestamp(context.expires_at) if context.expires_at else None,
            ),
        )

    def get_context(self, context_id: str) -> m.InvestigationContext:
        return self._get_context_in(self._connection, context_id)

    def _get_context_in(
        self, connection: _sqlite3.Connection, context_id: str
    ) -> m.InvestigationContext:
        row = connection.execute(
            "SELECT canonical_json FROM investigation_contexts WHERE context_id=?",
            (context_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(f"unknown context: {context_id}")
        return _context_from_json(row["canonical_json"])

    def find_context_by_id(self, context_id: str) -> m.InvestigationContext | None:
        row = self._connection.execute(
            "SELECT canonical_json FROM investigation_contexts WHERE context_id=?",
            (context_id,),
        ).fetchone()
        return None if row is None else _context_from_json(row["canonical_json"])

    def find_context(
        self, repository_id: str, request_id: str
    ) -> m.InvestigationContext | None:
        row = self._connection.execute(
            "SELECT canonical_json FROM investigation_contexts"
            " WHERE repository_id=? AND request_id=?",
            (repository_id, request_id),
        ).fetchone()
        return None if row is None else _context_from_json(row["canonical_json"])

    def abandon_context(self, context_id: str) -> bool:
        """Discard one context's operational payload and membership.

        Accepted understanding, challenge, verification and receipt state does
        not depend on the context row and survives. Returns whether a live row
        was removed.
        """
        with self._transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM investigation_contexts WHERE context_id=?",
                (context_id,),
            )
            return cursor.rowcount > 0

    # -- receipts ----------------------------------------------------------

    def get_receipt(self, identity: m.RecordingIdentity) -> m.RecordReceipt | None:
        return self._get_receipt_in(self._connection, identity, self._clock())

    def _get_receipt_in(
        self,
        connection: _sqlite3.Connection,
        identity: m.RecordingIdentity,
        now: _datetime.datetime,
    ) -> m.RecordReceipt | None:
        row = connection.execute(
            "SELECT canonical_json, replay_expires_at FROM record_receipts"
            " WHERE repository_id=? AND context_id=? AND submission_id=?",
            (
                identity.repository_id,
                identity.context_id.value,
                identity.submission_id.value,
            ),
        ).fetchone()
        if row is None:
            return None
        expiry = row["replay_expires_at"]
        if expiry is not None and _datetime.datetime.fromisoformat(expiry) < now:
            return None
        return m.from_canonical(m.RecordReceipt, _json.loads(row["canonical_json"]))

    # -- understanding recording ------------------------------------------

    def record_understanding(
        self,
        command: m.CreateUnderstandingCommand | m.UpdateUnderstandingCommand,
        *,
        understanding_id: m.UnderstandingId | None = None,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        digest = content_digest or record_content_digest(command)
        if isinstance(command, m.CreateUnderstandingCommand):
            if understanding_id is None:
                raise LifecycleStoreError(
                    "a create recording requires an understanding identity"
                )
            selected = understanding_id
        else:
            if (
                understanding_id is not None
                and understanding_id != command.understanding_id
            ):
                raise LifecycleStoreError(
                    "the update understanding identity does not match the command"
                )
            selected = command.understanding_id
        with self._transaction() as connection:
            now = self._clock()
            existing = self._get_receipt_in(connection, command.identity, now)
            decision = receipt_decision(existing, command.identity, digest)
            if decision.kind is m.ReceiptDecisionKind.REPLAY:
                if decision.receipt is None:
                    raise LifecycleStoreError("a replay decision carried no receipt")
                return decision.receipt
            if decision.kind is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    decision.reason
                    or "this submission identity already committed different content"
                )
            context = self._get_context_in(
                connection, command.identity.context_id.value
            )
            self._require_live_context(context, now, command.identity.repository_id)
            if isinstance(command, m.CreateUnderstandingCommand):
                transition = create_understanding(selected, command, context, now)
            else:
                understanding = self._get_understanding_in(connection, selected.value)
                version = self._get_version_in(
                    connection,
                    selected.value,
                    understanding.current_version.value,
                )
                conclusions = self._get_conclusions_in(connection, selected.value)
                transition = apply_update(
                    understanding,
                    version,
                    conclusions,
                    command,
                    context,
                    now,
                    existing_challenges=self._get_challenges_in(
                        connection, selected.value
                    ),
                )
            self._write_transition(connection, transition)
            self._write_challenge_effects(connection, transition.challenge_effects)
            receipt = build_receipt(
                command.identity,
                digest,
                now,
                understanding=(selected, transition.new_version.version),
                replay_expires_at=now + self.retention.replay_retention,
            )
            self._write_receipt(connection, receipt)
            return receipt

    def record_verification(
        self,
        command: m.RecordVerificationCommand,
        *,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        digest = content_digest or record_content_digest(command)
        with self._transaction() as connection:
            now = self._clock()
            existing = self._get_receipt_in(connection, command.identity, now)
            decision = receipt_decision(existing, command.identity, digest)
            if decision.kind is m.ReceiptDecisionKind.REPLAY:
                if decision.receipt is None:
                    raise LifecycleStoreError("a replay decision carried no receipt")
                return decision.receipt
            if decision.kind is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    decision.reason
                    or "this submission identity already committed different content"
                )
            context = self._get_context_in(
                connection, command.identity.context_id.value
            )
            self._require_live_context(context, now, command.identity.repository_id)
            if command.run.repository_id != command.identity.repository_id:
                raise RecordingValidationError(
                    "a verification run belongs to another repository"
                )
            run = m.VerificationRun(
                run_id=m.VerificationRunId(
                    f"run:{command.identity.context_id.value}:"
                    f"{command.identity.submission_id.value}"
                ),
                repository_id=command.run.repository_id,
                scope=command.run.scope,
                observations=command.run.observations,
                command=command.run.command,
                scenario=command.run.scenario,
                outcome=command.run.outcome,
                observed_at=command.run.observed_at,
                observer=command.run.observer,
                environment_limitations=command.run.environment_limitations,
                provenance=command.run.provenance,
            )
            connection.execute(
                "INSERT INTO verification_runs"
                "(run_id, repository_id, canonical_json) VALUES(?,?,?)",
                (
                    run.run_id.value,
                    run.repository_id,
                    _json.dumps(m.to_canonical(run), sort_keys=True),
                ),
            )
            for observation in run.observations:
                connection.execute(
                    "INSERT INTO verification_observations"
                    "(repository_id, run_id, observation_id) VALUES(?,?,?)",
                    (run.repository_id, run.run_id.value, observation.value),
                )
            receipt = build_receipt(
                command.identity,
                digest,
                now,
                verification_run_id=run.run_id,
                replay_expires_at=now + self.retention.replay_retention,
            )
            self._write_receipt(connection, receipt)
            return receipt

    def _require_live_context(
        self,
        context: m.InvestigationContext,
        now: _datetime.datetime,
        repository_id: str,
    ) -> None:
        if context.state is not m.ContextState.LIVE:
            raise RecordingValidationError("the investigation context is not live")
        if context.repository_id != repository_id:
            raise RecordingValidationError("the context belongs to another repository")
        if context.expires_at is not None and context.expires_at < now:
            raise RecordingValidationError("the investigation context has expired")

    # -- reads -------------------------------------------------------------

    def list_understandings(
        self,
        repository_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[m.Understanding, ...]:
        statement = (
            "SELECT canonical_json FROM understandings"
            " WHERE repository_id=? ORDER BY understanding_id"
        )
        parameters: list[object] = [repository_id]
        if limit is not None:
            statement += " LIMIT ? OFFSET ?"
            parameters.extend((limit, offset))
        rows = self._connection.execute(statement, tuple(parameters)).fetchall()
        return tuple(
            m.from_canonical(m.Understanding, _json.loads(row["canonical_json"]))
            for row in rows
        )

    def get_understanding(self, understanding_id: str) -> m.Understanding:
        return self._get_understanding_in(self._connection, understanding_id)

    def _get_understanding_in(
        self, connection: _sqlite3.Connection, understanding_id: str
    ) -> m.Understanding:
        row = connection.execute(
            "SELECT canonical_json FROM understandings WHERE understanding_id=?",
            (understanding_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(f"unknown understanding: {understanding_id}")
        return m.from_canonical(m.Understanding, _json.loads(row["canonical_json"]))

    def get_version(
        self, understanding_id: str, version: int
    ) -> m.UnderstandingVersion:
        return self._get_version_in(self._connection, understanding_id, version)

    def _get_version_in(
        self,
        connection: _sqlite3.Connection,
        understanding_id: str,
        version: int,
    ) -> m.UnderstandingVersion:
        row = connection.execute(
            "SELECT canonical_json FROM understanding_versions"
            " WHERE understanding_id=? AND version=?",
            (understanding_id, version),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(
                f"unknown understanding version: {understanding_id}@{version}"
            )
        return m.from_canonical(
            m.UnderstandingVersion, _json.loads(row["canonical_json"])
        )

    def get_conclusions(
        self, understanding_id: str
    ) -> tuple[m.ConclusionRevision, ...]:
        return self._get_conclusions_in(self._connection, understanding_id)

    def _get_conclusions_in(
        self, connection: _sqlite3.Connection, understanding_id: str
    ) -> tuple[m.ConclusionRevision, ...]:
        rows = connection.execute(
            "SELECT canonical_json FROM conclusions"
            " WHERE understanding_id=? ORDER BY conclusion_id, revision",
            (understanding_id,),
        ).fetchall()
        return tuple(
            m.from_canonical(m.ConclusionRevision, _json.loads(row["canonical_json"]))
            for row in rows
        )

    def get_version_conclusions(
        self, understanding_id: str, version: int
    ) -> tuple[m.ConclusionRevision, ...]:
        """Return only the conclusion revisions in one exact version."""
        rows = self._connection.execute(
            "SELECT c.canonical_json FROM understanding_membership m"
            " JOIN conclusions c"
            " ON c.understanding_id = m.understanding_id"
            " AND c.conclusion_id = m.conclusion_id"
            " AND c.revision = m.revision"
            " WHERE m.understanding_id=? AND m.version=?"
            " ORDER BY m.conclusion_id",
            (understanding_id, version),
        ).fetchall()
        return tuple(
            m.from_canonical(m.ConclusionRevision, _json.loads(row["canonical_json"]))
            for row in rows
        )

    def has_conclusion_revision(
        self, understanding_id: str, conclusion_id: str, revision: int
    ) -> bool:
        return self._has_conclusion_revision_in(
            self._connection, understanding_id, conclusion_id, revision
        )

    def _has_conclusion_revision_in(
        self,
        connection: _sqlite3.Connection,
        understanding_id: str,
        conclusion_id: str,
        revision: int,
    ) -> bool:
        row = connection.execute(
            "SELECT 1 FROM conclusions"
            " WHERE understanding_id=? AND conclusion_id=? AND revision=?",
            (understanding_id, conclusion_id, revision),
        ).fetchone()
        return row is not None

    def support_dependents(
        self, dependency_kind: str, dependency_ref: str
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        """Return exact revisions whose support references one identity."""
        rows = self._connection.execute(
            "SELECT understanding_id, conclusion_id, revision"
            " FROM support_dependencies"
            " WHERE dependency_kind=? AND dependency_ref=?"
            " ORDER BY understanding_id, conclusion_id, revision",
            (dependency_kind, dependency_ref),
        ).fetchall()
        return tuple(
            m.ConclusionRevisionRef(
                understanding_id=m.UnderstandingId(row["understanding_id"]),
                conclusion_id=m.ConclusionId(row["conclusion_id"]),
                revision=m.ConclusionRevisionNumber(row["revision"]),
            )
            for row in rows
        )

    # -- challenges --------------------------------------------------------

    def list_context_discovery(
        self, context_id: str
    ) -> tuple[m.DiscoveryObservation, ...]:
        rows = self._connection.execute(
            "SELECT o.canonical_json FROM context_discovery_evidence ce"
            " JOIN discovery_observations o"
            " ON o.observation_id = ce.observation_id"
            " AND o.repository_id = ce.repository_id"
            " WHERE ce.context_id=? ORDER BY o.observation_id",
            (context_id,),
        ).fetchall()
        return tuple(
            m.from_canonical(m.DiscoveryObservation, _json.loads(row["canonical_json"]))
            for row in rows
        )

    def create_challenge(self, challenge: m.Challenge) -> None:
        """Persist one explicit dispute at its current revision."""
        with self._transaction() as connection:
            self._validate_challenge_in(connection, challenge)
            if connection.execute(
                "SELECT 1 FROM challenges WHERE challenge_id=?",
                (challenge.challenge_id.value,),
            ).fetchone():
                raise LifecycleStoreError(
                    f"challenge already exists: {challenge.challenge_id.value}"
                )
            self._insert_challenge(connection, challenge)

    def _validate_challenge_in(
        self,
        connection: _sqlite3.Connection,
        challenge: m.Challenge,
    ) -> None:
        understanding = self._get_understanding_in(
            connection, challenge.understanding_id.value
        )
        self._get_version_in(
            connection,
            challenge.understanding_id.value,
            challenge.target_version.value,
        )
        for ref in challenge.target_conclusions:
            if not self._has_conclusion_revision_in(
                connection,
                ref.understanding_id.value,
                ref.conclusion_id.value,
                ref.revision.value,
            ):
                raise RecordingValidationError(
                    "challenge target revision does not exist: "
                    f"{ref.conclusion_id.value}@{ref.revision.value}"
                )
        for evidence_ref in challenge.evidence:
            if evidence_ref.repository_id != understanding.repository_id:
                raise RecordingValidationError(
                    "challenge evidence belongs to another repository"
                )

    def _insert_challenge(
        self,
        connection: _sqlite3.Connection,
        challenge: m.Challenge,
    ) -> None:
        connection.execute(
            "INSERT INTO challenges"
            "(challenge_id, understanding_id, canonical_json)"
            " VALUES(?,?,?)",
            (
                challenge.challenge_id.value,
                challenge.understanding_id.value,
                _json.dumps(m.to_canonical(challenge), sort_keys=True),
            ),
        )

    def record_challenge(
        self,
        command: m.CreateChallengeCommand,
        *,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        """Accept one challenge create with receipt-first replay."""
        digest = content_digest or record_content_digest(command)
        with self._transaction() as connection:
            now = self._clock()
            existing = self._get_receipt_in(connection, command.identity, now)
            decision = receipt_decision(existing, command.identity, digest)
            if decision.kind is m.ReceiptDecisionKind.REPLAY:
                if decision.receipt is None:
                    raise LifecycleStoreError("a replay decision carried no receipt")
                return decision.receipt
            if decision.kind is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    decision.reason
                    or "this submission identity already committed different content"
                )
            context = self._get_context_in(
                connection, command.identity.context_id.value
            )
            self._require_live_context(context, now, command.identity.repository_id)
            challenge_id = challenge_identity(command.identity)
            challenge = build_challenge(
                challenge_id=challenge_id,
                understanding_id=command.understanding_id,
                target_version=command.target_version,
                target_conclusions=command.target_conclusions,
                reason=command.reason,
                evidence=command.evidence,
                provenance=command.provenance,
                now=now,
            )
            self._validate_challenge_in(connection, challenge)
            self._insert_challenge(connection, challenge)
            receipt = build_receipt(
                command.identity,
                digest,
                now,
                challenge_id=challenge_id,
                replay_expires_at=now + self.retention.replay_retention,
            )
            self._write_receipt(connection, receipt)
            return receipt

    def get_challenge(self, challenge_id: str) -> m.Challenge:
        return self._get_challenge_in(self._connection, challenge_id)

    def _get_challenge_in(
        self, connection: _sqlite3.Connection, challenge_id: str
    ) -> m.Challenge:
        row = connection.execute(
            "SELECT canonical_json FROM challenges WHERE challenge_id=?",
            (challenge_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(f"unknown challenge: {challenge_id}")
        return m.from_canonical(m.Challenge, _json.loads(row["canonical_json"]))

    def get_challenges(self, understanding_id: str) -> tuple[m.Challenge, ...]:
        return self._get_challenges_in(self._connection, understanding_id)

    def _get_challenges_in(
        self, connection: _sqlite3.Connection, understanding_id: str
    ) -> tuple[m.Challenge, ...]:
        rows = connection.execute(
            "SELECT canonical_json FROM challenges"
            " WHERE understanding_id=? ORDER BY challenge_id",
            (understanding_id,),
        ).fetchall()
        return tuple(
            m.from_canonical(m.Challenge, _json.loads(row["canonical_json"]))
            for row in rows
        )

    def get_verification_run(self, run_id: str) -> m.VerificationRun:
        row = self._connection.execute(
            "SELECT canonical_json FROM verification_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise LifecycleStoreError(f"unknown verification run: {run_id}")
        return m.from_canonical(m.VerificationRun, _json.loads(row["canonical_json"]))

    # -- retention ---------------------------------------------------------

    def reap_expired(self, now: _datetime.datetime | None = None) -> int:
        """Remove expired operational context and replay state only."""
        moment = now or self._clock()
        with self._transaction() as connection:
            contexts = connection.execute(
                "DELETE FROM investigation_contexts"
                " WHERE expires_at IS NOT NULL AND expires_at < ?",
                (_timestamp(moment),),
            )
            receipts = connection.execute(
                "DELETE FROM record_receipts"
                " WHERE replay_expires_at IS NOT NULL AND replay_expires_at < ?",
                (_timestamp(moment),),
            )
            return contexts.rowcount + receipts.rowcount

    # -- transactional writers --------------------------------------------

    def _write_transition(
        self,
        connection: _sqlite3.Connection,
        transition: UnderstandingTransition,
    ) -> None:
        understanding = transition.understanding
        version = transition.new_version
        connection.execute(
            "INSERT INTO understandings"
            "(understanding_id, repository_id, question, scope_json,"
            " current_version, canonical_json) VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(understanding_id) DO UPDATE SET"
            " repository_id=excluded.repository_id,"
            " question=excluded.question,"
            " scope_json=excluded.scope_json,"
            " current_version=excluded.current_version,"
            " canonical_json=excluded.canonical_json",
            (
                understanding.understanding_id.value,
                understanding.repository_id,
                understanding.question,
                _json.dumps(m.to_canonical(understanding.scope), sort_keys=True),
                understanding.current_version.value,
                _json.dumps(m.to_canonical(understanding), sort_keys=True),
            ),
        )
        connection.execute(
            "INSERT INTO understanding_versions"
            "(understanding_id, version, canonical_json) VALUES(?,?,?)",
            (
                version.understanding_id.value,
                version.version.value,
                _json.dumps(m.to_canonical(version), sort_keys=True),
            ),
        )
        for revision in transition.new_conclusions:
            connection.execute(
                "INSERT INTO conclusions"
                "(understanding_id, conclusion_id, revision, canonical_json)"
                " VALUES(?,?,?,?)",
                (
                    revision.understanding_id.value,
                    revision.conclusion_id.value,
                    revision.revision.value,
                    _json.dumps(m.to_canonical(revision), sort_keys=True),
                ),
            )
            for dependency_kind, dependency_ref in _support_rows(revision):
                connection.execute(
                    "INSERT INTO support_dependencies"
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

    def _write_challenge_effects(
        self,
        connection: _sqlite3.Connection,
        effects: tuple[ChallengeEffect, ...],
    ) -> None:
        for effect in effects:
            challenge = self._get_challenge_in(connection, effect.challenge_id.value)
            updated = _dataclasses.replace(
                challenge,
                challenge_revision=effect.new_revision,
                state=effect.state,
                resolution=effect.resolution,
                dispositions=challenge.dispositions + (effect.disposition,),
            )
            connection.execute(
                "UPDATE challenges SET canonical_json=? WHERE challenge_id=?",
                (
                    _json.dumps(m.to_canonical(updated), sort_keys=True),
                    updated.challenge_id.value,
                ),
            )

    def _write_receipt(
        self, connection: _sqlite3.Connection, receipt: m.RecordReceipt
    ) -> None:
        connection.execute(
            "INSERT INTO record_receipts"
            "(repository_id, context_id, submission_id, content_digest,"
            " canonical_json, replay_expires_at) VALUES(?,?,?,?,?,?)",
            (
                receipt.identity.repository_id,
                receipt.identity.context_id.value,
                receipt.identity.submission_id.value,
                receipt.content_digest.value,
                _json.dumps(m.to_canonical(receipt), sort_keys=True),
                (
                    _timestamp(receipt.replay_expires_at)
                    if receipt.replay_expires_at
                    else None
                ),
            ),
        )


def _ranges_json(ranges: tuple[m.SourceRange, ...]) -> str:
    return _json.dumps([m.to_canonical(item) for item in ranges], sort_keys=True)


def _observation_from_row(row: _sqlite3.Row) -> SourceObservationRecord:
    ranges = tuple(
        m.from_canonical(m.SourceRange, item)
        for item in _json.loads(row["delivered_ranges_json"])
    )
    return SourceObservationRecord(
        observation_id=m.SourceObservationId(row["observation_id"]),
        repository_id=row["repository_id"],
        evidence=m.from_canonical(m.EvidenceRef, _json.loads(row["canonical_json"])),
        content_digest=m.ContentDigest(row["content_digest"]),
        captured_at=_datetime.datetime.fromisoformat(row["captured_at"]),
        total_lines=int(row["total_lines"]),
        delivered_ranges=ranges,
        whole_file=bool(row["whole_file"]),
        excerpt=row["excerpt"],
    )


def _context_from_json(payload: str) -> m.InvestigationContext:
    return m.from_canonical(m.InvestigationContext, _json.loads(payload))


def _support_rows(
    revision: m.ConclusionRevision,
) -> tuple[tuple[str, str], ...]:
    """Project one revision's typed support into its reverse-index rows."""
    rows: list[tuple[str, str]] = []
    for dependency in revision.content.support:
        if isinstance(dependency, m.SourceSupport):
            rows.append(("SOURCE", dependency.observation_id.value))
            continue
        if isinstance(dependency, m.DiscoverySupport):
            rows.append(("DISCOVERY", dependency.observation_id.value))
            continue
        if isinstance(dependency, m.PremiseSupport):
            premise = dependency.premise
            rows.append(
                (
                    "PREMISE",
                    f"{premise.understanding_id.value}/"
                    f"{premise.conclusion_id.value}@"
                    f"{premise.revision.value}",
                )
            )
            continue
        if isinstance(dependency, m.AuthoritySupportDependency):
            rows.append(
                ("AUTHORITY", dependency.authority.evidence_ref.evidence_id.value)
            )
            continue
        raise TypeError(f"unhandled support dependency: {type(dependency).__name__}")
    return tuple(rows)
