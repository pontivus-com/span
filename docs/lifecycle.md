# Agent lifecycle

Span maintains two related lifecycles.

For repositories intended to use project governance, Functional Pyramid
initialization/adoption establishes the governing map first. The ordinary
software-knowledge lifecycle then uses that governing orientation during each
task.

Repositories not using governance can enter the descriptive semantic lifecycle
without ACTIVE participation. UNCONFIGURED remains a valid descriptive state;
EXCLUDED records an explicit non-participation decision.

```text
repository installed and ready
  ├─ governed use → initialize/adopt → ACTIVE + VALID ─┐
  └─ descriptive use → UNCONFIGURED or EXCLUDED ──────┤
                                                       ↓
                                                start a task
                                  ↓
                        ask what is known
                                  ↓
                    investigate what is missing
                                  ↓
                    capture useful understanding
                                  ↓
                 review stable knowledge for reuse
                                  ↓
                    future tasks start better informed
                                  ↓
                    code or guidance changes
                                  ↓
                    reconsider affected knowledge
                                  ↺
```

UNCONFIGURED is not a completed governance setup. ACTIVE + DEGRADED requires
governance repair before the repository is treated as governance-ready.

## Initialize governing context before governed runtime

Functional Pyramid initialization/adoption establishes or revises the explicit
relationship from software scope to canonical project goals, principles,
contracts, functional design, and technical design.

Only explicit lifecycle actions change durable participation. Span does not
infer governance from repository layout, filenames, or semantic similarity, and
it does not copy governing prose into a second authority store.

Once a repository is ACTIVE + VALID, ordinary `ask` resolves the governing
projection for the same software scope as the semantic request. UNCONFIGURED and
EXCLUDED repositories can continue with the descriptive semantic lifecycle
without an ACTIVE governing projection; UNCONFIGURED must be initialized before
the user relies on governed behavior.

See [First investigation](onboarding-runbook.md) for the first setup/use flow and
[Evidence, authority, and interpretation](authority-trust.md) for the proof
model.

## Start from maintained knowledge

A task begins with the exact file, symbol, service, or domain the agent is about
to understand or change.

Span can return maintained knowledge already associated with that surface. If no
reusable knowledge exists, it returns an explicit gap.

For ACTIVE repositories, the same ask also resolves the currently applicable
governing projection.

## Capture what the work establishes

The coding agent investigates with its normal tools and remains responsible for
engineering judgment.

When the work establishes understanding that can help future tasks, the
conclusion can be captured with the evidence that supported it. Capture happens
close to the work while evidence, reasoning, and scope are clear.

Captured knowledge is retained but is not automatically shared with every future
agent.

## Review before shared reuse

A task-local conclusion is a candidate for durable shared knowledge.

A separate reviewer decides whether the captured revision is suitable for reuse.
Wrong, incomplete, duplicated, disputed, or badly scoped meaning is repaired
through the ordinary semantic lifecycle first.

Once a stable revision is accepted for reuse, later agents can receive it while
its required support still holds.

**Working agents capture. Reviewers curate. Span maintains the lifecycle.**

Review and support answer different questions:

- review asks whether this exact semantic revision is suitable for shared reuse;
- support asks whether the things that revision depends on still hold.

Neither is a claim that Span independently proved the interpretation true.

## Reuse in later work

A later session starts from the software surface, not from the previous
conversation or a saved internal identifier.

If reviewed knowledge is still usable, it becomes part of the new task's
starting context. For ACTIVE repositories, governing applicability is resolved
again from current declarations.

Pending review, lost support, and unassessed scope remain explicit.

## Change creates reassessment work

Source and project governance can change independently.

After relevant implementation or authority-source edits, `reconsider` identifies
retained knowledge that may depend on the changed paths. The agent revisits the
affected conclusions rather than re-investigating everything.

If meaning still holds, it can be re-established against current support. If
meaning changed, the corrected revision is captured and reviewed again before
shared reuse.

A Functional Pyramid participation write already returns its own affected
projection and re-establishment contexts; those obligations are disposed
directly.

See [Support currency and reassessment](freshness.md).

## Gaps, disputes, and verification remain explicit

A gap means required understanding has not been established. A dispute means an
interpretation is contested. A verification record says what an external test or
review observed.

Those facts remain separate. A passing test does not automatically settle a
semantic dispute, and a current dependency check does not prove an explanation
complete.

See [Interpretation and recording](interpretation.md).

## Ordinary runtime in one sentence

For governed work, complete initialization/adoption first. The repeating
semantic lifecycle is:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

Exact states and payloads are in the [MCP reference](mcp.md). Installation,
host setup, and store transitions are in [Install and connect](install.md).
