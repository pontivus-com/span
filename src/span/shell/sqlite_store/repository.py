"""Repository identity, initialization state, and target associations."""

from __future__ import annotations

from collections.abc import Callable as _Callable

import datetime as _datetime
import json as _json
import sqlite3 as _sqlite3

from span.core import model as m
from span.shell.sqlite_store.mapping import _encode


class RepositoryMixin:
    _db: _sqlite3.Connection
    _now: _Callable[[], _datetime.datetime]

    def repository_root(self, repository_id: str) -> str | None:
        row = self._db.execute(
            "SELECT value FROM meta WHERE key=?",
            (f"repository_root:{repository_id}",),
        ).fetchone()
        return str(row[0]) if row is not None else None

    def record_repository_root(self, repository_id: str, root: str) -> None:
        existing = self.repository_root(repository_id)
        if existing is not None and existing != root:
            raise m.RepositoryIdentityConflict(repository_id, existing, root)
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            (f"repository_root:{repository_id}", root),
        )
        self._db.commit()

    def load_repository_state(self, repository_id: str) -> m.RepositoryState | None:
        row = self._db.execute(
            "SELECT revision_id, dirty, state_fingerprint, observed_at "
            "FROM repositories WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return None
        return m.RepositoryState(
            repository_id=repository_id,
            revision_id=row[0],
            dirty=bool(row[1]),
            state_fingerprint=row[2],
            observed_at=_datetime.datetime.fromisoformat(row[3]),
        )

    def record_repository_initialization(
        self,
        state: m.RepositoryState,
        authority_seeds: tuple[m.EvidenceRef, ...],
    ) -> None:
        """Write one repository row holding state and authority seeds.

        One atomic INSERT OR REPLACE: initialization never leaves the
        state record and its configured authority seeds out of step.
        """
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO repositories"
                "(repository_id, revision_id, dirty, state_fingerprint, "
                "observed_at, authority_seeds_json) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (
                    state.repository_id,
                    state.revision_id,
                    int(state.dirty),
                    state.state_fingerprint,
                    state.observed_at.isoformat(),
                    _encode(m.to_canonical(authority_seeds)),
                ),
            )

    def load_repository_authority_seeds(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, ...]:
        """Persisted canonical authority seeds for a repository.

        No row means the repository was never initialized and yields
        ``()``. A row whose stored seeds are not canonical JSON (or not
        exactly ``EvidenceRef`` items) fails closed; configured data is
        never silently replaced by an empty tuple.
        """
        row = self._db.execute(
            "SELECT authority_seeds_json FROM repositories " "WHERE repository_id=?",
            (repository_id,),
        ).fetchone()
        if row is None:
            return ()
        try:
            decoded = m.from_canonical(tuple[m.EvidenceRef, ...], _json.loads(row[0]))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"repository {repository_id!r} authority seeds are not "
                f"canonical: {exc}"
            ) from None
        if not isinstance(decoded, tuple) or not all(
            isinstance(seed, m.EvidenceRef) for seed in decoded
        ):
            raise ValueError(
                f"repository {repository_id!r} authority seeds are not " "canonical"
            )
        for seed in decoded:
            if seed.repository_id != repository_id:
                raise ValueError(
                    f"repository {repository_id!r} authority seeds contain "
                    f"a seed for repository {seed.repository_id!r}"
                )
        return decoded

    def load_target_association(
        self, repository_id: str, target_id: m.TargetId
    ) -> m.TargetAssociation | None:
        try:
            row = self._db.execute(
                "SELECT canonical_json, expires_at FROM target_associations "
                "WHERE repository_id=? AND target_id=?",
                (repository_id, target_id.value),
            ).fetchone()
        except _sqlite3.OperationalError:
            return None
        if row is None:
            return None
        payload, expires_at = row
        # TTL-as-absent: expired rows read as absent without mutating.
        if expires_at <= self._now().isoformat():
            return None
        data = _json.loads(payload)
        value = m.from_canonical(m.TargetAssociation, data)
        assert isinstance(value, m.TargetAssociation)
        return value

    def count_target_associations(self, repository_id: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM target_associations "
            "WHERE repository_id=? AND expires_at > ?",
            (repository_id, self._now().isoformat()),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def load_active_target_associations(
        self, repository_id: str
    ) -> tuple[m.TargetAssociation, ...]:
        rows = self._db.execute(
            "SELECT canonical_json FROM target_associations "
            "WHERE repository_id=? AND expires_at > ? ORDER BY target_id",
            (repository_id, self._now().isoformat()),
        ).fetchall()
        associations: list[m.TargetAssociation] = []
        for (payload,) in rows:
            data = _json.loads(payload)
            value = m.from_canonical(m.TargetAssociation, data)
            assert isinstance(value, m.TargetAssociation)
            associations.append(value)
        return tuple(associations)
