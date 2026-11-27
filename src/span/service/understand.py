"""Exact retrieval of one stored snapshot, context, or retained receipt."""

from __future__ import annotations

from span.core import model as m
from span.core.recording import RecordingValidationError, create_challenge
from span.ports.lifecycle import LifecycleStorePort
from span.service.support import SupportService

__all__ = ["UnderstandService"]


def accepted_dispositions(
    store: LifecycleStorePort, effect: m.AcceptedUnderstandingEffect
) -> tuple[m.AcceptedChallengeDisposition, ...]:
    """Read precisely the disposition revision recorded by acceptance."""
    accepted: list[m.AcceptedChallengeDisposition] = []
    for coordinate in effect.challenge_dispositions:
        challenge = store.get_challenge(coordinate.challenge_id.value)
        matches = tuple(
            disposition
            for disposition in challenge.dispositions
            if disposition.challenge_revision == coordinate.challenge_revision
        )
        if (
            len(matches) != 1
            or challenge.understanding_id != effect.understanding_id
        ):
            raise RecordingValidationError(
                "the exact accepted challenge disposition is unavailable"
            )
        accepted.append(
            m.accepted_challenge_disposition(challenge.challenge_id, matches[0])
        )
    return tuple(accepted)


class UnderstandService:
    """Return exact retained detail addressed by a closed selector."""

    def __init__(self, *, store: LifecycleStorePort, support: SupportService) -> None:
        self._store = store
        self._support = support

    def retrieve(self, request: m.RetrieveRequest) -> m.RetrieveResult | m.Unavailable:
        """Return the selected snapshot, context, or retained receipt."""
        if isinstance(request, m.UnderstandingSnapshotSelector):
            return self.snapshot(request)
        if isinstance(request, m.ContextRetrievalSelector):
            context = self._store.get_context(request.context_id)
            self._require_repository(context.repository_id, request.repository_id)
            return m.RetrievedContext(
                context=context,
                observations=self._store.list_context_evidence(request.context_id),
                discovery=self._store.list_context_discovery(request.context_id),
            )
        if isinstance(request, m.ReceiptRetrievalSelector):
            return self.receipt(request)
        raise TypeError(f"unhandled retrieval selector: {type(request).__name__}")

    def snapshot(
        self, request: m.UnderstandingSnapshotSelector
    ) -> m.RetrievedUnderstanding:
        self._store.require_repository(request.repository_id)
        understanding = self._store.find_understanding(request.understanding_id)
        if understanding is None:
            raise RecordingValidationError(
                f"unknown understanding: {request.understanding_id!r}",
                public_identity=request.understanding_id,
                public_cause=(
                    "the exact understanding "
                    f"{request.understanding_id!r} does not exist"
                ),
            )
        version_number = (
            understanding.current_version.value
            if request.version is None
            else request.version
        )
        if request.version is None:
            # A missing current row is retained-state unavailability.
            version = self._store.get_version(request.understanding_id, version_number)
        else:
            selected_version = self._store.find_version(
                request.understanding_id, version_number
            )
            if selected_version is None:
                identity = f"{request.understanding_id}@{version_number}"
                raise RecordingValidationError(
                    f"unknown understanding version: {identity}",
                    public_identity=identity,
                    public_cause=(
                        f"the exact understanding version {identity!r} "
                        "does not exist"
                    ),
                )
            version = selected_version
        if understanding.repository_id != request.repository_id:
            raise RecordingValidationError(
                "selected understanding belongs to another repository"
            )
        return self._snapshot(understanding, version)

    def receipt(
        self, request: m.ReceiptRetrievalSelector
    ) -> m.RetrievedReceipt | m.Unavailable:
        self._store.require_repository(request.repository_id)
        key = m.RecordingKey(
            repository_id=request.repository_id,
            request_id=m.RequestId(request.request_id),
        )
        receipt = self._store.get_receipt(key)
        if receipt is None:
            raise RecordingValidationError(
                f"no receipt for request {request.request_id!r}"
            )
        try:
            accepted_effect = self._accepted_receipt_effect(receipt)
        except (OSError, RecordingValidationError) + self._store.operational_errors:
            accepted_effect = m.unavailable_acceptance(receipt)
        return m.RetrievedReceipt(
            receipt_selector=request,
            committed_at=receipt.committed_at,
            accepted_effect=accepted_effect,
        )

    def _accepted_receipt_effect(
        self, receipt: m.RecordReceipt
    ) -> (
        m.AcceptedUnderstandingReceipt
        | m.AcceptedVerificationReceipt
        | m.AcceptedSurfaceEffect
        | m.AcceptedChallengeOpeningEffect
        | m.HistoricalAcceptanceDetailUnavailable
    ):
        effect = receipt.accepted_effect
        if isinstance(effect, m.AcceptedVerificationEffect):
            run = self._store.get_verification_run(effect.run_id.value)
            return m.AcceptedVerificationReceipt((m.verification_view(run, None),))
        if isinstance(effect, m.AcceptedUnderstandingEffect):
            return m.AcceptedUnderstandingReceipt(
                understanding_id=effect.understanding_id,
                version=effect.version,
                revision_effects=effect.revision_effects,
                challenge_dispositions=accepted_dispositions(self._store, effect),
                dependent_effects=effect.dependent_effects,
            )
        if isinstance(effect, m.AcceptedSurfaceEffect):
            if not any(
                boundary.boundary_version == effect.boundary_version
                for boundary in self._store.surface_boundaries(effect.surface)
            ):
                raise RecordingValidationError(
                    "accepted surface boundary is unavailable"
                )
        return effect

    def challenge_opening(
        self, receipt: m.RecordReceipt
    ) -> m.Challenged | m.AcceptedDetailUnavailable:
        selector = m.ReceiptRetrievalSelector(
            repository_id=receipt.key.repository_id,
            request_id=receipt.key.request_id.value,
        )
        try:
            effect = receipt.accepted_effect
            if (
                not isinstance(effect, m.AcceptedChallengeOpeningEffect)
                or receipt.context is None
            ):
                raise RecordingValidationError("receipt has no exact challenge opening")
            retained = self._store.get_challenge(effect.challenge_id.value)
            if (
                retained.understanding_id != effect.understanding_id
                or retained.target_version != effect.target_version
                or retained.target_conclusions != effect.target_conclusions
            ):
                raise RecordingValidationError(
                    "accepted challenge coordinates are unavailable"
                )
            opening = create_challenge(
                challenge_id=retained.challenge_id,
                understanding_id=retained.understanding_id,
                target_version=retained.target_version,
                target_conclusions=retained.target_conclusions,
                reason=retained.reason,
                evidence=retained.evidence,
                provenance=retained.provenance,
                now=retained.created_at,
            )
            version = self._store.get_version(
                opening.understanding_id.value, opening.target_version.value
            )
            curations = self._store.get_curations(
                opening.understanding_id.value, as_of_version=version.version
            )
            conclusions = self._audit_membership(
                version, curations, selected=opening.target_conclusions
            )
        except (OSError, RecordingValidationError) + self._store.operational_errors:
            return m.AcceptedDetailUnavailable(
                receipt_selector=selector,
                committed_at=receipt.committed_at,
                detail=m.unavailable_acceptance(receipt),
            )
        return m.Challenged(
            receipt_selector=selector,
            committed_at=receipt.committed_at,
            challenge=m.challenge_view(opening),
            context=receipt.context,
            prior_conclusions=conclusions,
        )

    def _audit_membership(
        self,
        version: m.UnderstandingVersion,
        curations: tuple[m.CurationDisposition, ...],
        *,
        selected: tuple[m.ConclusionRevisionRef, ...] | None = None,
    ) -> tuple[m.AuditConclusion, ...]:
        curated = {item.ref for item in curations}
        refs = version.conclusions if selected is None else selected
        revisions = {
            m.ConclusionRevisionRef(
                revision.understanding_id, revision.conclusion_id, revision.revision
            ): revision
            for revision in self._store.get_version_conclusions(
                version.understanding_id.value, version.version.value
            )
        }
        if any(ref not in revisions for ref in refs):
            raise RecordingValidationError(
                "selected historical revision is unavailable"
            )
        return tuple(self._audit_revision(revisions[ref], curated) for ref in refs)

    def _snapshot(
        self, understanding: m.Understanding, version: m.UnderstandingVersion
    ) -> m.RetrievedUnderstanding:
        identity = understanding.understanding_id.value
        curations = self._store.get_curations(identity, as_of_version=version.version)
        conclusions = self._audit_membership(version, curations)
        return m.RetrievedUnderstanding(
            repository_id=understanding.repository_id,
            surface=understanding.surface,
            understanding_id=version.understanding_id,
            version=version.version,
            question=version.question,
            scope=version.scope,
            created_at=version.created_at,
            provenance=version.provenance,
            previous_version=version.previous_version,
            surface_boundary_version=version.surface_boundary_version,
            gaps=version.gaps,
            conclusions=conclusions,
            challenges=tuple(
                m.challenge_view(challenge)
                for challenge in self._store.get_challenges(identity)
                if challenge.target_version == version.version
            ),
            curations=curations,
        )

    def _audit_revision(
        self,
        revision: m.ConclusionRevision,
        curated: set[m.ConclusionRevisionRef],
    ) -> m.AuditConclusion:
        ref = m.ConclusionRevisionRef(
            understanding_id=revision.understanding_id,
            conclusion_id=revision.conclusion_id,
            revision=revision.revision,
        )
        bases = tuple(
            self._support.support_basis(item) for item in revision.content.support
        )
        qualification: m.SupportQualification | m.SupportUnavailable | None = None
        if isinstance(revision.content, m.SupportedConclusion):
            try:
                qualification = self._support.qualify_support(
                    self._support.evaluate_revision(ref)
                )
            except (OSError,) + self._store.operational_errors:
                qualification = m.SupportUnavailable(
                    "live support evaluation is unavailable"
                )
        maturity = (
            m.CurationState.CURATED if ref in curated else m.CurationState.CAPTURED
        )
        return m.audit_conclusion(
            revision, bases, maturity=maturity, qualification=qualification
        )

    @staticmethod
    def _require_repository(actual: str, requested: str) -> None:
        if actual != requested:
            raise RecordingValidationError(
                f"referenced content belongs to repository {actual!r}, not "
                f"{requested!r}"
            )
