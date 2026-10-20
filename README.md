# Span

Establish. Maintain. Expand. Span is evidence-grounded semantic memory: retained meaning with provenance, reusable while its supporting evidence stays current.

## Documentation that can't go stale silently.

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![Platform: Linux verified](https://img.shields.io/badge/platform-Linux%20verified-lightgrey)
![Status: Beta](https://img.shields.io/badge/status-beta-orange)

**Span lets coding agents reuse what is still current about a codebase and re-check only what changed, instead of repeatedly rebuilding their understanding from source.**

Code changes. Documentation and agent memory usually do not.

Nothing normally fails when an architecture note, ownership description, data-flow explanation, or previous agent conclusion stops matching the implementation. It still looks valid.

So coding agents face a bad choice:

- trust context that may be stale; or
- ignore it and reconstruct the system from source, tests, contracts, configuration, and decision records again.

Span gives them a third option.

When an agent establishes how part of a repository works, Span preserves that understanding **together with the repository evidence that supports it**.

When that evidence changes, affected understanding is no longer presented as current. It is flagged **stale** until an agent re-checks it.

Understanding that did not depend on the change stays current and reusable.

> **What is still current stays reusable. What may have changed is made explicit.**

Like tests give code a feedback loop, Span gives codebase understanding one too.

---

## The problem

Coding agents repeatedly pay the cost of understanding the same systems.

A typical session looks like this:

```text
Need to change unfamiliar code
        ↓
Find documentation or previous context
        ↓
Can I still trust it?
        ↓
Read source
Read tests
Follow callers
Inspect contracts
Check configuration
Find governing decisions
        ↓
Reconstruct how the system works
        ↓
Make the change
        ↓
Session ends
        ↓
The next agent starts over
```

Persistent memory only solves part of this problem.

Remembering yesterday's answer helps only if the agent also knows whether today's repository still supports it.

Ordinary documentation does not provide that feedback loop.

A document can have been completely accurate when it was written and still become misleading later without anything visibly failing.

Span changes the maintenance model.

---

## What Span does

Span makes established codebase understanding part of the same change cycle as the implementation it describes.

When an agent investigates a system area, Span can preserve conclusions about things such as:

- what a subsystem or component is responsible for;
- which component owns a decision;
- how data moves from producer to consumer;
- where important boundaries exist;
- which contracts or decisions govern behavior;
- what lifecycle or failure paths exist;
- which downstream areas depend on something;
- what a proposed change may affect.

Those conclusions remain connected to the evidence and semantic premises that supported them.

If that support changes, Span does not silently continue serving the old understanding as current.

It marks the affected understanding stale.

The agent can then re-check only that affected scope.

```text
establish understanding
        ↓
reuse while supporting evidence remains current
        ↓
supporting evidence changes
        ↓
affected understanding becomes STALE
        ↓
agent re-checks the affected scope
        ↓
updated understanding becomes reusable again
```

Unrelated changes do not invalidate unrelated understanding.

That is the central property Span adds:

> **A change underneath established understanding cannot silently leave that understanding looking current.**

---

## An example

Suppose an agent establishes:

```text
AuthenticationService owns session issuance.
```

Span records that conclusion together with the evidence used to establish it.

Later, a refactor changes one of those supporting sources.

Span does **not** claim:

```text
AuthenticationService no longer owns session issuance.
```

It does not know that merely because evidence changed.

Instead, the affected understanding may read back as:

```text
AuthenticationService owns session issuance

STALE

Supporting evidence changed:
  auth/session.py

Re-check this scope before relying on it.
```

That distinction is intentional.

**Stale means "needs another look."**

It does not mean "proven wrong."

Span tracks whether established understanding is still supported by the repository state it depends on. It does not pretend that evidence drift automatically determines semantic truth.

---

## Why this matters

Without Span, the safest coding agent often has to reconstruct the relevant system area from first principles.

That can mean repeatedly:

- searching for definitions;
- following imports and callers;
- opening tests;
- reconstructing producer-to-consumer paths;
- comparing implementation with contracts or ADRs;
- determining responsibility and ownership;
- resolving conflicting documentation;
- checking whether old explanations still apply.

With Span, previously established understanding can be reused while its supporting evidence remains current.

When something changes, the agent does not have to distrust everything.

It can focus its effort on the affected scope.

The intended result is:

- less repeated code archaeology;
- less time and context spent reconstructing known architecture;
- less accidental reliance on stale documentation;
- narrower investigations after changes;
- more continuity between coding agents and sessions.

---

## How Span is different

Span is not intended to replace code search, structural analysis, documentation, or your coding agent.

It fills the gap between them.

| Approach | Persists interpreted understanding | Tracks whether that understanding is still supported | Supports scoped semantic re-check |
| --- | --- | --- | --- |
| Traditional or generated documentation | Yes | Not inherently | No |
| General agent memory | Yes | Not inherently | Not inherently |
| Code search / structural graph | Different purpose | Can keep source or structure current | Not semantic reassessment |
| **Span** | **Yes** | **Yes** | **Yes** |

### Documentation records an answer

Span also records whether the evidence underneath that answer has changed.

### Agent memory remembers

Span separates remembering something from knowing whether it is still safe to treat as current.

### Search helps an agent investigate

Span helps prevent completed investigations from having to be repeated unnecessarily.

### Structural tools keep structure current

That is different from keeping an **interpretation of that structure** current.

A structural tool may establish:

```text
checkout.py calls PaymentService.charge()
```

Span can preserve conclusions such as:

```text
Checkout owns the final purchase-authorization decision.

PaymentService executes payment but does not decide purchase eligibility.

That understanding was established from these implementation,
contract, and authority sources.

One of those supporting sources has changed.

The ownership conclusion therefore needs to be re-checked.
```

Structural freshness and semantic freshness solve different problems.

They are complementary.

---

## Span works with your coding agent

Span is a Model Context Protocol (MCP) server.

It is designed to work with the coding agent you already use.

Current documented host integrations include Codex and OpenCode.

Span does **not**:

- invoke an LLM itself;
- choose a model;
- store model-provider credentials;
- edit source code;
- generate or apply patches;
- run tests;
- autonomously reinterpret your repository in the background.

The coding agent performs the investigation and implementation.

Span provides the persistent semantic state, evidence relationships, freshness checks, bounded investigation tasks, and retrieval surface that make the resulting understanding reusable.

Span data lives outside the repositories it analyzes.

---

## Quick start

### Requirements

Span currently requires:

- Python 3.12 or newer;
- Node.js plus npm (installation provisions the managed structural
  indexer into Span's tools directory; no separate indexer download);
- Linux for the currently verified installation path.

Span uses a managed structural wiring graph as structural evidence.
Provisioning (`initialize_repository`, including server startup
registration and installer verification) builds the provider-owned
index into Span's data directory when it is missing or stale:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

Builds are wiring-only (`--no-deep`, no credentials, no target
writes: `--no-gitignore --no-ignore`). Explicit `refresh` performs at
most one bounded rebuild. Ordinary reads (`status`, `explain`,
`locate`, `neighbors`), hooks, and background paths never build.

macOS and Windows paths are reserved but are not currently verified.

---

## Install

From the workspace containing the Span checkout:

```bash
python3 span/scripts/install-span.py \
  --span-repo <SPAN_REPO> \
  --repo <TARGET_REPO> \
  --data-dir <DATA_DIR>
```

`--repo` may be repeated for multiple target repositories.

If `--data-dir` is omitted, Span uses the platform default.

On Linux:

```text
~/.local/share/span/data
```

Preview installation without changing anything:

```bash
python3 span/scripts/install-span.py \
  --span-repo <SPAN_REPO> \
  --repo <TARGET_REPO> \
  --dry-run
```

Verify an existing installation:

```bash
span-install --verify-only
```

The doctor is read-only. It reports runtime verification, repository
readiness, and supported host-registration observability. OpenCode is
inspected from its JSON config when one is available; Codex registration is
reported as `manual` because Span's read-only contract cannot deterministically
inspect it.

Check that the MCP executable is available:

```bash
span-mcp --help
```

Installation establishes operational readiness only.

It does **not** mean Span already understands your repository.

---

## Connect your coding agent

### Codex

Register Span:

```bash
codex mcp add span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

Then verify:

```bash
codex mcp list
```

Use the absolute path to `span-mcp` if it is not on Codex's `PATH`.

### OpenCode

The installer can configure OpenCode automatically.

The equivalent manual `opencode.json` entry is:

```json
{
  "mcp": {
    "span": {
      "type": "local",
      "command": [
        "span-mcp",
        "--data-dir",
        "<DATA_DIR>",
        "--repo",
        "<TARGET_REPO>"
      ],
      "enabled": true
    }
  }
}
```

Reload OpenCode after changing its MCP configuration.

---

## First use

Once Span is connected:

1. Call `status` with no target.
2. Call `explain` on a known subsystem, component, symbol, or other bounded target.
3. If current understanding already exists, Span can return it with its supporting state.
4. If the required understanding has not yet been established, Span returns a bounded interpretation task.
5. Your coding agent investigates that task with its normal tools and model.
6. The result is submitted with `submit_interpretation`.
7. Continue until the original question resolves or an explicit unresolved requirement remains.

The interaction can therefore be immediate:

```text
explain
   ↓
established current understanding
```

or require investigation:

```text
explain
   ↓
PendingInterpretation
   ↓
coding agent investigates
   ↓
submit_interpretation
   ↓
answer or next bounded task
```

Span does not invoke the model during this process.

The host coding agent performs the reasoning.

Submitting accepted interpretation persists reusable knowledge.

Reading alone does not manufacture new semantic state.

---

## Establish a subsystem once

For an explicit directory or other bounded target that you want agents to understand and reuse, call:

```text
initialize_target
```

with:

- the exact target scope; and
- the objective for understanding it.

Span then coordinates a bounded establishment campaign through the host agent.

The target is partitioned into material areas.

Each material area must end with an explicit disposition rather than disappearing because it was ambiguous, difficult, or unsupported.

Established understanding becomes available to later agents.

Unresolved work remains visible.

See [the onboarding runbook](docs/onboarding-runbook.md) for the complete procedure.

---

## Current and stale are explicit

Span separates **whether an interpretation has been established** from **whether its support is still current**.

Those are different questions.

An interpretation can have been well established previously and still become stale because its evidence changed.

### Freshness

| State | Meaning |
| --- | --- |
| `CURRENT` | The recorded understanding is still supported by the evidence and premises it depends on. |
| `STALE` | Relevant support changed after the understanding was established. Re-check it before treating it as current. |
| `UNVERIFIABLE` | Span cannot currently establish whether the required support remains valid. The gap stays visible. |

### Unresolved work

Span also preserves unresolved investigation instead of forcing an answer.

For example:

| State | Meaning |
| --- | --- |
| `OPEN` | A material unresolved requirement is known and recorded. |
| `PENDING` | Required investigation has not yet been completed. |

The deeper establishment model also preserves ambiguity, conflict, partial support, and unresolved conclusions where appropriate.

The important user-facing behavior is simple:

> **Span does not flatten uncertainty into a confident answer.**

See [the freshness model](docs/freshness.md) and [authority and trust](docs/authority-trust.md) for the complete contract.

---

## How freshness works

Before recorded understanding is presented as current, Span checks the evidence and semantic premises it depends on.

At a high level:

```text
recorded understanding
        ↓
load supporting evidence
        ↓
compare against current repository state
        ↓
check dependent semantic premises
        ↓
CURRENT / STALE / UNVERIFIABLE
```

Span checks fingerprints and coverage dependencies rather than trusting an old timestamp or a previously stored status.

Changed or retired premises can make dependent understanding stale.

If required support cannot be verified, Span reports that limitation rather than presenting the old interpretation as current.

Stored history is not the same thing as effective current state.

---

## Scoped re-checking

When understanding becomes stale, Span does not automatically rewrite it.

Instead:

```text
identify affected stale scope
        ↓
select current evidence for that scope
        ↓
coding agent re-investigates
        ↓
submit interpretation
        ↓
Span validates and reconciles the result
        ↓
fresh state becomes reusable
```

Current unaffected understanding stays untouched.

A failed or incomplete reassessment remains visibly stale, unverifiable, open, or pending as appropriate.

A `refresh` call alone does not prove that understanding has been corrected.

Reassessment does.

---

## Typical development workflow

Span is designed to fit into normal coding work.

```text
ORIENT
retrieve what is already known
        ↓
PREPARE
check likely semantic impact
        ↓
INVESTIGATE
resolve only what is missing, unclear, or stale
        ↓
IMPLEMENT
edit with your normal coding tools
        ↓
VERIFY
run normal tests and review
check semantic currency
        ↓
CLOSE OUT
re-check affected understanding
        ↓
REUSE
the next agent starts from current established context
```

Tests and Span answer different questions.

**Tests check executable behavior.**

**Span checks whether the evidence supporting recorded understanding is still current.**

Passing tests do not automatically prove a semantic interpretation.

Likewise, semantic currency does not replace executable testing.

They participate in the same development cycle while preserving their distinct responsibilities.

See [the lifecycle documentation](docs/lifecycle.md).

---

## MCP operations

Span exposes twelve canonical MCP operations. No semantic_* aliases exist.

| Need | Operation |
| --- | --- |
| Set up repository storage and identity | `initialize_repository` |
| Establish an exact bounded target | `initialize_target` |
| Understand what something is, does, or means | `explain` |
| Assess what a proposed change may affect | `impact` |
| Follow established producer → transformation → consumer semantics | `trace` |
| Determine what governs something | `authority` |
| Inspect readiness, coverage, and currency | `status` |
| Re-check established understanding | `refresh` |
| Submit agent interpretation | `submit_interpretation` |
| Recover one eligible failed interpretation exchange | `reissue_interpretation` |
| Find files, symbols, outlines, or target members | `locate` |
| Inspect bounded structural adjacency | `neighbors` |

Every non-current `status` entry names the next exact step: stale or
unverifiable work uses `refresh` with that entry's exact `SubjectSelector`;
unassessed work uses a question-local `explain`; pending question work
continues only through the continuation returned by the suspending
operation. Never invent a `cont-*` token.

See [the MCP reference](docs/mcp.md) for exact request and response contracts.

---

## Structural navigation vs semantic understanding

Span includes structural navigation because structural information is useful evidence.

Use:

```text
locate
```

for:

- files;
- symbols;
- file outlines;
- target members.

Use:

```text
neighbors
```

for bounded relationships such as:

- callers;
- callees;
- upstream adjacency;
- downstream adjacency.

`locate` takes exactly one mode: `SYMBOL` (requires `query`, optional
target scope; `EXACT` resolves an exact locator to its declaration/name
with no partial matches, `CONTAINS` returns substring matches in provider
order), `FILE_OUTLINE` (one file locator, no target scope or match mode),
or `TARGET_MEMBERS` (exact target scope, no query).

These operations answer structural questions.

They do not establish semantic truth by themselves.

For semantic questions, use:

```text
explain
trace
authority
impact
```

The distinction matters.

A call edge can be mechanically observed.

Ownership, purpose, responsibility, governance, and lifecycle meaning still require interpretation against the relevant evidence and authority.

---

## Evidence and authority

Span deliberately keeps **evidence** and **authority** separate.

Relevant repository evidence may include:

- source code;
- documentation;
- tests;
- configuration;
- contracts;
- specifications;
- decision records;
- project configuration;
- external specifications;
- other repository material.

Finding relevant evidence does not automatically make it authoritative.

For example:

### Source code

Can show what the implementation currently does.

### Tests

Can provide observed verification evidence when actually executed and recorded as such.

The mere existence of a test is not equivalent to a passing verification result.

### Configuration

Can establish a declared or runtime operating choice depending on the evidence available.

### Contracts, specifications, ADRs, and product decisions

May govern what the system is supposed to do where the repository establishes their authority and applicability.

Span can preserve an interpretation of these sources.

It does not silently turn an AI-generated conclusion into governing authority.

Where authority is missing, ambiguous, superseded, or conflicting, that state remains explicit.

See [authority and trust](docs/authority-trust.md).

---

## Change impact

Before a material edit, an agent can use:

```text
impact
```

to evaluate a proposed change against already established understanding.

That can surface more than a structural blast radius.

A structural tool might answer:

```text
What calls this function?
```

Span can reuse established understanding to help answer questions such as:

```text
Which capability owns this behavior?

Which consumers rely on this contract?

Which governing source constrains this change?

Which lifecycle boundary does this cross?

Which established conclusions may need to be re-checked?
```

`impact` returns a change brief.

It is not approval to modify the repository.

---

## Trace

Use:

```text
trace
```

when the important question is not merely "what calls this?" but how an established semantic path works.

For example:

```text
request
  ↓
validation owner
  ↓
canonical carrier
  ↓
transformation
  ↓
consumer
  ↓
terminal state
```

A semantic trace can preserve responsibilities, boundaries, and lifecycle meaning around that path.

Structural adjacency remains evidence underneath it.

---

## Authority

Use:

```text
authority
```

when the question is:

> What actually governs this behavior, contract, responsibility, or decision?

Span can place relevant governing sources and competing evidence side by side while preserving:

- authority kind;
- declared status;
- applicability;
- precedence where explicitly established;
- conflicts;
- missing authority.

It does not reconstruct precedence that the repository never declared.

---

## What Span does not do

Span is deliberately narrow.

It does not:

- edit source code;
- generate or apply patches;
- run tests;
- orchestrate implementation workflows;
- invoke an LLM;
- select models or providers;
- store model credentials;
- automatically interpret repositories in the background;
- automatically make stale understanding current;
- treat structural relationships as semantic truth;
- invent missing product intent;
- invent architectural authority;
- invent professional or methodological authority;
- infer precedence where none is established;
- claim complete understanding of an entire repository;
- claim infallible interpretation;
- claim that persisted knowledge is unconditionally current.

**No claim of infallible interpretation, universal coverage, or autonomous maintenance is made.**

The coding agent remains responsible for investigation and implementation.

Span makes that investigation persistent, evidence-backed, freshness-aware, and reusable.

---

## Span is not a documentation generator

A generated document can have exactly the same failure mode as a handwritten one:

```text
generate explanation
        ↓
repository changes
        ↓
explanation remains readable
        ↓
nothing says it needs another look
```

Span's durable state is not simply a generated Markdown file.

It preserves structured, evidence-backed semantic understanding with explicit freshness and unresolved state.

Documentation or other views can be rendered from that state.

Those rendered artifacts do not become independent authority merely because Span produced them.

---

## Span is not agent conversation memory

Conversation memory can preserve:

```text
The auth service owns sessions.
```

Span is designed to preserve more of the context required to use that conclusion responsibly:

```text
What exactly was established?

Which evidence supported it?

What authority governed it?

Which other semantic conclusions depended on it?

Has the supporting repository state changed?

Can this still be treated as current?

If not, what needs to be re-checked?
```

Persistence alone is not the product.

The relationship between persisted understanding and the current repository is.

---

## Span is not a replacement for code search

Search answers questions such as:

> Where is this implemented?

Structural analysis answers questions such as:

> What calls this?

Span is intended to preserve established answers to questions such as:

> What responsibility does this component own?

> Why does this boundary exist?

> What governs this behavior?

> What is the producer-to-consumer path?

> What may this change affect?

> Is our previous understanding still current?

Search and structural analysis remain useful inputs.

Span makes the resulting interpretation reusable.

---

## Repository readiness is not repository understanding

A successful installation can report that Span is operational.

That is not a claim that Span understands your repository.

`READY` means the repository integration and store are operational.

It does not mean:

```text
every system area has been interpreted
```

or:

```text
all codebase knowledge is complete
```

Normal repository-level `status` reports bounded persisted semantic coverage separately from operational readiness.

That can include:

- current established knowledge;
- stale knowledge;
- unverifiable knowledge;
- incomplete work;
- unresolved work;
- unassessed scope within the bounded returned frontier.

Coverage and readiness are intentionally separate.

---

## Large repositories

Span is bounded by design.

It does not require an unconditional whole-repository semantic crawl.

A large repository may have a bounded or truncated structural evidence inventory while Span remains operational.

Additional evidence can be discovered on demand as agents investigate relevant scopes.

The product therefore does not equate:

```text
READY
```

with:

```text
COMPLETE REPOSITORY UNDERSTANDING
```

Nor does it raise operational bounds merely to create the appearance of exhaustive coverage.

---

## Hooks

Span can integrate with host lifecycle events such as:

```text
session-start
source-changed
session-stop
```

Hooks are report-only.

They can surface conditions such as:

- uninitialized state;
- stale understanding;
- missing coverage;
- moved dependents;
- open work;
- pending work.

They do not:

- initialize semantic knowledge;
- interpret repository meaning;
- invoke a model;
- run a semantic refresh;
- rebuild the structural index;
- make implementation decisions.

When nothing relevant needs attention, hooks stay quiet.

See [`integrations/hosts/triggers.md`](integrations/hosts/triggers.md).

---

## Storage and repository isolation

Span stores its state outside every target repository.

The target repository is evidence.

It is not Span's persistence location.

Span consumes the provider-owned structural index as its structural
source:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

built from the target repository on explicit setup/refresh only.
Generated provider prose stays provider-local and is never semantic
evidence.

Span does not:

- write Span semantic state into the target repository;
- write provider artifacts into the target repository;
- modify the target's structural index artifacts, Markdown cards, or
  dotfiles.

The configured data directory holds Span's persistent state, provider
caches, and exchange data. Provider caches are bounded (one current
index per repository, no per-build append-only artifacts) and are
reused across restarts; remove
`<DATA_DIR>/structural/<repository-id>/` on repository removal or
uninstall. An interrupted build keeps serving the last good index;
a missing or malformed build output provisions as unavailable, never
as empty structural results.

---

## Corrections do not silently fork knowledge

Established understanding can be challenged even when its supporting evidence has not changed.

Span does not resolve that by creating an unrelated second memory and leaving both looking current.

A correction re-examines the existing persisted question scope.

Superseded or withdrawn conclusions remain part of history rather than being silently erased.

The goal is convergence on one explicit current interpretation state, with unresolved disagreement retained where it cannot be resolved.

---

## Investigation stays bounded

When Span does not have enough current understanding to answer a question, it does not silently broaden into an unlimited repository investigation.

Instead, it can return a bounded interpretation task describing:

- the objective;
- the exact scope;
- relevant evidence;
- applicable authority;
- the required semantic question;
- expected result shape;
- unresolved requirements.

The coding agent investigates that bounded unit and submits its result.

The same mechanism is used for:

- initial establishment;
- later expansion;
- stale reassessment;
- explicit correction.

---

## Establish, maintain, expand

Span's behavior can be understood as three recurring activities.

### Establish

Investigate a bounded area and preserve what has been established about:

- purpose;
- ownership;
- contracts;
- flow;
- boundaries;
- authority;
- lifecycle;
- failure behavior.

### Maintain

When supporting evidence changes, affected understanding becomes visibly noncurrent.

The editing agent re-checks the affected scope during closeout.

### Expand

Normal investigations may expose previously unexamined but relevant understanding.

That knowledge can be deliberately established through the same bounded interpretation mechanism.

Expansion is explicit.

Span does not silently turn a local query into an unbounded semantic crawl.

---

## Why not just regenerate everything?

Because most code changes do not invalidate the entire system model.

A broad regeneration approach would throw away one of Span's main advantages: knowing which established understanding remains reusable.

Span instead tries to preserve locality:

```text
change A
   ↓
understanding dependent on A → needs re-checking

understanding dependent on B → remains current
```

That makes semantic maintenance proportional to relevant change rather than repository size.

---

## FAQ

### Is Span deciding whether documentation is true?

No.

Span distinguishes between an interpretation and whether the repository evidence supporting that interpretation is still current.

Changed evidence means the conclusion needs reassessment.

It does not automatically mean the conclusion is false.

---

### Is Span a documentation generator?

No.

Its canonical state is structured semantic understanding, supporting evidence, authority relationships, coverage, and freshness.

Documentation can be produced from that state, but generated prose is not the primary source of truth.

---

### Is Span an LLM service?

No.

Span never invokes a model.

Your coding agent performs semantic interpretation using the model and tools already available to it.

Span validates, persists, relates, retrieves, and tracks the resulting established understanding.

---

### Does Span understand my whole repository after installation?

No.

Installation establishes operational readiness.

Understanding must be established through normal queries or explicit bounded target campaigns.

Coverage stays visible separately from readiness.

---

### Does Span automatically fix stale knowledge?

No.

It identifies that required support changed and keeps the affected understanding noncurrent.

An agent must re-investigate and submit the reassessed result.

---

### Can unrelated changes make everything stale?

They should not.

Freshness is dependency-based and scoped.

Understanding that does not depend on changed evidence should remain current.

---

### What builds the structural index?

Installation provisions a managed structural indexer into Span's tools
directory. Setup and explicit `refresh` build the wiring-only index
into the data directory when needed, with no target writes.

The indexer provides structural evidence.

Span adds persistent semantic interpretation, semantic dependency, authority, freshness, and reassessment on top of structural evidence.

---

### Does Span replace search?

No.

Search remains useful for evidence discovery.

Span reduces the need to repeatedly reinterpret evidence that agents have already examined and established.

---

### Does `READY` mean all knowledge is current?

No.

`READY` is operational readiness.

Semantic coverage and freshness are separate.

---

### Can Span be wrong?

Yes.

Interpretation is performed by coding agents and is not assumed infallible.

Span preserves evidence, uncertainty, conflicts, unresolved questions, and freshness so that interpretations can be challenged and reassessed rather than being treated as unquestionable truth.

---

### Where does Span store data?

Outside the target repositories, in the configured Span data directory.

---

## Documentation

Start here:

- [Onboarding runbook](docs/onboarding-runbook.md) — establish reusable understanding for an exact target.
- [Lifecycle](docs/lifecycle.md) — how Span fits into coding-agent work.
- [MCP reference](docs/mcp.md) — operations and exact transport contracts.
- [Freshness](docs/freshness.md) — current, stale, and unverifiable behavior.
- [Authority and trust](docs/authority-trust.md) — evidence, authority, establishment, and freshness.
- [Interpretation exchange](docs/interpretation.md) — bounded agent investigation.
- [Architecture](docs/architecture.md) — internal architecture and responsibility boundaries.
- [Acceptance](docs/acceptance.md) — acceptance model and evidence.
- [Hooks](docs/hooks.md) — lifecycle hook behavior.
- [Skills](docs/skills.md) — coding-agent integration guidance.
- [Contributing](docs/contributing.md) — development and contribution rules.
- [Full documentation index](docs/README.md).

---

## Architecture

Span is implemented as a standalone semantic repository-intelligence system with a functional core and isolated effects.

At a high level:

```text
repository
   +
structural evidence
   +
governing sources
        ↓
bounded evidence selection
        ↓
agent interpretation task
        ↓
coding agent investigates
        ↓
typed semantic submission
        ↓
validation + reconciliation
        ↓
persistent semantic state
        ↓
freshness / premise checks
        ↓
future agent retrieval
```

Responsibilities remain deliberately separated.

### The target repository owns

- implementation;
- tests;
- contracts;
- configuration;
- governing documentation;
- authority.

### The coding agent owns

- semantic investigation;
- model reasoning;
- implementation work;
- external verification.

### Span owns

- canonical semantic contracts;
- bounded task exchange;
- validation;
- persistence;
- relationships;
- semantic dependencies;
- evidence references;
- authority bindings;
- freshness;
- reconciliation;
- query responses;
- MCP exposure.

Span does not become another implementation or authority source.

---

## Design principles

### Current is earned, not assumed

Persisted understanding is history until its required support is known to remain current.

### Preserve uncertainty

Missing, ambiguous, conflicting, partial, stale, and unverifiable knowledge remain visible.

### Evidence is not authority

Finding a source does not make it governing.

### Authority is not inference

Span does not create project authority because an AI interpretation sounds plausible.

### Structural facts are evidence

A call graph or symbol index can support reasoning without being semantic truth.

### Invalidate narrowly

Relevant changes should affect dependent understanding, not unrelated knowledge.

### Reassess instead of pretending to repair

Stale semantics require interpretation.

They are not deterministically patched from changed filenames or call edges.

### Reading does not write

A query does not silently manufacture durable semantic knowledge.

### History remains history

Corrections and supersession do not erase the fact that earlier understanding existed.

### The agent does the thinking

Span deliberately owns no LLM provider, prompt execution service, or autonomous semantic-maintenance process.

---

## Project status

Span is designed as an independent open-source project.

It may be developed inside a larger private workspace, but the standalone Span product has no required Pontivus, Pontivus Legal, Pontivus Graph, or other proprietary:

- runtime dependency;
- schema dependency;
- fixture dependency;
- build dependency;
- test dependency;
- documentation dependency.

The public product must be understandable and operable without access to private systems.

---

## Contributing

See [the contributing guide](docs/contributing.md).

Changes should preserve Span's central contract:

> **Established understanding remains reusable only while its required supporting evidence remains current.**

In particular, changes should not introduce:

- parallel semantic stores;
- hidden sources of semantic truth;
- automatic model-driven interpretation inside Span;
- silent fallback behavior;
- broad invalidation where dependency-scoped invalidation is possible;
- deterministic semantic inference from structural facts;
- generated documentation as independent authority.

---

## License

Span is licensed under **GNU General Public License v3.0 only (`GPL-3.0-only`)**.

See [LICENSE](LICENSE) for the full license text.

---

## In one sentence

**Span gives coding agents documentation that can't go stale silently: reuse what is still current, and re-check only what changed.**