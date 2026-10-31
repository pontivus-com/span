---
name: span-document
description: Build evidence-backed understanding of one scope with Span: ask bounded questions, admit exact sources, record supported conclusions and gaps, and keep a gap ledger.
---

# Span — document one scope

Use this skill when the task is to explain a bounded area, not to change it.

1. Fix the scope. Ask `understand_question` with that exact scope. If Span
   returns `DiscoveryLimit`, narrow the scope explicitly; do not claim the
   repository is empty of understanding.
2. Admit the sources you actually read with one `evidence_start` batch, then
   `evidence_extend` for later files. Every admitted observation is canonical;
   failures and omissions stay visible.
3. Record a coherent investigation result through `record_create`, or update an
   existing understanding with the matching tool. Carry:
   - supported conclusions with their exact observation or authority support;
   - explicit gaps for questions still unanswered;
   - a basis that states what you checked.
4. Never present a gap as a conclusion. Never present an unsupported statement
   as current. An empty scope is a scope decision, not coverage.
5. Settle disputes only through `record_update`. Verification claims use
   `record_verification` with the observations actually tested.
6. Close with `understand_retrieve` on the recorded understanding so the final
   text comes from the stored snapshot, not from memory.

Keep a short gap ledger in your report: each open question, its basis, and the
exact scope it belongs to. Preserve `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`,
`UNRESOLVED`, `STALE`, and `UNVERIFIABLE` verbatim. Missing authority stays missing.

Detail: [Span skill](https://github.com/pontivus-com/span/blob/master/skills/span/SKILL.md),
[scope](https://github.com/pontivus-com/span/blob/master/docs/scope.md),
[lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md).
