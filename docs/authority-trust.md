# Evidence, authority, trust

## Evidence

`EvidenceRef`: repository, source kind (`SOURCE_CODE`,
`DOCUMENTATION`, `DECISION_RECORD`, `CONTRACT_SPECIFICATION`,
`CONFIGURATION`, `TEST_VERIFICATION`, `USER_PROJECT_CONFIG`,
`EXTERNAL_SPEC`, `OTHER`), locator, revision/fingerprint,
section/span. Discovery (structural context → referenced sources →
authority seeds → anchored search, bounded) finds *potentially
relevant* material. It confers nothing.

## Authority

`AuthorityBinding`: evidence ref + kind (`REPOSITORY_RULE`,
`DECISION_RECORD`, `CONTRACT_SPECIFICATION`, `PRODUCT_BUSINESS`,
`TERMINOLOGY`, `LEGAL_METHOD_PROFESSIONAL`, `CONFIGURATION_RUNTIME`,
`SECURITY_OPERATIONAL`, `EXTERNAL_SPEC`, `OTHER`) + status
(`ACCEPTED`=adopted/current, `DECLARED`=rules stated but currency
unestablished, `DRAFT`, `SUPERSEDED`, `UNKNOWN`=unestablishable) +
applicability + optional declared precedence. Created only when the
bounded evidence explicitly supports governance, status, and scope.
Precedence is `PRIORITY_RANK` (lower wins; same explicit scheme only)
or `OVERRIDES` (named evidence only); absence is never reconstructed.
Without authority, claims stay `PARTIAL`/`UNRESOLVED` — never
inferred, never confidence-approved. Supersession is explicit with
retained history.

## Trust vs freshness (never mixed)

`TrustState` (ESTABLISHED/PARTIAL/AMBIGUOUS/CONFLICTED/UNRESOLVED) is
establishment only. `Freshness` (CURRENT/STALE/UNVERIFIABLE) is
currency only. Conflicts surface both sides plus declared precedence;
ambiguity returns candidates; missing knowledge returns unresolved
with a deterministic `ResolutionRequirement` where statable.

---

## Evidence kinds in practice

Span deliberately keeps **evidence** and **authority** separate.

Relevant repository evidence may include:

- source code;
- documentation;
- tests;
- configuration;
- contracts;
- specifications;
- decision records;
- project configuration;
- external specifications;
- other repository material.

Finding relevant evidence does not automatically make it authoritative.

For example:

### Source code

Can show what the implementation currently does.

### Tests

Can provide observed verification evidence when actually executed and recorded as such.

The mere existence of a test is not equivalent to a passing verification result.

### Configuration

Can establish a declared or runtime operating choice depending on the evidence available.

### Contracts, specifications, ADRs, and product decisions

May govern what the system is supposed to do where the repository establishes their authority and applicability.

Span can preserve an interpretation of these sources.

It does not silently turn an AI-generated conclusion into governing authority.

Where authority is missing, ambiguous, superseded, or conflicting, that state remains explicit.


---
