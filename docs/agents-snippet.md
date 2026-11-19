## Span lifecycle (MCP only)

Consult Span before deriving semantic understanding. Record supported
conclusions when established. After edits, reconsider changed paths and record
the supported dispositions before completing the work.

- Before any source access used to understand a surface — native `Read`/`Grep` or shell reads/searches such as `cat`, `rg`, or `grep` — `ask` the exact surface or reference with no question or request identity.
- Use `RecordedQuestionSelector` only when you already know the exact recorded question; it is exact surface-scoped lookup, not semantic matching.
- If a Gap's source pointers need bytes, make an explicit evidence-admission `ask`; follow only the continuation it returns.
- Treat returned context references as opaque handles; copy them only into declared `context` fields.
- After editing: `reconsider`; investigate `REASSESSMENT_REQUIRED`/`UNVERIFIABLE` conclusions and record their dispositions.
- After establishing a conclusion: `record`.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md),
[router skill](https://github.com/pontivus-com/span/blob/master/skills/span-router/SKILL.md).
