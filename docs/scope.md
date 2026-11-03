# Scope and product boundaries

Span carries an agent's useful investigation into later work: the explanation,
the evidence it cites, the premises it relies on, and the reasons it needs
another look. The agent chooses what to investigate and what is worth saving.

## The unit is an explanation

An understanding answers a question over a declared scope. Its immutable
versions contain exact conclusion revisions and explicit gaps. An understanding
may span source, tests, configuration, and contracts. A file or symbol is an
evidence anchor; it does not create a documentation obligation by itself.

An agent can select an exact `FILE`, `SYMBOL`, `SERVICE`, or `DOMAIN` surface.
A service or domain surface is declared through `record(kind="surface")` with a
boundary and optional parent; its identity survives boundary updates, which use
compare-and-set. A file or symbol surface needs no declaration. The service
never auto-declares a surface from an understanding.

Ordinary coding work can start with saved answers, a cold investigation,
or evidence gathered outside Span. Recording is an explicit action, with an
inspectable receipt. There is no required whole-repository campaign, internal
question taxonomy, or suspended interpretation exchange in 0.9.1.

## Reuse has qualifications

Candidates are found through scope association and term overlap. The agent
judges applicability and meaning. A `CURRENT` qualification establishes only
that declared support still passes its checks. It does not prove semantic
correctness, full coverage, or the absence of an unresolved dispute.

A relevant source/authority change, superseded premise, or changed recorded
membership boundary can require reassessment. Unsupported or missing evidence
remains explicit. Changes outside a declared dependency boundary do not make
all saved understanding noncurrent.

The intended benefit is continuity between investigations and focused review
of affected explanations. Net time/token savings depend on the task, recording
effort, reuse, and host delivery. The beta does not claim a measured universal
saving or a comparative product-fitness ACCEPT result.

## Agent and server responsibilities

The agent owns semantic judgment, source investigation, applicability, edits,
and external tests. The repository's owners supply authority. Span validates
commands, admits evidence, preserves versions and receipts, qualifies support,
and returns bounded discovery with explicit omissions.

Source search and structural tools remain useful for new investigation.
Span's structural navigation describes locations and adjacency; it cannot
assign ownership, policy, intent, or professional authority from topology.

## Scope and boundedness

A surface reports its unexamined members as a bounded status, never as
completeness. Source inventory and evidence batches expose their limits.
An unexamined file or truncated result is not proof of absence. A complete
membership observation must actually cover its stated boundary. See
[queries](queries.md).

Investigation scope is explicit. Broader work requires the agent to choose
and examine the broader scope; Span does not turn a local question into an
automatic semantic crawl. There is no repository coverage score or promise
that installation establishes repository understanding.

## Local storage and operational effects

The runtime uses schema 11 in an external data directory. Recoverable contexts
and observation admission are operational state; recording creates semantic
history. Context expiry does not erase accepted conclusions, challenges,
verification runs, or retained receipts. Receipt expiry ends that replay
window, not the existence of the recorded understanding.

The managed structural artifact lives under
`<DATA_DIR>/structural/<repository-id>/.graph/wiring.json`. Explicit setup owns
provider currency work. Ordinary lifecycle operations and hooks do not build
it. Runtime operation does not write target source or provider artifacts into
the target repository. Installation may write a managed `AGENTS.md` block and
host configuration as described in [install](install.md).

Existing schema-7/8/9/10 stores use the separately invoked offline
inspect/apply/verify/rollback protocol. Their semantic content is archived and
exported as history, not promoted as current understanding. See the
[transition procedure](install.md#upgrade-an-existing-store).

## Beta delivery boundary

The supported live targets are Codex and OpenCode. Both have candidate-specific
captures of the declared grammar, request identity, and recovery behavior.
Implemented registration, configured hooks, and observed model behavior remain
separate facts. Hooks are optional notices; ordinary retrieval
and recording still check support when hooks are disabled.

See [usage](usage.md), [freshness](freshness.md), and [FAQ](faq.md).
