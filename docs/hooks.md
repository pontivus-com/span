# Lifecycle hooks

Hooks are optional agentic lifecycle reminders. Their foundational purpose is to
reduce lifecycle non-compliance caused by agent omission: an agent can start,
read, edit or finish work without voluntarily calling Span even when the
lifecycle requires an action.

The binding behavior is owned by Functional Design FD-58/FD-94 and Technical
Design §22. In practical terms, Span operations preserve correctness when they
are used; hooks make the required operation visible at host-observable moments
where the agent could otherwise skip it.

Hooks do **not** make the lifecycle correct by themselves. Span's normal
`ask`, `record`, and `reconsider` operations still enforce the relevant
support and reuse rules when hooks are absent, disabled, delayed, or missed.

## Lifecycle interception points

A hook is appropriate only for an externally observable moment that can create
or expose an omitted lifecycle obligation:

| Host moment | Semantic-understanding plane | Functional Pyramid plane |
| --- | --- | --- |
| Session start/resume/compact | remind the agent to orient before deriving understanding | surface UNCONFIGURED, EXCLUDED, ACTIVE/VALID or ACTIVE/DEGRADED status as the canonical participation/health state requires |
| Pre-investigation source access, only where a host exposes it reliably | remind the agent to `ask` before semantic derivation | ACTIVE governance orientation is composed into that same lifecycle; do not invent a second authority action |
| External edit/write | preserve the complete changed scope for `reconsider` | the same canonical effect projection determines authority/route/cross-repository consequences |
| Idle/stop/completion | remind only about known outstanding work from this session | preserve known governance/effect obligations; do not perform a repository-wide speculative scan |

Either plane may require action, both may require action, or neither may require
action. That is a notice-selection decision over canonical Span results, not a
new hook state machine or public carrier.

Transitions already exposed by an `ask`, `record`, or `reconsider` result
remain result-owned. Hooks do not rediscover curation state, challenge
disposition, candidate-validation outcomes, or the dependent effects already
returned by an accepted Functional Pyramid write.

## What hooks can report

Span ships hook commands for a small set of lifecycle moments:

| Hook command | Purpose |
| --- | --- |
| `session-start` | Compose one readiness, Functional Pyramid participation/health and semantic-orientation notice for the active repository. |
| `adoption-primer` | Emit the standalone lifecycle primer when invoked directly; managed OpenCode session entry uses the composed `session-start` path. |
| `source-changed` | Evaluate the complete normalized changed scope through the canonical reconsider preview, then render bounded diagnostic detail. |
| `session-stop` | Report bounded support effects associated with supplied session paths. |

Session entry is lifecycle-singular: readiness, Functional Pyramid state and
semantic orientation are composed into one notice rather than competing host
instructions. These notices reuse Span's normal readiness and canonical dependency-effect
projection. Change notices do not maintain a second SOURCE-only dependency scan
or freshness policy; they consume the same containment/direct/indirect,
discovery, authority, Functional Pyramid route, premise-closure and
cross-repository projection owned by reconsideration, without issuing
re-establishment contexts. The complete changed scope available from the host is
evaluated before notice rendering is bounded; repeated edits remain accumulated
until their lifecycle obligation is handed off.

## Hooks are advisory, not semantic actors

A hook never decides what code means.

Hooks do not:

- create or migrate Span stores;
- record semantic understanding;
- curate captured knowledge;
- reinterpret source;
- activate or revise Functional Pyramid participation;
- run tests;
- invoke a model; or
- rebuild the structural index.

When a hook reports that something may need attention, the agent follows the
normal lifecycle to investigate and record the result.

For example, an edit notice can tell the agent to call `reconsider` with the
changed paths. The hook may preview the canonical affected projection to decide
whether a notice is useful, but it does not persist a reconsideration context,
perform a disposition, or make support current.

## Silence does not mean everything is current

Routine current state can be quiet.

A silent hook does **not** establish that:

- the whole repository is understood;
- every retained conclusion is current;
- no cross-repository governance effect exists; or
- a configured hook was actually delivered to the model.

That is why correctness lives in the lifecycle operations rather than in
notification delivery.

If an event occurs outside a registered repository, the hook can ignore it.
Operational inability and semantic uncertainty remain separate.

## Project-governance notices

For repositories using the Functional Pyramid, hook notices can reflect the
repository's participation and present governance health.

Those notices remain read-only and advisory.

A hook can direct an agent toward governance setup or indicate that change may
have affected governed knowledge. It cannot create participation, change
governing relationships, repair authority, or make a normative conclusion
current.

Cross-repository governance effects are resolved through the same Span
lifecycle used by ordinary MCP requests. A hook is not a substitute for the
required `reconsider` step.

## Host delivery

Span can wire lifecycle reminders for its supported managed hosts.

The exact installation behavior differs by host:

- **Codex** — hook configuration is managed alongside the MCP setup and carries the same configured Span data directory;
- **Claude Code** — supported session/edit/stop hook entries can be added to an
  existing user settings file while preserving unrelated configuration; and
- **OpenCode** — the Span lifecycle plugin supplies the host-side reminder
  path under the configured plugin scope.

Host configuration, plugin scope, ownership, upgrade behavior, and removal are
installation concerns. See [Install and connect](install.md) for the current
operator procedure and [host trigger support](../integrations/hosts/triggers.md)
for the current delivery status.

Configured wiring, observed invocation, and model-delivered behavior are
different facts. Do not infer one from another.

## When hooks are disabled

Span is designed to work without hooks.

The agent still follows the same operating lifecycle:

> **Ask before deriving → investigate normally → capture what you establish →
> review for shared reuse → reconsider after change.**

Support checks happen through Span itself, not through the reminder mechanism.

This makes hooks a usability aid rather than a hidden correctness dependency.

## Exact behavior and evidence

Use:

- [MCP reference](mcp.md) for exact lifecycle operations;
- [Using Span](usage.md) for the normal workflow;
- [Install and connect](install.md) for hook/plugin configuration; and
- [Acceptance and evidence](acceptance.md) for verified host-delivery evidence.

The shipped runtime remains the implementation source for exact hook behavior.
