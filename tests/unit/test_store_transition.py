"""Offline transition gate (G-6): lossless archive/export and recovery.

Every fixture is created inside a temporary directory. No live Span store is
opened, migrated or reaped by this module.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import pathlib
import sqlite3

import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from span.core import model as m
from span.shell import store_transition as st

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)

LEGACY_DDL = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE repositories(
  repository_id TEXT PRIMARY KEY,
  revision_id TEXT,
  dirty INTEGER NOT NULL,
  state_fingerprint TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  authority_seeds_json TEXT NOT NULL
);
CREATE TABLE subjects(
  repository_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  kind TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, locator, kind)
);
CREATE TABLE claims(
  claim_id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,
  subject_locator TEXT NOT NULL,
  subject_kind TEXT NOT NULL,
  kind TEXT NOT NULL,
  trust TEXT NOT NULL,
  freshness_state TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE TABLE question_coverages(
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
    repository_id, scope_root_locator, scope_root_kind, subject_locator,
    subject_kind, question_class, question_slice
  )
);
CREATE TABLE target_associations(
  repository_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  last_touched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  canonical_json TEXT NOT NULL,
  PRIMARY KEY(repository_id, target_id)
);
CREATE TABLE experimental_notes(
  note_id INTEGER PRIMARY KEY,
  body TEXT,
  payload BLOB,
  score REAL,
  missing TEXT
);
"""


def _seed() -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId("ev-rule"),
        repository_id="demo",
        source_kind=m.EvidenceSourceKind.DOCUMENTATION,
        locator="docs/rule.md",
        revision_or_fingerprint="sha256:rule",
    )


def _legacy_store(
    path: pathlib.Path,
    *,
    version: int = 9,
    seeds: tuple[m.EvidenceRef, ...] = (),
    with_seed_column: bool = True,
) -> pathlib.Path:
    connection = sqlite3.connect(path)
    try:
        if with_seed_column:
            connection.executescript(LEGACY_DDL)
        else:
            connection.executescript(
                LEGACY_DDL.replace(",\n  authority_seeds_json TEXT NOT NULL", "")
            )
        connection.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
            (str(version),),
        )
        if with_seed_column:
            connection.execute(
                "INSERT INTO repositories VALUES(?,?,?,?,?,?)",
                (
                    "demo",
                    "rev-1",
                    0,
                    "fp-1",
                    "2026-10-30T00:00:00+00:00",
                    json.dumps(
                        [m.to_canonical(item) for item in seeds], sort_keys=True
                    ),
                ),
            )
        else:
            connection.execute(
                "INSERT INTO repositories VALUES(?,?,?,?,?)",
                (
                    "demo",
                    "rev-1",
                    0,
                    "fp-1",
                    "2026-10-30T00:00:00+00:00",
                ),
            )
        connection.execute(
            "INSERT INTO subjects VALUES(?,?,?,?)",
            ("demo", "src/app.py", "COMPONENT", '{"subject":"src/app.py"}'),
        )
        connection.execute(
            "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
            (
                "claim-1",
                "demo",
                "src/app.py",
                "COMPONENT",
                "PURPOSE",
                "ACCEPTED",
                "CURRENT",
                '{"statement":"The app has an entry point."}',
            ),
        )
        connection.execute(
            "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
            (
                "claim-orphan",
                "demo",
                "",
                "",
                "RESPONSIBILITY",
                "ACCEPTED",
                "CURRENT",
                '{"statement":"Unassociated legacy fact."}',
            ),
        )
        connection.execute(
            "INSERT INTO question_coverages VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "demo",
                "src",
                "COMPONENT",
                "src/app.py",
                "COMPONENT",
                "PURPOSE",
                "slice",
                "ANSWERED",
                "2026-10-30T00:00:00+00:00",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO target_associations VALUES(?,?,?,?,?)",
            (
                "demo",
                "tgt-1",
                "2026-10-30T00:00:00+00:00",
                "2027-01-01T00:00:00+00:00",
                '{"progress":"partial"}',
            ),
        )
        connection.execute(
            "INSERT INTO experimental_notes VALUES(?,?,?,?,?)",
            (1, "text", b"\x00\x01\xfe\xff", float("inf"), None),
        )
        connection.execute(
            "INSERT INTO experimental_notes VALUES(?,?,?,?,?)",
            (2, None, None, 1.5, "present"),
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _schema11_store(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    """Build one schema-11-shaped store with a stored excerpt."""
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    root.mkdir(parents=True, exist_ok=True)
    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    store.register_repository("demo", str(root))
    store.put_source_observation(
        m.SourceObservation(
            observation_id=m.SourceObservationId("obs-a"),
            repository_id="demo",
            evidence=m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-a"),
                repository_id="demo",
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint="sha256:a",
            ),
            content_digest=m.ContentDigest("sha256:a"),
            captured_at=NOW,
            total_lines=1,
            whole_file=True,
        )
    )
    store.close()
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "ALTER TABLE source_observations ADD COLUMN excerpt TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "UPDATE source_observations SET excerpt='a\n' WHERE observation_id='obs-a'"
        )
        connection.execute("UPDATE meta SET value='11' WHERE key='schema_version'")
        connection.commit()
    finally:
        connection.close()
    return path


def _schema10_store(
    path: pathlib.Path, root: pathlib.Path, *, unresolved: bool = False
) -> pathlib.Path:
    """Build one real current-schema store, then present its schema-10 shape."""
    from span.core.recording import create_challenge
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    path.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "src/a.py").write_text("a\n", encoding="utf-8")
    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    store.register_repository("demo", str(root))
    store.put_source_observation(
        m.SourceObservation(
            observation_id=m.SourceObservationId("obs-a"),
            repository_id="demo",
            evidence=m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-a"),
                repository_id="demo",
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint="sha256:a",
            ),
            content_digest=m.ContentDigest("sha256:a"),
            captured_at=NOW,
            total_lines=1,
            whole_file=True,
        )
    )
    for context_id, request_id in (("ctx-1", "req-1"), ("ctx-2", "req-2")):
        store.put_context(
            m.InvestigationContext(
                context_id=m.InvestigationContextId(context_id),
                repository_id="demo",
                request_id=m.RequestId(request_id),
                binding_digest=m.ContentDigest(f"sha256:{request_id}"),
                origin=m.ContextOrigin.QUESTION,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(paths=("src/a.py",)),
                created_at=NOW,
                expires_at=NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime,
                question="What does A do?",
            )
        )
    basis = m.SemanticBasis(
        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
        summary="read",
        input_refs=(),
    )
    store.record_understanding(
        m.CreateUnderstandingCommand(
            identity=m.RecordingIdentity(
                repository_id="demo",
                request_id=m.RequestId("req-1"),
                context_id=m.InvestigationContextId("ctx-1"),
            ),
            surface=m.SurfaceKey(
                repository_id="demo",
                kind=m.SurfaceKind.FILE,
                locator="src/a.py",
            ),
            target=m.ContextBoundTarget(),
            conclusions=(
                m.ProposedConclusion(
                    conclusion_id=m.ConclusionId("c-1"),
                    statement="A is present.",
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                    support=(
                        m.SourceSupport(observation_id=m.SourceObservationId("obs-a")),
                    ),
                    basis=basis,
                ),
            ),
            gaps=(m.GapDraft(question="Is A complete?", basis="not checked"),),
        ),
        understanding_id=m.UnderstandingId("u-1"),
    )
    store.create_challenge(
        create_challenge(
            challenge_id=m.ChallengeId("ch-1"),
            understanding_id=m.UnderstandingId("u-1"),
            target_version=m.UnderstandingVersionNumber(1),
            target_conclusions=(
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId("u-1"),
                    conclusion_id=m.ConclusionId("c-1"),
                    revision=m.ConclusionRevisionNumber(1),
                ),
            ),
            reason="disputed",
            evidence=(),
            provenance="fixture",
            now=NOW,
        )
    )
    store.record_verification(
        m.RecordVerificationCommand(
            identity=m.RecordingIdentity(
                repository_id="demo",
                request_id=m.RequestId("req-2"),
                context_id=m.InvestigationContextId("ctx-2"),
            ),
            run=m.ProposedVerificationRun(
                repository_id="demo",
                scope=m.VerificationScope(
                    description="app",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                observations=(m.SourceObservationId("obs-a"),),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="fixture",
            ),
        )
    )
    if unresolved:
        store.put_context(
            m.InvestigationContext(
                context_id=m.InvestigationContextId("ctx-3"),
                repository_id="demo",
                request_id=m.RequestId("req-3"),
                binding_digest=m.ContentDigest("sha256:req-3"),
                origin=m.ContextOrigin.QUESTION,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(paths=("src/a.py", "src/b.py")),
                created_at=NOW,
                expires_at=NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime,
                question="Which file owns this?",
            )
        )
        store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="demo",
                    request_id=m.RequestId("req-3"),
                    context_id=m.InvestigationContextId("ctx-3"),
                ),
                surface=m.SurfaceKey(
                    repository_id="demo",
                    kind=m.SurfaceKind.FILE,
                    locator="src/a.py",
                ),
                target=m.ContextBoundTarget(),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-wide"),
                        statement="Two files participate.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(paths=("src/a.py", "src/b.py")),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId("obs-a")
                            ),
                        ),
                        basis=basis,
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-wide"),
        )
    store.close()

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "ALTER TABLE source_observations ADD COLUMN excerpt TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "UPDATE source_observations SET excerpt='a\n' WHERE observation_id='obs-a'"
        )
        connection.execute("UPDATE meta SET value='10' WHERE key='schema_version'")
        connection.execute("DROP TABLE surfaces")
        connection.execute("DROP TABLE surface_boundary_versions")
        connection.execute(
            "CREATE TABLE understandings_old("
            "understanding_id TEXT PRIMARY KEY, repository_id TEXT NOT NULL,"
            " question TEXT NOT NULL, scope_json TEXT NOT NULL,"
            " current_version INTEGER NOT NULL, canonical_json TEXT NOT NULL)"
        )
        for row in connection.execute(
            "SELECT understanding_id, repository_id, question, scope_json,"
            " current_version, canonical_json FROM understandings"
        ).fetchall():
            payload = json.loads(row[5])
            payload.pop("surface", None)
            connection.execute(
                "INSERT INTO understandings_old VALUES(?,?,?,?,?,?)",
                (*row[:5], json.dumps(payload, sort_keys=True)),
            )
        connection.execute("DROP TABLE understandings")
        connection.execute("ALTER TABLE understandings_old RENAME TO understandings")
        rows = connection.execute(
            "SELECT understanding_id, version, canonical_json"
            " FROM understanding_versions"
        ).fetchall()
        for understanding_id, version, canonical in rows:
            payload = json.loads(canonical)
            payload.pop("surface_boundary_version", None)
            for gap in payload.get("gaps", []):
                gap["$type"] = "Gap"
            connection.execute(
                "UPDATE understanding_versions SET canonical_json=?"
                " WHERE understanding_id=? AND version=?",
                (json.dumps(payload, sort_keys=True), understanding_id, version),
            )
        receipts = connection.execute(
            "SELECT repository_id, canonical_json, replay_expires_at"
            " FROM record_receipts"
        ).fetchall()
        connection.execute("DROP TABLE record_receipts")
        connection.execute(
            "CREATE TABLE record_receipts("
            "repository_id TEXT NOT NULL, context_id TEXT NOT NULL,"
            " submission_id TEXT NOT NULL, content_digest TEXT NOT NULL,"
            " canonical_json TEXT NOT NULL, replay_expires_at TEXT,"
            " PRIMARY KEY(repository_id, context_id, submission_id))"
        )
        for repository_id, canonical, expires in receipts:
            payload = json.loads(canonical)
            context_id = payload["identity"]["context_id"]["value"]
            submission = payload["identity"]["request_id"]["value"]
            payload["identity"] = {
                "$type": "RecordingIdentity",
                "repository_id": repository_id,
                "context_id": {"$type": "InvestigationContextId", "value": context_id},
                "submission_id": {"$type": "SubmissionId", "value": submission},
            }
            connection.execute(
                "INSERT INTO record_receipts VALUES(?,?,?,?,?,?)",
                (
                    repository_id,
                    context_id,
                    submission,
                    payload["content_digest"]["value"],
                    json.dumps(payload, sort_keys=True),
                    expires,
                ),
            )
        connection.commit()
    finally:
        connection.close()
    return path


def _schema12_store(
    path: pathlib.Path,
    root: pathlib.Path,
    *,
    live_context: bool,
) -> pathlib.Path:
    """Build schema-13 durable state, then rewrite only the context shape to 12."""
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    path.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "src/a.py").write_text("a\n", encoding="utf-8")
    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    store.register_repository("demo", str(root))
    observation = m.SourceObservation(
        observation_id=m.SourceObservationId("obs-schema12"),
        repository_id="demo",
        evidence=m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-schema12"),
            repository_id="demo",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/a.py",
            revision_or_fingerprint="sha256:a",
        ),
        content_digest=m.ContentDigest("sha256:a"),
        captured_at=NOW,
        total_lines=1,
        whole_file=True,
    )
    store.put_source_observation(observation)
    created_at = NOW
    expires_at = NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime
    context = m.InvestigationContext(
        context_id=m.InvestigationContextId("ctx-schema12"),
        repository_id="demo",
        request_id=m.RequestId("req-schema12"),
        binding_digest=m.ContentDigest("sha256:legacy-wire"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(paths=("src/a.py",)),
        created_at=created_at,
        expires_at=expires_at,
    )
    store.put_context(context)
    store.add_context_evidence("ctx-schema12", "obs-schema12")
    receipt = store.record_verification(
        m.RecordVerificationCommand(
            identity=m.RecordingIdentity(
                repository_id="demo",
                request_id=m.RequestId("req-schema12"),
                context_id=m.InvestigationContextId("ctx-schema12"),
            ),
            run=m.ProposedVerificationRun(
                repository_id="demo",
                scope=m.VerificationScope(
                    description="schema12 fixture",
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                ),
                observations=(m.SourceObservationId("obs-schema12"),),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="fixture",
            ),
        )
    )
    assert receipt.accepted_verification_run_ids
    store.close()

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "ALTER TABLE investigation_contexts"
            " RENAME COLUMN binding_digest TO request_digest"
        )
        rows = connection.execute(
            "SELECT context_id, canonical_json FROM investigation_contexts"
        ).fetchall()
        for context_id, canonical in rows:
            payload = json.loads(canonical)
            payload["request_digest"] = payload.pop("binding_digest")
            persisted_expiry = payload.get("expires_at")
            if not live_context:
                payload["created_at"] = (NOW - datetime.timedelta(days=2)).isoformat()
                payload["expires_at"] = (NOW - datetime.timedelta(days=1)).isoformat()
                persisted_expiry = payload["expires_at"]
            connection.execute(
                "UPDATE investigation_contexts SET canonical_json=?, expires_at=?"
                " WHERE context_id=?",
                (json.dumps(payload, sort_keys=True), persisted_expiry, context_id),
            )
        connection.execute("UPDATE meta SET value='12' WHERE key='schema_version'")
        connection.commit()
    finally:
        connection.close()
    return path


def _schema13_store(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    """Build current state, then remove Version-1 projections to reproduce 13."""
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    path.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "src/a.py").write_text("a\n", encoding="utf-8")

    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    store.register_repository("demo", str(root))
    store.put_source_observation(
        m.SourceObservation(
            observation_id=m.SourceObservationId("obs-schema13"),
            repository_id="demo",
            evidence=m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-schema13"),
                repository_id="demo",
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint="sha256:a",
            ),
            content_digest=m.ContentDigest("sha256:a"),
            captured_at=NOW,
            total_lines=1,
            whole_file=True,
        )
    )
    context = m.InvestigationContext(
        context_id=m.InvestigationContextId("ctx-schema13"),
        repository_id="demo",
        request_id=m.RequestId("req-schema13"),
        binding_digest=m.ContentDigest("sha256:schema13"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(paths=("src/a.py",)),
        created_at=NOW,
        expires_at=NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime,
    )
    store.put_context(context)
    store.add_context_evidence("ctx-schema13", "obs-schema13")
    store.record_understanding(
        m.CreateUnderstandingCommand(
            identity=m.RecordingIdentity(
                repository_id="demo",
                request_id=m.RequestId("record-schema13"),
                context_id=m.InvestigationContextId("ctx-schema13"),
            ),
            surface=m.SurfaceKey(
                repository_id="demo",
                kind=m.SurfaceKind.FILE,
                locator="src/a.py",
            ),
            target=m.ExplicitTarget(
                question="What governs A?",
                scope=m.EvidenceScope(paths=("src/a.py",)),
            ),
            conclusions=(
                m.ProposedConclusion(
                    conclusion_id=m.ConclusionId("c-pre-route"),
                    statement="A was normatively assessed before route support existed.",
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                    support=(
                        m.SourceSupport(
                            observation_id=m.SourceObservationId("obs-schema13")
                        ),
                    ),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                        summary="pre-route schema13 fixture",
                        input_refs=(),
                    ),
                ),
            ),
        ),
        understanding_id=m.UnderstandingId("u-schema13"),
    )
    store.close()

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE conclusion_curations")
        connection.execute("DROP TABLE functional_route_dependency_index")
        connection.execute("UPDATE meta SET value='13' WHERE key='schema_version'")
        connection.commit()
    finally:
        connection.close()
    return path


def _schema14_store(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    """Build schema-15 state, then remove only curation storage to reproduce 14."""
    from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
    from span.shell.sqlite_store.lifecycle import LifecycleStore

    path.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    source_path = root / "src/a.py"
    source_path.write_text("a\n", encoding="utf-8")
    source_fingerprint = hashlib.sha256(source_path.read_bytes()).hexdigest()

    store = LifecycleStore(
        path, retention=DEFAULT_LIFECYCLE_RETENTION, clock=lambda: NOW
    )
    store.register_repository("demo", str(root), authority_seeds=(_seed(),))
    store.put_source_observation(
        m.SourceObservation(
            observation_id=m.SourceObservationId("obs-schema14"),
            repository_id="demo",
            evidence=m.EvidenceRef(
                evidence_id=m.EvidenceId("ev-schema14"),
                repository_id="demo",
                source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                locator="src/a.py",
                revision_or_fingerprint=source_fingerprint,
            ),
            content_digest=m.ContentDigest(f"sha256:{source_fingerprint}"),
            captured_at=NOW,
            total_lines=1,
            whole_file=True,
        )
    )
    context = m.InvestigationContext(
        context_id=m.InvestigationContextId("ctx-schema14"),
        repository_id="demo",
        request_id=m.RequestId("req-schema14"),
        binding_digest=m.ContentDigest("sha256:schema14"),
        origin=m.ContextOrigin.EVIDENCE_ONLY,
        state=m.ContextState.LIVE,
        scope=m.EvidenceScope(paths=("src/a.py",)),
        created_at=NOW,
        expires_at=NOW + DEFAULT_LIFECYCLE_RETENTION.context_lifetime,
    )
    store.put_context(context)
    store.add_context_evidence("ctx-schema14", "obs-schema14")
    store.record_understanding(
        m.CreateUnderstandingCommand(
            identity=m.RecordingIdentity(
                repository_id="demo",
                request_id=m.RequestId("record-schema14"),
                context_id=m.InvestigationContextId("ctx-schema14"),
            ),
            surface=m.SurfaceKey(
                repository_id="demo",
                kind=m.SurfaceKind.FILE,
                locator="src/a.py",
            ),
            target=m.ExplicitTarget(
                question="What does A do?",
                scope=m.EvidenceScope(paths=("src/a.py",)),
            ),
            conclusions=(
                m.ProposedConclusion(
                    conclusion_id=m.ConclusionId("c-schema14"),
                    statement="A has retained schema-14 meaning.",
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    scope=m.EvidenceScope(paths=("src/a.py",)),
                    support=(
                        m.SourceSupport(
                            observation_id=m.SourceObservationId("obs-schema14")
                        ),
                    ),
                    basis=m.SemanticBasis(
                        derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                        summary="schema14 preservation fixture",
                    ),
                ),
            ),
        ),
        understanding_id=m.UnderstandingId("u-schema14"),
    )
    store.close()

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO functional_route_dependency_index"
            "(understanding_id, conclusion_id, revision, pyramid_id,"
            " repository_id, route_identity) VALUES(?,?,?,?,?,?)",
            ("u-schema14", "c-schema14", 1, "p-1", "demo", "route-1"),
        )
        connection.execute("DROP TABLE conclusion_curations")
        connection.execute("UPDATE meta SET value='14' WHERE key='schema_version'")
        connection.commit()
    finally:
        connection.close()
    return path


def _config(
    root: pathlib.Path,
    data: pathlib.Path,
    *,
    free_bytes=None,
) -> st.TransitionConfig:
    kwargs = {"clock": lambda: NOW}
    if free_bytes is not None:
        kwargs["free_bytes"] = free_bytes
    return st.TransitionConfig(
        data_dir=data,
        repository_id="demo",
        root=str(root),
        **kwargs,
    )


def _export_tables(path: pathlib.Path) -> dict[str, list[dict[str, object]]]:
    tables: dict[str, list[dict[str, object]]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if "table" in payload and "columns" in payload:
            current = payload["table"]
            tables[current] = []
        elif "rows" in payload:
            assert payload["table"] == current
        elif current is not None:
            tables[current].append(payload)
    return tables


class InspectTest(unittest.TestCase):
    def test_inspect_is_read_only_and_reports_unknown_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            inspection = st.inspect_store(_config(root, data))
            self.assertEqual(inspection.schema_version, 9)
            self.assertEqual(inspection.integrity, "ok")
            self.assertEqual(inspection.unknown_tables, ("experimental_notes",))
            self.assertIn(
                "unknown tables preserved and exported: experimental_notes",
                inspection.limitations,
            )
            self.assertFalse((data / "transitions").exists())
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(before, after)

    def test_inspect_missing_store_reports_setup_not_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            inspection = st.inspect_store(_config(root, data))
            self.assertFalse(inspection.exists)
            self.assertEqual(inspection.required_free_bytes, 0)
            self.assertIn("explicit installer provisioning", inspection.limitations[0])


class Schema13To15Test(unittest.TestCase):
    def test_schema13_state_is_preserved_without_fabricating_pyramid_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _schema13_store(data / "demo.db", root)

            report = st.apply(_config(root, data))

            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            connection = sqlite3.connect(data / "demo.db")
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='schema_version'"
                    ).fetchone()[0],
                    "15",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM understandings"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM investigation_contexts"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM record_receipts"
                    ).fetchone()[0],
                    1,
                )
                functional_tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                        " AND name LIKE 'functional_%'"
                    )
                }
                self.assertEqual(
                    functional_tables,
                    {"functional_route_dependency_index"},
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM functional_route_dependency_index"
                    ).fetchone()[0],
                    0,
                )
                route = connection.execute(
                    "SELECT pyramid_id, repository_id, route_identity"
                    " FROM functional_route_dependency_index"
                ).fetchone()
                self.assertIsNone(route)
                pre_route_dependencies = connection.execute(
                    "SELECT dependency_kind, dependency_ref"
                    " FROM support_dependencies"
                    " WHERE understanding_id=? AND conclusion_id=? AND revision=?"
                    " ORDER BY dependency_kind, dependency_ref",
                    ("u-schema13", "c-pre-route", 1),
                ).fetchall()
                self.assertEqual(
                    pre_route_dependencies,
                    [("SOURCE", "obs-schema13")],
                )
            finally:
                connection.close()

    def test_schema14_current_revision_migrates_as_pending_capture(self) -> None:
        from span.service.answer import AnswerService
        from span.service.evidence import EvidenceService
        from span.service.support import SupportService
        from span.shell.filesystem_evidence import FilesystemEvidenceSource
        from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
        from span.shell.sqlite_store.lifecycle import LifecycleStore

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _schema14_store(data / "demo.db", root)

            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)

            store = LifecycleStore(
                data / "demo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(store.close)
            evidence = FilesystemEvidenceSource("demo", root)
            support = SupportService(
                store=store,
                evidence=evidence,
                authority=store,
                clock=lambda: NOW,
            )
            answer = AnswerService(
                store=store,
                support=support,
                evidence=EvidenceService(
                    store=store,
                    evidence=evidence,
                    clock=lambda: NOW,
                ),
                clock=lambda: NOW,
                functional_pyramid_orientation=lambda _repository_id, _surface, _scope: (
                    m.FunctionalPyramidParticipation(
                        m.FunctionalPyramidParticipationState.UNCONFIGURED
                    )
                ),
            )

            snapshot = store.get_version("u-schema14", 1)
            ref = snapshot.conclusions[0]
            self.assertIs(
                support.evaluate_revision(ref).state,
                m.SupportState.CURRENT,
            )
            self.assertIsNone(store.find_curation(ref))
            candidates = store.pending_curation_candidates("demo")
            self.assertEqual(tuple(item.ref for item in candidates), (ref,))

            captured = answer.ask(
                m.AskRequest(
                    selector=m.CurrentUnderstandingSelector(
                        repository_id="demo",
                        understanding_id="u-schema14",
                    )
                )
            )
            self.assertIsInstance(captured, m.Gap)
            assert isinstance(captured, m.Gap)
            self.assertIs(captured.reason, m.GapReason.PENDING_CURATION)

            pending = answer.ask(
                m.AskRequest(selector=m.PendingCurationSelector(repository_id="demo"))
            )
            self.assertIsInstance(pending, m.PendingCuration)
            assert isinstance(pending, m.PendingCuration)
            self.assertEqual(tuple(item.ref for item in pending.items), (ref,))

    def test_schema13_transition_rollback_restores_schema13(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _schema13_store(data / "demo.db", root)
            st.apply(_config(root, data))

            report = st.rollback(_config(root, data))

            self.assertEqual(report.state, st.TransitionState.ROLLED_BACK)
            self.assertEqual(st._read_schema_version_ro(data / "demo.db"), 13)


class Schema14To15Test(unittest.TestCase):
    def test_schema14_undecodable_route_payload_preserves_cutover_coordinates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _schema14_store(data / "demo.db", root)
            connection = sqlite3.connect(source)
            try:
                connection.execute(
                    "UPDATE conclusions SET canonical_json=?"
                    " WHERE understanding_id='u-schema14'"
                    " AND conclusion_id='c-schema14' AND revision=1",
                    (
                        json.dumps(
                            {
                                "$type": "ConclusionRevision",
                                "legacy_v1_functional_route_support": {
                                    "pyramid_id": "p-1",
                                    "route_identity": "route-1",
                                },
                            },
                            sort_keys=True,
                        ),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)

            from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
            from span.shell.sqlite_store.lifecycle import LifecycleStore

            migrated = LifecycleStore(
                data / "demo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            self.addCleanup(migrated.close)
            self.assertEqual(
                migrated.current_functional_route_dependents("p-1"),
                (
                    m.ConclusionRevisionRef(
                        understanding_id=m.UnderstandingId("u-schema14"),
                        conclusion_id=m.ConclusionId("c-schema14"),
                        revision=m.ConclusionRevisionNumber(1),
                    ),
                ),
            )
            with self.assertRaises(m.CanonicalDecodeError):
                migrated.get_conclusions("u-schema14")

    def test_schema14_state_is_preserved_and_curation_starts_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _schema14_store(data / "demo.db", root)
            before = hashlib.sha256(source.read_bytes()).hexdigest()

            installation = data / "installation"
            installation.mkdir()
            fp_store = installation / "functional-pyramid.db"
            fp = sqlite3.connect(fp_store)
            try:
                fp.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
                fp.execute("INSERT INTO meta VALUES('schema_version', '1')")
                fp.execute("INSERT INTO meta VALUES('sentinel', 'unchanged')")
                fp.commit()
            finally:
                fp.close()
            fp_before = hashlib.sha256(fp_store.read_bytes()).hexdigest()

            report = st.apply(_config(root, data))

            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            connection = sqlite3.connect(data / "demo.db")
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='schema_version'"
                    ).fetchone()[0],
                    "15",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM conclusion_curations"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT understanding_id, conclusion_id, revision,"
                        " pyramid_id, repository_id, route_identity"
                        " FROM functional_route_dependency_index"
                    ).fetchall(),
                    [
                        (
                            "u-schema14",
                            "c-schema14",
                            1,
                            "p-1",
                            "demo",
                            "route-1",
                        )
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM understandings"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM record_receipts"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()
            self.assertEqual(
                hashlib.sha256(fp_store.read_bytes()).hexdigest(),
                fp_before,
            )

            rollback = st.rollback(_config(root, data))
            self.assertEqual(rollback.state, st.TransitionState.ROLLED_BACK)
            self.assertEqual(st._read_schema_version_ro(data / "demo.db"), 14)
            self.assertEqual(
                hashlib.sha256((data / "demo.db").read_bytes()).hexdigest(),
                before,
            )
            self.assertEqual(
                hashlib.sha256(fp_store.read_bytes()).hexdigest(),
                fp_before,
            )


class ApplyTest(unittest.TestCase):
    def _apply(
        self, tmp: str
    ) -> tuple[pathlib.Path, pathlib.Path, st.TransitionReport]:
        root = pathlib.Path(tmp) / "demo"
        root.mkdir()
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        _legacy_store(data / "demo.db", seeds=(_seed(),))
        report = st.apply(_config(root, data))
        return root, data, report

    def test_apply_archives_stages_and_activates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data, report = self._apply(tmp)
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            self.assertTrue(report.changed)
            active = data / "demo.db"
            connection = sqlite3.connect(active)
            try:
                version = connection.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()[0]
                self.assertEqual(version, "15")
                root_row = connection.execute(
                    "SELECT root FROM repositories WHERE repository_id='demo'"
                ).fetchone()[0]
                self.assertEqual(root_row, str(root.resolve()))
                seeds = json.loads(
                    connection.execute(
                        "SELECT authority_seeds_json FROM repositories"
                        " WHERE repository_id='demo'"
                    ).fetchone()[0]
                )
                self.assertEqual(seeds, [m.to_canonical(_seed())])
                for table in (
                    "understandings",
                    "conclusions",
                    "challenges",
                    "verification_runs",
                    "record_receipts",
                ):
                    self.assertEqual(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                            0
                        ],
                        0,
                    )
            finally:
                connection.close()
            paths = st.TransitionPaths(data, "demo")
            self.assertTrue(paths.archive.is_file())
            self.assertTrue(paths.export.is_file())
            self.assertTrue(paths.export_report.is_file())
            report_text = paths.report.read_text(encoding="utf-8")
            self.assertIn("raw historical export", report_text)
            self.assertIn("does not create an", report_text)
            self.assertIn("claim-orphan", report_text)
            self.assertIn("tgt-1", report_text)

    def test_export_preserves_cell_types_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, data, _ = self._apply(tmp)
            paths = st.TransitionPaths(data, "demo")
            tables = _export_tables(paths.export)
            notes = tables["experimental_notes"]
            self.assertEqual(
                notes[0],
                [
                    1,
                    "text",
                    {"$span.blob": base64.b64encode(b"\x00\x01\xfe\xff").decode()},
                    {"$span.real": "inf"},
                    None,
                ],
            )
            self.assertEqual(notes[1], [2, None, None, 1.5, "present"])
            self.assertIn("claim-orphan", json.dumps(tables["claims"]))

    def test_schema_seven_and_eight_are_lossless_without_seed_column(self):
        for version in (7, 8):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as tmp:
                    root = pathlib.Path(tmp) / "demo"
                    root.mkdir()
                    data = pathlib.Path(tmp) / "data"
                    data.mkdir()
                    _legacy_store(
                        data / "demo.db",
                        version=version,
                        with_seed_column=False,
                    )
                    report = st.apply(_config(root, data))
                    self.assertEqual(report.state, st.TransitionState.VERIFIED)
                    self.assertTrue(
                        any(
                            "no authority_seeds_json" in item
                            for item in report.limitations
                        )
                    )
                    paths = st.TransitionPaths(data, "demo")
                    self.assertEqual(st._reconcile_export(paths)[0].name, "claims")

    def test_export_has_no_legacy_decoder_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            code = f"""
import pathlib, sys
from span.shell import store_transition as st
config = st.TransitionConfig(
    data_dir=pathlib.Path({str(data)!r}),
    repository_id='demo',
    root={str(root)!r},
)
st.inspect_store(config)
paths = st.TransitionPaths(config.data_dir, 'demo')
paths.transition_dir.mkdir(parents=True, exist_ok=True)
with st._exclusive_source(paths.active) as source:
    st._archive(paths, config, source)
st._export(paths)
forbidden = [
    name for name in sys.modules
    if name in {{
        'span.shell.sqlite_store.mapping',
        'span.shell.sqlite_store.store',
        'span.shell.sqlite_store.migrations',
    }}
]
print(','.join(sorted(forbidden)))
"""
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                env={
                    "PYTHONPATH": str(
                        pathlib.Path(__file__).resolve().parents[2] / "src"
                    ),
                    "PATH": "/usr/bin:/bin",
                },
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "")


class RefusalTest(unittest.TestCase):
    def test_unsupported_source_schema_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _legacy_store(data / "demo.db", version=6)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(
                st.TransitionError, "unsupported source schema 6"
            ):
                st.apply(_config(root, data))
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_occupied_store_refuses_without_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            holder = sqlite3.connect(data / "demo.db")
            try:
                holder.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(
                    st.TransitionError, "held by a live process"
                ):
                    st.apply(_config(root, data))
            finally:
                holder.rollback()
                holder.close()
            manifest = st._read_manifest(st.TransitionPaths(data, "demo"))
            self.assertIsNone(manifest)
            self.assertEqual(st._read_schema_version_ro(data / "demo.db"), 9)

    def test_wrong_root_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "different-name"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            with self.assertRaisesRegex(st.TransitionError, "derives repository id"):
                st.apply(_config(root, data))

    def test_missing_root_refuses_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            config = st.TransitionConfig(
                data_dir=data, repository_id="demo", clock=lambda: NOW
            )
            with self.assertRaisesRegex(st.TransitionError, "transition-root"):
                st.apply(config)

    def test_low_space_refuses_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            with self.assertRaisesRegex(st.TransitionError, "insufficient free space"):
                st.apply(_config(root, data, free_bytes=lambda _path: 0))
            self.assertFalse((data / "transitions" / "demo" / "archive.db").exists())

    def test_schema11_copies_without_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _schema11_store(data / "demo.db", root)
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            connection = sqlite3.connect(data / "demo.db")
            try:
                columns = [
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(source_observations)"
                    )
                ]
                self.assertNotIn("excerpt", columns)
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='schema_version'"
                    ).fetchone()[0],
                    "15",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM source_observations"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_schema12_live_context_refuses_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _schema12_store(data / "demo.db", root, live_context=True)
            with self.assertRaisesRegex(
                st.TransitionError, "live investigation context"
            ):
                st.apply(_config(root, data))
            self.assertEqual(st._read_schema_version_ro(source), 12)

    def test_schema12_live_context_without_expiry_refuses_and_is_preserved(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            source = _schema12_store(data / "demo.db", root, live_context=True)
            connection = sqlite3.connect(source)
            try:
                row = connection.execute(
                    "SELECT context_id, canonical_json"
                    " FROM investigation_contexts WHERE repository_id='demo'"
                ).fetchone()
                payload = json.loads(row[1])
                payload["expires_at"] = None
                connection.execute(
                    "UPDATE investigation_contexts"
                    " SET canonical_json=?, expires_at=NULL"
                    " WHERE repository_id='demo' AND context_id=?",
                    (json.dumps(payload, sort_keys=True), row[0]),
                )
                connection.commit()
            finally:
                connection.close()

            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(
                st.TransitionError, "live investigation context"
            ):
                st.apply(_config(root, data))
            self.assertEqual(st._read_schema_version_ro(source), 12)

            connection = sqlite3.connect(source)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM investigation_contexts"
                        " WHERE repository_id='demo'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM context_evidence"
                        " WHERE repository_id='demo'"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_schema12_drained_context_cutover_preserves_durable_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _schema12_store(data / "demo.db", root, live_context=False)
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            connection = sqlite3.connect(data / "demo.db")
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='schema_version'"
                    ).fetchone()[0],
                    "15",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM investigation_contexts"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM context_evidence"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM verification_runs"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM record_receipts"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()
            mapping = json.loads(
                (data / "transitions" / "demo" / "mapping.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(mapping["drained_not_copied"]["investigation_contexts"], 1)

            from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
            from span.shell.sqlite_store.lifecycle import LifecycleStore

            store = LifecycleStore(
                data / "demo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            try:
                receipt = store.get_receipt(
                    m.RecordingKey(
                        repository_id="demo",
                        request_id=m.RequestId("req-schema12"),
                    )
                )
                self.assertIsNotNone(receipt)
                assert receipt is not None
                self.assertEqual(len(receipt.accepted_verification_run_ids), 1)
                run = store.get_verification_run(
                    receipt.accepted_verification_run_ids[0].value
                )
                self.assertEqual(run.command, "python3 -m unittest")
                self.assertEqual(run.repository_id, "demo")
                self.assertEqual(run.scope.scope.paths, ("src/a.py",))
            finally:
                store.close()

    def test_already_current_apply_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            st.apply(_config(root, data))
            with self.assertRaisesRegex(st.TransitionError, "already schema 15"):
                st.apply(_config(root, data))
            inspection, _, state = st.inspect_store_report(_config(root, data))
            self.assertEqual(state, st.TransitionState.ALREADY_CURRENT)


class RecoveryTest(unittest.TestCase):
    def _fixture(self, tmp: str) -> tuple[pathlib.Path, pathlib.Path]:
        root = pathlib.Path(tmp) / "demo"
        root.mkdir()
        data = pathlib.Path(tmp) / "data"
        data.mkdir()
        _legacy_store(data / "demo.db", seeds=(_seed(),))
        return root, data

    def test_schema10_unresolved_scope_is_preserved_not_imported(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "demo"
            data = base / "data"
            _schema10_store(data / "demo.db", root, unresolved=True)
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            mapping_path = data / "transitions" / "demo" / "mapping.json"
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(mapping["counts"]["unresolved"], 1)
            self.assertTrue(
                any(item["source_id"] == "u-wide" for item in mapping["unresolved"]),
            )
            from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
            from span.shell.sqlite_store.lifecycle import (
                LifecycleStore,
                LifecycleStoreError,
            )

            store = LifecycleStore(
                data / "demo.db", retention=DEFAULT_LIFECYCLE_RETENTION
            )
            try:
                with self.assertRaises(LifecycleStoreError):
                    store.get_understanding("u-wide")
                self.assertEqual(
                    store.get_understanding("u-1").surface.locator, "src/a.py"
                )
            finally:
                store.close()

    def test_interruption_after_archive_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_export", stop):
                with self.assertRaisesRegex(
                    st.TransitionError, "simulated interruption"
                ):
                    st.apply(_config(root, data))
            manifest = st._read_manifest(st.TransitionPaths(data, "demo"))
            self.assertEqual(manifest.state, st.TransitionState.ARCHIVED)
            self.assertTrue((data / "transitions" / "demo" / "archive.db").is_file())
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)

    def test_interruption_after_export_resumes_without_rearchiving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_stage", stop):
                with self.assertRaises(st.TransitionError):
                    st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            manifest = st._read_manifest(paths)
            self.assertEqual(manifest.state, st.TransitionState.STAGED)
            archive_hash = hashlib.sha256(paths.archive.read_bytes()).hexdigest()
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            self.assertEqual(
                archive_hash, hashlib.sha256(paths.archive.read_bytes()).hexdigest()
            )

    def test_rollback_before_activation_discards_owned_staging_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)

            def stop(*_args, **_kwargs):
                raise st.TransitionError("simulated interruption")

            with mock.patch.object(st, "_stage", stop):
                with self.assertRaises(st.TransitionError):
                    st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            paths.staging.write_bytes(b"owned staging")
            report = st.rollback(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.ROLLED_BACK)
            self.assertFalse(paths.staging.exists())
            self.assertTrue(paths.archive.is_file())
            self.assertTrue(paths.export.is_file())
            self.assertEqual(st._read_schema_version_ro(paths.active), 9)

    def test_rollback_after_activation_preserves_new_format_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            connection = sqlite3.connect(paths.active)
            try:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('new-write', 'kept')"
                )
                connection.commit()
            finally:
                connection.close()
            report = st.rollback(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.ROLLED_BACK)
            self.assertEqual(st._read_schema_version_ro(paths.active), 9)
            preserved = list(paths.transition_dir.glob("new-format-*.db"))
            self.assertEqual(len(preserved), 1)
            connection = sqlite3.connect(preserved[0])
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT value FROM meta WHERE key='new-write'"
                    ).fetchone()[0],
                    "kept",
                )
            finally:
                connection.close()

    def test_corrupt_archive_fails_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            paths = st.TransitionPaths(data, "demo")
            paths.archive.write_bytes(b"not a database")
            with self.assertRaises(st.TransitionError):
                st.verify(_config(root, data))

    def test_verify_is_observational(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, data = self._fixture(tmp)
            st.apply(_config(root, data))
            active = data / "demo.db"
            before = hashlib.sha256(active.read_bytes()).hexdigest()
            report = st.verify(_config(root, data))
            self.assertFalse(report.changed)
            self.assertEqual(before, hashlib.sha256(active.read_bytes()).hexdigest())


class DispatchTest(unittest.TestCase):
    def test_parse_phase_rejects_unknown(self):
        with self.assertRaisesRegex(st.TransitionError, "unknown transition phase"):
            st.parse_phase("migrate")

    def test_report_payload_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            report = st.dispatch(_config(root, data), st.TransitionPhase.INSPECT)
            payload = st.report_payload(report)
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(payload["inspection"]["schema_version"], 9)
            json.dumps(payload)


class InstallerCommandTest(unittest.TestCase):
    def test_migrate_store_is_an_unknown_argument(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--migrate-store", "demo", "--data-dir", str(data)])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(list(data.iterdir()), [])

    def test_transition_phase_requires_store(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--transition-phase", "inspect", "--data-dir", str(data)])
            self.assertIn("require --transition-store", str(raised.exception))

    def test_transition_store_requires_phase(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            with self.assertRaises(SystemExit) as raised:
                install.main(["--transition-store", "demo", "--data-dir", str(data)])
            self.assertIn("requires --transition-phase", str(raised.exception))

    def test_apply_dry_run_changes_nothing(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "demo"
            root.mkdir()
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            import contextlib
            import io

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install.main(
                    [
                        "--transition-store",
                        "demo",
                        "--transition-phase",
                        "apply",
                        "--transition-root",
                        str(root),
                        "--data-dir",
                        str(data),
                        "--dry-run",
                    ]
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(
                before, hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            )
            self.assertFalse((data / "transitions").exists())

    def test_inspect_command_prints_report_and_changes_nothing(self):
        from span.shell import install

        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            _legacy_store(data / "demo.db", seeds=(_seed(),))
            before = hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            import contextlib
            import io

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                install.main(
                    [
                        "--transition-store",
                        "demo",
                        "--transition-phase",
                        "inspect",
                        "--data-dir",
                        str(data),
                    ]
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["phase"], "inspect")
            self.assertEqual(payload["inspection"]["schema_version"], 9)
            self.assertEqual(
                before, hashlib.sha256((data / "demo.db").read_bytes()).hexdigest()
            )
            self.assertFalse((data / "transitions").exists())

    def test_schema10_maps_surfaces_history_and_receipts(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / "demo"
            data = base / "data"
            source = _schema10_store(data / "demo.db", root)
            inspection = st.inspect_store(_config(root, data))
            self.assertEqual(inspection.schema_version, 10)
            report = st.apply(_config(root, data))
            self.assertEqual(report.state, st.TransitionState.VERIFIED)
            mapping_path = data / "transitions" / "demo" / "mapping.json"
            self.assertTrue(mapping_path.is_file())
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            self.assertEqual(mapping["counts"]["unresolved"], 0)
            self.assertGreaterEqual(mapping["counts"]["transformed"], 1)
            self.assertEqual(st._read_schema_version_ro(source), 15)
            from span.shell.policy import DEFAULT_LIFECYCLE_RETENTION
            from span.shell.sqlite_store.lifecycle import LifecycleStore

            store = LifecycleStore(
                data / "demo.db",
                retention=DEFAULT_LIFECYCLE_RETENTION,
                clock=lambda: NOW,
            )
            try:
                understanding = store.get_understanding("u-1")
                self.assertEqual(understanding.surface.locator, "src/a.py")
                self.assertEqual(understanding.surface.kind, m.SurfaceKind.FILE)
                self.assertEqual(len(store.get_version("u-1", 1).conclusions), 1)
                self.assertEqual(len(store.get_version("u-1", 1).gaps), 1)
                self.assertEqual(len(store.get_challenges("u-1")), 1)
                self.assertEqual(
                    store.get_verification_run("run:ctx-2:req-2").run_id.value,
                    "run:ctx-2:req-2",
                )
                receipt = store.get_receipt(
                    m.RecordingKey(
                        repository_id="demo", request_id=m.RequestId("req-1")
                    )
                )
                self.assertIsNotNone(receipt)
                assert receipt is not None
                self.assertEqual(receipt.identity.context_id.value, "ctx-1")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
