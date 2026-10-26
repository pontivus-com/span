"""Canonical test factories: one definition per concept (plan §1.3, D7).

Tests describe the fixture they need; they do not re-implement it. Each
factory here is the single definition of one test concept, so a change to a
fixture shape happens once. Test modules import these (optionally through
``functools.partial`` for their repository or file map) instead of defining
per-file copies.
"""

from __future__ import annotations

from span import service as ops
from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)
from tests.support.evidence import FixtureEvidenceSource

__all__ = [
    "query_bounds",
    "subject_id",
    "evidence_ref",
    "semantic_harness",
    "candidate_claim",
    "candidate_claim_for",
    "question_decision",
    "proposed_questions",
    "proposed_question",
    "answered_decision",
    "pending_suspension",
]

REPOSITORY_ID = "repo-1"

_DOCUMENT_SUFFIXES = (".md", ".rst", ".txt", ".yaml", ".yml")


def query_bounds(**overrides: object) -> m.QueryBounds:
    """The standard bounded query, with named overrides."""
    base: dict[str, object] = {
        "max_results": 50,
        "max_depth": 5,
        "max_subjects": 8,
        "max_evidence_units": 24,
        "max_evidence_bytes": 96_000,
        "max_candidate_claims": 64,
        "max_candidate_relationships": 64,
    }
    base.update(overrides)
    return m.QueryBounds(**base)  # type: ignore[arg-type]


def subject_id(
    locator: str = "src/a.py",
    kind: m.SubjectKind = m.SubjectKind.COMPONENT,
    *,
    repository_id: str = REPOSITORY_ID,
) -> m.SubjectId:
    """One canonical subject identity."""
    return m.SubjectId(
        repository_id=repository_id,
        subject_kind=kind,
        canonical_locator=locator,
    )


def evidence_ref(
    path: str = "src/a.py",
    *,
    repository_id: str = REPOSITORY_ID,
    files: dict[str, str] | None = None,
    fingerprint: str | None = None,
    span: str | None = None,
    evidence_id: str | None = None,
    source_kind: m.EvidenceSourceKind | None = None,
) -> m.EvidenceRef:
    """One canonical evidence reference.

    Fingerprints come from the file map when supplied; otherwise the stable
    ``fp-1`` marker keeps tests that do not exercise freshness independent of
    fixture text.
    """
    if evidence_id is None:
        evidence_id = f"ev-{path}"
    if fingerprint is None:
        fingerprint = (
            fingerprint_content(files[path])
            if files is not None and path in files
            else "fp-1"
        )
    if source_kind is None:
        source_kind = (
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(_DOCUMENT_SUFFIXES)
            else m.EvidenceSourceKind.SOURCE_CODE
        )
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(evidence_id),
        repository_id=repository_id,
        source_kind=source_kind,
        locator=path,
        revision_or_fingerprint=fingerprint,
        section_or_span=span,
    )


def semantic_harness(
    repository_id: str,
    files: dict[str, str],
    *,
    subjects: tuple[object, ...] | None = None,
    edges: tuple[object, ...] = (),
    initialize: bool = True,
    db_path: str = ":memory:",
    locator: str = "fixture",
    structural: object | None = None,
    evidence: object | None = None,
    with_agent: dict[str, object] | None = None,
    complete_questions: bool = False,
) -> tuple[object, ...]:
    """Wired structural, evidence, and store fixtures for one repository.

    A caller that needs a provider-backed structural source passes it in; the
    factory still owns evidence, store creation, and the initialization call.
    """
    if structural is None:
        fixture_subjects = subjects
        if fixture_subjects is None:
            fixture_subjects = tuple(
                InMemorySubject(path, m.SubjectKind.COMPONENT, path.rsplit("/", 1)[-1])
                for path in files
            )
        structural = InMemoryStructuralSource(
            repository_id,
            tuple(InMemoryFile(path, content) for path, content in files.items()),
            fixture_subjects,
            edges,
        )
    if evidence is None:
        evidence = FixtureEvidenceSource(repository_id, dict(files))
    store = SqliteSemanticStore(db_path)
    if initialize:
        ops.initialize_repository(
            ops.SemanticInitializeRepositoryRequest(
                repository_locator=locator,
                authority_seeds=(),
            ),
            repository_id=repository_id,
            structural=structural,
            evidence=evidence,
            store=store,
        )
    if with_agent is not None:
        from tests.support.agent_fixture import FixtureAgent

        return (
            structural,
            evidence,
            store,
            FixtureAgent(with_agent, complete_questions=complete_questions),
        )
    return structural, evidence, store


def candidate_claim(
    *,
    key: str = "purpose-main",
    subject: m.SubjectId | None = None,
    note: str = "does things",
    evidence_paths: tuple[str, ...] = ("README.md", "src/main.py"),
    repository_id: str = REPOSITORY_ID,
    files: dict[str, str] | None = None,
    with_authority: bool = True,
    authority_kind: m.AuthorityKind = m.AuthorityKind.REPOSITORY_RULE,
    quoted_span: str = "Does things",
    basis_reason: str = "README states the service purpose",
) -> m.CandidateSemanticClaim:
    """One canonical purpose candidate with its optional authority."""
    claim_subject = subject or subject_id(repository_id=repository_id)
    references = tuple(
        evidence_ref(
            path,
            repository_id=repository_id,
            files=files,
        )
        for path in evidence_paths
    )
    authority = None
    if with_authority:
        authority = m.CandidateAuthority(
            binding=m.AuthorityBinding(
                evidence_ref=references[0],
                authority_kind=authority_kind,
                status=m.AuthorityStatus.ACCEPTED,
            ),
            support=m.AuthoritySupport(
                quoted_span=quoted_span,
                status_section=evidence_paths[0],
                applicability_section=None,
            ),
        )
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=claim_subject,
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue(note, ()),
        evidence=references,
        candidate_authority=authority,
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            basis_reason,
        ),
    )


def candidate_claim_for(
    locator: str,
    evidence: m.EvidenceRef,
    *,
    repository_id: str = REPOSITORY_ID,
    key: str = "purpose",
) -> m.CandidateSemanticClaim:
    """A purpose candidate for one locator citing one prepared reference."""
    return m.CandidateSemanticClaim(
        candidate_key=key,
        subject=subject_id(locator, repository_id=repository_id),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue(f"{locator} serves its module", ()),
        evidence=(evidence,),
        candidate_authority=None,
        basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION, "test"),
    )


def question_decision(
    coverage: m.InterpretationCoverage,
) -> m.SemanticQuestionDecision:
    """Express an authored coverage as the compact decision."""
    return m.SemanticQuestionDecision(
        disposition=coverage.disposition,
        evidence_scope=coverage.evidence_scope,
        resolution_requirements=coverage.resolution_requirements,
        disposition_basis=coverage.disposition_basis,
    )


def proposed_questions(
    *coverages: m.InterpretationCoverage,
) -> tuple[m.ProposedSemanticQuestion, ...]:
    """Express authored coverages as proposed questions."""
    return tuple(
        m.ProposedSemanticQuestion(coverage.question, question_decision(coverage))
        for coverage in coverages
    )


def proposed_question(
    scope: m.SemanticQuestionScope,
    disposition: m.SemanticQuestionDisposition,
    *,
    requirements: tuple[object, ...] = (),
    basis: str = "",
) -> m.ProposedSemanticQuestion:
    """Express one authored question and decision as a proposal."""
    return m.ProposedSemanticQuestion(
        scope,
        m.SemanticQuestionDecision(
            disposition=disposition,
            resolution_requirements=requirements,  # type: ignore[arg-type]
            disposition_basis=basis,
        ),
    )


def answered_decision(
    request: object = None,
    basis: str = "test explicit completion",
) -> m.SemanticQuestionDecision:
    """Explicit ANSWERED completion decision for the bound question.

    Identity, completion, result refs, and question evidence are Span-owned;
    the agent supplies only the disposition and basis.
    """
    return m.SemanticQuestionDecision(
        disposition=m.SemanticQuestionDisposition.ANSWERED,
        disposition_basis=basis,
    )


def pending_suspension(
    structural: object,
    evidence: object,
    store: object,
    continuations: object,
    *,
    repository_id: str,
    locator: str,
) -> PendingInterpretation:
    """Drive one explain request until it suspends on missing semantics."""
    current = ops.explain(
        ops.SemanticExplainRequest(
            repository_id=repository_id,
            target=m.SubjectSelector(None, locator, (), None),
            bounds=query_bounds(),
        ),
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    assert isinstance(current, PendingInterpretation), type(current)
    return current
