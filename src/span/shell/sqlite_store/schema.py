"""Schema-15 lifecycle SQLite definition and open-time validation."""

from __future__ import annotations

import sqlite3 as _sqlite3
import typing as _typing

SCHEMA_VERSION = 16


def validate_schema(
    connection: _sqlite3.Connection,
    *,
    allow_empty: bool,
    error_factory: _typing.Callable[[str], Exception],
) -> None:
    """Validate one existing lifecycle database without mutating it."""
    tables = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if "meta" not in tables and (tables or not allow_empty):
        raise error_factory(
            "existing store has no schema version marker; refusing to open"
        )
    if "meta" not in tables:
        return
    row = connection.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()
    if row is None:
        raise error_factory("existing store has no schema version; refusing to open")
    if int(row["value"]) != SCHEMA_VERSION:
        raise error_factory(
            f"unsupported lifecycle store schema {row['value']}; "
            f"expected {SCHEMA_VERSION}"
        )


DDL = (
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
    CREATE TABLE IF NOT EXISTS surfaces(
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        kind TEXT NOT NULL,
        locator TEXT NOT NULL,
        parent_kind TEXT,
        parent_locator TEXT,
        boundary_version INTEGER NOT NULL,
        canonical_json TEXT NOT NULL,
        PRIMARY KEY(repository_id, kind, locator),
        UNIQUE(repository_id, locator)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS surface_boundary_versions(
        repository_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        locator TEXT NOT NULL,
        boundary_version INTEGER NOT NULL,
        boundary_digest TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        PRIMARY KEY(repository_id, kind, locator, boundary_version),
        FOREIGN KEY(repository_id, kind, locator)
            REFERENCES surfaces(repository_id, kind, locator)
            ON DELETE CASCADE
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
        binding_digest TEXT NOT NULL,
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
        surface_kind TEXT NOT NULL,
        surface_locator TEXT NOT NULL,
        question TEXT NOT NULL,
        scope_json TEXT NOT NULL,
        current_version INTEGER NOT NULL,
        canonical_json TEXT NOT NULL,
        UNIQUE(repository_id, surface_kind, surface_locator, question)
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
    CREATE TABLE IF NOT EXISTS conclusion_curations(
        understanding_id TEXT NOT NULL,
        conclusion_id TEXT NOT NULL,
        revision INTEGER NOT NULL,
        accepted_in_version INTEGER NOT NULL,
        origin TEXT NOT NULL
            CHECK(origin IN ('EXPLICIT', 'INHERITED_CONFIRMATION')),
        inherited_from_revision INTEGER,
        canonical_json TEXT NOT NULL,
        PRIMARY KEY(understanding_id, conclusion_id, revision),
        FOREIGN KEY(understanding_id, conclusion_id, revision)
            REFERENCES conclusions(understanding_id, conclusion_id, revision),
        FOREIGN KEY(understanding_id, accepted_in_version)
            REFERENCES understanding_versions(understanding_id, version),
        FOREIGN KEY(understanding_id, conclusion_id, inherited_from_revision)
            REFERENCES conclusions(understanding_id, conclusion_id, revision),
        CHECK(
            (origin='EXPLICIT' AND inherited_from_revision IS NULL)
            OR
            (origin='INHERITED_CONFIRMATION'
             AND inherited_from_revision IS NOT NULL)
        )
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
        request_id TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        replay_expires_at TEXT,
        PRIMARY KEY(repository_id, request_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS functional_route_dependency_index(
        understanding_id TEXT NOT NULL,
        conclusion_id TEXT NOT NULL,
        revision INTEGER NOT NULL,
        pyramid_id TEXT NOT NULL,
        repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
        route_identity TEXT NOT NULL,
        PRIMARY KEY(
            understanding_id, conclusion_id, revision,
            pyramid_id, repository_id, route_identity
        ),
        FOREIGN KEY(understanding_id, conclusion_id, revision)
            REFERENCES conclusions(understanding_id, conclusion_id, revision)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS functional_route_dependency_route
    ON functional_route_dependency_index(
        route_identity, pyramid_id, repository_id
    )
    """,
)
