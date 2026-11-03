# Span foundations

**Status: binding.** Layer 1 of the pyramid. The [goals](goals.md) above it state
why Span exists; this document states what must hold for those goals to be met.
It defines the constraints that every Span design, contract, implementation,
test, prompt, and release must satisfy. It is not a guide, a proposal, or a
snapshot of current behaviour. Where any plan, ADR, changelog, guide, skill, or
instruction conflicts with the goals or this document, they govern, and the
conflicting statement is superseded in that respect.

## 1. What Span is

Span maintains an auditable semantic understanding of named code surfaces, to
remove the failure described in the [goals](goals.md): documentation that drifts
statement by statement while readers cannot tell which parts are still true.

Every conclusion is bound to the exact code it describes, so its currency is
known individually. A surface reports its status as a distribution over its
conclusions and its boundary, at whatever granularity it is declared.

A **surface** is a bounded region of code with a meaning: a file, a symbol, a
service, or a domain boundary. Semantic boundaries and domain boundaries both
exist, and surfaces may contain one another. The same question asked at file
scope and at service scope is a different question with a different answer,
because the scope of the code being described is different.

Span is a local MCP server. It never selects a model, calls a provider, edits a
target repository, or runs tests on the user's behalf. It owns evidence
identity, support, validity, retention, retrieval, and re-alignment. The agent
owns meaning.

The purpose is not documentation production. It is to make surface-bound
understanding of code reusable and checked.

## 2. Axioms about the agent

These are facts about the thing that uses Span. They cannot be changed by
design, only accommodated. Each one constrains a different part of the system.

**A1 — The agent forgets.** Sessions end, context compacts, pruning drops
detail. Nothing survives unless it is written outside the model.
*Therefore* durability lives in Span, and every answer must be reconstructable
from Span alone, without the originating transcript.

**A2 — Failure is normal.** Tool errors, restarts, dropped connections, and
retries are ordinary operation, not edge cases.
*Therefore* capture must be idempotent, receipts replayable, and a lost
response must not cost duplicated work.

**A3 — There are several agents.** Parallel sessions, subagents, and worktrees
touch the same repository.
*Therefore* understanding is versioned with compare-and-set semantics; no
conclusion is silently overwritten.

**A4 — The agent does not remember to do bookkeeping.** A rule that depends on
the agent calling the right tool at the right time will be violated.
*Therefore* the server owns every invariant that keeps returned understanding
safe. Alignment must never depend on the agent remembering to ask for it.

**A5 — The agent's account of its own work is unreliable.** It misremembers
what it read and paraphrases inaccurately; the file does not.
*Therefore* bind to source bytes and their content identity, never to the
agent's description of them.

**A6 — The agent's confidence is not evidence.** Self-reported certainty
correlates poorly with correctness.
*Therefore* store support, never self-assessment. No confidence scores, no
scored thresholds.

**A7 — The agent believes what the tool returns.** A warning label does not
neutralise stale content; it is read, then acted on.
*Therefore* the default response must be safe. Safety cannot be opt-in through
a flag the agent may skim past.

**A8 — The agent takes the cheapest path.** If Span costs more than reading the
code, it will not be used; if it blocks without a way forward, it will be worked
around.
*Therefore* Span must beat re-derivation on effort, and every refusal must
carry the evidence, the cause, and the context needed to proceed.

**A9 — The agent acts on partial knowledge and is judged on outcomes.** It must
move before it knows everything, and nobody is scoring it on documentation
coverage.
*Therefore* gaps and partial answers are first-class and immediately usable.
Nothing is required to be documented, and absence of understanding is reported,
never enforced.

## 3. Principles of the system

Each principle is a requirement, not an aspiration, and each serves one or more
of the [goals](goals.md); the goal table records which. Each names how adherence
is demonstrated. A principle without a test remains binding; the missing test is
debt, never permission.

### F1 — Code is the authority

Every stored conclusion is bound to exact source ranges and their content
identity. Understanding is a judgment *about* code, never a substitute for it. No
conclusion exists without evidence.
*Demonstration:* every returned answer can name the bytes it rests on.

### F2 — Only supported understanding is an answer

An answer may be returned only while every **declared** dependency still matches
current source. Otherwise the result is a gap that names what changed. Stale
content may be retained as history; it is never served as current.

```text
servable(answer, t)  ⇔  ∀ d ∈ deps_declared(answer):
                        identity(d, t) = identity(d, t_recorded)
```

**Supported means exactly one thing here: the recorded support is current.** It
does not mean the interpretation is correct, and it does not mean every relevant
dependency was recorded. An uncited caller, configuration, generated file, or
runtime condition is outside the check by construction. Completeness of support
is the agent's responsibility; Span verifies only what was declared.

*Demonstration:* changing a cited byte makes the answer non-servable. Changing an
uncited file does not; the contract states that limit instead of implying a
completeness it cannot check.

### F3 — Understanding is retained and addressable

Answers survive the session, are versioned, and are reachable by surface,
question, or reference. Reuse never requires the conversation that produced
them.
*Demonstration:* a fresh session with no memory finds and uses a prior answer.

### F4 — Change is an obligation, not a notification

When support changes, Span must produce the affected set, the cause, the current
evidence, and a bounded context for re-establishment. A change has three distinct
effects, and they must not be conflated:

- **Containment** — every surface whose boundary contains the changed path is
  marked for re-examination. This is an audit-scope effect; it does not by itself
  invalidate that surface's conclusions.
- **Direct support** — conclusions that cite the changed evidence lose support.
- **Indirect support** — conclusions whose premises depend on an unsupported
  conclusion lose support transitively.

Marking something stale and stopping does not satisfy this.
*Demonstration:* after a commit, one operation returns the impacted surfaces and
conclusions without re-asking the original questions, and a premise-dependent
conclusion is reported as unsupported even though its own cited file is unchanged.

### F5 — Span composes; the agent means

Span never originates semantic judgment. It validates, stores, qualifies,
retrieves, and re-aligns. Semantic content is authored by the agent; Span
assembles it with live evidence and states exactly what is missing.
*Demonstration:* no answer exists without an agent-recorded conclusion.

### F6 — The lifecycle is the API

The public API is **obtain, retain, re-align, bind, navigate**. Storage
transitions are private. Validity is an attribute of every returned answer,
never a separate call the agent must remember to make.
*Demonstration:* every advertised operation maps to a lifecycle verb, and every
answer carries its support state.

### F7 — Capture is a by-product, never a task

Span must attach to artifacts the agent already produces — reads, edits, test
runs, conclusions, retries — and must derive everything else itself. Recording
one conclusion may require no information the agent does not already hold at the
moment it concluded.

The agent supplies what it already has; Span derives what it can.

*Demonstration:* recording a conclusion requires no id to be fetched, no verb to
be selected from a family, and no evidence body to be re-submitted.

### F8 — Reuse must beat re-derivation

Span is justified only where reusing retained understanding is cheaper than
maintaining parallel documentation or acting on understanding that has gone
stale. This is a comparative measurement, never a fixed threshold.

```text
value(surface) = cost_maintaining_parallel_docs(surface)
               + cost_acting_on_stale_understanding(surface)
               − [ cost_capture + cost_query + cost_re_align ]
```

All terms are measured in the same unit for the same task class — agent steps
and tokens. F7 protects the capture term, F2 and F4 protect the re-align term,
F3 protects the query term.
*Demonstration:* a measured task class shows positive value, or Span has no
claim over it.

### F9 — Scope is a surface, and status is reported at its granularity

Understanding is always bound to a surface with a boundary and a kind — either a
declared surface or a path surface. Currency is per conclusion; a surface's
status is a distribution over its conclusions and its boundary, never a single
stamp. A larger surface may contain both current and stale understanding, and
that is expected rather than a defect. Span always reports a surface's status.

Status is not an optional feature. If the product's job is to distinguish current
from stale, it must report which is which, or the reader cannot determine it. If
the scope being described varies, the report is necessarily a distribution,
because an entire domain can hold both current and stale answers at once.

*Demonstration:* the same change produces different, correct status at file and
service granularity, and a surface with no understanding reports its absence
rather than silence.

### F10 — The surface is reachable at the moment of need

The public surface is derived from the agent's lifecycle moments. Every public
operation must be reachable at the moment the agent already recognizes, without
learning Span's internals, and the surface is the smallest set that lets the
agent act. (F6, F7, A4, A8)

*Demonstration:* an agent that has not used Span before, on the product as
delivered, reaches for the lifecycle operation before reading source and the
operation succeeds. F10 is demonstrated on the delivered product; a bare server
registration is not the product.

## 4. What Span must do, and when

The agentic lifecycle is the contract's spine. Span's moments coincide with
artifacts the agent already produces; it never creates a parallel workflow.

| Moment | Span must | Agent must |
| --- | --- | --- |
| **Orient** — a task starts on an area | return current retained understanding for the surface with its currency, or an explicit gap | decide applicability |
| **Investigate** — gap or new area | bind exact evidence to identity and keep it addressable | read, judge, conclude |
| **Record** — understanding reached | validate declared support before acceptance; make acceptance durable and replay-safe | state the answer and its evidence |
| **Reuse** — later session or another agent | return current understanding with its currency, or an explicit gap | act on it |
| **Change** — code moves | produce the affected set with its cause and current evidence | decide what to re-establish |
| **Re-establish** — after change | accept a superseding understanding without losing prior acceptance | re-investigate the changed scope |
| **Dispute** — a challenge is raised | preserve the dispute and never settle it implicitly | resolve it with reasoning |

An unsupported answer returns as: the prior answer marked historical, the exact
changed evidence, the cause, and a context to re-establish. Never a bare
"stale", never stale-as-current, never a dead end.

## 5. Non-goals

Non-goals are scope decisions, not invariants. They are stated once in
[goals](goals.md) §4; this layer adds none of its own.

## 6. Adherence and precedence

- These axioms and principles bind design, contracts, code, tests, prompts,
  skills, documentation, and releases equally.
- A change that cannot satisfy a principle is rejected, not deferred.
- If a principle is wrong, amend this document first, explicitly, with the
  owner's decision. It is never worked around, weakened, or contradicted in
  silence.
- Every change identifies the principle IDs it preserves or affects. Review
  checks the final diff against this document, not only against the change's own
  goals.
- Code remains the source of truth for what the software does. When behaviour
  and this document disagree, one of them is defect; determine which, and fix
  the authoritative one.

## 7. What this document does not define

The operation names and their functional behaviour are defined in the second
layer, [lifecycle contract](lifecycle-contract.md). The behaviour that makes them
deterministic is the [functional design](functional-design.md), layer 3. Wire
schemas, storage model, transport, and host integration are layer 4. Both are
consequences of this document, not inputs to it, and must remain derivable from
the axioms and principles above. When they stop being derivable, they are wrong
even if they are internally consistent.
