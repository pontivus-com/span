# Interpretation and recording

The coding agent investigates and judges meaning. Span accepts explicit,
supported recording commands and keeps their history. Follow [the required lifecycle](lifecycle-contract.md#required-agent-completion).
Direct-create ingress also accepts pre-existing evidence and conclusions.

## Evidence before conclusions

Cite the evidence you already hold through `record`. The agent reads the
material sources and records locator/range support; Span admits it internally. Source support
records a content observation; authority support cites declared governance;
premise support names an exact conclusion revision; discovery support names
an observed membership boundary. See [authority](authority-trust.md).

One conclusion can explain behavior across several files. Give it a statement,
assertion nature, exact scope, support, and basis. Record descriptive behavior
separately from a normative claim about what ought to govern. Include gaps for
unresolved questions. Shape acceptance does not prove the prose is correct.

## Create and update

`record(kind="understanding", conclusion, locator|observation_id|support)` creates
an understanding and its first immutable version. `support` is the complete typed
dependency set when the agent already holds one. Scope is supplied or derived
independently through `scope_paths`, the context, or a declared surface. A
question-bound context supplies its question/scope; an evidence-only context
requires an explicit target within the admitted scope.

| Action | Effect |
| --- | --- |
| `actions.add` | Add a conclusion lineage while retaining other membership. |
| `actions.confirm` | Record that the current explanation still holds, after reassessing its supplied support. |
| `actions.correct` | Revise the explanation in its existing lineage. |
| `actions.replace` | Supersede the current conclusion with a new lineage and a stated reason. |
| `actions.withdraw` | Record an explicit withdrawal and its reason. |
| `actions` object | Apply multiple conclusion actions and named challenge dispositions atomically. |

Update actions are compact deltas: the caller supplies the conclusion text and
the evidence already held; Span derives new lineage identities, the old
revision, unchanged assertion nature or scope, and the mechanical basis. `add`
takes no identity; `confirm`, `correct`, `replace`, and `withdraw` name an
existing `conclusion_id` returned by Span. Each action names one evidence mode
(`locator`, `observation_id`, or non-empty `support`); a withdrawal may name
none.

Updates compare the expected understanding version. Each accepted version
records its full membership of exact conclusion revisions; earlier versions
and revision history remain retrievable. Omitted conclusions are retained.
Invalid references or version conflicts reject the command without a partial
semantic write.

## Explicit disputes

`reconsider` records a dispute against an understanding/version and its
specified conclusions. Challenge revisions are independent of understanding
versions. `record` names the expected challenge revision and either
records an unresolved question/basis or an evidence-backed resolution tied to
the resulting version and conclusion revisions. Unmentioned disputes survive.
Neither matching bytes nor a passing verification run resolves one implicitly.

## Acceptance and replay

The caller preserves `(repository_id, request_id)` and content
before sending. Matching replay returns its retained receipt before checking
whether a new write could be accepted today. Different content under the same
identity conflicts. A new update uses a new request identity.

A record result contains the receipt and present support qualification.
`SupportUnavailable` after commit means acceptance succeeded but qualification
failed; recover the receipt and investigate availability. It is not a rejected
write and is not a support verdict.

## Independent verification

Use `record(kind="verification")` after an actual external execution, independently of
semantic recording. Record command or scenario, tested source observations or
evidence, observer, time, `PASS`/`FAIL`/`INCONCLUSIVE`, and environment
limitations. A run requires observations or evidence; either is accepted. It
applies to the surfaces within its declared scope; a single-file run is not
widened to a broader service. `ask` returns the run with its live qualification
without rerunning the work.

See [MCP reference](mcp.md) for the authoritative request/result grammar and
[lifecycle](lifecycle.md) for context expiry and operational retention.
