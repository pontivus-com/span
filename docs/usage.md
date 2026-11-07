# Using Span

Investigate a real engineering question, record the useful result, and let the
next session find it with its support attached. The coding agent owns the
reasoning, edits, and test execution. Span owns evidence admission, recording,
version history, and checks on the dependencies the agent declared.

## Ask an ordinary question

After [setup](install.md), use the registered `repository_id` — the basename
of the repository root recorded by the installer. `span-install --verify-only`
prints it; it is never a filesystem path. Call `ask` with that ID, a caller-chosen `request_id`, a
natural-language question, and either a surface reference (a declared name or a
path you are looking at) or an exact `surface={kind, locator}`. For example:
“How does this request reach persistence?” with the relevant service surface.

Span returns an `Answer` with current conclusions, their support and evidence,
and surface status; a `Gap` with inspectable evidence, the prior statement as
historical content, and a context; an `AmbiguousSurface` when more than one
granularity matches; or `Unavailable` with its recovery. The surface status
carries `stale_refs`: each names the exact stale conclusion revision, the
understanding version, and its present non-current state. Omitting the question
returns the surface document view. That view
is the normal reuse path: a fresh agent that does not know the exact recorded
question reads it and selects the conclusion it needs. An exact question is a
targeted query; a paraphrase returns `no_match` with a recovery that points back
to the document view. Span never semantic-matches questions. If the gap omitted
evidence to fit the response, follow its continuation. Currentness is checked
against present support; a saved conclusion is never served as current on the
strength of its wording.

## Investigate and record

1. Inspect the returned evidence and the material gaps. Use normal source search
   or host navigation. After code changes, call `reconsider` with the changed
   paths to see every affected surface, why it was considered, and which
   conclusions actually lost support.
2. Record a coherent result with `record(kind="understanding")`. A create is
   one conclusion with exactly one evidence mode: `locator`, the
   `observation_id` from the ask gap, or non-empty `support`. Scope is supplied
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

A question-bound context supplies the create target. Do not also send the
question or scope with that context; the conflict is rejected. If the work began
outside Span, `record` can issue its own context from the supplied scope and
cited locators. A preliminary question is optional.

Payloads come from the installed `tools/list` schemas. The [MCP reference](mcp.md)
owns the wire grammar; this guide describes the procedure.

## Reuse in another session

Read the surface document view first: call `ask` with the surface and no question.
Select the current conclusion that answers the task; no prior conversation or
saved understanding ID is required. If you already know the exact recorded
question, ask it as a targeted query. A paraphrase is a different question and
returns `no_match`; use its recovery to read the document view.

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

A gap whose evidence was omitted carries a continuation. Call `ask` with only
the repository and that continuation until the evidence is complete. Never
fetch or construct a context id. A `stale_refs` entry is a reference, not
content: read the prior statement with
`ask(selector=UnderstandingSnapshotSelector{understanding_id, version})`, then
settle it with `record(kind="understanding", understanding_id=..., expected_version=...,
actions={withdraw|correct|replace: ...})`. After a lost recording response,
resend the exact identity and content. After receipt retention expires, inspect
stored history before deciding what new work to record. Do not assume that a
missing receipt means the original write never happened.

Hooks are optional notices. Retrieval and recording check support even when
hooks are disabled. See [lifecycle](lifecycle.md), [freshness](freshness.md), and
[onboarding](onboarding-runbook.md) for the responsibilities and limits.
