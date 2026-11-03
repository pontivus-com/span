"""Exact retrieval of one stored snapshot, context, or retained receipt."""

from __future__ import annotations

from span.core import model as m
from span.core.recording import RecordingValidationError
from span.ports.lifecycle import LifecycleStorePort
from span.service.support import SupportService

__all__ = ["UnderstandService"]


class UnderstandService:
    """Return exact retained detail addressed by a closed selector."""

    def __init__(self, *, store: LifecycleStorePort, support: SupportService) -> None:
        self._store = store
        self._support = support

    def retrieve(self, request: m.RetrieveRequest) -> m.RetrieveResult:
        """Return the selected snapshot, context, or retained receipt."""
        if isinstance(request, m.UnderstandingSnapshotSelector):
            self._store.require_repository(request.repository_id)
            return self._snapshot(
                request.repository_id,
                request.understanding_id,
                request.version,
            )
        if isinstance(request, m.ContextRetrievalSelector):
            context = self._store.get_context(request.context_id)
            self._require_repository(context.repository_id, request.repository_id)
            return m.RetrievedContext(
                context=context,
                observations=self._store.list_context_evidence(request.context_id),
                discovery=self._store.list_context_discovery(request.context_id),
            )
        if isinstance(request, m.ReceiptRetrievalSelector):
            key = m.RecordingKey(
                repository_id=request.repository_id,
                request_id=m.RequestId(request.request_id),
            )
            receipt = self._store.get_receipt(key)
            if receipt is None:
                raise RecordingValidationError(
                    "no retained receipt for "
                    f"{request.repository_id}/{request.request_id}"
                )
            return m.RetrievedReceipt(
                receipt=receipt,
                context=self._store.find_context_by_request(
                    request.repository_id, m.RequestId(request.request_id)
                ),
            )
        raise TypeError(f"unhandled retrieval selector: {type(request).__name__}")

    def _snapshot(
        self,
        repository_id: str,
        understanding_id: str,
        version: int | None,
    ) -> m.RetrievedUnderstanding:
        understanding = self._store.get_understanding(understanding_id)
        self._require_repository(understanding.repository_id, repository_id)
        selected = understanding.current_version.value if version is None else version
        snapshot = self._store.get_version(understanding_id, selected)
        conclusions = self._store.get_version_conclusions(understanding_id, selected)
        return m.RetrievedUnderstanding(
            understanding=understanding,
            version=snapshot,
            conclusions=conclusions,
            support=self._support.evaluate_version(understanding_id, selected),
            challenges=self._store.get_challenges(understanding_id),
        )

    @staticmethod
    def _require_repository(actual: str, requested: str) -> None:
        if actual != requested:
            raise RecordingValidationError(
                f"referenced content belongs to repository {actual!r}, not "
                f"{requested!r}"
            )
