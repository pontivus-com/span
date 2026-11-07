"""Canonical compact record-wire projection tests."""

from __future__ import annotations

import datetime
import unittest

from span.core import model as m
from span.core.identity import conclusion_identity
from span.core.schema import from_wire, schema_for_request
from span.core.schema import record_wire as w

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)


def _evidence(reference: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(reference),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/a.py",
    )


def _authority(reference: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=_evidence(reference),
        authority_kind=m.AuthorityKind.OTHER,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _resolver() -> w.RecordWireResolver:
    return w.RecordWireResolver(
        reference=_evidence,
        authority=_authority,
        source=lambda locator, ranges: m.SourceObservationId("obs-1"),
        discovery=lambda scope: m.DiscoveryObservationId("disc-1"),
        observation_locator=lambda observation_id: "src/a.py",
    )


def _revision(
    conclusion_id: str = "c-1",
    *,
    statement: str = "A does X",
    revision: int = 1,
    assertion_nature: m.AssertionNature = m.AssertionNature.DESCRIPTIVE,
    scope_paths: tuple[str, ...] = ("src/a.py",),
) -> m.ConclusionRevision:
    return m.ConclusionRevision(
        understanding_id=m.UnderstandingId("u-1"),
        conclusion_id=m.ConclusionId(conclusion_id),
        revision=m.ConclusionRevisionNumber(revision),
        originating_version=m.UnderstandingVersionNumber(1),
        content=m.SupportedConclusion(
            statement=statement,
            assertion_nature=assertion_nature,
            scope=m.EvidenceScope(paths=scope_paths),
            support=(m.SourceSupport(observation_id=m.SourceObservationId("obs-1")),),
        ),
        basis=m.SemanticBasis(
            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
            summary="read source",
            input_refs=(),
        ),
    )


class RecordWireSchemaTest(unittest.TestCase):
    def test_component_schemas_are_object_roots(self):
        for root in (
            w.VerificationRunWire,
            w.AddConclusionWire,
            w.ConfirmConclusionWire,
            w.CorrectConclusionWire,
            w.ReplaceActionWire,
            w.WithdrawActionWire,
        ):
            schema = schema_for_request(root)
            self.assertEqual(schema["type"], "object")
            self.assertIn("$defs", schema)

    def test_legacy_parallel_wire_is_absent(self):
        for name in (
            "ConclusionWire",
            "RecordCreateWire",
            "RecordChallengeWire",
            "RecordVerificationWire",
            "ChallengeConclusionRefWire",
            "create_command",
            "challenge_command",
            "verification_command",
        ):
            self.assertFalse(hasattr(w, name), name)

    def test_public_update_grammar_is_compact(self):
        schema = schema_for_request(w.RecordRequestWire)
        defs = schema["$defs"]
        self.assertNotIn("conclusion_id", schema["properties"])
        self.assertNotIn("scope_evidence_refs", schema["properties"])
        add = defs["AddConclusionWire"]
        self.assertNotIn("conclusion_id", add["properties"])
        self.assertNotIn("scope_evidence_refs", add["properties"])
        self.assertNotIn("statement", add["properties"])
        self.assertNotIn("basis_derivation", add["properties"])
        replace = defs["ReplaceActionWire"]
        self.assertNotIn("new_conclusion_id", replace["properties"])
        self.assertNotIn("new_conclusion", replace["properties"])
        self.assertNotIn("old_understanding_id", replace["properties"])
        self.assertNotIn("scope_evidence_refs", replace["properties"])
        self.assertIn("conclusion_id", replace["properties"])
        self.assertNotIn("ReplaceWire", defs)
        self.assertNotIn("WithdrawWire", defs)


def _update_request(
    actions: w.RecordActionsWire,
    *,
    request_id: str = "sub-update",
    understanding_id: str = "u-1",
    expected_version: int = 1,
) -> w.RecordRequestWire:
    return w.RecordRequestWire(
        repository_id="repo-1",
        request_id=request_id,
        context_id="ctx-1",
        kind=m.RecordKind.UNDERSTANDING,
        understanding_id=understanding_id,
        expected_version=expected_version,
        actions=actions,
    )


class ConclusionIdentityTest(unittest.TestCase):
    def test_same_repository_request_role_and_ordinal_are_stable(self):
        self.assertEqual(
            conclusion_identity("repo-1", "req-1", "add", 0),
            conclusion_identity("repo-1", "req-1", "add", 0),
        )

    def test_changed_request_identity_changes_the_identity(self):
        self.assertNotEqual(
            conclusion_identity("repo-1", "req-1", "add", 0),
            conclusion_identity("repo-1", "req-2", "add", 0),
        )

    def test_changed_role_changes_the_identity(self):
        self.assertNotEqual(
            conclusion_identity("repo-1", "req-1", "add", 0),
            conclusion_identity("repo-1", "req-1", "replace", 0),
        )

    def test_changed_ordinal_changes_the_identity(self):
        self.assertNotEqual(
            conclusion_identity("repo-1", "req-1", "add", 0),
            conclusion_identity("repo-1", "req-1", "add", 1),
        )

    def test_unknown_role_rejects(self):
        with self.assertRaisesRegex(ValueError, "role"):
            conclusion_identity("repo-1", "req-1", "confirm", 0)


class RecordActionWireTest(unittest.TestCase):
    def test_create_derives_a_conclusion_id(self):
        proposed = w.flat_conclusion(
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-create",
                context_id="ctx-1",
                kind=m.RecordKind.UNDERSTANDING,
                conclusion="A does X",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            ),
            _resolver(),
            locator="src/a.py",
            default_support=None,
        )
        self.assertEqual(
            proposed.conclusion_id,
            conclusion_identity("repo-1", "sub-create", "create", 0),
        )

    def test_create_defaults_assertion_nature(self):
        proposed = w.flat_conclusion(
            w.RecordRequestWire(
                repository_id="repo-1",
                request_id="sub-create",
                context_id="ctx-1",
                kind=m.RecordKind.UNDERSTANDING,
                conclusion="A does X",
                support=(w.SourceSupportWire(locator="src/a.py"),),
            ),
            _resolver(),
            locator="src/a.py",
            default_support=None,
        )
        self.assertEqual(proposed.assertion_nature, m.AssertionNature.DESCRIPTIVE)

    def test_add_action_derives_a_new_lineage_identity(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="B performs Y.",
                            locator="src/a.py",
                        ),
                    )
                ),
                request_id="sub-add",
            ),
            _resolver(),
        )
        self.assertEqual(len(command.add), 1)
        self.assertEqual(
            command.add[0].conclusion_id,
            conclusion_identity("repo-1", "sub-add", "add", 0),
        )
        self.assertEqual(command.add[0].statement, "B performs Y.")
        self.assertEqual(
            command.add[0].basis.derivation, m.DerivationKind.EXPLICIT_EVIDENCE
        )
        self.assertEqual(command.confirm, ())

    def test_multiple_adds_derive_distinct_ids(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="B performs Y.",
                            locator="src/a.py",
                        ),
                        w.AddConclusionWire(
                            conclusion="C performs Z.",
                            locator="src/a.py",
                        ),
                    )
                )
            ),
            _resolver(),
        )
        self.assertEqual(
            [item.conclusion_id for item in command.add],
            [
                conclusion_identity("repo-1", "sub-update", "add", 0),
                conclusion_identity("repo-1", "sub-update", "add", 1),
            ],
        )

    def test_add_derives_scope_from_locator(self):
        proposed = w._add_proposed(
            w.AddConclusionWire(
                conclusion="B performs Y.",
                locator="src/a.py",
            ),
            _resolver(),
            m.ConclusionId("c:test"),
        )
        self.assertEqual(proposed.scope.paths, ("src/a.py",))

    def test_add_derives_scope_from_one_support_path(self):
        proposed = w._add_proposed(
            w.AddConclusionWire(
                conclusion="B performs Y.",
                support=(w.SourceSupportWire(locator="src/b.py"),),
            ),
            _resolver(),
            m.ConclusionId("c:test"),
        )
        self.assertEqual(proposed.scope.paths, ("src/b.py",))

    def test_add_without_one_derivable_path_rejects(self):
        with self.assertRaisesRegex(ValueError, "requires scope_paths"):
            w._add_proposed(
                w.AddConclusionWire(
                    conclusion="B performs Y.",
                    support=(w.AuthoritySupportWire(authority_ref="auth-1"),),
                ),
                _resolver(),
                m.ConclusionId("c:test"),
            )

    def test_confirm_preserves_current_content(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    confirm=(
                        w.ConfirmConclusionWire(
                            conclusion_id="c-1",
                            locator="src/a.py",
                        ),
                    )
                ),
                request_id="sub-confirm",
            ),
            _resolver(),
            current_revisions=(_revision(),),
        )
        action = command.confirm[0]
        self.assertEqual(action.statement, "A does X")
        self.assertEqual(action.assertion_nature, m.AssertionNature.DESCRIPTIVE)
        self.assertEqual(action.scope.paths, ("src/a.py",))
        self.assertEqual(action.basis.derivation, m.DerivationKind.EXPLICIT_EVIDENCE)

    def test_correct_preserves_omitted_nature_and_scope(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    correct=(
                        w.CorrectConclusionWire(
                            conclusion_id="c-1",
                            conclusion="A now performs Z.",
                            locator="src/a.py",
                        ),
                    )
                ),
                request_id="sub-correct",
            ),
            _resolver(),
            current_revisions=(
                _revision(
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    scope_paths=("src/a.py", "src/b.py"),
                ),
            ),
        )
        action = command.correct[0]
        self.assertEqual(action.statement, "A now performs Z.")
        self.assertEqual(action.assertion_nature, m.AssertionNature.NORMATIVE)
        self.assertEqual(action.scope.paths, ("src/a.py", "src/b.py"))

    def test_replace_derives_old_revision_and_new_identity(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    replace=(
                        w.ReplaceActionWire(
                            conclusion_id="c-1",
                            conclusion="The replacement behaviour is Z.",
                            reason="The prior implementation was superseded.",
                            locator="src/a.py",
                        ),
                    )
                ),
                request_id="sub-replace",
                expected_version=3,
            ),
            _resolver(),
            current_revisions=(_revision(revision=3),),
        )
        action = command.replace[0]
        self.assertEqual(action.old.understanding_id.value, "u-1")
        self.assertEqual(action.old.conclusion_id.value, "c-1")
        self.assertEqual(action.old.revision.value, 3)
        self.assertEqual(
            action.new_conclusion_id,
            conclusion_identity("repo-1", "sub-replace", "replace", 0),
        )
        self.assertEqual(
            action.replacement_basis.derivation,
            m.DerivationKind.SEMANTIC_INTERPRETATION,
        )
        self.assertEqual(
            action.replacement_basis.summary,
            "The prior implementation was superseded.",
        )

    def test_multiple_replacements_derive_distinct_ids(self):
        revisions = (_revision("c-1"), _revision("c-2"))
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    replace=(
                        w.ReplaceActionWire(
                            conclusion_id="c-1",
                            conclusion="Replacement one.",
                            reason="superseded",
                            locator="src/a.py",
                        ),
                        w.ReplaceActionWire(
                            conclusion_id="c-2",
                            conclusion="Replacement two.",
                            reason="superseded",
                            locator="src/a.py",
                        ),
                    )
                )
            ),
            _resolver(),
            current_revisions=revisions,
        )
        self.assertEqual(
            [item.new_conclusion_id for item in command.replace],
            [
                conclusion_identity("repo-1", "sub-update", "replace", 0),
                conclusion_identity("repo-1", "sub-update", "replace", 1),
            ],
        )

    def test_replace_requires_a_current_membership_target(self):
        with self.assertRaisesRegex(ValueError, "not a member of expected_version"):
            w.record_command(
                _update_request(
                    w.RecordActionsWire(
                        replace=(
                            w.ReplaceActionWire(
                                conclusion_id="c-9",
                                conclusion="Z.",
                                reason="superseded",
                                locator="src/a.py",
                            ),
                        )
                    ),
                    request_id="sub-replace",
                    expected_version=2,
                ),
                _resolver(),
                current_revisions=(_revision(),),
            )

    def test_withdraw_derives_the_reason_as_semantic_basis(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    withdraw=(
                        w.WithdrawActionWire(
                            conclusion_id="c-1",
                            reason="The implementation no longer has this behaviour.",
                        ),
                    )
                ),
                request_id="sub-withdraw",
            ),
            _resolver(),
        )
        action = command.withdraw[0]
        self.assertEqual(
            action.basis.derivation, m.DerivationKind.SEMANTIC_INTERPRETATION
        )
        self.assertEqual(
            action.basis.summary,
            "The implementation no longer has this behaviour.",
        )
        self.assertEqual(action.support, ())

    def test_multiple_actions_map_atomically(self):
        command = w.record_command(
            _update_request(
                w.RecordActionsWire(
                    add=(
                        w.AddConclusionWire(
                            conclusion="B performs Y.",
                            locator="src/b.py",
                        ),
                    ),
                    correct=(
                        w.CorrectConclusionWire(
                            conclusion_id="c-1",
                            conclusion="A now performs Z.",
                            locator="src/a.py",
                        ),
                    ),
                ),
                request_id="sub-multi",
            ),
            _resolver(),
            current_revisions=(_revision(),),
        )
        self.assertEqual(
            command.add[0].conclusion_id,
            conclusion_identity("repo-1", "sub-multi", "add", 0),
        )
        self.assertEqual(command.correct[0].conclusion_id.value, "c-1")


class RecordWireMalformedTest(unittest.TestCase):
    def _create(self, **overrides: object) -> dict:
        payload = {
            "repository_id": "repo-1",
            "request_id": "sub-create",
            "kind": "understanding",
            "question": "What?",
            "conclusion": "X.",
            "locator": "src/a.py",
        }
        payload.update(overrides)
        return payload

    def _update(self, **overrides: object) -> dict:
        payload = {
            "repository_id": "repo-1",
            "request_id": "sub-update",
            "kind": "understanding",
            "understanding_id": "u-1",
            "expected_version": 1,
            "actions": {"add": [{"conclusion": "X.", "locator": "src/a.py"}]},
        }
        payload.update(overrides)
        return payload

    def _verification(self, **overrides: object) -> dict:
        payload = {
            "repository_id": "repo-1",
            "request_id": "sub-verification",
            "kind": "verification",
            "run": {
                "repository_id": "repo-1",
                "scope_description": "probe",
                "scope_paths": ["src/a.py"],
                "observations": ["obs-1"],
                "command": None,
                "scenario": None,
                "outcome": "PASS",
                "observed_at": "2026-11-07T00:00:00Z",
                "observer": "test",
            },
        }
        payload.update(overrides)
        return payload

    def _surface(self, **overrides: object) -> dict:
        payload = {
            "repository_id": "repo-1",
            "request_id": "sub-surface",
            "kind": "surface",
            "action": "create",
            "surface": {
                "kind": "SERVICE",
                "locator": "billing",
                "boundary": {"paths": ["src"], "symbols": []},
            },
        }
        payload.update(overrides)
        return payload

    def test_missing_add_conclusion_rejects(self):
        with self.assertRaisesRegex(ValueError, "conclusion"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={"add": [{"locator": "src/a.py"}]},
                ),
            )

    def test_missing_correct_conclusion_rejects(self):
        with self.assertRaisesRegex(ValueError, "conclusion"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "correct": [{"conclusion_id": "c-1", "locator": "src/a.py"}]
                    },
                ),
            )

    def test_missing_replacement_reason_rejects(self):
        with self.assertRaisesRegex(ValueError, "reason"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "replace": [
                            {
                                "conclusion_id": "c-1",
                                "conclusion": "Z.",
                                "locator": "src/a.py",
                            }
                        ]
                    },
                ),
            )

    def test_missing_withdrawal_reason_rejects(self):
        with self.assertRaisesRegex(ValueError, "reason"):
            from_wire(
                w.RecordRequestWire,
                self._update(actions={"withdraw": [{"conclusion_id": "c-1"}]}),
            )

    def test_missing_evidence_rejects(self):
        with self.assertRaisesRegex(ValueError, "evidence mode"):
            from_wire(
                w.RecordRequestWire,
                self._update(actions={"add": [{"conclusion": "X."}]}),
            )

    def test_multiple_evidence_modes_reject(self):
        with self.assertRaisesRegex(ValueError, "more than one"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "add": [
                            {
                                "conclusion": "X.",
                                "locator": "src/a.py",
                                "observation_id": "obs-1",
                            }
                        ]
                    },
                ),
            )

    def test_unknown_fields_reject(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "add": [
                            {
                                "conclusion": "X.",
                                "locator": "src/a.py",
                                "unexpected": True,
                            }
                        ]
                    },
                ),
            )

    def test_old_create_conclusion_id_rejects(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._create(conclusion_id="c-1"),
            )

    def test_old_add_conclusion_id_rejects(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "add": [
                            {
                                "conclusion_id": "c-2",
                                "conclusion": "X.",
                                "locator": "src/a.py",
                            }
                        ]
                    },
                ),
            )

    def test_old_replace_new_conclusion_id_rejects(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "replace": [
                            {
                                "conclusion_id": "c-1",
                                "new_conclusion_id": "c-2",
                                "conclusion": "Z.",
                                "reason": "superseded",
                                "locator": "src/a.py",
                            }
                        ]
                    },
                ),
            )

    def test_scope_evidence_refs_is_not_public(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._create(scope_evidence_refs=[]),
            )
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "correct": [
                            {
                                "conclusion_id": "c-1",
                                "conclusion": "Z.",
                                "locator": "src/a.py",
                                "scope_evidence_refs": [],
                            }
                        ]
                    },
                ),
            )

    def test_irrelevant_update_root_fields_reject(self):
        for field, value in (
            ("question", "Why?"),
            ("surface", {"kind": "FILE", "locator": "src/a.py"}),
            ("scope_paths", ["src/a.py"]),
            ("locator", "src/a.py"),
            ("observation_id", "obs-1"),
            ("support", [{"$type": "SourceSupportWire", "locator": "src/a.py"}]),
            ("assertion_nature", "DESCRIPTIVE"),
            ("conclusion", "X."),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    from_wire(w.RecordRequestWire, self._update(**{field: value}))

    def test_irrelevant_verification_root_fields_reject(self):
        for field, value in (
            ("surface", {"kind": "FILE", "locator": "src/a.py"}),
            ("question", "Why?"),
            ("scope_paths", ["src/a.py"]),
            ("actions", {"add": [{"conclusion": "X.", "locator": "src/a.py"}]}),
            ("understanding_id", "u-1"),
            ("expected_version", 1),
            ("gaps", []),
            (
                "challenge_dispositions",
                [
                    {
                        "$type": "UnresolvedDispositionWire",
                        "challenge_id": "ch-1",
                        "expected_challenge_revision": 1,
                        "remaining_question": "What?",
                        "basis": "Open.",
                    }
                ],
            ),
            ("conclusion", "X."),
            ("locator", "src/a.py"),
            ("observation_id", "obs-1"),
            ("support", [{"$type": "SourceSupportWire", "locator": "src/a.py"}]),
            ("assertion_nature", "DESCRIPTIVE"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    from_wire(w.RecordRequestWire, self._verification(**{field: value}))

    def test_irrelevant_surface_root_fields_reject(self):
        for field, value in (
            ("context_id", "ctx-1"),
            ("question", "Why?"),
            ("scope_paths", ["src/a.py"]),
            ("actions", {"add": [{"conclusion": "X.", "locator": "src/a.py"}]}),
            (
                "run",
                {
                    "repository_id": "repo-1",
                    "scope_description": "probe",
                    "scope_paths": ["src/a.py"],
                    "observations": ["obs-1"],
                    "command": None,
                    "scenario": None,
                    "outcome": "PASS",
                    "observed_at": "2026-11-07T00:00:00Z",
                    "observer": "test",
                },
            ),
            ("understanding_id", "u-1"),
            ("expected_version", 1),
            ("gaps", []),
            (
                "challenge_dispositions",
                [
                    {
                        "$type": "UnresolvedDispositionWire",
                        "challenge_id": "ch-1",
                        "expected_challenge_revision": 1,
                        "remaining_question": "What?",
                        "basis": "Open.",
                    }
                ],
            ),
            ("conclusion", "X."),
            ("locator", "src/a.py"),
            ("observation_id", "obs-1"),
            ("support", [{"$type": "SourceSupportWire", "locator": "src/a.py"}]),
            ("assertion_nature", "DESCRIPTIVE"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    from_wire(w.RecordRequestWire, self._surface(**{field: value}))

    def test_create_accepts_support_and_locator(self):
        request = from_wire(
            w.RecordRequestWire,
            self._create(
                support=[{"$type": "SourceSupportWire", "locator": "src/b.py"}]
            ),
        )
        self.assertIsInstance(request, w.RecordRequestWire)

    def test_create_accepts_support_only_with_explicit_scope(self):
        request = from_wire(
            w.RecordRequestWire,
            self._create(
                locator=None,
                scope_paths=["src/a.py", "src/b.py"],
                support=[
                    {"$type": "SourceSupportWire", "locator": "src/a.py"},
                    {"$type": "SourceSupportWire", "locator": "src/b.py"},
                ],
            ),
        )
        self.assertIsInstance(request, w.RecordRequestWire)

    def test_create_rejects_locator_and_observation(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            from_wire(
                w.RecordRequestWire,
                self._create(observation_id="obs-1"),
            )

    def test_create_rejects_support_and_observation(self):
        with self.assertRaisesRegex(ValueError, "support or observation_id"):
            from_wire(
                w.RecordRequestWire,
                self._create(
                    locator=None,
                    observation_id="obs-1",
                    support=[{"$type": "SourceSupportWire", "locator": "src/a.py"}],
                ),
            )

    def test_old_full_update_grammar_rejects(self):
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_wire(
                w.RecordRequestWire,
                self._update(
                    actions={
                        "add": [
                            {
                                "statement": "X.",
                                "assertion_nature": "DESCRIPTIVE",
                                "scope_paths": ["src/a.py"],
                                "support": [],
                                "basis_derivation": "EXPLICIT_EVIDENCE",
                                "basis_summary": "read",
                                "basis_input_refs": [],
                            }
                        ]
                    },
                ),
            )


class RecordWireCodecTest(unittest.TestCase):
    def test_verification_requires_observations_or_evidence(self):
        with self.assertRaises(ValueError) as raised:
            w.VerificationRunWire(
                repository_id="repo-1",
                scope_description="probe",
                scope_paths=("src/a.py",),
                command="python3 -m unittest",
                scenario=None,
                outcome=m.VerificationOutcome.PASS,
                observed_at=NOW,
                observer="test",
            )
        self.assertIn("observations or evidence", str(raised.exception))
        self.assertIn("obs:", str(raised.exception))
        self.assertIn("locator", str(raised.exception))

    def test_verification_accepts_evidence_only(self):
        run = w.VerificationRunWire(
            repository_id="repo-1",
            scope_description="probe",
            scope_paths=("src/a.py",),
            command="python3 -m unittest",
            scenario=None,
            outcome=m.VerificationOutcome.PASS,
            observed_at=NOW,
            observer="test",
            evidence=(w.SourceSupportWire(locator="src/a.py"),),
        )
        self.assertEqual(run.observations, ())
        self.assertEqual(run.evidence[0].locator, "src/a.py")


if __name__ == "__main__":
    unittest.main()
