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

A **document placement** is different. It is a declared canonical document at
one pyramid layer together with the explicit repository-relative directory scope
where it applies. Several placements may apply to one directory, a placement
applies to every descendant of its scope, and one document may be placed at
several layers or scopes. Placement overlap is normal; it is not semantic-surface
ownership.

The **Functional Pyramid** is the declared graph from repository directories
through document placements to their higher-layer dependencies. Span resolves
that graph deterministically and keeps unresolved, unavailable or conflicted
relationships explicit. It never infers a placement, scope, document or
relationship from topology, names, similarity or model judgment.

Span is a local MCP server. It never selects a model, calls a model provider,
edits a target repository, runs application tests, or originates repository or
professional authority. It owns evidence identity, declared-authority identity,
Functional Pyramid resolution, support qualification, retention, retrieval and
re-alignment. Repository owners supply authority. The agent or human investigator
owns semantic and conformance judgment.

Surface-bound understanding is retained and checked. A captured semantic
revision becomes ordinary shared reusable knowledge only after explicit
curation; canonical governing sources remain canonical sources rather than
becoming copied Span conclusions.

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
safe. Returned support and reuse eligibility are checked automatically.
Required capture and re-alignment are integrated into ordinary work, and
forgetting a later curation step cannot cause captured-only content to be served
as shared knowledge (F2, F3, F7, F10, F13).

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

**A10 — The task agent's objective is narrower than shared knowledge maintenance.**
A working agent is primarily optimizing for the task it is performing. It may
establish a locally supported conclusion without establishing that the same
statement is the right abstraction, granularity or durable shared knowledge for
future agents. *Therefore* evidence-near capture and shared-reuse qualification
are distinct acts. Span must not infer curation from support currency, task
completion, confidence or authorship.

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
normative conclusion—including a conformance judgment, which is recorded as
`assertion_nature=NORMATIVE`—that depends on repository governance is also
bound to the applicable declared authority and Functional Pyramid route.
Canonical governing rules remain at their owning sources; Span records
references and support, not a competing copy of their meaning.

*Demonstration:* a current source observation can coexist with a changed
governing route, and an unchanged governing rule can coexist with changed source.
Span reports those states independently and never promotes one to proof of the
other.

### F2 — Only supported and curated understanding is an answer

A conclusion may be returned as ordinary shared Answer content only while its
exact semantic revision has been explicitly curated and every dependency
required by its support contract remains usable. Source, discovery, authority,
Functional Pyramid route and premise dependencies are evaluated by their own
rules. Captured-only and non-current content may be retained and audited; neither
is served as shared Answer content.

```text
servable(conclusion, t)
    ⇔ curation(conclusion.revision) = CURATED
    ∧ ∀ d ∈ deps_required(conclusion):
          state(d, t) = CURRENT
```

**Supported** means that every required dependency currently passes its owning
check. **Curated** means only that an explicit external reviewer accepted that
exact semantic revision for shared reuse. Neither means the interpretation is
intrinsically correct. For ordinary descriptive conclusions, completeness of
explicitly supplied empirical support remains the investigator's responsibility.
For normative conclusions in an ACTIVE Functional Pyramid repository, the
applicable governing route and its authority dependencies are server-derived and
cannot be omitted by the caller.

*Demonstration:* a newly recorded CURRENT conclusion remains non-servable until
curated; changing a cited byte makes a curated conclusion non-servable; changing
an uncited file does not.

### F3 — Established understanding is retained and addressable

Supported semantic understanding established during work is retained through
Span as part of that work, whether or not it is yet curated for shared reuse.
Understandings survive the session, are versioned, and are reachable by surface,
question or reference without the originating conversation. Ordinary reuse is
governed by F2.
*Demonstration:* an agent retains a captured conclusion during its investigation;
a later reviewer can retrieve it without the transcript, curate the exact
revision, and a fresh session can then reuse it.

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

Governance effects follow the Functional Pyramid instance rather than stopping
at a repository boundary. A changed authority, placement, governing edge or
repository availability in one member repository can therefore directly affect
normative understanding retained in another member repository when the declared
graph connects them.

Marking something stale and stopping does not satisfy this.
*Demonstration:* after a commit, one operation returns the impacted surfaces and
conclusions without re-asking the original questions, including a
cross-repository normative dependent when the declared governing route crosses
repository boundaries; a premise-dependent conclusion is likewise reported as
unsupported even though its own cited file is unchanged.

### F5 — Span composes; the agent means

Span never originates semantic or governing judgment. It validates, stores,
qualifies, retrieves, resolves declared applicability and re-aligns. Semantic
conclusions, including normative conformance judgments, are authored by an agent
or human investigator; curation decisions are authored by an external agent or
human reviewer; governing meaning is authored by the repository's declared
authority owner. Span records the curation act but does not decide that a
semantic statement is good enough to publish.
*Demonstration:* no semantic answer exists without an investigator-recorded,
curated conclusion, and no governing rule exists merely because Span found
relevant prose.

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
required within the investigation that produces the understanding. Capture does
not itself publish the conclusion as shared knowledge: a semantic create or
change begins captured and requires a separate curation act before ordinary
reuse. Curation cannot be bundled into the same semantic write that creates or
changes meaning.

*Demonstration:* recording a conclusion needs no internal identity lookup,
source-body re-submission or separate evidence-admission step, and a newly
accepted CURRENT capture remains absent from ordinary Answer content until
curated.

### F8 — Reuse must justify its overhead in real work

Span adds lifecycle work: obtaining context, capturing and curating useful
conclusions, and re-aligning them after change. That overhead is justified only
when the resulting working context is useful enough to improve real engineering
work over time.

Beta evaluates that product value through sustained adopter use on real tasks,
including cold investigation, fresh-session reuse, implementation changes,
governance changes, recovery, and ordinary failure. Friction, omissions, and
incorrect assumptions found in that use become product defects or follow-up
improvements and are corrected in Beta patch releases.

Synthetic equivalent-task scoring is not a release gate. Time, token, or cost
comparisons may still be measured when useful, but Span makes no universal
saving claim without evidence for that specific claim.

*Demonstration:* an adopter can use Span as part of normal software work, the
working context remains usable across the lifecycle, and real-world defects can
be identified and corrected without weakening F1–F7 or the rest of the product
contract.

### F9 — Scope is a surface, and status is reported at its granularity

Understanding is always bound to a surface with a boundary and a kind — either a
declared surface or a path surface. Currency is per conclusion; a surface's
status is a distribution over its conclusions and its boundary, never a single
stamp. A larger surface may contain both current and stale understanding, and
that is expected rather than a defect. Span reports the status of the selected semantic population; surface obtains describe the whole surface, narrower obtains identify their narrower population. Acceptance of a write reports its own effects, not an unrelated surface distribution.

Functional Pyramid applicability is reported separately from semantic ownership.
A path can match several document placements without causing surface ambiguity,
and one placement can cover every directory in its scope.

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

An ACTIVE Functional Pyramid repository declares applicability, canonical
document references, their places in the pyramid and the relationships between
them. Each declared document placement carries an explicit repository-relative
directory scope; the repository root is the widest scope. Span resolves every
placement whose scope contains the requested directory or the effective
semantic scope, follows the declared relationships between documents, and retains the basis of each resolved branch. A directory lookup includes
documents that apply to that directory through their own declared scope or a
declared ancestor scope. A placement confined to a descendant directory does
not, by that fact alone, apply to its parent.

Applicability is a total function for a participating repository. A valid
activation requires at least one repository-root-scoped P0 placement, so every
directory resolves to at least the foundational documents and never to an
absence of governance. The resolved set is bounded by the declarations that
exist; Span reports declared and absent layers but never invents a placement,
and documentation completeness remains the declaring owner's responsibility.

The Functional Pyramid view is the governing projection of that semantic scope:
it exposes canonical document locations, applicable scopes/layers and unresolved state. Declared relationships and per-path provenance determine the complete selection; their internal graph and traversal representations are not consumer outputs. The consumer can locate the canonical sources without knowing repository namespaces. A relevant document can
participate without enumerating its statements or assigning identities to
individual rules. When the agent needs substantive content, it follows the
canonical reference and reads that source through the ordinary evidence
lifecycle. The view does not ingest, summarize or copy that content.

Matching is additive: a more specific placement adds obligations and never
silently replaces a broader applicable placement. Missing repositories, unknown
documents, cycles, invalid declarations and unresolved governing relationships remain
explicit. Cross-repository authority is followed only through declared stable
identities and configured repository bindings.

Span never infers applicability or precedence from file names, directory
placement, document class, prominence, similarity, source age or structural
adjacency.

For a normative conclusion in an ACTIVE Functional Pyramid repository, Span derives the
applicable Functional Pyramid route and authority dependencies from the
conclusion's semantic scope. The caller cannot omit or override them.

*Demonstration:* the same directory may return several branches of relevant
documents with shared ancestors; changing a placement or governing relationship
makes an affected normative conclusion require reassessment even when its source
bytes did not change.

### F12 — Functional Pyramid participation is explicit lifecycle state

Registration makes a repository available to Span; it does not place that
repository into a Functional Pyramid. One Functional Pyramid instance explicitly
names the registered repositories whose declared governance may resolve together.
A repository may belong to at most one ACTIVE Functional Pyramid instance at a
time so repository-scoped lifecycle operations have one governing instance.
Membership supplies resolution reachability only: it never makes a member's
documents applicable to another member without an explicit placement or document relationship.

Durable participation state is exactly `UNCONFIGURED`, `EXCLUDED`, or
`ACTIVE`. Only an accepted Functional Pyramid `record` changes that durable
state. An ACTIVE pyramid also has live health, computed from present declarations
and member availability: `VALID` or `DEGRADED`. Health is qualification of
the active graph, not another durable participation state and never requires a
hidden write during `ask`, `reconsider`, or hook delivery.

Participation is whole-repository. An ACTIVE member governs every directory in
its repository; there is no member functional boundary that can exclude a
directory from resolution. Each member declares its canonical document
placements and the exact directory scope of each placement. The repository root
placement is mandatory: activation requires at least one root-scoped P0
placement whose governing relationship is `ROOT`. That invariant is what makes
directory resolution total.

A directory with no placement of its own resolves through every declared
ancestor scope and therefore receives the foundational documents and any
applicable intermediate documents. Span never returns an uncovered-path
outcome for a participating repository: a directory either resolves to the
declared placements that contain it or reports an explicit structural or
operational defect. Documentation coverage and quality are the declaring
owner's responsibility; Span reports which layers are declared for a location
and which are absent, and it never manufactures a missing document or
relationship.

Participation, health and route state remain distinct: an ACTIVE pyramid may be
DEGRADED while an unaffected route still resolves. A DEGRADED health state
reports a structural defect in the declared graph, not a directory without
governance.

Activation or revision is based only on explicit repository-owned governance
input. The repository supplies governance decisions; Span derives and manages
the structural representation and performs the mechanical establishment of
that governance. Explicit governed initialization authorizes the existing
participation write; registration alone, ordinary runtime and hooks do not.
Canonical governing content remains at its owner. Span retains only the
membership, references, relationships, placement scopes and identities needed
to resolve and maintain the graph, not a second documentation corpus.

*Demonstration:* registering or adding a repository changes no applicable route
unless a declared relationship makes it relevant. If a still-declared ACTIVE
member or required declaration becomes operationally unavailable, participation
remains ACTIVE, live health becomes DEGRADED and affected routes remain explicit;
restoring that availability can return health to VALID without a participation
write. By contrast, an accepted revision that removes a member changes that
repository's durable participation to UNCONFIGURED and affected governed
understanding requires reassessment; rejoining requires another accepted
participation write.


### F13 — Capture and curation are distinct, revision-bound facts

Every supported semantic conclusion revision projects exactly one reuse-maturity
state: `CAPTURED` or `CURATED`. CAPTURED means the revision is retained but
has no accepted curation disposition; CURATED means an explicit curation
disposition exists for that exact revision.

Create, add, correct and replace produce CAPTURED semantic revisions. Withdrawal
produces no reusable semantic content. A substantive support-only confirmation
may preserve prior curation only because the statement, assertion nature and
semantic scope remain unchanged; curation never transfers across a semantic
content change. Curation never substitutes for evidence, authority, support
currency or challenge settlement.

*Demonstration:* a correction to a curated conclusion is retained as a new
CAPTURED revision and cannot be served as shared Answer content until separately
curated; a support-only confirmation of unchanged curated meaning can become
servable again without manufacturing another semantic review.

### F14 — Public documentation starts from the user's problem and discloses detail progressively

Public documentation is part of the delivered product. Each public document has
one reader job and begins at the level of abstraction required for that job.
Front-door documentation starts from the user's problem, the outcome Span
provides, and credible evidence or context for why the problem matters. It
introduces Span mechanisms only to the degree needed for the reader to
understand, trust, or act on that outcome.

Information order follows product dependency order. A prerequisite state,
initialization step, or orientation must appear before the workflow that depends
on it. Where a governed runtime depends on prior Functional Pyramid
initialization/adoption, public guidance presents that prerequisite before the
ordinary runtime lifecycle that consumes governing orientation. Exact lifecycle
states and transition rules remain owned by Layer 2 rather than being restated
here.

Detail is disclosed progressively. User guidance explains the task and next
action; concept documentation explains the product model; reference
documentation owns exact operational mechanics; contributor documentation
explains implementation ownership; and the Functional Pyramid remains the
single owner of binding product authority. A public guide may explain the
consequence of a canonical rule for its reader, but it links to that rule rather
than reproducing the normative contract.

Public documentation does not narrate its own information architecture or
editorial method. Headings, sequence, links, and document boundaries perform
that work. Self-referential commentary such as why a document is organized a
certain way, that it uses progressive disclosure, or that it is intentionally
high-level is omitted unless the statement is itself operationally necessary,
for example to distinguish authority, verification evidence, or historical
material.

External sources may establish industry context, evidence, or credibility for a
problem or practice. They do not become Span product authority and do not import
another product's architecture or requirements into Span.

*Demonstration:* a new reader can understand the problem Span solves, follow the
required setup in dependency order, and reach the first successful workflow
without learning implementation internals. A governed first-use path completes
the required Functional Pyramid initialization/adoption before ordinary governed
runtime work. Exact mechanics and authority remain reachable at the next
appropriate depth; public pages do not explain the documentation strategy
itself; and the corpus contains no competing copy of a normative rule.

## 4. Lifecycle responsibilities

The agent's required actions and task-completion boundary are owned by
[lifecycle contract §7](lifecycle-contract.md#required-agent-completion),
derived from F3, F7, F10–F13. The contract owns the procedure; these principles
govern it.

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
  retained normative conformance conclusion disagree, preserve the disagreement and fix
  the owning defect rather than allowing one proof type to overwrite another.

## 7. What this document does not define

The operation names and their functional behaviour are defined in the second
layer, [lifecycle contract](lifecycle-contract.md). The behaviour that makes them
deterministic is the [functional design](functional-design.md), layer 3. Wire
schemas, storage model, transport, and host integration are layer 4. Both are
consequences of this document, not inputs to it, and must remain derivable from
the axioms and principles above. When they stop being derivable, they are wrong
even if they are internally consistent.
