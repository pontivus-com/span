<h1 align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/v0.6.0/assets/span-logo-plate-dark.png" alt="Span" width="360">
</h1>

<p align="center">
  <strong>Carry useful investigations into the next coding session.</strong>
</p>

<p align="center">
  Span keeps the explanations your coding agent worked out, the evidence
  behind them, and what needs another look when that evidence changes.
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-server-111B21?style=flat-square" alt="MCP server"></a>
  <a href="https://github.com/pontivus-com/span/actions/workflows/ci.yml"><img src="https://github.com/pontivus-com/span/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/pontivus-com/span/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Linux%20verified-lightgrey?style=flat-square" alt="Linux verified">
  <img src="https://img.shields.io/badge/status-beta-orange?style=flat-square" alt="Beta">
  <a href="https://github.com/pontivus-com/span/stargazers"><img src="https://img.shields.io/github/stars/pontivus-com/span?style=flat-square" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="#how-it-works"><strong>How it works</strong></a> ·
  <a href="https://github.com/pontivus-com/span/tree/master/docs"><strong>Docs</strong></a>
</p>

## Keep the understanding your agent worked for

A coding agent traces a request across services, checks the tests, finds the
contract, and explains why the boundary exists. The next session should be
able to find that explanation and see whether its support still holds.

Span makes that investigation reusable. It is a local MCP server where agents
record coherent explanations with exact source support, explicit gaps, and
version history. Later agents can discover the explanation through an ordinary
engineering question, then inspect what is current, disputed, or changed.

The coding agent does the thinking. Span keeps the record and checks its
support.

## How it works

1. **Investigate a real question.** Ask over the relevant scope. Span returns
   qualified saved candidates or inspectable source evidence and an honest gap.
2. **Record the useful result.** Save conclusions across the files you actually
   examined, with their support and unanswered questions. Work that started
   outside Span can be recorded directly after evidence admission.
3. **Reuse in a fresh session.** Ask the next engineering question, discover
   applicable understanding, and retrieve it with live support and challenges.
4. **Reassess after change.** Check affected dependencies, investigate what
   changed, then confirm, correct, replace, or withdraw the explanation.
   Earlier versions remain inspectable.

One explanation can span code, tests, CSS, configuration, and contracts. The
agent decides what is worth recording; a file inventory does not become a
mandatory documentation campaign.

## See the lifecycle

Illustrative tool sequence, not literal request JSON. The installed schemas
and [MCP reference](docs/mcp.md) own the wire grammar.

```text
understand_question: "How does checkout decide whether to charge?"
  → InvestigationNeeded: exact evidence and an explicit gap

agent investigates; evidence_extend admits the additional sources

record_create: explanation + admitted support + remaining questions
  → committed receipt, understanding version 1, support qualification

fresh session asks: "Where is purchase eligibility decided?"
  → associated saved candidates; agent checks applicability
understand_retrieve
  → recorded explanation, live support, gaps, and challenges

supporting source changes
reassess
  → REASSESSMENT_REQUIRED with the affected dependencies

agent investigates and records a correction against the expected version
  → version 2; version 1 remains history
```

Source association and term overlap help discovery. A different wording can
find saved understanding without its original ID, but semantic equivalence is
not guaranteed. A candidate is a starting point for judgment.

## Know what can be reused

| Qualification | What the agent can conclude |
| --- | --- |
| `CURRENT` | The declared support still passes its checks. Applicability and semantic correctness still need judgment. |
| `REASSESSMENT_REQUIRED` | Source, authority, premise, or recorded membership support changed. Revisit the affected explanation. |
| `UNVERIFIABLE` | Required support cannot be established. The limitation stays explicit. |

Gaps and challenges remain visible independently of support currency. Matching
bytes do not settle a dispute, and test existence does not establish a pass.
Independent verification records the observations actually tested and preserves
failures as failures.

Recording is atomic and returns a receipt. The caller preserves identity
before sending; retrying the same identity and content recovers the retained
receipt after a lost response or process restart. A committed receipt and a
present support qualification answer different questions.

## Quick start

The verified installation path is Linux with Python 3.12+, Node.js, and npm.
From a checkout containing the 0.9.0 candidate:

```bash
python3 scripts/install-span.py --repo /path/to/your/repo
```

For a published package release, install `span-mcp` with your Python package
manager and run `span-install --repo /path/to/your/repo`. See
[install and connect](docs/install.md) for registration, verification, and the
offline store transition.

The installer provisions the managed structural indexer, runtime, skills, and
host integration. Reconnect your coding agent after upgrade so it receives the
new tools and instructions. Verify operational setup with:

```bash
span-install --verify-only
```

Setup creates no understanding. Begin with a question from your actual task;
see [using Span](docs/usage.md).

## Beta host status

| Host | Current scope |
| --- | --- |
| Codex | Live beta validation target; packaged lifecycle calls work with hooks explicitly disabled. |
| OpenCode | Managed integration remains implemented; earlier trials are not final-package revalidation. |
| Claude Code | Managed integration remains implemented; live model grammar and caller identity are UNVERIFIED under the owner waiver. |
| Other MCP hosts | Manual stdio connection is available; model-delivery behavior needs host-specific verification. |

Registration, hook configuration, and model-delivered behavior are distinct.
Optional hooks provide notices; retrieval and recording still check support
when hooks are absent. See [host integration](integrations/hosts/triggers.md).

## Fits around your agent

Span runs locally over stdio and keeps state outside target repositories. Your
agent uses its own model, tools, edits, and test runner. Span does not invoke a
model or store provider credentials. Structural search helps investigation;
recorded conclusions retain the agent's interpretation and declared support.

The intended benefit is continuity between sessions and a focused review of
changed support. Recording and host delivery have costs. This beta makes no
universal time/token-saving claim or completed comparative product-fitness
ACCEPT claim. See [acceptance](docs/acceptance.md).

## Status and documentation

This checkout describes **0.9.0 beta**: nineteen lifecycle tools, schema-10
storage, explicit offline transition, and live support qualification.
macOS and Windows installation paths remain unverified. Publication and
product acceptance are separate from the implementation version.

- [Install and connect](docs/install.md)
- [Using Span](docs/usage.md) and [first investigation](docs/onboarding-runbook.md)
- [Agent lifecycle](docs/lifecycle.md) and [MCP reference](docs/mcp.md)
- [Support and reassessment](docs/freshness.md)
- [Evidence and authority](docs/authority-trust.md)
- [Scope and boundaries](docs/scope.md) and [FAQ](docs/faq.md)
- [Architecture](docs/architecture.md), [repository overview](docs/overview.md), and [all docs](docs/README.md)
- [Changelog](CHANGELOG.md)

Older [acceptance evidence](docs/acceptance-evidence/) retains its historical
protocol and does not certify the rebuilt API or comparative value.

## Contributing

See [contributing](CONTRIBUTING.md). Preserve the central contract: useful
understanding stays attached to its support, noncurrent or uncertain state
stays explicit, and corrections preserve history. Security reports go through
[SECURITY.md](SECURITY.md); support expectations are in [SUPPORT.md](SUPPORT.md).

## Registry

Official MCP Registry entry: `io.github.pontivus-com/span`

mcp-name: io.github.pontivus-com/span

## License

Span is licensed under **Apache License 2.0** (`Apache-2.0`). See [LICENSE](LICENSE).
