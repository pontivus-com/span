# Frequently asked questions


## Is Span deciding whether documentation is true?

No.

Span distinguishes between an interpretation and whether the repository evidence supporting that interpretation is still current.

Changed evidence means the conclusion needs reassessment.

It does not automatically mean the conclusion is false.

---

## Is Span a documentation generator?

No.

Its canonical state is structured semantic understanding, supporting evidence, authority relationships, coverage, and freshness.

Documentation can be produced from that state, but generated prose is not the primary source of truth.

---

## Is Span an LLM service?

No.

Span never invokes a model.

Your coding agent performs semantic interpretation using the model and tools already available to it.

Span validates, persists, relates, retrieves, and tracks the resulting established understanding.

---

## Does Span understand my whole repository after installation?

No.

Installation establishes operational readiness.

Understanding must be established through normal queries or explicit bounded target campaigns.

Coverage stays visible separately from store readiness.

---

## Does Span automatically fix stale knowledge?

No.

It identifies that required support changed and keeps the affected understanding noncurrent.

An agent must re-investigate and submit the reassessed result.

---

## Can unrelated changes make everything stale?

They should not.

Freshness is dependency-based and scoped.

Understanding that does not depend on changed evidence should remain current.

---

## What builds the structural index?

Installation provisions a managed structural indexer into Span's tools
directory. Setup and explicit `refresh` build the wiring-only index
into the data directory when needed, with no target writes.

The indexer provides structural evidence.

Span adds persistent semantic interpretation, semantic dependency, authority, freshness, and reassessment on top of structural evidence.

---

## Does Span replace search?

No.

Search remains useful for evidence discovery.

Span reduces the need to repeatedly reinterpret evidence that agents have already examined and established.

---

## Does `READY` mean all knowledge is current?

No.

`store_readiness: READY` is operational readiness.

Semantic coverage and freshness are separate.

---

## Can Span be wrong?

Yes.

Interpretation is performed by coding agents and is not assumed infallible.

Span preserves evidence, uncertainty, conflicts, unresolved questions, and freshness so that interpretations can be challenged and reassessed rather than being treated as unquestionable truth.

---

## Where does Span store data?

Outside the target repositories, in the configured Span data directory.

---
