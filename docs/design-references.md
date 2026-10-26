# Design references

The design notes referred to in code comments as **A–M** were the working design
series used while the product moved from 0.7 to 0.8. They are historical
identifiers, not current specifications. This page maps each identifier to the
canonical documentation that now owns the subject.

| note | subject | current owner |
| --- | --- | --- |
| A | Subject resolution: exact locator precedence and ambiguous identity | [queries.md](queries.md) |
| B | Question coverage, disposition, and missing-state decisions | [freshness.md](freshness.md), [interpretation.md](interpretation.md) |
| C | Explicit completion: `ANSWERED` must assert; no implied completion | [interpretation.md](interpretation.md) |
| D | Target establishment and host-facing admission | [scope.md](scope.md) |
| E | Installer lifecycle, target accounting, and artifact census | [install.md](install.md), [scope.md](scope.md) |
| F | Structural navigation: locate, neighbors, outline, and cursors | [ports.md](ports.md) |
| G | Structural diagnostics, Graft provisioning, and preflight facts | [indexing.md](indexing.md) |
| H | Interpretation exchange, correction, and resumption | [interpretation.md](interpretation.md) |
| I | Answer surfaces: pages, excerpts, currency, and state explanation | [queries.md](queries.md), [mcp.md](mcp.md) |
| J | Scoped pagination and scoped freshness | [scope.md](scope.md), [freshness.md](freshness.md) |
| L | Coverage and evidence ownership | [interpretation.md](interpretation.md) |
| M | Task brief shape and submission readback | [interpretation.md](interpretation.md) |

When a comment names a note, read the linked document; the note number only
records where the requirement originated.
