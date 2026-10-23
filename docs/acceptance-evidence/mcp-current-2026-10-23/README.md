# Current MCP session — 2026-10-23

Source: an external-client acceptance run against the installed `span-mcp`
(eleven tools, compact wire), recorded 2026-10-23.
Repository: the `synth` fixture (`src/alpha.py`, `src/beta.py`).

The client is a scripted external MCP client, not an LLM. This records the
wire exchange and the server's freshness behaviour, not model behaviour.

## Controlled edit

`src/alpha.py` changes from:

```text
VALUE = 1
```

to:

```text
VALUE = 1
# touched
```

`src/beta.py` is unchanged.

## Round log

| # | Tool | Target | Result |
|---|---|---|---|
| 1 | `explain` | `src/alpha.py` | `PendingInterpretation`, `cont-1`, CQ-01 |
| 2 | `submit_interpretation` | `cont-1` | PURPOSE `CURRENT` |
| 3 | `explain` | `src/alpha.py` | PURPOSE `CURRENT`, no suspension |
| 4 | — | edit | `# touched` appended |
| 5 | `status` | `src/alpha.py` | PURPOSE `STALE`, refresh scope `src/alpha.py` |
| 6 | `refresh` | `src/alpha.py` | `PendingInterpretation`, `cont-6`, CQ-01 |
| 7 | `submit_interpretation` | `cont-6` | new PURPOSE `CURRENT`; predecessor `STALE` |
| 8 | `status` | `src/beta.py` | PURPOSE `CURRENT`; subject `UNVERIFIABLE` (dirty tree) |

## Compact transcript

```text
> explain src/alpha.py
PendingInterpretation  cont-1  CQ-01
  evidence: src/alpha.py L1-L2  "VALUE = 1"

> submit_interpretation  cont-1
PURPOSE  alpha computes the value            CURRENT

> explain src/alpha.py
PURPOSE  alpha computes the value            CURRENT

# edit src/alpha.py  (append "# touched")

> status src/alpha.py
PURPOSE  alpha computes the value            STALE
reason: evidence fingerprint changed since indexing
refresh scope: src/alpha.py

> refresh src/alpha.py
PendingInterpretation  cont-6  CQ-01
  evidence: src/alpha.py L1-L3  "VALUE = 1\n# touched"

> submit_interpretation  cont-6
PURPOSE  alpha computes the value            CURRENT
PURPOSE  alpha computes the value            STALE  (superseded predecessor)
```

## Files

`transcript.jsonl` contains the selected verbatim records in chronological
order. No absolute paths.
