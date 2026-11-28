"""Exact retrieval of one stored snapshot, context, or retained receipt."""

from __future__ import annotations

from span.core import model as m
from span.core.recording import RecordingValidationError, create_challenge
from span.ports.lifecycle import LifecycleStorePort
from span.service.support import SupportService

__all__ = ["UnderstandService"]


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
        effect = receipt.accepted_effect
        accepted_effect: (
            m.AcceptedVerificationReceipt
            | m.AcceptedUnderstandingEffect
            | m.AcceptedSurfaceEffect
            | m.AcceptedChallengeOpeningEffect
            | m.HistoricalAcceptanceDetailUnavailable
        )
        if isinstance(effect, m.AcceptedVerificationEffect):
            try:
                accepted_effect = m.AcceptedVerificationReceipt(
                    (
                        m.verification_view(
                            self._store.get_verification_run(effect.run_id.value), None
                        ),
                    )
                )
            except (OSError,) + self._store.operational_errors:
                accepted_effect = self.unavailable_acceptance(receipt)
        else:
            accepted_effect = effect
        return m.RetrievedReceipt(
            receipt_selector=request,
            committed_at=receipt.committed_at,
            accepted_effect=accepted_effect,
        )

    @staticmethod
    def unavailable_acceptance(
        receipt: m.RecordReceipt,
    ) -> m.HistoricalAcceptanceDetailUnavailable:
        if isinstance(receipt.accepted_effect, m.HistoricalAcceptanceDetailUnavailable):
            return receipt.accepted_effect
        return m.HistoricalAcceptanceDetailUnavailable(
            understanding_versions=receipt.understanding_versions,
            verification_run_ids=receipt.verification_run_ids,
            challenge_ids=receipt.challenge_ids,
            dependent_effect_refs=receipt.dependency_refs,
            reason="exact accepted detail is unavailable",
            recovery="retrieve the named historical records; do not repeat the write",
        )

    def challenge_opening(
        self, receipt: m.RecordReceipt
    ) -> m.Challenged | m.AcceptedDetailUnavailable:
        selector = receipt.selector
        effect = receipt.accepted_effect
        try:
            if (
                not isinstance(effect, m.AcceptedChallengeOpeningEffect)
                or receipt.context is None
            ):
                raise RecordingValidationError("receipt has no exact challenge opening")
            retained = self._store.get_challenge(effect.challenge_id.value)
            if (
                retained.facts.understanding_id != effect.understanding_id
                or retained.facts.target_version != effect.target_version
                or retained.target_conclusions != effect.target_conclusions
            ):
                raise RecordingValidationError(
                    "accepted challenge target differs from retained detail"
                )
            opening = create_challenge(
                challenge_id=retained.facts.challenge_id,
                understanding_id=retained.facts.understanding_id,
                target_version=retained.facts.target_version,
                target_conclusions=retained.target_conclusions,
                reason=retained.facts.reason,
                evidence=retained.evidence,
                provenance=retained.facts.provenance,
                now=retained.facts.created_at,
            )
            version = self._store.get_version(
                opening.facts.understanding_id.value, opening.facts.target_version.value
            )
            curations = self._store.get_curations(
                opening.facts.understanding_id.value, as_of_version=version.version
            )
            conclusions = self._audit_membership(
                version, curations, selected=opening.target_conclusions
            )
        except (OSError, RecordingValidationError) + self._store.operational_errors:
            return m.AcceptedDetailUnavailable(
                receipt_selector=selector,
                committed_at=receipt.committed_at,
                detail=self.unavailable_acceptance(receipt),
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
                if challenge.facts.target_version == version.version
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
