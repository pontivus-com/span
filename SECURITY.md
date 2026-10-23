# Security policy

## Supported versions

Span is pre-1.0. Security fixes land on the current `0.6.x` line.

## Reporting a vulnerability

Please report privately. Use GitHub's **Report a vulnerability** flow on the
repository's Security tab, or email `r.streefkerk@gmail.com`.

Include:

- the Span version and how it was installed;
- your operating system and Python version;
- the affected operation or file;
- a minimal reproduction, if one is available.

Do not open a public issue for a suspected vulnerability before a fix is
available.

## Scope

Span runs locally over stdio. It does not open a network listener, call a
model provider, or send repository content to a hosted service. Its state
lives in a local data directory outside the repositories it analyzes.

The installer writes to deliberately chosen locations: Span's own virtual
environment and tools directory, the user's binary directory, host MCP
configuration, target-repository `AGENTS.md` managed blocks, and deployed
skill files. A report that one of those writes escapes its documented
location is in scope.

Secrets in a target repository are not read intentionally. If Span surfaces
a credential in evidence or an answer, treat it as a security report.
