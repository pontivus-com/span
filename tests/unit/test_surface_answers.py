"""Canonical surface and answer carrier invariants (FD-1, FD-5–FD-8, FD-23–FD-29)."""

from __future__ import annotations

import typing
import unittest

from span.core import model as m

KEY = m.SurfaceKey(
    repository_id="repo-1",
    kind=m.SurfaceKind.SERVICE,
    locator="billing",
)
FILE_KEY = m.SurfaceKey(
    repository_id="repo-1",
    kind=m.SurfaceKind.FILE,
    locator="src/billing/rates.py",
)
REF = m.ConclusionRevisionRef(
    understanding_id=m.UnderstandingId("u-1"),
    conclusion_id=m.ConclusionId("c-1"),
    revision=m.ConclusionRevisionNumber(1),
)


def status(surface: m.SurfaceKey = KEY) -> m.SurfaceStatus:
    return m.SurfaceStatus(surface=surface, current=1)


class SurfaceCarrierTest(unittest.TestCase):
    def test_surface_key_is_repository_relative(self) -> None:
        with self.assertRaises(ValueError):
            m.SurfaceKey(
                repository_id="repo-1",
                kind=m.SurfaceKind.FILE,
                locator="/etc/passwd",
            )
        with self.assertRaises(ValueError):
            m.SurfaceKey(
                repository_id="", kind=m.SurfaceKind.SERVICE, locator="billing"
            )

    def test_boundary_rejects_duplicates_and_absolute_paths(self) -> None:
        m.SurfaceBoundary(paths=("src",), symbols=("src/a.py::f",))
        with self.assertRaises(ValueError):
            m.SurfaceBoundary(paths=("src", "src"))
        with self.assertRaises(ValueError):
            m.SurfaceBoundary(paths=("/src",))
        with self.assertRaises(ValueError):
            m.SurfaceBoundary(symbols=("a", "a"))

    def test_parent_must_share_repository_and_not_be_self(self) -> None:
        surface = m.Surface(key=KEY, boundary=m.SurfaceBoundary(paths=("src",)))
        self.assertIsNone(surface.parent)
        other = m.SurfaceKey(
            repository_id="repo-2", kind=m.SurfaceKind.DOMAIN, locator="root"
        )
        with self.assertRaises(ValueError):
            m.Surface(key=KEY, parent=other)
        with self.assertRaises(ValueError):
            m.Surface(key=KEY, parent=KEY)
        with self.assertRaises(ValueError):
            m.Surface(key=KEY, boundary_version=0)

    def test_status_counts_are_non_negative(self) -> None:
        m.SurfaceStatus(surface=KEY)
        with self.assertRaises(ValueError):
            m.SurfaceStatus(surface=KEY, stale=-1)
        with self.assertRaises(ValueError):
            m.SurfaceStatus(surface=KEY, current=True)


class AnswerCarrierTest(unittest.TestCase):
    def test_answer_requires_current_content_and_matching_status(self) -> None:
        m.Answer(
            surface=KEY,
            question="What does billing do?",
            conclusions=(REF,),
            status=status(),
        )
        with self.assertRaises(ValueError):
            m.Answer(
                surface=KEY,
                question="What does billing do?",
                conclusions=(),
                status=status(),
            )
        with self.assertRaises(ValueError):
            m.Answer(
                surface=KEY,
                question="What does billing do?",
                conclusions=(REF,),
                status=status(FILE_KEY),
            )

    def test_gap_reasons_are_exhaustive(self) -> None:
        self.assertEqual(
            {reason.value for reason in m.GapReason},
            {"invalidated", "unverifiable", "unassessed", "no_match"},
        )
        m.Gap(
            surface=KEY,
            question="What?",
            reason=m.GapReason.NO_MATCH,
            recovery="ask the same surface without a question",
        )
        m.Gap(
            surface=KEY,
            reason=m.GapReason.UNASSESSED,
            recovery="read the cited evidence, then record the conclusion",
        )
        with self.assertRaises(ValueError):
            m.Gap(surface=KEY, reason=m.GapReason.UNASSESSED, recovery="")

    def test_ambiguity_requires_distinct_candidates(self) -> None:
        m.AmbiguousSurface(
            reference="billing",
            candidates=(KEY, FILE_KEY),
            missing_decision="choose granularity",
        )
        with self.assertRaises(ValueError):
            m.AmbiguousSurface(
                reference="billing",
                candidates=(KEY,),
                missing_decision="choose granularity",
            )
        with self.assertRaises(ValueError):
            m.AmbiguousSurface(
                reference="billing",
                candidates=(KEY, KEY),
                missing_decision="choose granularity",
            )

    def test_unavailable_and_rejected_are_actionable(self) -> None:
        m.Unavailable(operation="ask", failure="store down", recovery="retry")
        with self.assertRaises(ValueError):
            m.Unavailable(operation="ask", failure="", recovery="retry")
        m.Rejected(
            identity="repo/req-1",
            required_action="use a new request id",
            cause_kind=m.RejectionCauseKind.VALIDATION,
            cause="duplicate request id",
        )
        with self.assertRaises(ValueError):
            m.Rejected(
                identity="",
                required_action="retry",
                cause_kind=m.RejectionCauseKind.VALIDATION,
                cause="bad identity",
            )
        with self.assertRaises(ValueError):
            m.Rejected(
                identity="repo/req-1",
                required_action="retry",
                cause_kind=m.RejectionCauseKind.VALIDATION,
                cause="",
            )
        with self.assertRaises(ValueError):
            m.Rejected(
                identity="repo/req-1",
                required_action="retry",
                cause_kind=m.RejectionCauseKind.VERSION_CONFLICT,
                cause="stale version",
                current_version=0,
            )
        with self.assertRaises(ValueError):
            m.Rejected(
                identity="repo/req-1",
                required_action="retry",
                cause_kind=m.RejectionCauseKind.SURFACE_CONFLICT,
                cause="stale boundary",
                current_boundary_version=0,
            )


class ChangeCarrierTest(unittest.TestCase):
    def test_changed_surface_requires_reasons(self) -> None:
        changed = m.ChangedSurface(surface=KEY, reasons=(m.ChangeReason.CONTAINMENT,))
        self.assertEqual(changed.reasons, (m.ChangeReason.CONTAINMENT,))
        self.assertEqual(changed.conclusions, ())
        with self.assertRaises(ValueError):
            m.ChangedSurface(surface=KEY, reasons=())
        with self.assertRaises(ValueError):
            m.ChangedSurface(
                surface=KEY,
                reasons=(m.ChangeReason.DIRECT, m.ChangeReason.DIRECT),
            )

    def test_truncated_walk_cannot_claim_unaffected(self) -> None:
        m.Changed(surfaces=(m.ChangedSurface(KEY, (m.ChangeReason.DIRECT,)),))
        with self.assertRaises(ValueError):
            m.Changed(truncated=True, unaffected=(FILE_KEY,))

    def test_result_unions_are_closed(self) -> None:
        ask = set(typing.get_args(m.AskResult))
        record = set(typing.get_args(m.RecordResult))
        reconsider = set(typing.get_args(m.ReconsiderResult))
        self.assertEqual(
            ask,
            {
                m.Answer,
                m.Gap,
                m.AmbiguousSurface,
                m.RetrievedUnderstanding,
                m.RetrievedReceipt,
                m.EvidencePage,
                m.Unavailable,
            },
        )
        self.assertEqual(
            record,
            {
                m.UnderstandingRecorded,
                m.VerificationRecorded,
                m.SurfaceDeclared,
                m.Rejected,
                m.Unavailable,
            },
        )
        self.assertEqual(
            reconsider,
            {m.Changed, m.Challenged, m.Rejected, m.Unavailable},
        )
