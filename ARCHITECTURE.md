# Architecture

```
  UK Find a Tender      UK Contracts Finder        EU TED
  (OCDS releases)        (OCDS releases)         (eForms API)
        │                      │                      │
        └───────── one OCDS mapper ──────────── eForms mapper
                       │                              │
                       ▼                              ▼
             src/tender_radar/ingest  →  data/raw/{source}.parquet
                       (idempotent merge, keyed on source+notice_id)
                                   │
                                   ▼
                    dbt on DuckDB (dbt/ project)
          staging (views) → core (notices, tenders, cpv) → marts
                                   │
                 fct_tenders  ←  enforced model contract
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
   semantic/layer.yaml      MCP server (stdio)      dedupe matcher
   (metrics+dimensions) ←── 5 tools, 1 resource     tender_links.parquet
   compiled to SQL by       NO free-SQL tool        (measured P/R)
   semantic/compiler.py            │
                                   ▼
                  any MCP client: desktop AI apps, MCP
                  Inspector, or the CLI agent loop
                  (src/tender_radar/agent — Gemini Flash)
                                   │
                                   ▼
                    evals/harness.py: 52 questions,
                    SQL gold answers, frozen fixture
```

## The one-paragraph version

Three procurement portals, two publication standards, one OCDS-shaped schema.
Python mappers normalize at ingest; dbt layers the warehouse and enforces a
contract on the single mart the rest of the system reads. Everything an AI
agent can do is defined by the MCP server, and everything the server can
aggregate is declared in one YAML file. Correctness is demonstrated, not
asserted: dbt tests and 42 unit/governance tests on every commit, and a
52-question agent eval suite scored on evidence against a frozen fixture.

## Components

| Component | Where | Job |
|---|---|---|
| Ingest | `src/tender_radar/ingest/` | Fetch + map each source into `UnifiedNotice`; idempotent parquet merge |
| Transform | `dbt/` | staging → core → marts; CPV hierarchy from code prefixes; lifecycle dedup keyed on `tender_ref` |
| Cross-portal dedup | `src/tender_radar/dedupe/` | FTS↔CF heuristic matcher; links table with confidence; thresholds measured on labeled pairs |
| Semantic layer | `src/tender_radar/semantic/` | `layer.yaml` declares metrics/dimensions; the compiler is the only path to SQL |
| MCP server | `src/tender_radar/mcp_server/` | stdio server; 5 tools + the YAML as a discoverable resource |
| Agent | `src/tender_radar/agent/` | ~100-line loop; provider-agnostic; collects citations |
| Evals | `evals/` + `fixtures/` | Frozen 511-notice fixture, pinned clock, SQL gold answers |

## Key invariants

1. **No free SQL, anywhere.** The MCP server offers no tool that accepts SQL,
   so governance cannot be bypassed by any client ([ADR-0001](docs/adr/0001-governance-in-the-server.md)).
2. **The clock is injectable.** Every "today" flows through
   `config.today()` (`TENDER_RADAR_TODAY`), so deadline logic is identical on
   live data and the frozen fixture.
3. **Marts are a contract.** dbt's enforced contract on `fct_tenders` turns
   schema drift into a build failure before the semantic layer can notice.
4. **Reruns are free.** Ingest merges are keyed and idempotent; the fixture
   is script-built; eval responses are cached.
5. **Tender text is data.** Titles and descriptions are third-party input;
   the system prompt says so and the injection evals test it.

## Decision records

- [ADR-0001](docs/adr/0001-governance-in-the-server.md) — governance enforced in the MCP server
- [ADR-0002](docs/adr/0002-hand-rolled-agent-loop.md) — hand-rolled agent loop over a framework
- [ADR-0003](docs/adr/0003-hand-rolled-semantic-layer.md) — Cube-style YAML over MetricFlow
- [ADR-0004](docs/adr/0004-data-on-release-assets.md) — data lives in GitHub Release assets
- [ADR-0005](docs/adr/0005-frozen-fixture-evals.md) — two-tier evals on a frozen fixture
- [ADR-0006](docs/adr/0006-ocds-shaped-schema-and-sources.md) — OCDS-shaped schema; why Contracts Finder is a source
