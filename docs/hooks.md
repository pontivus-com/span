# Lifecycle hooks

Hooks are optional reminders that help Span's lifecycle appear at the moment an
agent is likely to need it.

They are useful for things such as:

- reminding an agent to consult Span when a session starts;
- noticing that edited paths may affect retained knowledge; and
- prompting the agent to run the appropriate lifecycle action after change.

Hooks do **not** make the lifecycle correct by themselves.

Span's normal `ask`, `record`, and `reconsider` operations still enforce
the relevant support and reuse rules when hooks are absent, disabled, delayed,
or missed.

## What hooks can report

Span ships hook commands for a small set of lifecycle moments:

| Hook command | Purpose |
| --- | --- |
| `session-start` | Check whether Span is operational for the registered repository containing the working directory. |
| `adoption-primer` | Remind the agent of the required Span lifecycle when a registered repository is ready. |
| `source-changed` | Inspect bounded changed paths for retained knowledge that may need attention. |
| `session-stop` | Report bounded support effects associated with supplied session paths. |

These notices reuse Span's normal readiness and canonical dependency-effect
projection. Change notices do not maintain a second SOURCE-only dependency scan
or freshness policy; they consume the same containment/direct/indirect,
discovery, authority, Functional Pyramid route, premise-closure and
cross-repository projection owned by reconsideration, without issuing
re-establishment contexts.

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

- **Codex** — hook configuration can be managed alongside the MCP setup;
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
