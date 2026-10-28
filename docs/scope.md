# Scope, boundaries, and differentiation

Span is deliberately narrow. It maintains established understanding and its
freshness; it does not become an implementation tool, an authority source, or
an autonomous maintenance process.

## How Span is different

Span is not intended to replace code search, structural analysis, documentation, or your coding agent.

It fills the gap between them.

| Approach | Persists interpreted understanding | Tracks whether it is still supported | Surfaces what changed, with its scope | Supports scoped semantic re-check |
| --- | --- | --- | --- | --- |
| Traditional or generated documentation | Yes | Not inherently | No | No |
| General agent memory | Yes | Not inherently | No | Not inherently |
| Citation-validated agent memory | Yes | Yes, per fact | No — unverified items are withheld | No |
| Code search / structural graph | Different purpose | Source or structure only | Structural only | Not semantic reassessment |
| **Span** | **Yes** | **Yes, per item, premise, and discovery scope** | **Yes, with the reason** | **Yes** |

### Documentation records an answer

Span also records whether the evidence underneath that answer has changed.

### Agent memory remembers

Span separates remembering something from knowing whether it is still safe to treat as current.

### Validated memory still hides the work

Citation validation answers a narrow question: does this fact still match the code it points at? When it does not, the fact is withheld.

That protects the agent from a wrong answer. It does not tell the agent what became doubtful, which other conclusions rested on the same evidence, how far the change reaches, or what still needs checking. The work of reassessment stays invisible.

Span returns the affected item as stale with the changed evidence and the scope to re-check, keeps unverifiable and never-assessed state explicit, and leaves unaffected understanding in place.

Hiding a doubt and scoping a doubt are different products.

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

## What Span does not do

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

## Span is not agent memory, validated or otherwise

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

Memory products now cite the code behind a fact and check those citations before use. That is a real improvement over blind recall, and it is still a narrower guarantee than Span makes.

Validation answers whether a fact still matches the code it points at. When it does not, the fact is withheld: the agent is protected from a wrong answer, but it is not told what became doubtful, which conclusions shared the same evidence, or how far the change reaches. The reassessment work stays invisible.

Span preserves the conclusion, its evidence, its authority, the premises that depend on it, and the coverage of the scope that was examined. When support changes it returns the item as stale with the changed evidence and the scope to re-check. When it cannot decide, it says unverifiable. When a scope was never examined, it says so.

Persistence alone is not the product. Validation alone is not either.

Knowing what is still supported, what is not, and what nobody has checked yet is.

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

## Store readiness is not repository understanding

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

Normal repository-level `status` reports bounded persisted semantic coverage separately from operational store readiness.

That can include:

- current established knowledge;
- stale knowledge;
- unverifiable knowledge;
- incomplete work;
- unresolved work;
- unassessed scope within the bounded returned frontier.

Coverage and store readiness are intentionally separate.

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

## Storage and repository isolation

Span stores its state outside every target repository.

The semantic store supports schema 9 only. A fresh store is created at
schema 9, an existing schema-9 store opens normally, and any other store
version fails closed; Span performs no runtime schema migration.
`span-install --migrate-store <repository-id>` is the explicit upgrade: it
migrates a schema-7 or schema-8 store to schema 9 and cleans schema-9 payloads
written by 0.8.0, in one transaction. Repository
state and the configured authority seeds persist together in one atomic
row, and persisted seeds are rehydrated after a process or host restart.
Omitting `authority_seeds` preserves configured seeds, an explicit empty
tuple clears them, and a non-empty tuple replaces them.

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

## Establish. Maintain. Expand.

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
