# Acceptance and evidence

> **Document role: current verification evidence.** This page records what the
> active Beta-3 candidate has demonstrated and what remains unverified. It does
> not define product requirements; those remain in the Functional Pyramid.

Use this page to answer one question:

> **What can we currently claim about the Beta-3 candidate, based on evidence?**

Historical Beta-1 and 0.11 campaign evidence has moved to
[Historical acceptance evidence](acceptance-history.md).

## Current Beta-3 verification state

The current functional acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance),
with executable traceability through
[FA-01–FA-64](functional-acceptance.md). The
[Invariant audit matrix](invariants.md) covers cross-layer architecture
boundaries.

### Semantic/runtime baseline

The Beta-3 semantic/runtime baseline was exercised at
`b80fd8a154d8f7785e37fbbc6e74deb017ba6e60` by GitHub Actions CI run
`45177585406`:

- build/distribution passed;
- Ruff and Black passed;
- the zero-error typing ratchet passed;
- pytest reported `977 passed, 1 skipped, 148 subtests`;
- aggregate coverage was 85%;
- standalone plugin-notice delivery passed; and
- the installed production-topology acceptance surface passed.

This establishes the semantic/runtime baseline used by the Beta-3 corrective
work.

### External integration revalidation

External integration revalidation passed on 2026-11-24 using
repository-controlled integration inputs whose identities and contents remain
outside this public repository.

From an empty Span data directory, the run demonstrated:

- canonical `span-install` provisioning of repository schema **15**;
- separate installation Functional Pyramid schema **1**;
- exactly the public `ask`, `record`, and `reconsider` MCP operations;
- an activation-ready Functional Pyramid candidate with no validation/graph
  findings;
- a real governed integration surface with a resolved governing path;
- a representative normative conclusion withheld from shared reuse while
  captured/pending review;
- explicit curation of the exact revision; and
- fresh-process reuse of that reviewed conclusion with the same resolved
  governing projection.

Only generic acceptance outcomes are retained in Span Git. External repository
identities, revisions, paths, authority identifiers, configuration payloads,
transcripts, receipts, local stores, and manifests remain outside this public
repository.

The run also detected incorrect initial integration content fingerprints. The
external configuration was corrected; Span's support/currentness rules were not
weakened to make the run pass.

### Corrective baseline

The Beta-3 corrective baseline at
`f797c049917c0d3e70d402e2f4fed714dfd6efd5` passed push CI
`45296868951` and pull-request CI `45296879433`.

That evidence demonstrated:

- package build/install as `span_mcp-1.0.0b3`;
- Ruff/Black success;
- zero typing errors;
- `980 passed, 1 skipped, 150 subtests`;
- 85% aggregate coverage;
- plugin notice delivery;
- strict rejection of missing canonical authority discriminators; and
- the Beta-3 release-identity guard.

This SHA is the last fully recorded **pre-documentation-remediation corrective
baseline**. It must not be described as the current branch head after the
documentation remediation that followed it.

### Current documentation-remediation head

The Beta-3 branch has advanced through the F14 documentation remediation after
the corrective baseline above.

Those changes are intended to be documentation-only, but the current branch
must still pass final exact-head CI before release-readiness is re-established.
A prior green SHA is evidence for its own tree; it is not evidence that a later
head passed.

Until that final verification is recorded here, the correct release-verification
state is:

**documentation remediation in progress / final exact-head CI pending.**

## Release identity and authorization

The assembled Beta-3 identity remains:

| Surface | Identity |
| --- | --- |
| Package/PyPI | `1.0.0b3` |
| Git tag | `v1.0.0b3` |
| GitHub Release | `Span 1.0.0 Beta 3` |
| MCP Registry | `1.0.0-beta.3` |
| Repository lifecycle schema | **15** |
| Installation Functional Pyramid schema | **1** |

Schema-14 migration fabricates no curation approval for retained Beta-1
conclusions.

Publication remains a separate owner decision. The release workflow is
manual-only, runs from `master`, and requires exact package-version
confirmation.

**Beta 3 is not authorized for publication.** Green CI or implementation
completion does not authorize tagging, PyPI publication, GitHub Release
creation, or MCP Registry publication.

## Host-delivery evidence

The installed-MCP lane verifies the packaged command, advertised schemas,
request/result boundaries, recovery, and concurrency behavior.

Managed-host registration/support and authenticated model delivery are different
claims.

For the current Version-1 candidate:

- Codex remains a managed integration target;
- OpenCode managed integration/plugin delivery is supported;
- Claude Code registration/health/installer support is present; and
- authenticated live Version-1 model delivery remains **UNVERIFIED** unless a
  separate recorded acceptance run establishes it.

Hook wiring is likewise not proof that a notice reached a model.

See [host trigger support](../integrations/hosts/triggers.md) for the current
host-specific evidence.

## Functional and architectural traceability

Do not use this page as a second requirements catalog.

- [Functional acceptance](functional-acceptance.md) maps FA-01–FA-64 to live
  boundary tests.
- [Invariant audit matrix](invariants.md) maps architecture invariants to tests
  or explicit review enforcement.
- [Method grounding](method-grounding.md) explains external industry/method
  evidence without turning that evidence into Span authority.

Passing tests demonstrate the boundaries their assertions cover. A named test
does not by itself prove every semantic interpretation or every host delivery
claim.

## Product value

Beta product value is evaluated through real engineering use rather than a
synthetic equivalent-task release score.

Useful evidence includes:

- cold investigation;
- fresh-session reuse;
- implementation change and focused reassessment;
- governance change;
- recovery;
- ordinary operational failure;
- omissions/gaps; and
- the overhead of capture and review.

A populated store is not itself useful reuse. A successful release also does not
prove universal time or token savings.

Any comparative efficiency claim requires evidence scoped to that specific
claim.

### Documentation replacement (G6)

A readable Span answer is not enough to prove that Span can replace duplicated
surface-bound explanatory documentation.

The named scenario is:

1. choose a covered surface that already has explanatory Markdown;
2. freeze a non-empty set of claims from that page before recording/scoring;
3. establish and retain the surface's current understanding;
4. remove or reduce the duplicated explanation;
5. in a fresh session, obtain the maintained surface knowledge and map each
   frozen claim to supported current understanding; and
6. record what documentation was removed, which frozen claims were answered,
   which unsupported claims were caught, and any exclusions.

The scenario passes only when every frozen in-scope claim maps to supported
current understanding and stale content is not served as current.

An unavailable frozen claim is a failure, not an exclusion. Claims outside the
frozen set cannot be used to satisfy the gate.

## Reporting evidence

Release/verification records publish sanitized outcomes and their limits.

Raw external-integration captures, transcripts, receipts, local stores, and
manifests remain outside Span Git and distributions, except for the explicitly
defined repository-portable backup artifact.

Historical candidate evidence is retained in
[Historical acceptance evidence](acceptance-history.md).
