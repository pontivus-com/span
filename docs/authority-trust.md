# Evidence, authority, and interpretation

A source can show what code does. A governing source can establish what a
project requires when its authority and applicability are declared. The agent
must distinguish those uses; relevance alone grants neither authority nor
semantic truth.

## Evidence and support

Exact source admission creates an immutable `SourceObservation`: its repository,
locator, content identity, and delivered excerpts/ranges. A recorded conclusion
cites admitted support rather than resending source bodies or inventing
fingerprints. CSS and configuration can support investigation even when
structural parsing is unavailable.

The four support branches are source observations, declared authority bindings,
exact premise revisions, and recorded discovery membership. Their typed
contracts live in `core/model/support.py`; [freshness](freshness.md) explains
how their present state is evaluated.

## Declared governance

`AuthorityBinding` carries an evidence reference, kind, status, applicability,
and optional declared precedence. Setup registers explicit bindings; recording
resolves references through the authority port. Finding a file with a promising
name or admitting its bytes does not create a binding.

Accepted, declared, draft, superseded, and unknown statuses remain distinct.
Current authority support requires its declared accepted state, identity,
applicability, kind, and recorded content to remain compatible with present
evidence. Missing authority stays unverifiable; superseded or changed support
requires reassessment. Precedence must come from an explicit declaration,
not from a model's preferred interpretation or a ranking score.

## Meaning, currency, and dispute

`SupportedConclusion` contains an agent-authored statement, descriptive or
normative assertion nature, scope, support, and a basis. A basis explains what
was checked; it is not proof of semantic correctness. Mechanical admission
and acceptance do not certify the interpretation.

`CURRENT`, `REASSESSMENT_REQUIRED`, and `UNVERIFIABLE` classify support currency.
Explicit gaps preserve unanswered questions. Challenges preserve contested
interpretations and their disposition history independently of current source
bytes. A later version or passing run does not silently resolve disagreement.

Legacy trust/claim-kind vocabulary may remain in retained core types and
historical exports. It is not a required taxonomy for authoring a 0.9.0
understanding. See [taxonomy](taxonomy.md) and [recording](interpretation.md).

## Verification is its own record

An external execution is recorded independently with its observed outcome and
source observations. Test existence is not a pass. A current failed run still
records failure; changed tested bytes require a new execution before a fresh
pass can be claimed. `verification_support` checks currency without running
anything. Span never originates repository or professional authority.
