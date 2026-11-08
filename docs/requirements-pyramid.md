# Requirements pyramid model

**Status: binding for the requirements corpus.** This document governs the form
of the requirement documents. It is not a product layer and adds no product
requirement. It exists so that anyone can see how the layers were derived, what
each one is allowed to contain, and where a new statement belongs.

## 1. Purpose

Requirements are stated in layers, where each layer is a consequence of the one
above it. The model has two jobs:

1. keep the top small — a few outcomes, not a specification;
2. keep the bottom derivable — every requirement traceable upward to a goal.

A corpus that mixes layers cannot be judged: an implementation detail looks like
an outcome, and a missing outcome cannot be detected because no layer above was
supposed to state it.

## 2. The layers and what each owns

| Layer | Document | Exclusive ownership | Must not contain | Answers |
| --- | --- | --- | --- | --- |
| **0** | `goals.md` | the problem, the outcomes, success, non-goals | mechanisms, invariants, operations, carriers | Why does this exist, and what does success look like? |
| **1** | `foundations.md` | the domain definition, axioms about the agent, and invariants that must hold | outcomes, operation shapes, carriers, storage | What is it, and what must be true at all times? |
| **2** | `lifecycle-contract.md` | surfaces, operations, payloads, contract laws, internal boundary | restated goals or principles | What must the agent send and receive? |
| **3** | `functional-design.md` | behaviour that makes the contract deterministic: identity, containment, support evaluation, propagation, composition, transitions, failure, retention, concurrency, host expectations, truncation | implementation mechanisms, wire formats, storage layout, product outcomes | How must it behave to keep the promise? |
| **4** | `technical-design.md` | implementation choices: schemas, storage, transport, hosts; the baseline and refactoring set | new requirements | How is it realised? |

Each layer's document may *reference* a statement in another layer by its ID. It
may not paraphrase it. A reference keeps one source of truth; a paraphrase
creates a second.

## 3. The placement test

To decide where a statement belongs, ask in order:

1. **Is it an outcome or success condition rather than a mechanism?** If yes, it
   belongs at layer 0.
2. **Is it a fact about the agent, or a guarantee that must hold regardless of
   implementation, stated without a procedure?** If yes, it is an invariant and
   belongs at layer 1.
3. **Does it constrain what the agent sends, receives, or is guaranteed, stated
   without a procedure?** If yes, it belongs at layer 2.
4. **Is it a deterministic rule or procedure that makes a guarantee true, without
   choosing a mechanism?** If yes, it belongs at layer 3.
5. **Does it select one mechanism?** If yes, it is a layer-4 choice, and it must
   be justified by the statement it serves.

Layers 1 and 2 say **what must be true**. Layer 3 says **how the system decides**
in order to make it true. Layer 4 says **how it is built**. Implementation
independence holds at layers 1–3; the distinguishing question is declarative
versus procedural, not whether an implementation could differ.

Implementation independence is what makes a statement an invariant, not what
disqualifies it. "Atomic recording" holds across storage implementations; that is
why it belongs at layer 1, not why it does not.

If a statement passes none of these, it is either unjustified or it belongs above
the document being edited.

A definition is not a requirement. It belongs with the layer that first needs it;
in this corpus the domain definition lives at layer 1, and later layers reference
it.

## 4. Direction of authority and derivation

- **Authority flows upward.** A lower layer may not contradict a higher one. On
  conflict, the higher layer governs and the lower one is the defect.
- **Derivation flows downward.** A lower layer is a consequence of the one above
  it. A lower-layer choice must be consistent with, and justified by, the
  statement it serves. Each layer constrains the next; it does not uniquely
  determine it. A choice that contradicts a higher layer is wrong even when it
  works; a choice that merely differs from another valid choice is not a defect.
- **The defect is in the pyramid, not in the goal.** If an invariant stops
  serving an outcome, the invariant is wrong. If an outcome cannot be made true
  by any invariant, the outcome is either wrong or incomplete.
- **A layer-4 surface is derived.** Every advertised operation names the
  lifecycle verb it realizes and the agent moment it serves. An operation that
  cannot is a defect in the layer that advertised it, not a lower-layer choice.

## 5. No restatement

- A **contradiction** is a defect.
- A **restatement** is also a defect, because a second copy is a second source of
  truth and will drift.
- Test: if a line can be deleted and the rule still holds by derivation from the
  layer above, delete it.
- Citations are how layers connect. Use the IDs (`G1–G6`, `A1–A9`, `F1–F10`,
  `L1–L11`, `FD-1–FD-60`) instead of repeating the statement they name.

This rule applies within a layer as well as between layers. Two sections that say
the same thing are one too many, even in the same document.

## 6. Placement examples

The statements below are illustrations of placement, not requirements. The
requirement itself lives in the layer named.

| Statement | Layer | Why |
| --- | --- | --- |
| "The agent forgets between sessions." | 1 (A1) | a fact about the user, not a product choice |
| "Understanding is found without the originating conversation." | 0 (G2), enforced at 1 (F3) | an outcome, not a mechanism |
| "A changed path marks every containing surface." | 2 (L10) | it constrains what the agent receives after an edit |
| "The store keeps immutable versions in SQLite." | 3 | an implementation choice; not derivable as a requirement |
| "The same change yields different status at file and service granularity." | nowhere new | it follows from F9 and L10; stating it again would be a restatement |

The last row is the point of the model. A true statement is not automatically a
requirement. If it is derivable, it is a consequence, and consequences are
demonstrated by tests, not re-declared as rules.

## 7. Changing a requirement

1. Decide the layer with the placement test in §3.
2. If the change belongs above the document being edited, amend the higher layer
   first. Never compensate for a missing higher-layer statement by adding one
   lower down.
3. Cite the IDs affected.
4. Delete the restatement the change supersedes.
5. If a lower layer can no longer be satisfied or justified after the change, the
   model is telling you the change is incomplete.

## 8. Relationship to the product documents

- [Goals](goals.md) — layer 0.
- [Foundations](foundations.md) — layer 1.
- [Lifecycle contract](lifecycle-contract.md) — layer 2.
- [Functional design](functional-design.md) — layer 3.
- [Technical design](technical-design.md) — layer 4.

This document governs their form and ownership. It does not state what Span must
do; that is the product documents' job. If this document and a product document
disagree about *content*, the product document governs. If they disagree about
*layer or ownership*, this document governs.

[Method grounding](method-grounding.md) is supporting evidence, not a
layer. It adds no requirement and is judged by the same rule: if it starts
stating what Span must do, the statement belongs in a product layer.

The same boundary discipline structures a target repository's surfaces. That is a
product outcome, stated in [goals](goals.md) §2, not a rule of this corpus.
