# Span documentation

This index separates **user guidance**, **reference**, **binding authority**,
**verification evidence**, and **programme history**. They serve different
purposes and should not be read as one continuous documentation set.

If you are trying to use Span, start with the user path below. The requirements
pyramid and implementation plans are not tutorials.

## Start here

| Need | Read |
| --- | --- |
| Understand what Span is and whether it is useful | [Project README](../README.md) |
| Install and connect it | [Install and connect](install.md) |
| Run a first real investigation | [First investigation](onboarding-runbook.md) |
| Use Span during normal engineering work | [Using Span](usage.md) |
| Look up the exact MCP grammar | [MCP reference](mcp.md) |
| Resolve a conceptual or Beta-limit question | [FAQ](faq.md) |

A normal user should not need the binding design corpus or implementation plans
to operate Span.

## Documentation roles

| Role | Purpose | Authority |
| --- | --- | --- |
| User guidance | Explain how to install, understand, and use Span | Explanatory; does not redefine the product contract |
| Concepts | Explain lifecycle, support, governance, scope, and interpretation | Explanatory; canonical rules remain in the authority layers |
| Operator/reference | Exact protocol, installation, recovery, and host behavior | Reference for the implemented interface; wire grammar is owned by the MCP reference and generated schemas |
| Contributor/developer | Explain code ownership, architecture, ports, and integration surfaces | Derived from the binding design and implementation |
| Binding authority | State why Span exists and the requirements/design it must satisfy | Normative |
| Verification/evidence | Record what a candidate actually demonstrated | Evidence only; passing evidence does not create product authority |
| Programme records | Track implementation campaigns, decisions, and release gates | Planning/history only; not product documentation |

## User guidance

- [Using Span](usage.md) — the ordinary ask → investigate → record → curate →
  reuse → reconsider workflow.
- [First investigation](onboarding-runbook.md) — a first end-to-end working
  session and fresh-session reuse.
- [FAQ](faq.md) — product boundaries, common misconceptions, and Beta limits.
- [Scope and product boundaries](scope.md) — what Span owns and deliberately
  does not own.

## Concepts

These pages explain parts of the same lifecycle model. They are explanatory
material, not additional requirements layers.

- [Agent lifecycle](lifecycle.md) — the lifecycle at a conceptual level.
- [Support currency and reassessment](freshness.md) — CURRENT,
  REASSESSMENT_REQUIRED, and UNVERIFIABLE.
- [Evidence, authority, and interpretation](authority-trust.md) — why
  implementation evidence and governing authority are different.
- [Interpretation and recording](interpretation.md) — agent judgment, support,
  disputes, and recording.
- [Questions, retrieval, and bounds](queries.md) — retrieval paths, exact detail,
  bounds, and continuations.

## Operator and protocol reference

Use these when you need an exact operational answer rather than another product
explanation.

- [Install and connect](install.md)
- [MCP reference](mcp.md) — authoritative public request/result grammar.
- [Backup and recovery](recovery.md)
- [Lifecycle hooks](hooks.md)
- [Glossary](glossary.md)

## Contributor and developer reference

- [Architecture](architecture.md) — implementation ownership and composition.
- [Repository overview](overview.md) — code layout and where changes belong.
- [Port contracts](ports.md)
- [Structural evidence and indexing](indexing.md)
- [Lifecycle vocabulary](taxonomy.md)
- [Agent skills integration](skills.md)
- [Managed agent snippet](agents-snippet.md)
- [Historical design references](design-references.md)
- [Contributing](contributing.md)

These documents help contributors navigate the implementation. They do not
replace the binding authority below.

## Binding authority

Read these when changing Span's requirements, behavior, or implementation
design. They are intentionally separate from the normal user reading path.

1. [Requirements pyramid](requirements-pyramid.md) — governs placement and
   derivation.
2. [Goals](goals.md) — layer 0: outcomes and non-goals.
3. [Foundations](foundations.md) — layer 1: axioms and principles.
4. [Lifecycle contract](lifecycle-contract.md) — layer 2: public lifecycle
   requirements and contract laws.
5. [Functional design](functional-design.md) — layer 3: deterministic behavior.
6. [Technical design](technical-design.md) — layer 4: implementation
   mechanisms.
7. [Offline initialization contract](../INITIALIZATION_CONTRACT.md) — explicit
   administrative initialization/readiness contract.

[Method grounding](method-grounding.md) is supporting evidence for the method;
it is not an authority layer.

## Verification and evidence

- [Acceptance and evidence](acceptance.md) — current candidate evidence first,
  with older candidate evidence retained only for audit.
- [Functional acceptance matrix](functional-acceptance.md) — executable
  traceability from functional requirements to tests.
- [Invariant audit matrix](invariants.md) — cross-layer verification boundaries.
- [Method grounding](method-grounding.md) — external grounding and claim limits.

Verification says what was demonstrated. It does not redefine what Span is
supposed to do.

## Current programme record

The only active implementation campaign on this Beta-3 line is:

- [Span 1.0.0 Beta 3 implementation plan](implementation-plans/1.0.0-beta3.md)

Implementation plans are **programme records, not product documentation**.
Completed plans are retained only for provenance and audit and are deliberately
excluded from the normal reading path. See the
[implementation-plan index](implementation-plans/README.md) when historical
campaign detail is specifically needed.

## Documentation ownership rules

To prevent the corpus from growing back into one undifferentiated body:

- user guides explain the product and workflow; they do not restate the binding
  contract in full;
- the MCP reference and generated schemas own exact public wire grammar;
- binding requirements/design are stated once at their owning pyramid layer;
- contributor docs describe implementation ownership without creating new
  product requirements;
- acceptance documents record evidence, not authority;
- implementation plans record campaigns and release gates, not permanent user
  guidance;
- historical material stays out of the primary navigation unless it is needed
  to explain a current behavior.
