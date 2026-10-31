# Support currency and reassessment

Span checks whether the dependencies recorded for an explanation remain
current. It does not determine semantic truth from a fingerprint. The agent
judges the meaning and completeness of the explanation.

## States

| Support state | Meaning |
| --- | --- |
| `CURRENT` | The declared dependencies passed their current checks. |
| `REASSESSMENT_REQUIRED` | Recorded support changed or a premise was superseded/withdrawn; investigate before reuse. |
| `UNVERIFIABLE` | Required support cannot be established, such as missing evidence, unresolved authority, or a bounded/cyclic premise walk. |

These are support states, separate from gaps, challenge state, operational
availability, and test outcome. An all-current aggregate does not prove that
any substantive conclusion exists or that the investigation was complete.

## What is checked

- **Source:** current content against the immutable observation's digest.
  Missing content is unverifiable; changed bytes require reassessment.
- **Authority:** declared identity, accepted status, kind, applicability, and
  recorded content identity. Missing/undeclared authority is not promoted by
  finding relevant prose. Superseded or changed authority requires review.
- **Premise:** existence and current membership of an exact conclusion
  revision, then its support through a bounded dependency walk. A replacement
  or withdrawal can affect dependents without changing their own source files.
- **Discovery:** current membership against the recorded scope fingerprint.
  Additions/removals matter for conclusions that declare this dependency.
  Truncated inventory never supplies a complete membership observation.

Checks follow declared dependencies. A conclusion citing a whole-file content
observation can require reassessment after any change to that file, even if
the meaning still holds. Unrelated files do not invalidate it merely because
repository HEAD or a timestamp changed. Omitted support cannot be detected
as a semantic omission by deterministic comparison alone.

## Reading and recording

Snapshot retrieval, `reassess`, new recording, and verification qualification
use the owning support service and pure core rules. A provider/store failure
is operational failure, not an invented support state. After an accepted
record, a qualification failure is `SupportUnavailable` beside the durable
receipt; it must not be reported as a rejected write.

After a relevant edit, investigate the affected explanation, admit current
evidence, and record the appropriate update with its basis. A new immutable
version preserves history. `reassess` checks currency; it does not reinterpret,
execute tests, or settle a challenge. Gaps and disputes remain explicit.

## Independent runs

`verification_support` checks the source observations tied to a saved run,
including dirty-tree changes without a new commit. The run's
`PASS`/`FAIL`/`INCONCLUSIVE` outcome remains historical fact. Current support
for a failed run means the failure evidence still applies; it does not mean
that the test now passes. See [recording](interpretation.md).
