"""Support evaluation: gather typed observations, apply core support rules.

The deterministic decisions live in ``span.core.support_rules``. This service
only obtains present observations through ports and composes the resulting
canonical carriers.
"""

from __future__ import annotations

import datetime as _datetime

from span.core import model as m
from span.core import support_rules as _rules
from span.core.recording import RecordingValidationError
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import (
    LifecycleAuthorityResolver,
    LifecycleStorePort,
)

__all__ = ["SupportService"]


def _key(ref: m.ConclusionRevisionRef) -> tuple[str, str, int]:
    return (
        ref.understanding_id.value,
        ref.conclusion_id.value,
        ref.revision.value,
    )


class SupportService:
    """Qualify exact supported content against present evidence."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        evidence: EvidenceSource,
        authority: LifecycleAuthorityResolver,
        clock=None,
    ) -> None:
        self._store = store
        self._evidence = evidence
        self._authority = authority
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))

    def evaluate_version(
        self,
        understanding_id: str,
        version: int | None = None,
    ) -> m.UnderstandingSupport:
        understanding = self._store.get_understanding(understanding_id)
        selected = understanding.current_version.value if version is None else version
        snapshot = self._store.get_version(understanding_id, selected)
        evaluations: list[m.ConclusionSupport] = []
        limitations: list[str] = []
        for ref in snapshot.conclusions:
            evaluation = self.evaluate_revision(ref)
            evaluations.append(m.ConclusionSupport(ref=ref, evaluation=evaluation))
            if evaluation.state is not m.SupportState.CURRENT:
                limitations.append(
                    f"{ref.conclusion_id.value}@{ref.revision.value}: "
                    f"{evaluation.state.value}"
                )
        states = tuple(item.evaluation.state for item in evaluations)
        return m.UnderstandingSupport(
            understanding_id=m.UnderstandingId(understanding_id),
            version=m.UnderstandingVersionNumber(selected),
            conclusions=tuple(evaluations),
            state=_rules.combine_states(states),
            observed_at=self._clock(),
            limitations=tuple(limitations),
        )

    def evaluate_revision(self, ref: m.ConclusionRevisionRef) -> m.SupportEvaluation:
        return self._revision_eval(ref, frozenset())

    def evaluate_command(
        self,
        command: m.RecordCommand,
    ) -> m.SupportEvaluation:
        """Qualify every support dependency declared by a command."""
        dependencies = m.command_support_dependencies(command)
        evaluations = tuple(
            self._dependency_eval(dependency, frozenset())
            for dependency in dependencies
        )
        state = _rules.combine_states(tuple(item.state for item in evaluations))
        reasons = tuple(
            item.reason
            for item in evaluations
            if item.state is not m.SupportState.CURRENT and item.reason
        )
        return _rules.evaluation(
            state, self._clock(), "; ".join(reasons), dependencies=dependencies
        )

    def assert_current(self, command: m.RecordCommand) -> None:
        """Reject acceptance when declared support is not current."""
        evaluation = self.evaluate_command(command)
        if evaluation.state is not m.SupportState.CURRENT:
            raise RecordingValidationError(
                "support is not current: "
                f"{evaluation.state.value}: {evaluation.reason}"
            )

    def assert_observations(
        self, observation_ids: tuple[m.SourceObservationId, ...]
    ) -> None:
        """Reject a run whose cited observation state is no longer current."""
        for observation_id in observation_ids:
            evaluation = self._source_eval(observation_id.value)
            if evaluation.state is not m.SupportState.CURRENT:
                raise RecordingValidationError(
                    "verification observation is not current: "
                    f"{observation_id.value}: {evaluation.state.value}"
                )

    def evaluate_verification(self, run_id: str) -> m.VerificationSupport:
        """Qualify the exact observations cited by one independent run."""
        run = self._store.get_verification_run(run_id)
        observations = tuple(
            m.ObservationSupport(
                observation_id=observation,
                evaluation=self._source_eval(observation.value),
            )
            for observation in run.observations
        )
        state = _rules.combine_states(
            tuple(item.evaluation.state for item in observations)
        )
        limitations = tuple(
            f"{item.observation_id.value}: {item.evaluation.state.value}"
            for item in observations
            if item.evaluation.state is not m.SupportState.CURRENT
        )
        return m.VerificationSupport(
            run=run,
            observations=observations,
            state=state,
            observed_at=self._clock(),
            limitations=limitations,
        )

    # -- dependency evaluation --------------------------------------------

    def _revision_eval(
        self,
        ref: m.ConclusionRevisionRef,
        visited: frozenset[tuple[str, str, int]],
    ) -> m.SupportEvaluation:
        key = _key(ref)
        if key in visited:
            return _rules.evaluation(
                m.SupportState.UNVERIFIABLE, self._clock(), "premise cycle"
            )
        revisions = self._store.get_conclusions(ref.understanding_id.value)
        revision = next(
            (
                item
                for item in revisions
                if item.conclusion_id == ref.conclusion_id
                and item.revision == ref.revision
            ),
            None,
        )
        if revision is None:
            return _rules.evaluation(
                m.SupportState.UNVERIFIABLE,
                self._clock(),
                "conclusion revision no longer exists",
            )
        if isinstance(revision.content, m.WithdrawnConclusion):
            return _rules.evaluation(
                m.SupportState.CURRENT, self._clock(), "explicitly withdrawn"
            )
        dependencies = tuple(revision.content.support)
        evaluations = tuple(
            self._dependency_eval(dependency, visited | {key})
            for dependency in dependencies
        )
        state = _rules.combine_states(tuple(item.state for item in evaluations))
        reasons = tuple(
            item.reason
            for item in evaluations
            if item.state is not m.SupportState.CURRENT and item.reason
        )
        return _rules.evaluation(
            state, self._clock(), "; ".join(reasons), dependencies=dependencies
        )

    def _dependency_eval(
        self,
        dependency: m.SupportDependency,
        visited: frozenset[tuple[str, str, int]],
    ) -> m.SupportEvaluation:
        if isinstance(dependency, m.SourceSupport):
            return self._source_eval(dependency.observation_id.value)
        if isinstance(dependency, m.DiscoverySupport):
            return self._discovery_eval(dependency.observation_id.value)
        if isinstance(dependency, m.PremiseSupport):
            return self._premise_eval(dependency.premise, visited)
        if isinstance(dependency, m.AuthoritySupportDependency):
            return self._authority_eval(dependency.authority)
        raise TypeError("unhandled support dependency: " f"{type(dependency).__name__}")

    def _source_eval(self, observation_id: str) -> m.SupportEvaluation:
        record = self._store.find_source_observation(observation_id)
        observed: str | None = None
        if record is not None:
            _, fingerprints = self._evidence.list_inventory_entries(
                record.repository_id,
                m.EvidenceScope(),
                (record.evidence.locator,),
            )
            observed = fingerprints.get(record.evidence.locator)
        return _rules.source_state(
            record=record,
            observed_fingerprint=observed,
            observed_at=self._clock(),
        )

    def _discovery_eval(self, observation_id: str) -> m.SupportEvaluation:
        record = self._store.find_discovery_observation(observation_id)
        observed: str | None = None
        if record is not None:
            pairs, _ = self._evidence.list_inventory_entries(
                record.repository_id, record.scope
            )
            observed = _rules.discovery_membership_fingerprint(pairs)
        return _rules.discovery_state(
            record=record,
            observed_fingerprint=observed,
            observed_at=self._clock(),
        )

    def _authority_eval(self, binding: m.AuthorityBinding) -> m.SupportEvaluation:
        reference = binding.evidence_ref
        try:
            declared: m.AuthorityBinding | None = self._authority.resolve_authority(
                reference.repository_id, reference.evidence_id.value
            )
        except RecordingValidationError:
            declared = None
        observed: str | None = None
        if declared is not None:
            _, fingerprints = self._evidence.list_inventory_entries(
                reference.repository_id,
                m.EvidenceScope(),
                (declared.evidence_ref.locator,),
            )
            observed = fingerprints.get(declared.evidence_ref.locator)
        return _rules.authority_state(
            recorded=binding,
            declared=declared,
            observed_fingerprint=observed,
            observed_at=self._clock(),
        )

    def _premise_eval(
        self,
        premise: m.ConclusionRevisionRef,
        visited: frozenset[tuple[str, str, int]],
    ) -> m.SupportEvaluation:
        if _key(premise) in visited:
            return _rules.evaluation(
                m.SupportState.UNVERIFIABLE, self._clock(), "premise cycle"
            )
        exists = self._store.has_conclusion_revision(
            premise.understanding_id.value,
            premise.conclusion_id.value,
            premise.revision.value,
        )
        in_membership = False
        if exists:
            understanding = self._store.get_understanding(
                premise.understanding_id.value
            )
            current = self._store.get_version(
                premise.understanding_id.value,
                understanding.current_version.value,
            )
            in_membership = any(
                ref.conclusion_id == premise.conclusion_id
                and ref.revision == premise.revision
                for ref in current.conclusions
            )
        membership = _rules.premise_membership_state(
            exists=exists,
            in_current_membership=in_membership,
            observed_at=self._clock(),
        )
        if membership.state is not m.SupportState.CURRENT:
            return membership
        return self._revision_eval(premise, visited)
