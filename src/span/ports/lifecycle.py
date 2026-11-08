"""Lifecycle port interfaces.

The authority binding a conclusion cites is declared governance, not a shape
the service may infer from an evidence ID. The composition root supplies the
resolver; the service never fabricates authority kind, status, or precedence.
"""

import typing as _typing

from span.core import model as m


@_typing.runtime_checkable
class LifecycleAuthorityResolver(_typing.Protocol):
    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        """Resolve one declared authority reference for a repository."""
        ...


@_typing.runtime_checkable
class LifecycleStorePort(_typing.Protocol):
    """Persistence boundary the lifecycle service coordinates.

    The SQLite shell implements this structurally; the service owns no SQL
    and reads decisions only through these operations.
    """

    retention: m.LifecycleRetention
    # Store-owned operational failures; programming/contract errors are excluded.
    operational_errors: tuple[type[Exception], ...]

    def schema_version(self) -> int:
        """Return the active lifecycle schema version."""
        ...

    def require_repository(self, repository_id: str) -> str:
        """Return the registered root or reject an unknown repository."""
        ...

    def register_repository(
        self,
        repository_id: str,
        root: str,
        *,
        authority_seeds: tuple[m.EvidenceRef, ...] = (),
        authority_bindings: tuple[m.AuthorityBinding, ...] | None = None,
    ) -> None:
        """Bind one repository root and declared authority configuration."""
        ...

    def load_authority_seeds(self, repository_id: str) -> tuple[m.EvidenceRef, ...]:
        """Return declared authority seeds; malformed seeds fail closed."""
        ...

    def load_authority_bindings(
        self, repository_id: str
    ) -> tuple[m.AuthorityBinding, ...]:
        """Return declared authority bindings; malformed data fails closed."""
        ...

    def resolve_context(
        self,
        repository_id: str,
        request_id: m.RequestId,
        request_digest: m.ContentDigest,
        factory: _typing.Callable[[], m.InvestigationContext],
    ) -> m.InvestigationContext:
        """Return the request-bound context, creating exactly one if absent."""
        ...

    def get_context(self, context_id: str) -> m.InvestigationContext:
        """Return one stored context or reject an unknown identity."""
        ...

    def find_context_by_id(self, context_id: str) -> m.InvestigationContext | None:
        """Return one stored context by identity, or None after reaping."""
        ...

    def list_understandings(
        self,
        repository_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[m.Understanding, ...]:
        """Return one deterministic page of stored understandings."""
        ...

    def get_understanding(self, understanding_id: str) -> m.Understanding:
        """Return one stored understanding."""
        ...

    def get_version(
        self, understanding_id: str, version: int
    ) -> m.UnderstandingVersion:
        """Return one exact immutable understanding version."""
        ...

    def get_conclusions(
        self, understanding_id: str
    ) -> tuple[m.ConclusionRevision, ...]:
        """Return every historical conclusion revision of one understanding."""
        ...

    def get_version_conclusions(
        self, understanding_id: str, version: int
    ) -> tuple[m.ConclusionRevision, ...]:
        """Return only the conclusion revisions in one exact version."""
        ...

    def get_challenges(self, understanding_id: str) -> tuple[m.Challenge, ...]:
        """Return every challenge bound to one understanding."""
        ...

    def get_challenge(self, challenge_id: str) -> m.Challenge:
        """Return one stored challenge with its disposition history."""
        ...

    def put_source_observation(self, record: m.SourceObservation) -> None:
        """Insert one immutable source observation."""
        ...

    def put_discovery_observation(self, observation: m.DiscoveryObservation) -> None:
        """Insert one immutable discovery-membership observation."""
        ...

    def has_source_observation(self, observation_id: str) -> bool:
        """Whether one source observation already exists."""
        ...

    def add_context_evidence(self, context_id: str, observation_id: str) -> None:
        """Admit one existing observation into a context."""
        ...

    def add_context_discovery_evidence(
        self, context_id: str, observation_id: str
    ) -> None:
        """Admit one discovery observation into a context."""
        ...

    def list_context_evidence(self, context_id: str) -> tuple[m.SourceObservation, ...]:
        """Return the context's admitted source observations."""
        ...

    def list_context_discovery(
        self, context_id: str
    ) -> tuple[m.DiscoveryObservation, ...]:
        """Return the context's admitted discovery observations."""
        ...

    def find_admitted_evidence(
        self, context_id: str, reference: str
    ) -> m.EvidenceRef | None:
        """Resolve one admitted evidence reference by identity."""
        ...

    def has_admitted_observation(self, context_id: str, observation_id: str) -> bool:
        """Whether one source observation is admitted in a context."""
        ...

    def has_admitted_discovery(self, context_id: str, observation_id: str) -> bool:
        """Whether one discovery observation is admitted in a context."""
        ...

    def has_conclusion_revision(
        self, understanding_id: str, conclusion_id: str, revision: int
    ) -> bool:
        """Whether one exact conclusion revision exists."""
        ...

    def get_source_observation(self, observation_id: str) -> m.SourceObservation:
        """Return one stored source observation."""
        ...

    def source_observation_ids_for_locator(
        self, repository_id: str, locator: str
    ) -> tuple[str, ...]:
        """Return observations captured from one repository locator."""
        ...

    def support_dependents(
        self, dependency_kind: str, dependency_ref: str
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        """Return exact revisions whose support references one identity."""
        ...

    def find_source_observation(
        self, observation_id: str
    ) -> m.SourceObservation | None:
        """Return one stored source observation, or None."""
        ...

    def find_discovery_observation(
        self, observation_id: str
    ) -> m.DiscoveryObservation | None:
        """Return one stored discovery observation, or None."""
        ...

    def find_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding | None:
        """Return one declared authority binding, or None."""
        ...

    def get_discovery_observation(self, observation_id: str) -> m.DiscoveryObservation:
        """Return one stored discovery observation."""
        ...

    def list_discovery_observations(
        self, repository_id: str
    ) -> tuple[m.DiscoveryObservation, ...]:
        """Return every discovery observation for one repository."""
        ...

    def get_verification_run(self, run_id: str) -> m.VerificationRun:
        """Return one stored independent verification run."""
        ...

    def list_verification_runs(
        self, repository_id: str
    ) -> tuple[m.VerificationRun, ...]:
        """Return every stored independent verification run for one repository."""
        ...

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        """Resolve one declared authority binding."""
        ...

    def put_surface(self, surface: m.Surface) -> m.Surface:
        """Persist a surface, idempotent for identical content."""
        ...

    def update_surface(
        self, surface: m.Surface, *, expected_boundary_version: int
    ) -> m.Surface:
        """Apply a compare-and-set boundary update and keep its history."""
        ...

    def find_surface(self, key: m.SurfaceKey) -> m.Surface | None:
        """Return one surface, or None when it has never been declared."""
        ...

    def get_surface(self, key: m.SurfaceKey) -> m.Surface:
        """Return one surface or reject an unknown identity."""
        ...

    def list_surfaces(self, repository_id: str) -> tuple[m.Surface, ...]:
        """Return every declared surface of one repository."""
        ...

    def surface_boundaries(self, key: m.SurfaceKey) -> tuple[m.Surface, ...]:
        """Return every immutable boundary version of one surface."""
        ...

    def get_receipt(self, key: m.RecordingKey) -> m.RecordReceipt | None:
        """Return the retained receipt for one request key."""
        ...

    def record_noop(
        self,
        identity: m.RecordingIdentity,
        content_digest: m.ContentDigest,
        understanding_id: m.UnderstandingId,
    ) -> m.RecordReceipt:
        """Persist acceptance for an unchanged, already-current version."""
        ...

    def find_context_by_request(
        self, repository_id: str, request_id: m.RequestId
    ) -> m.InvestigationContext | None:
        """Return the context bound to a request identity, or None."""
        ...

    def record_understanding(
        self,
        command: m.CreateUnderstandingCommand | m.UpdateUnderstandingCommand,
        *,
        understanding_id: m.UnderstandingId | None = None,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        """Accept one understanding create/update atomically."""
        ...

    def record_verification(
        self,
        command: m.RecordVerificationCommand,
        *,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        """Accept one independent verification run atomically."""
        ...

    def record_challenge(
        self,
        command: m.CreateChallengeCommand,
        *,
        content_digest: m.ContentDigest | None = None,
    ) -> m.RecordReceipt:
        """Accept one challenge create with receipt-first replay."""
        ...
