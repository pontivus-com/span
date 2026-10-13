"""E-13A: canonical target-accounting types, identity, and store (Addendum E)."""

import unittest

from span.core import model as m
from span.shell.sqlite_store import SqliteSemanticStore


def _ref(eid="ev-a", loc="a.py", repo="r1"):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(eid),
        repository_id=repo,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=loc,
    )


def _sid(loc="a", repo="r1"):
    return m.SubjectId(
        repository_id=repo,
        subject_kind=m.SubjectKind.OTHER,
        canonical_locator=loc,
    )


class TargetIdentityTest(unittest.TestCase):
    def test_canonicalize_and_stable_id(self):
        scope = m.EvidenceScope(paths=("b.py", "./a.py", "a.py"), evidence_refs=())
        cs1, obj1 = m.canonicalize_target_scope("r1", scope, "  goal  ")
        self.assertEqual(obj1, "goal")
        self.assertEqual(cs1.paths, ("a.py", "b.py"))
        tid1 = m.derive_target_id("r1", cs1, obj1)
        scope2 = m.EvidenceScope(paths=("a.py", "b.py"), evidence_refs=())
        cs2, obj2 = m.canonicalize_target_scope("r1", scope2, "goal")
        self.assertEqual(m.derive_target_id("r1", cs2, obj2), tid1)
        self.assertTrue(tid1.value.startswith("tgt-"))

    def test_union_and_section_reject(self):
        scope = m.EvidenceScope(paths=("a.py",), evidence_refs=(_ref("ev-b", "b.py"),))
        cs, _ = m.canonicalize_target_scope("r1", scope, "goal")
        self.assertEqual(cs.paths, ("a.py",))
        self.assertEqual(len(cs.evidence_refs), 1)
        bad = m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-x"),
            repository_id="r1",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="x.py",
            section_or_span="L1",
        )
        with self.assertRaises(ValueError):
            m.canonicalize_target_scope(
                "r1", m.EvidenceScope(evidence_refs=(bad,)), "goal"
            )

    def test_outcome_exclusivity(self):
        with self.assertRaises(ValueError):
            m.TargetInventoryAccount(evidence_ref=_ref())
        with self.assertRaises(ValueError):
            m.TargetInventoryAccount(
                evidence_ref=_ref(),
                assigned_area_subjects=(_sid(),),
                exclusion_basis=m.SemanticBasis(
                    derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
                    summary="x",
                ),
            )

    def test_inventory_fingerprint_membership_only(self):
        a = m.EvidenceInventoryItem(evidence_ref=_ref("ev-a", "a.py"), content_fingerprint="c1")
        b = m.EvidenceInventoryItem(evidence_ref=_ref("ev-b", "b.py"), content_fingerprint="c2")
        f1 = m.target_inventory_fingerprint((a, b))
        b2 = m.EvidenceInventoryItem(evidence_ref=_ref("ev-b", "b.py"), content_fingerprint="CHANGED")
        f2 = m.target_inventory_fingerprint((a, b2))
        self.assertEqual(f1, f2)

    def test_store_round_trip_and_ttl(self):
        store = SqliteSemanticStore(":memory:")
        try:
            scope, obj = m.canonicalize_target_scope(
                "r1", m.EvidenceScope(paths=("a.py",)), "goal"
            )
            tid = m.derive_target_id("r1", scope, obj)
            assoc = m.TargetAssociation(
                target_id=tid,
                repository_id="r1",
                target_scope=scope,
                objective=obj,
                inventory_fingerprint="fp1",
            )
            store.write_index_batch(m.CanonicalIndexBatch(target_associations=(assoc,)))
            loaded = store.load_target_association("r1", tid)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.target_id, tid)
            self.assertEqual(loaded.objective, "goal")
        finally:
            store.close()


class RetiredFieldTransitionTest(unittest.TestCase):
    def test_strict_decoder_rejects_retired_field(self):
        from span.core.model import CanonicalDecodeError

        ref = _ref()
        sid = _sid()
        clean = m.to_canonical(
            m.TargetInventoryAccount(
                evidence_ref=ref, assigned_area_subjects=(sid,)
            )
        )
        assert isinstance(clean, dict)
        legacy = dict(clean)
        legacy["observed_content_fingerprint"] = "deadbeef"
        with self.assertRaises(CanonicalDecodeError):
            m.from_canonical(m.TargetInventoryAccount, legacy)

    def test_store_loads_legacy_row_at_persistence_boundary(self):
        import json

        store = SqliteSemanticStore(":memory:")
        try:
            scope, obj = m.canonicalize_target_scope(
                "r1", m.EvidenceScope(paths=("a.py",)), "goal"
            )
            tid = m.derive_target_id("r1", scope, obj)
            acc = m.TargetInventoryAccount(
                evidence_ref=_ref(), assigned_area_subjects=(_sid(),)
            )
            assoc = m.TargetAssociation(
                target_id=tid, repository_id="r1", target_scope=scope,
                objective=obj, area_subjects=(_sid(),),
                target_questions=(), inventory_accounting=(acc,),
                inventory_fingerprint="fp1",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(assoc,))
            )
            row = store._db.execute(
                "SELECT canonical_json FROM target_associations "
                "WHERE repository_id=? AND target_id=?",
                ("r1", tid.value),
            ).fetchone()
            assert row is not None
            data = json.loads(row[0])
            for entry in data.get("inventory_accounting", []):
                if entry.get("$type") == "TargetInventoryAccount":
                    entry["observed_content_fingerprint"] = "deadbeef"
            store._db.execute(
                "UPDATE target_associations SET canonical_json=? "
                "WHERE repository_id=? AND target_id=?",
                (json.dumps(data, sort_keys=True), "r1", tid.value),
            )
            store._db.commit()
            loaded = store.load_target_association("r1", tid)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(len(loaded.inventory_accounting), 1)
            self.assertEqual(
                loaded.inventory_accounting[0].assigned_area_subjects,
                (_sid(),),
            )
            self.assertFalse(
                hasattr(
                    loaded.inventory_accounting[0],
                    "observed_content_fingerprint",
                )
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()

class TargetValidationTest(unittest.TestCase):
    def test_account_and_question_validation(self):
        from span.core import validation as v
        repo = "r1"
        ref = m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-a"), repository_id=repo,
            source_kind=m.EvidenceSourceKind.SOURCE_CODE, locator="a.py",
        )
        sid = m.SubjectId(repository_id=repo, subject_kind=m.SubjectKind.OTHER, canonical_locator="a")
        ctx = v.ValidationContext(
            allowed_claim_kinds=tuple(m.ClaimKind),
            allowed_relationship_kinds=tuple(m.RelationshipKind),
            known_evidence_ids=frozenset({"ev-a"}),
            known_subject_ids=(sid,),
            evidence_fingerprints={"ev-a": "fp"},
        )
        ok_acc = m.TargetInventoryAccount(evidence_ref=ref, assigned_area_subjects=(sid,))
        ok = v.validate_target_inventory_account(
            ok_acc, ctx, current_inventory_ids=frozenset({"ev-a"}),
            expected_evidence_id="ev-a", admitted_area_ids=(sid,),
        )
        self.assertTrue(ok.ok)
        bad = v.validate_target_inventory_account(
            ok_acc, ctx, current_inventory_ids=frozenset({"ev-other"}),
        )
        self.assertFalse(bad.ok)
        q = m.SemanticQuestionScope(
            scope_root=sid, subject=sid,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="s", materiality_basis="b",
        )
        self.assertTrue(v.validate_target_questions((q,), admitted_area_ids=(sid,)).ok)
        other = m.SubjectId(repository_id=repo, subject_kind=m.SubjectKind.OTHER, canonical_locator="z")
        q2 = m.SemanticQuestionScope(
            scope_root=other, subject=other,
            question_class=m.SemanticQuestionClass.CQ_01,
            question_slice="s", materiality_basis="b",
        )
        self.assertFalse(v.validate_target_questions((q2,), admitted_area_ids=(sid,)).ok)


class TargetStatusTest(unittest.TestCase):
    def _harness(self):
        from span import service as ops
        from span.shell.agent_exchange.continuations import ContinuationStore
        from span.shell.evidence import FixtureEvidenceSource
        from span.shell.structural.memory import (
            InMemoryFile, InMemoryStructuralSource, InMemorySubject,
        )
        repo = "tgt-status-1"
        files = {"a.py": "A=1\n", "b.py": "B=2\n"}
        structural = InMemoryStructuralSource(
            repo, tuple(InMemoryFile(p, c) for p, c in files.items()),
            (InMemorySubject("a.py", m.SubjectKind.COMPONENT, "a"),
             InMemorySubject("b.py", m.SubjectKind.COMPONENT, "b")), (),
        )
        evidence = FixtureEvidenceSource(repo, dict(files))
        store = SqliteSemanticStore(":memory:")
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator="fixture",
                structural_provider_config="memory:test", authority_seeds=(),
            ),
            repository_id=repo, structural=structural, evidence=evidence, store=store,
        )
        return ops, structural, evidence, store, repo, ContinuationStore()

    def test_unassessed_then_incomplete_and_hook_fast_reject(self):
        ops, structural, evidence, store, repo, conts = self._harness()
        try:
            bounds = m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64)
            missing = m.TargetId("tgt-deadbeefdeadbeef")
            ans = ops.status(
                ops.SemanticStatusRequest(repository_id=repo, target=missing, bounds=bounds),
                structural=structural, evidence=evidence, store=store,
                continuations=conts,
            )
            assert isinstance(ans, m.SemanticAnswer)
            assert isinstance(ans.content, m.StatusContent)
            self.assertEqual(ans.content.target_disposition, m.SemanticCoverageDisposition.UNASSESSED)
            pending = ops.initialize_target(
                ops.SemanticInitializeTargetRequest(
                    repository_id=repo,
                    target=m.EvidenceScope(paths=("a.py", "b.py"), evidence_refs=()),
                    objective=" goal ", bounds=bounds,
                ),
                structural=structural, evidence=evidence, store=store,
                continuations=conts,
            )
            # Association created with canonical objective + deterministic ID.
            scope, obj = m.canonicalize_target_scope(
                repo, m.EvidenceScope(paths=("a.py", "b.py"), evidence_refs=()), " goal ")
            tid = m.derive_target_id(repo, scope, obj)
            loaded = store.load_target_association(repo, tid)
            self.assertIsNotNone(loaded)
            ans2 = ops.status(
                ops.SemanticStatusRequest(repository_id=repo, target=tid, bounds=bounds),
                structural=structural, evidence=evidence, store=store,
                continuations=conts,
            )
            assert isinstance(ans2, m.SemanticAnswer)
            assert isinstance(ans2.content, m.StatusContent)
            # No accounting yet → INCOMPLETE (not CURRENT).
            self.assertEqual(ans2.content.target_disposition, m.SemanticCoverageDisposition.INCOMPLETE)
            with self.assertRaises(Exception):
                ops.status(
                    ops.SemanticStatusRequest(
                        repository_id=repo, target=tid, bounds=bounds,
                        mode=m.StatusMode.HOOK_FAST,
                    ),
                    structural=structural, evidence=evidence, store=store,
                    continuations=conts,
                )
        finally:
            store.close()


class TargetRetentionTest(unittest.TestCase):
    def test_expiry_reap_and_touch(self):
        import datetime

        from span.shell.sqlite_store import SqliteSemanticStore

        base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        now = [base]

        def _clock():
            return now[0]

        store = SqliteSemanticStore(
            ":memory:", target_retention_days=30, utc_now=_clock
        )
        try:
            scope, obj = m.canonicalize_target_scope(
                "r1", m.EvidenceScope(paths=("a.py",)), "goal"
            )
            tid = m.derive_target_id("r1", scope, obj)
            assoc = m.TargetAssociation(
                target_id=tid, repository_id="r1", target_scope=scope,
                objective=obj, inventory_fingerprint="fp1",
            )
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(assoc,))
            )
            self.assertIsNotNone(store.load_target_association("r1", tid))
            # Touch before expiry extends TTL.
            now[0] = base + datetime.timedelta(days=10)
            store.write_index_batch(
                m.CanonicalIndexBatch(target_associations=(assoc,))
            )
            self.assertIsNotNone(store.load_target_association("r1", tid))
            # Past extended expiry reads as absent without mutating.
            now[0] = base + datetime.timedelta(days=41)
            self.assertIsNone(store.load_target_association("r1", tid))
            # Event-driven reap on open deletes the expired row.
            self.assertEqual(store._reap_expired_target_associations(), 1)
            self.assertIsNone(store.load_target_association("r1", tid))
        finally:
            store.close()
