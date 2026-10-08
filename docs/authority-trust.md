# Evidence, authority, trust (plan §4.6, §6, MI-05)

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
