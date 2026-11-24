# Support currency and reassessment

Maintained software knowledge is useful only while the things it depends on
still hold.

Span therefore checks **support currency** separately from the meaning of the
explanation itself. It can tell you that recorded support changed; it does not
pretend that a matching fingerprint proves the explanation semantically true.

## The three support states

| State | What it means for the user |
| --- | --- |
| `CURRENT` | The recorded dependencies still pass their checks. |
| `REASSESSMENT_REQUIRED` | Something the conclusion depends on changed; investigate the conclusion again before reuse. |
| `UNVERIFIABLE` | Span cannot currently establish required support, for example because evidence or declared authority is unavailable or unresolved. |

These states answer **“does the recorded support still hold?”**

They do not answer:

- whether the explanation is complete;
- whether the interpretation was originally correct;
- whether a dispute has been resolved;
- whether a test passed; or
- whether the repository has been fully investigated.

Those are separate questions.

## What can make knowledge need another look?

A conclusion can depend on several kinds of things.

### Source evidence

If recorded source content changes or disappears, a conclusion that depends on
it may require reassessment.

A broad source dependency can make a conclusion sensitive to any change inside
that dependency. Unrelated source does not become stale merely because the
repository has a newer commit or timestamp.

### Project authority

A normative conclusion can depend on project goals, contracts, rules, or design
decisions.

If the declared authority changes, becomes superseded, becomes unavailable, or
stops applying to the software scope, dependent knowledge may need another look
even when the implementation itself did not change.

### Other retained knowledge

A conclusion may depend on another exact conclusion. Correcting, replacing, or
withdrawing that premise can therefore affect downstream knowledge without any
source edit.

### Observed membership

Some conclusions depend on what was found within a declared search or discovery
boundary. If members are added or removed, the conclusion may need
reassessment.

An incomplete or truncated inventory is not silently treated as proof of a
complete boundary.

### The governing route

For repositories using the Functional Pyramid, a conclusion can also depend on
the declared path that connects its software scope to applicable project
guidance.

Changing coverage, relationships, repository bindings, or applicability can
change that route even when the text of the governing rule is unchanged.

The governing route and the governing rule's own content are therefore checked
as separate dependencies.

## What happens after change?

After changing source or relevant project guidance, call `reconsider` with the
changed paths.

Span identifies retained knowledge that may depend on those changes and reports
its present support state.

Inclusion in that result does **not** automatically mean the conclusion is
wrong. Some considered knowledge may remain current.

For knowledge that actually requires reassessment:

- investigate the changed support;
- confirm the meaning if it still holds;
- correct or replace it if the meaning changed; or
- withdraw it if it no longer applies.

A semantic change creates a new captured revision that must go through review
again before shared reuse.

See [Using Span — After code or project guidance changes](usage.md#after-code-or-project-guidance-changes)
for the workflow and [MCP reference — reconsider](mcp.md#reconsider) for the
exact result contract.

## Why Span does not automatically rewrite knowledge

A changed dependency tells Span **where human or agent judgment is needed**. It
does not tell Span what the new meaning should be.

That distinction matters. A source edit may leave an explanation semantically
unchanged, or a one-line change may completely invalidate it.

Span identifies the reassessment obligation and preserves history; the
investigator decides the new meaning.

## Verification has its own currency

An external test or review is retained as an observation with its own support.

If a recorded run says `FAIL`, and its support remains current, that means the
recorded failure evidence still applies. It does not mean the test has somehow
become a pass.

Likewise, changed tested source can make an old run require new verification.

Verification evidence and semantic understanding remain separate so neither is
mistaken for the other.

See [Interpretation and recording](interpretation.md).

## Go deeper

For the conceptual distinction between implementation evidence and project
authority, read [Evidence, authority, and interpretation](authority-trust.md).

For exact support fields, historical retrieval, stale references, and typed
results, use the [MCP reference](mcp.md).
