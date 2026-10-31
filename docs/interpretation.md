# Interpretation and recording

The coding agent investigates and judges meaning. Span accepts explicit,
supported recording commands and keeps their history. A question can return an
investigation gap, but recording is also available after an investigation that
started outside Span. No suspended model task or continuation is required.

## Evidence before conclusions

Admit exact evidence through `evidence_start` or `evidence_extend`. The agent
reads the material sources and cites returned observation IDs. Source support
records a content observation; authority support cites declared governance;
premise support names an exact conclusion revision; discovery support names
an observed membership boundary. See [authority](authority-trust.md).

One conclusion can explain behavior across several files. Give it a statement,
assertion nature, exact scope, support, and basis. Record descriptive behavior
separately from a normative claim about what ought to govern. Include gaps for
unresolved questions. Shape acceptance does not prove the prose is correct.

## Create and update

`record_create` creates an understanding and its first immutable version.
A question-bound context supplies its question/scope; an evidence-only
context requires an explicit target within the admitted scope.

| Action | Effect |
| --- | --- |
| `record_add` | Add a conclusion lineage while retaining other membership. |
| `record_confirm` | Record that the explanation still holds, with current support and a reassessment basis. |
| `record_correct` | Revise the explanation in its existing lineage. |
| `record_replace` | Replace an exact old conclusion revision with a new lineage. |
| `record_withdraw` | Record an explicit withdrawal and its reason. |
| `record_update` | Apply conclusion actions and named challenge dispositions atomically. |

Updates compare the expected understanding version. Each accepted version
records its full membership of exact conclusion revisions; earlier versions
and revision history remain retrievable. Omitted conclusions are retained.
Invalid references or version conflicts reject the command without a partial
semantic write.

## Explicit disputes

`record_challenge` records a dispute against an understanding/version and its
specified conclusions. Challenge revisions are independent of understanding
versions. `record_update` names the expected challenge revision and either
records an unresolved question/basis or an evidence-backed resolution tied to
the resulting version and conclusion revisions. Unmentioned disputes survive.
Neither matching bytes nor a passing verification run resolves one implicitly.

## Acceptance and replay

The caller preserves `(repository_id, context_id, submission_id)` and content
before sending. Matching replay returns its retained receipt before checking
whether a new write could be accepted today. Different content under the same
identity conflicts. A new update uses a new submission identity.

A record result contains the receipt and present support qualification.
`SupportUnavailable` after commit means acceptance succeeded but qualification
failed; recover the receipt and investigate availability. It is not a rejected
write and is not a support verdict.

## Independent verification

Use `record_verification` after an actual external execution, independently of
semantic recording. Record command or scenario, tested source observations,
observer, time, `PASS`/`FAIL`/`INCONCLUSIVE`, and environment limitations.
`verification_support` qualifies those observations without rerunning the work.

See [MCP reference](mcp.md) for the authoritative request/result grammar and
[lifecycle](lifecycle.md) for context expiry and operational retention.
