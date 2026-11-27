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
        try:
            verification_runs = tuple(
                self._store.get_verification_run(run_id.value)
                for run_id in receipt.accepted_verification_run_ids
            )
        except self._store.operational_errors:
            return m.Unavailable(
                operation="ask",
                failure="accepted receipt references unavailable retained history",
                recovery=(
                    "report the unavailable history and preserve the receipt; "
                    "do not repeat the historical write"
                ),
            )
        accepted_effect: (
            m.AcceptedVerificationReceipt | m.HistoricalAcceptanceDetailUnavailable
        )
        if (
            verification_runs
            and not receipt.accepted_understanding_ids
            and not receipt.accepted_challenge_ids
            and not receipt.dependent_effects
        ):
            accepted_effect = m.AcceptedVerificationReceipt(verification_runs)
        else:
            accepted_effect = self.unavailable_acceptance(receipt)
        return m.RetrievedReceipt(
            receipt_selector=request,
            committed_at=receipt.committed_at,
            accepted_effect=accepted_effect,
        )

    @staticmethod
    def unavailable_acceptance(
        receipt: m.RecordReceipt,
    ) -> m.HistoricalAcceptanceDetailUnavailable:
        return m.HistoricalAcceptanceDetailUnavailable(
            understanding_versions=tuple(
                m.UnderstandingVersionRef(identity, version)
                for identity, version in zip(
                    receipt.accepted_understanding_ids,
                    receipt.accepted_understanding_versions,
                    strict=True,
                )
            ),
            verification_run_ids=receipt.accepted_verification_run_ids,
            challenge_ids=receipt.accepted_challenge_ids,
            dependent_effect_refs=receipt.dependent_effects,
            reason="exact accepted detail is unavailable",
            recovery="retrieve the named historical records; do not repeat the write",
        )

    def challenge_opening(
        self, receipt: m.RecordReceipt
    ) -> m.Challenged | m.AcceptedDetailUnavailable:
        selector = m.ReceiptRetrievalSelector(
            repository_id=receipt.identity.repository_id,
            request_id=receipt.identity.request_id.value,
        )
        try:
            if len(receipt.accepted_challenge_ids) != 1:
                raise RecordingValidationError("receipt has no exact challenge opening")
            retained = self._store.get_challenge(
                receipt.accepted_challenge_ids[0].value
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
                detail=self.unavailable_acceptance(receipt),
            )
        return m.Challenged(
            receipt_selector=selector,
            committed_at=receipt.committed_at,
            challenge=opening,
            context=m.InvestigationContextRef(
                repository_id=receipt.identity.repository_id,
                context_id=receipt.identity.context_id,
            ),
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
                challenge
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
