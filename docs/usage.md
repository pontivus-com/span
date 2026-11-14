# Using Span

Investigate a real engineering question, record the useful result, and let the
next session find it with its support attached. The coding agent owns the
reasoning, edits, and test execution. Span owns evidence admission, recording,
version history, and checks on the dependencies the agent declared.

## Ask a surface

After [setup](install.md), use the registered `repository_id` — never a
filesystem path. The normal reuse call is surface-first and carries no question
or request identity:

```json
{"repository_id": "repo-1", "surface": {"kind": "FILE", "locator": "src/service.py"}}
```

Use `reference` only when the path or declared name resolves unambiguously. A
pure obtain returns the current surface document view grouped by recorded
question, or an honest `Gap` with status, historical content where applicable,
and concrete source pointers. It creates no investigation context and delivers no
source body automatically.

When the exact recorded question is already known, use
`RecordedQuestionSelector`. It matches exact text on the exact surface and is
not semantic search; a non-match is `Gap/unassessed`. When source bytes are
needed, make an explicit evidence-admission `ask` with the same surface or
reference, a new `request_id`, and non-empty `evidence`. That call returns the
same Answer/Gap classification plus admission outcomes, exact deliveries, a
bound context reference, and a continuation when selected evidence is deferred.

Currentness is checked against present support. A saved conclusion is never
served as current on the strength of its wording.

## Investigate and record

1. Inspect the returned evidence and the material gaps. Use normal source search
   or host navigation. After code changes, call `reconsider` with the changed
   paths to see every affected surface, why it was considered, and which
   conclusions actually lost support.
2. Record a coherent result with `record(kind="understanding")`. A create is
   one conclusion with exactly one evidence mode: `locator`, the
   `observation_id` returned by explicit evidence admission, or non-empty `support`. Scope is supplied
   or derived independently through `scope_paths`, the context, or a surface.
   Cite what you already hold.
   Distinguish observed behavior from governing intent, and include unresolved
   questions with their basis as gaps. Use `actions.add`, `confirm`, `correct`,
   `replace`, or `withdraw` for an update; each action names the conclusion and
   exactly one evidence mode, and Span derives the old revision and unchanged
   content metadata.
3. Preserve the caller identity and full submission before sending. Retrying
   identical content with the same identity returns the retained receipt.
4. Read back an exact snapshot or receipt with `ask(selector=...)` if needed.
   Check its conclusions, support, and challenges before reporting what was
   saved.

A bound context from explicit evidence admission or `reconsider` supplies its
recording namespace/scope. Do not send an independent repository override or a
conflicting explicit target with that context; the conflict is rejected. If the work began
outside Span, `record` can issue its own context from the supplied scope and
cited locators. This direct-create capability does not waive consultation before deriving
understanding; follow [the required lifecycle](lifecycle-contract.md#required-agent-completion).

Payloads come from the installed `tools/list` schemas. The [MCP reference](mcp.md)
owns the wire grammar; this guide describes the procedure.

## Reuse in another session

Read the surface document view first: call `ask` with the surface and no
request identity. Select the current conclusion that answers the task; no prior
conversation or saved understanding ID is required. If you already know the
exact recorded question, use `RecordedQuestionSelector`. A different or
paraphrased question does not similarity-match; unmatched exact selection is
`Gap/unassessed`.

`CURRENT` means the recorded dependencies still check out. It does not certify
that the original interpretation was correct or complete. Open challenges and
gaps remain relevant even when source bytes match.

## After a change

Use your normal tools to edit and test. Call `reconsider` with the paths you
just edited. It returns every affected surface, the reasons each was considered,
and each conclusion's present support. `surfaces` is the complete containment
set: a surface with no `conclusions` is containment-only. Act only on
conclusions whose state is `REASSESSMENT_REQUIRED` or `UNVERIFIABLE`; a
`CURRENT` conclusion in the set needs no work. Keep the returned order.
Changed source bytes, authority, premises, or discovery membership can produce
actual loss; unrelated changes leave conclusions current when they do not
affect a declared dependency.

Investigate the changed support, then record the matching update. Updates use an
expected version and create a new immutable snapshot; omission is not deletion.
A confirmation records a substantive reassessment with its current support; a
correction supplies the new statement and complete support; a replacement adds
its reason. `Changed` already carries the expected version and context, so the
continuation into `record` needs no extra `ask`.

Raise a challenge through `reconsider` when an explanation is disputed even with
unchanged sources. Settle or carry the dispute forward explicitly through
`record` with named dispositions; a later version or passing test does not
settle it.

## Verification and recovery

Record an actual external test or review with `record(kind="verification")`,
including its tested evidence, outcome, and limitations. A run needs
`observations` or `evidence`; either is accepted. It applies to the surfaces
**within** its declared scope (a scope path covers a surface path when it is
equal or an ancestor); record it against the surface it verifies. `ask` returns
the applicable verification runs and their present qualification; it does not
rerun the test or turn a recorded failure into a pass.

An explicit evidence admission may carry a continuation. Call `ask` with only
that continuation until the selected evidence is complete. Never
fetch or construct a context id. A `stale_refs` entry is a reference, not
content: read the prior statement with
`ask(selector=UnderstandingSnapshotSelector{understanding_id, version})`, then
settle it with `record(kind="understanding", understanding_id=..., expected_version=...,
actions={withdraw|correct|replace: ...})`. After a lost recording response,
resend the exact identity and content. After receipt retention expires, inspect
stored history before deciding what new work to record. Do not assume that a
missing receipt means the original write never happened.

Hooks deliver lifecycle reminders. Retrieval and recording check support even when
hooks are disabled. See [lifecycle](lifecycle.md), [freshness](freshness.md), and
[onboarding](onboarding-runbook.md) for the responsibilities and limits.
