# Acceptance and evidence

> **Document role: current verification evidence.** This page records what the
> active Beta-3 candidate has demonstrated and what remains unverified. It does
> not define product requirements; those remain in the Functional Pyramid.

> **What can we currently claim about the Beta-3 candidate, based on evidence?**

Historical Beta-1 and 0.11 campaign evidence has moved to
[Historical acceptance evidence](acceptance-history.md).

## Current Beta-3 verification state

The current functional acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
FA-01–FA-64 remain the numbered acceptance set, but the corrected FA-28
lifecycle-hook case is not yet fully evidenced by the existing
[functional-acceptance matrix](functional-acceptance.md); Beta-3 task T14-H6
owns that executable closure. The [Invariant audit matrix](invariants.md)
continues to cover cross-layer architecture boundaries and must be reconciled
with the new hook tests when they exist.

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

### Documentation-remediation verification

The first F14 documentation/authority restructuring was verified at
`f3ca2065a7bbee1af02ef9bd61006f210f0952c9` by GitHub Actions CI run
`45329316520`.

A second F14 refinement then audited the public corpus against the actual
product dependency order. That refinement identified two remaining
documentation defects:

- public pages still contained non-operational commentary about their own
  organization/disclosure strategy; and
- the first-use/usage path did not consistently present Functional Pyramid
  initialization/adoption before ordinary **governed** runtime use, even though
  lifecycle §7 already owns that ordering.

F14 was amended at Layer 1 to require dependency-ordered information and to
forbid unnecessary self-commentary without restating Layer-2 participation
states or transitions.

The refined content head is
`ef0ff8f4bc0352c4f52cf2254163d7f1da8ac27a`.
GitHub Actions CI run `45333961735` passed on that exact tree:

- build/distribution passed;
- Ruff and Black passed;
- typing remained at **0 errors**;
- pytest reported **980 passed, 1 skipped, 150 subtests**;
- aggregate coverage remained **85%**;
- plugin notice delivery passed; and
- the coverage artifact uploaded successfully.

The refinement changed documentation and managed agent guidance only; no
`src/` or `tests/` file changed.

The resulting public order is:

1. install and verify Span;
2. for governed use, initialize/adopt the Functional Pyramid and establish
   governance readiness;
3. complete the first investigation and capture/review/reuse loop;
4. use the repeating semantic lifecycle during normal engineering work; and
5. consult concepts/reference only when deeper detail is needed.

The ordinary descriptive semantic lifecycle remains available without ACTIVE
Functional Pyramid participation. UNCONFIGURED is therefore not misrepresented
as a runtime failure, while it is also no longer presented as completed
governance setup.

README, documentation index, install, first investigation, usage, lifecycle,
FAQ, managed AGENTS guidance and packaged router/before-read guidance now share
that ordering. The active primary navigation was rechecked on the refined tree:
repository-relative file links and referenced section anchors resolve.

This acceptance file and the Beta-3 programme record are closure receipts for
that verified F14 content tree.

A subsequent substantive review of all five shipped `SKILL.md` files and the
agentic hook path found defects that structural presence/JSON-decoding tests had
not detected. The corrections are part of Beta 3 rather than a post-release
workstream:

- skill prose now preserves the CURRENT + CURATED Answer boundary, bounded
  PendingCuration pagination, Functional Pyramid `exclude`, NORMATIVE
  conformance examples, exact action grammar, challenge-context alternatives,
  and the current lifecycle authority anchor;
- the hook runtime no longer maintains a parallel SOURCE-only dependent scan.
  Change notices use a read-only preview of the same canonical changed-scope
  projection as `reconsider`, including containment, source/discovery,
  authority/route, premise and cross-repository effects, without issuing
  re-establishment contexts;
- OpenCode change reminders carry a complete changed-scope request shape, and
  host-trigger documentation no longer carries stale Beta-1/T13 candidate
  claims; and
- the new semantic skill/hook regressions increased the measured
  `test_lines` ratchet from **32,443 to 32,486**. No production/source-quality
  ceiling or product gate was weakened.

The earlier F14 run remains evidence for its exact documentation tree. The
subsequent skill/hook exact-head run likewise remains evidence for the tree it
tested, but a deeper lifecycle review has reopened T14. That review corrected
FD-58/FD-94 and Technical Design §22 and identified remaining implementation
work around complete changed-scope input, session edit accumulation, managed
host installation identity, session-entry composition and executable hook
acceptance. No prior green run is therefore the Beta-3 closure proof for the
current design.

The authoritative Beta-3 closure proof will be the required GitHub CI check
attached to the exact commit that completes T14-H2 through T14-H7. Its run
identifier is intentionally not embedded in the candidate tree because doing so
would create another head.

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
  boundary tests; the expanded FA-28 hook contract remains explicitly incomplete
  until T14-H6 adds and records its missing live evidence.
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
