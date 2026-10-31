"""Local host-contract probe for the canonical lifecycle grammar.

This is the automated half of the G-0 probe described in the plan §4.4.
It proves that the candidate carriers project to concrete schemas and that
the wire codec accepts/rejects the documented branch shape. It does not
prove host conversion or live delivery; see ``tests/fixtures/host-contract``.
"""

from __future__ import annotations

import datetime
import unittest

from span.core import model as m
from span.core.schema import from_wire, schema_for_request, schema_for_result, to_wire

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)


def _probe_evidence() -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId("ev:probe"),
        repository_id="repo-probe",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/probe.py",
        revision_or_fingerprint="sha256:probe",
    )


def _probe_support() -> tuple[m.SupportDependency, ...]:
    return (m.SourceSupport(observation_id=m.SourceObservationId("obs:probe")),)


def _probe_content() -> dict[str, object]:
    return {
        "statement": "The probe component owns the fixture behavior.",
        "assertion_nature": m.AssertionNature.DESCRIPTIVE,
        "scope": m.EvidenceScope(paths=("src/probe.py",)),
        "support": _probe_support(),
        "basis": m.SemanticBasis(
            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
            summary="read the project-authored fixture",
            input_refs=(_probe_evidence(),),
        ),
    }


def _probe_identity() -> m.RecordingIdentity:
    return m.RecordingIdentity(
        repository_id="repo-probe",
        context_id=m.InvestigationContextId("ctx-probe"),
        submission_id=m.SubmissionId("sub-probe"),
    )


def _probe_create() -> m.CreateUnderstandingCommand:
    return m.CreateUnderstandingCommand(
        identity=_probe_identity(),
        target=m.ExplicitTarget(
            question="What does the probe component do?",
            scope=m.EvidenceScope(paths=("src/probe.py",)),
        ),
        conclusions=(
            m.ProposedConclusion(
                conclusion_id=m.ConclusionId("c-probe"),
                **_probe_content(),
            ),
        ),
    )


def _probe_update() -> m.UpdateUnderstandingCommand:
    return m.UpdateUnderstandingCommand(
        identity=_probe_identity(),
        understanding_id=m.UnderstandingId("u-probe"),
        expected_version=m.UnderstandingVersionNumber(1),
        add=(
            m.ProposedConclusion(
                conclusion_id=m.ConclusionId("c-probe-2"),
                **_probe_content(),
            ),
        ),
        challenge_dispositions=(
            m.UnresolvedChallengeDisposition(
                challenge_id=m.ChallengeId("ch-probe"),
                expected_challenge_revision=m.ChallengeRevision(1),
                remaining_question="Is the probe behavior complete?",
                basis="more evidence is needed",
            ),
        ),
    )


def _probe_verification() -> m.RecordVerificationCommand:
    return m.RecordVerificationCommand(
        identity=_probe_identity(),
        run=m.ProposedVerificationRun(
            repository_id="repo-probe",
            scope=m.VerificationScope(
                description="probe behavior",
                scope=m.EvidenceScope(paths=("src/probe.py",)),
            ),
            observations=(m.SourceObservationId("obs:probe"),),
            command="python3 -m unittest tests.integration.test_host_contract",
            scenario=None,
            outcome=m.VerificationOutcome.PASS,
            observed_at=NOW,
            observer="test-host-contract",
        ),
    )


class CandidateSchemaTest(unittest.TestCase):
    def test_create_request_is_concrete(self):
        schema = schema_for_request(m.CreateUnderstandingCommand)
        self.assertEqual(
            set(schema["required"]),
            {"identity", "target", "conclusions"},
        )
        self.assertIn("ContextBoundTarget__tag", schema["$defs"])
        self.assertIn("ExplicitTarget__tag", schema["$defs"])
        self.assertEqual(schema["type"], "object")
        self.assertNotIn("additionalProperties", schema.get("properties", {}))

    def test_update_request_advertises_every_action(self):
        schema = schema_for_request(m.UpdateUnderstandingCommand)
        for carrier in (
            "ConfirmConclusion",
            "CorrectConclusion",
            "ReplaceConclusion",
            "WithdrawConclusion",
        ):
            self.assertIn(carrier, schema["$defs"])
        properties = schema["properties"]
        for field in ("add", "confirm", "correct", "replace", "withdraw"):
            self.assertIn(field, properties)
        self.assertEqual(
            set(schema["required"]),
            {"identity", "understanding_id", "expected_version"},
        )

    def test_challenge_branches_state_required_fields(self):
        schema = schema_for_result(m.RecordCommand)
        defs = schema["$defs"]
        unresolved = defs["UnresolvedChallengeDisposition__tag"]["properties"]
        self.assertIn("remaining_question", unresolved)
        self.assertIn("basis", unresolved)
        resolved = defs["ResolvedChallengeDisposition__tag"]["properties"]
        self.assertIn("reasoning", resolved)
        self.assertIn("resulting_understanding_id", resolved)
        self.assertIn("resulting_version", resolved)

    def test_record_command_advertises_all_record_variants(self):
        schema = schema_for_result(m.RecordCommand)
        text = str(schema)
        for carrier in (
            "CreateUnderstandingCommand__tag",
            "UpdateUnderstandingCommand__tag",
            "RecordVerificationCommand__tag",
        ):
            self.assertIn(carrier, text)


class WireContractTest(unittest.TestCase):
    def test_create_round_trips_through_compact_wire(self):
        command = _probe_create()
        canonical = m.to_canonical(command)
        wire = to_wire(canonical, m.CreateUnderstandingCommand)
        self.assertNotIn("$type", wire)
        decoded = from_wire(m.CreateUnderstandingCommand, wire)
        self.assertEqual(decoded, command)

    def test_missing_target_tag_rejects(self):
        command = _probe_create()
        wire = to_wire(m.to_canonical(command), m.CreateUnderstandingCommand)
        wire["target"] = {
            "question": "What?",
            "scope": {"paths": [], "evidence_refs": []},
        }
        with self.assertRaises(ValueError):
            from_wire(m.CreateUnderstandingCommand, wire)

    def test_unknown_field_rejects(self):
        command = _probe_create()
        wire = to_wire(m.to_canonical(command), m.CreateUnderstandingCommand)
        wire["unexpected"] = True
        with self.assertRaises(ValueError):
            from_wire(m.CreateUnderstandingCommand, wire)

    def test_missing_branch_field_rejects(self):
        command = _probe_create()
        wire = to_wire(m.to_canonical(command), m.CreateUnderstandingCommand)
        del wire["conclusions"]
        with self.assertRaises(ValueError):
            from_wire(m.CreateUnderstandingCommand, wire)

    def test_update_round_trips_through_compact_wire(self):
        command = _probe_update()
        wire = to_wire(m.to_canonical(command), m.UpdateUnderstandingCommand)
        self.assertEqual(wire["add"][0]["conclusion_id"]["value"], "c-probe-2")
        self.assertEqual(
            wire["challenge_dispositions"][0]["$type"],
            "UnresolvedChallengeDisposition",
        )
        self.assertEqual(
            from_wire(m.UpdateUnderstandingCommand, wire),
            command,
        )

    def test_verification_round_trips_through_compact_wire(self):
        command = _probe_verification()
        wire = to_wire(m.to_canonical(command), m.RecordVerificationCommand)
        self.assertEqual(
            from_wire(m.RecordVerificationCommand, wire),
            command,
        )

    def test_record_union_discriminates_without_guessing(self):
        command = _probe_create()
        encoded = m.to_canonical(command)
        decoded = m.from_canonical(m.RecordCommand, encoded)
        self.assertEqual(decoded, command)
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(
                m.RecordCommand,
                {"$type": "UnknownRecordCommand"},
            )

    def test_unresolved_challenge_requires_remaining_question(self):
        command = _probe_update()
        wire = to_wire(m.to_canonical(command), m.UpdateUnderstandingCommand)
        del wire["challenge_dispositions"][0]["remaining_question"]
        with self.assertRaises(ValueError):
            from_wire(m.UpdateUnderstandingCommand, wire)


if __name__ == "__main__":
    unittest.main()
