# Using Span

Investigate a real engineering question, record the useful result, and let the
next session find it with its support attached. The coding agent owns the
reasoning, edits, and test execution. Span owns evidence admission, recording,
version history, and checks on the dependencies the agent declared.

## Ask an ordinary question

After [setup](install.md), discover the canonical `repository_id` from
`tools/list`. Call `understand_question` with that ID, a caller-chosen
`request_id`, a natural-language question, and the paths you need to examine.
For example: “How does this request reach persistence?” over the relevant
service and storage directories.

Span returns saved candidates with live support, an `InvestigationNeeded`
result with inspectable evidence, or an explicit discovery or byte-budget
limit. The agent decides whether a candidate answers the question. Scope
association and term overlap help discovery; they do not prove applicability.
A differently worded question can find associated understanding without its
saved ID, but universal paraphrase matching is not promised.

## Investigate and record

1. Inspect the returned evidence and the material gaps. Use normal source
   search, or `locate` and `neighbors` for structural navigation.
2. Admit additional exact files or line ranges in a batch with
   `evidence_extend`. Read every per-item outcome; missing, unreadable,
   ambiguous, and omitted sources are not accepted support.
3. Record a coherent result with `record_create`. Cite the admitted
   observations, distinguish observed behavior from governing intent, and
   include unresolved questions with their basis as gaps.
4. Preserve the caller identity and full submission before sending. Retrying
   identical content with the same identity returns the retained receipt.
5. Read back the accepted understanding with `understand_retrieve`. Check
   its conclusions, support, and challenges before reporting what was saved.

A question-bound context supplies the create target. An evidence-only context
requires an explicit question and scope when creating understanding. If the
work began outside Span, use `evidence_start` to admit the sources and record
that investigation directly. A preliminary question is optional.

Payloads come from the installed `tools/list` schemas. The [MCP reference](mcp.md)
owns the wire grammar; this guide describes the procedure.

## Reuse in another session

Ask the engineering question over its scope. No prior conversation, original
wording, or saved understanding ID is required for candidate discovery.
Retrieve any referenced detail and assess the result's relevance.

`CURRENT` means the recorded dependencies still check out. It does not certify
that the original interpretation was correct or complete. Open challenges and
gaps remain relevant even when source bytes match.

## After a change

Use your normal tools to edit and test. Call `reassess` for the relevant
understanding and version. Changed supporting bytes, authority, premises, or
recorded discovery membership can require reconsideration. Unrelated changes
leave conclusions current when they do not affect a declared dependency.

Investigate the changed support, admit current evidence, then choose the
matching update: add, confirm, correct, replace, or withdraw. Updates use an
expected version and create a new immutable snapshot; omission is not deletion.
A confirmation records a substantive reassessment, including its current
support and basis. `reassess` alone changes no interpretation.

Use `record_challenge` when an explanation is disputed even with unchanged
sources. Settle or carry the dispute forward explicitly through
`record_update`; a later version or passing test does not settle it.

## Verification and recovery

Record an actual external test or review with `record_verification`, including
its tested observations, outcome, and limitations. `verification_support`
checks those observations today; it does not rerun the test or turn a recorded
failure into a pass.

Recover saved context excerpts or a retained receipt through
`understand_retrieve`. After a lost recording response, resend the exact
identity and content. After receipt retention expires, inspect stored history
before deciding what new work to record. Do not assume that a missing receipt
means the original write never happened.

Hooks are optional notices. Retrieval and recording check support even when
hooks are disabled. See [lifecycle](lifecycle.md), [freshness](freshness.md), and
[onboarding](onboarding-runbook.md) for the responsibilities and limits.
