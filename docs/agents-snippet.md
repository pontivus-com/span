## Span lifecycle (MCP only)

- Before `Read`/`Grep` to understand a covered surface: `ask`.
- Use an exact `surface={kind, locator}` when a path resolves to more than one granularity.
- After editing: `reconsider`; act only on `REASSESSMENT_REQUIRED`/`UNVERIFIABLE` conclusions.
- After establishing a conclusion: `record`.
- Follow a gap continuation; on `no_match`, ask the surface without a question; never fetch a context id.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md),
[router skill](https://github.com/pontivus-com/span/blob/master/skills/span-router/SKILL.md).
