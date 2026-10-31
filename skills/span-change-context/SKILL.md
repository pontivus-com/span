---
name: span-change-context
description: Prepare a pre-change semantic brief with Span: understand the affected scope, reassess recorded conclusions, and identify open challenges before editing.
---

# Span — change context

Use this skill before a material change. It prepares investigation; it never
approves a change and never writes understanding.

1. Ask `understand_question` for the affected scope. Read saved candidates as
   candidates: the agent judges applicability.
2. For each relevant candidate, call `reassess` with its exact understanding and
   version. Report `CURRENT`, `REASSESSMENT_REQUIRED`, or `UNVERIFIABLE`
   verbatim.
3. Admit the exact sources you will rely on with `evidence_start` or
   `evidence_extend`. Failed or omitted items stay explicit; a source failure is
   never an admitted observation.
4. If a recorded conclusion is disputed, use `record_challenge`. Do not infer a
   resolution from your reading, a test result, or a later version.
5. Use `locate`/`neighbors` only for structural adjacency. They are navigation
   evidence, not authority or causation.
6. State the affected conclusions, the checked differences, the still-open
   questions, and the limitations. Do not invent coverage.

Record what you established only after the change, through the matching
`record_*` tool. Settlement is explicit: `record_update` with named challenge
dispositions, or the challenge remains open.

Keep `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, `UNRESOLVED`, `STALE`, and
`UNVERIFIABLE` verbatim. Missing authority stays missing.

Detail: [Span skill](https://github.com/pontivus-com/span/blob/master/skills/span/SKILL.md),
[freshness](https://github.com/pontivus-com/span/blob/master/docs/freshness.md),
[authority trust](https://github.com/pontivus-com/span/blob/master/docs/authority-trust.md).
