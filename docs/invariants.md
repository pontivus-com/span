# Invariant audit matrix (G-09, plan §17)

Method: each invariant traced from canonical ingress through
storage, service composition, and MCP output to its tests. Verdict
`Test` = mechanically test-enforced; `Review` = code-inspection
enforced (no meaningful runtime probe exists). No violations found;
first offending boundary would be recorded here.

| ID | Invariant | Verdict | Evidence |
|---|---|---|---|
| I-01 | Functional-core purity | Test | `CorePurityTest` (stdlib + `span.core` only, AST scan) |
| I-02 | Strict ingress | Test | Unknown tags/values/fields rejected (`test_core_model`); MCP ingress tests |
| I-03 | Closed semantic vocabulary | Test | Kind-allowlist rejections; enum-exactness tests |
| I-04 | One semantic carrier | Test | `ChangeKind` single home; schema-sync test; no-DTO store design |
| I-05 | Evidence integrity | Test | Missing-evidence rejections; unresolved + resolver requirements |
| I-06 | Authority integrity | Test | UNKNOWN/status/section/quote checks; structural-derivation rejection |
| I-07 | Ownership integrity | Test | EC-05 populations; owner-vs-consumer assertions; retired-owner test |
| I-08 | Conflict integrity | Test | Core + recorded conflicts merged; pair-atomicity test; S-01/S-02 |
| I-09 | Ambiguity integrity | Test | Ambiguous-identity candidates, no arbitrary pick |
| I-10 | Freshness preflight | Test | Stale/current assertions; coverage step-0; hook read-only proof |
| I-11 | Partial-refresh integrity | Test | Failed-unit-preserved-as-stale; history preservation assertions |
| I-12 | Verification integrity | Test | Candidate vs pass currency distinguished; never presented as passed |
| I-13 | Structural separation | Review | Store holds canonical JSON + query columns only; no graph duplication |
| I-14 | Provider neutrality | Test | Graft errors on unknown vocabulary; generic port protocol tests |
| I-15 | No semantic reconstruction | Review | Composers project stored state; MCP/adapter/store add no judgments |
| I-16 | Boundedness | Test | Bounds policy, rejection-never-clamped, truncation categories |
| I-17 | Publication isolation | Test | Isolation gate; hermetic venv install + suite (see G-07 record) |
| I-18 | No semantic `Any` | Test | Import/type scan clean; canonical decode refuses untyped collections |
| I-19 | Success-path completeness | Test | Fixture exchanges settle first-pass; validation as backstop |
| I-20 | Demand-driven indexing | Test | Bounded units; init performs no interpretation; no whole-repo crawl in code |
| I-21 | Reconstructible rebuild only | Review | §10.4 rule; rebuild paths preserve required history (retired tables) |
| I-22 | Missing authority remains missing | Test | UNRESOLVED + live-agent run qualified without invention |
| I-23 | Skill non-authority | Test | `test_skills.py` allowlist/vocabulary/preservation/independence |
| I-24 | Skill/API consistency | Test | Canonical-ops-only scan across both skills |
| I-25 | Skill optionality | Test | Implementation-independence scan; suite runs skill-free |
| I-26 | Lifecycle placement | Test | Impact/status/refresh brief and currency assertions |
| I-27 | Offline bootstrap isolation | Test | UNINITIALIZED answers + setup notices; no-implicit-bootstrap scan |
| I-28 | Interactive hook boundedness | Test | HOOK_FAST scoped work; closure/silence assertions |
| I-29 | No automatic semantic interpretation | Test | Adapter operation scan; hook paths never suspend |
| I-30 | No automatic refresh | Test | Hooks report only; refresh explicit with suspension |
| I-31 | Readiness/trust separation | Test | Readiness enum distinct; status carries both distinctly |
| I-32 | Irrelevant-change silence | Test | Unrelated-edit and unknown-hook silence assertions |
| I-33 | Trust/freshness singularity | Test | Enum-exactness (no STALE in trust); separate dimensions end to end |
| I-34 | Tagged reference ingress | Test | Bare-id unions absent from `src/`; ref resolution tests |
| I-35 | Canonical operational bounds | Test | Policy defaults/maxima/hook bounds; rejection tests |
| I-36 | Answer self-containment | Test | I-36 ref-resolution assertions; pair-atomic selection |
| I-37 | Coverage-scoped atomic reconciliation | Test | Withdrawal, retire-history, supersession recovery, latest-wins |
| I-38 | Proposal-typed change classification | Test | Gating tests with/without affected assertions |
| I-39 | Continuation/pagination separation | Test | Union submit results; redeemable `pg:` cursors; malformed-token failures |

Downstream-compensation check (no silent repairs, no salvage, no
fallback parsing): validation rejects whole units; strict decode has
no fallback branch; service never synthesizes summaries, quotes, or
identifiers (auto-keys are deterministic intra-result labels, not
semantic content).
