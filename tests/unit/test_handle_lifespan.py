"""Handles state their own lifespan.

A cursor is a position that survives a restart; a continuation is an assignment
that does not; a campaign handle is durable with a retention window. The carrier
says which, so a restarted session cannot mistake an expired continuation for a
resumable page.
"""

import unittest

import datetime as _datetime

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.service.answers import ANSWER_ASSEMBLER
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.sqlite_store import SqliteSemanticStore
from tests.support.agent_exchange import (
    REPO,
    _bounds,
    _harness,
)


class LifespanVocabularyTest(unittest.TestCase):
    def test_cursor_is_a_durable_position(self):
        self.assertIs(m.CURSOR_LIFESPAN.kind, m.HandleKind.DURABLE)
        self.assertIs(m.CURSOR_LIFESPAN.scope, m.HandleScope.REPOSITORY)
        self.assertIs(m.CURSOR_LIFESPAN.recovery, m.HandleRecovery.RESTART_LISTING)
        self.assertIsNone(m.CURSOR_LIFESPAN.expires_at)

    def test_continuation_is_an_ephemeral_assignment(self):
        self.assertIs(m.CONTINUATION_LIFESPAN.kind, m.HandleKind.EPHEMERAL)
        self.assertIs(m.CONTINUATION_LIFESPAN.scope, m.HandleScope.PROCESS)
        self.assertIs(
            m.CONTINUATION_LIFESPAN.recovery, m.HandleRecovery.REISSUE_OPERATION
        )

    def test_every_answer_states_the_cursor_lifespan(self):
        answer = ANSWER_ASSEMBLER.build(
            answer_id=m.AnswerId("a-1"),
            intent=m.SemanticIntent.EXPLAIN,
            repository_state=m.RepositoryState(
                repository_id="r",
                revision_id=None,
                dirty=False,
                state_fingerprint="fp",
                observed_at=_now(),
            ),
            content=m.ExplainContent(),
            bounds=_bounds(),
        )
        self.assertEqual(answer.bound_info.lifespan, m.CURSOR_LIFESPAN)

    def test_pending_interpretation_is_ephemeral(self):
        pending = PendingInterpretation(continuation="cont-1", request=_empty_request())
        self.assertEqual(pending.lifespan, m.CONTINUATION_LIFESPAN)


class CampaignHandleTest(unittest.TestCase):
    def test_campaign_handle_reports_its_deadline(self):
        store = SqliteSemanticStore(":memory:")
        structural, evidence, _unused, agent = _harness()
        try:
            ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator="fixture", authority_seeds=()
                ),
                repository_id=REPO,
                structural=structural,
                evidence=evidence,
                store=store,
            )
            association = m.TargetAssociation(
                target_id=m.TargetId("tgt-1"),
                repository_id=REPO,
                target_scope=m.EvidenceScope(paths=("src",), evidence_refs=()),
                objective="wire lifespan",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(association,))
            )
            answer = ops.status(
                ops.SemanticStatusRequest(
                    repository_id=REPO,
                    target=m.TargetId("tgt-1"),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=ContinuationStore(),
            )
            lifespan = answer.content.target_handle_lifespan
            self.assertIsNotNone(lifespan)
            self.assertIs(lifespan.kind, m.HandleKind.DURABLE)
            self.assertIs(lifespan.scope, m.HandleScope.REPOSITORY)
            self.assertIs(lifespan.recovery, m.HandleRecovery.REINITIALIZE_TARGET)
            self.assertIsNotNone(lifespan.expires_at)
        finally:
            store.close()


def _now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _empty_request() -> m.SemanticInterpretationRequest:
    from tests.support.agent_exchange import _harness as _make

    structural, evidence, store, agent = _make()
    try:
        pending = ops.explain(
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, "src/flow.py", (), None),
                bounds=_bounds(),
            ),
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=ContinuationStore(),
        )
    finally:
        store.close()
    assert isinstance(pending, PendingInterpretation)
    return pending.request


if __name__ == "__main__":
    unittest.main()
