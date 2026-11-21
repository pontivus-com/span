# Span foundations

**Status: binding target for Span 1.0 Beta.** Layer 1 of the pyramid. The [goals](goals.md) above it state
why Span exists; this document states what must hold for those goals to be met.
It defines the constraints that every Span design, contract, implementation,
test, prompt, and release must satisfy. It is not a guide, a proposal, or a
snapshot of current behaviour. Where any plan, ADR, changelog, guide, skill, or
instruction conflicts with the goals or this document, they govern, and the
conflicting statement is superseded in that respect.

## 1. What Span is

Span maintains auditable understanding of a software system.

There are two distinct sources of maintained understanding.

**Empirical understanding** describes observed implementation: source code,
configuration, tests, executions and the semantic conclusions an investigator
establishes from them. Its support can be checked against present evidence.

**Governing understanding** describes what the implementation is intended to
satisfy: purpose, invariants, contracts, functional design and technical design.
Its authority comes from explicit canonical ownership, accepted status,
applicability and derivation, not from execution.

A **surface** remains the semantic unit of retained understanding: a file, symbol,
service or domain boundary. One conclusion belongs to exactly one surface.

A **functional context** is different. It is a declared responsibility or
applicability context used to determine which governing rules apply to one or
more repository paths. Several functional contexts may apply to one path and one
functional context may cover several unrelated paths. Context overlap is normal;
it is not semantic-surface ownership.

The **Functional Pyramid** is the declared graph from repository paths through
functional contexts to canonical governing rules and their higher-layer
dependencies. Span resolves that graph deterministically and keeps unresolved,
unavailable or conflicted relationships explicit. It never infers a functional
context or governing rule from topology, names, similarity or model judgment.

Span is a local MCP server. It never selects a model, calls a model provider,
edits a target repository, runs application tests, or originates repository or
professional authority. It owns evidence identity, declared-authority identity,
Functional Pyramid resolution, support qualification, retention, retrieval and
re-alignment. Repository owners supply authority. The agent or human investigator
owns semantic and conformance judgment.

Surface-bound understanding is retained, reusable and checked. Canonical
governing sources remain canonical sources rather than becoming copied Span
conclusions.

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
safe. Returned support is checked automatically. Required capture and re-alignment
are integrated into the agent's ordinary work (F3, F7, F10).

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

**A9 — The agent follows the instructions it receives.** Ambiguous exemptions
and competing procedures lead to omitted or incorrect lifecycle actions.
*Therefore* delivered guidance must state the required action at its moment of
use and derive it from the same governing contract.

## 3. Principles of the system

Each principle is a requirement, not an aspiration, and each serves one or more
of the [goals](goals.md); the goal table records which. Each names how adherence
is demonstrated. A principle without a test remains binding; the missing test is
debt, never permission.

### F1 — Evidence and authority are distinct

Observed source establishes what was present in the implementation. Declared
governing authority establishes what the repository requires. Neither proof type
substitutes for the other.

A descriptive conclusion is bound to the exact evidence on which it rests. A
normative or conformance conclusion that depends on repository governance is
also bound to the applicable declared authority and Functional Pyramid route.
Canonical governing rules remain at their owning sources; Span records
references and support, not a competing copy of their meaning.

*Demonstration:* a current source observation can coexist with a changed
governing route, and an unchanged governing rule can coexist with changed source.
Span reports those states independently and never promotes one to proof of the
other.

### F2 — Only supported understanding is an answer

An answer may be returned only while every dependency required by its support
contract remains usable. Source, discovery, authority, Functional Pyramid route
and premise dependencies are evaluated by their own rules. Otherwise the result
is a gap that names what changed or could not be established. Stale content may
be retained as history; it is never served as current.

```text
servable(answer, t)  ⇔  ∀ d ∈ deps_required(answer):
                        state(d, t) = CURRENT
```

**Supported means that every dependency required for the conclusion currently
passes its owning check.** It does not mean the interpretation is correct. For
ordinary descriptive conclusions, completeness of explicitly supplied empirical
support remains the investigator's responsibility. For normative conclusions in
a Functional Pyramid repository, the applicable governing route and its
authority dependencies are server-derived and cannot be omitted by the caller.

*Demonstration:* changing a cited byte makes the answer non-servable. Changing an
uncited file does not; the contract states that limit instead of implying a
completeness it cannot check.

### F3 — Established understanding is retained and addressable

Supported semantic understanding established during work is retained through
Span as part of that work. Answers survive the session, are versioned, and are reachable by surface,
question, or reference. Reuse never requires the conversation that produced
them.
*Demonstration:* an agent retains a conclusion during its investigation; a fresh
session with no memory finds and uses it.

### F4 — Change is an obligation, not a notification

When support changes, Span must produce the affected set, the cause, the current
evidence or governing state, and a bounded context for re-establishment. Source
changes and governance changes are equally capable of invalidating dependent
understanding. A change has distinct effects, and they must not be conflated:

- **Containment** — every surface whose boundary contains the changed path is
  marked for re-examination. This is an audit-scope effect; it does not by itself
  invalidate that surface's conclusions.
- **Direct support** — conclusions that cite changed evidence or declared
  authority, or whose server-derived Functional Pyramid route changed, lose
  support.
- **Indirect support** — conclusions whose premises depend on an unsupported
  conclusion lose support transitively.

Marking something stale and stopping does not satisfy this.
*Demonstration:* after a commit, one operation returns the impacted surfaces and
conclusions without re-asking the original questions, and a premise-dependent
conclusion is reported as unsupported even though its own cited file is unchanged.

### F5 — Span composes; the agent means

Span never originates semantic or governing judgment. It validates, stores,
qualifies, retrieves, resolves declared applicability and re-aligns. Semantic
and conformance conclusions are authored by the agent or human investigator;
governing meaning is authored by the repository's declared authority owner.
Span assembles retained conclusions with live evidence and declared governance
and states exactly what is missing.
*Demonstration:* no semantic answer exists without an investigator-recorded
conclusion, and no governing rule exists merely because Span found relevant
prose.

### F6 — The lifecycle is the API

The public API is **obtain, retain, re-align**. Repository binding belongs to
installation; general structural navigation belongs to the host. Declared
Functional Pyramid resolution is Span-owned orientation and support computation,
folded into the lifecycle rather than exposed as another operation. Storage
transitions are private. Validity and governing applicability are attributes of
the lifecycle result, never separate calls the agent must remember to make.
*Demonstration:* every advertised operation maps to a lifecycle verb, and every
answer carries its support state.

### F7 — Capture is part of ordinary work

Span must attach to artifacts the agent already produces — reads, edits, test
runs, conclusions, retries — and must derive everything else itself. Recording
one conclusion may require no information the agent does not already hold at the
moment it concluded.

The agent records its conclusion when established, using the evidence it
already holds; Span derives identity, context and qualification. Capture is
required within the investigation that produces the understanding.

*Demonstration:* recording a conclusion needs no internal identity lookup,
source-body re-submission or separate evidence-admission step.

### F8 — Reuse must beat re-derivation

Span is justified only where reusing retained understanding is cheaper than
maintaining parallel documentation or acting on understanding that has gone
stale. This is a comparative measurement, never a fixed threshold.

```text
value(surface) = cost_maintaining_parallel_explanation(surface)
               + cost_rederiving_governing_applicability(surface)
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

Functional Pyramid applicability is reported separately from semantic ownership.
A path can match several functional contexts without causing surface ambiguity,
and a functional context can cover several disconnected paths.

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

### F11 — Governing applicability is explicit and mechanically composable

A participating repository declares Functional Pyramid contexts, canonical rule
identities, rule layers and governing relationships. Span resolves every
applicable context for the selected semantic scope, including narrower contexts
that intersect a broader directory, service, domain or repository-wide scope,
expands context inheritance and rule derivation, and returns the resulting route
with provenance.

Matching is additive: a more specific context adds obligations and never
silently replaces a broader applicable context. Missing repositories, unknown
rules, cycles, invalid declarations and unresolved governing relationships remain
explicit. Cross-repository authority is followed only through declared stable
identities and configured repository bindings.

Span never infers applicability or precedence from file names, directory
placement, document class, prominence, similarity, source age or structural
adjacency.

For a normative conclusion in a participating repository, Span derives the
applicable Functional Pyramid route and authority dependencies from the
conclusion's semantic scope. The caller cannot omit or override them.

*Demonstration:* the same path may return several applicable contexts and one
complete deduplicated authority route; changing a context or governing edge
makes an affected normative conclusion require reassessment even when its source
bytes did not change.

## 4. Lifecycle responsibilities

The agent's required actions and task-completion boundary are owned by
[lifecycle contract §7](lifecycle-contract.md#required-agent-completion),
derived from F3, F7, F10 and F11. The contract owns the procedure; these
principles govern it.

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
- Code and observed execution remain the source of truth for what the software
  does. Canonical governing sources remain the source of truth for what the
  repository declares must hold. When implementation, governing authority and a
  retained conformance conclusion disagree, preserve the disagreement and fix
  the owning defect rather than allowing one proof type to overwrite another.

## 7. What this document does not define

The operation names and their functional behaviour are defined in the second
layer, [lifecycle contract](lifecycle-contract.md). The behaviour that makes them
deterministic is the [functional design](functional-design.md), layer 3. Wire
schemas, storage model, transport, and host integration are layer 4. Both are
consequences of this document, not inputs to it, and must remain derivable from
the axioms and principles above. When they stop being derivable, they are wrong
even if they are internally consistent.
