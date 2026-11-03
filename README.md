# Tender Radar

[![CI](https://github.com/ZohaibAamer/tender-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/ZohaibAamer/tender-radar/actions/workflows/ci.yml)

**A Public Tender Intelligence Agent: unified UK + EU procurement data, served
to AI agents through a governed MCP server, proven by an eval suite.**

Ask it *"Which open tenders fit a 50-person UK data consultancy?"* and it
answers with ranked matches and cited source links — through Claude Desktop,
MCP Inspector, or the bundled CLI agent.

---

## The problem

Public-sector contracts are a huge market that small and mid-sized companies
systematically miss, for a mundane reason: **the notices are scattered.**

- The UK publishes above-threshold tenders on **Find a Tender** and
  lower-value ones on **Contracts Finder** — in OCDS format, and often the
  same tender appears on both portals with different IDs.
- The EU publishes on **TED** — in a completely different standard (eForms),
  across 24 languages.

An SME bid team can't watch three portals in two data standards. And if you
put an LLM on top of raw data, you trade one problem for another: agents that
write their own SQL produce confident, wrong numbers — silently adding euros
to pounds, averaging framework ceilings into contract values, citing tenders
that don't exist.

Tender Radar solves both halves: **one unified dataset** and **an agent that
can only query it through governed, tested paths.**

## What it does

| Capability | How |
|---|---|
| Unifies 3 portals, 2 standards | One OCDS-shaped schema; one mapper per standard |
| Deduplicates | Lifecycle grouping by OCDS `ocid` + cross-portal matching with **measured precision 0.93 / recall 0.89** |
| Serves agents | MCP server (stdio) with 5 tools + a discoverable semantic-layer resource |
| Governs queries | Agents aggregate only via `query_metric`, compiled from [one YAML file](src/tender_radar/semantic/layer.yaml) — **no free-SQL tool exists** |
| Matches companies | YAML company profiles (Pydantic-validated) ranked against open tenders with reasons |
| Proves it works | 52 agent evals with SQL-derived gold answers, incl. governance negatives and prompt-injection tests |

## Architecture overview

```
  UK Find a Tender      UK Contracts Finder        EU TED
  (OCDS releases)        (OCDS releases)         (eForms API)
        │                      │                      │
        └───────── one OCDS mapper ──────────── eForms mapper
                       │                              │
                       ▼                              ▼
              Python ingest  →  data/raw/{source}.parquet
                  (idempotent merge, keyed per notice)
                                 │
                                 ▼
                       dbt on DuckDB
         staging (views) → core (notices, tenders, CPV) → marts
                                 │
                fct_tenders ← enforced model contract
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
   semantic layer         MCP server (stdio)     dedupe matcher
   (YAML → SQL           5 tools, 1 resource,    links + confidence,
    compiler)             NO free-SQL tool       measured P/R
                                 │
                                 ▼
               any MCP client: Claude Desktop,
               MCP Inspector, or the CLI agent
                   (Gemini Flash, swappable)
                                 │
                                 ▼
                  evals: 52 questions, SQL gold
                  answers, frozen 511-notice fixture
```

**The flow in words:** Python clients fetch each portal and map every notice
into one `UnifiedNotice` schema, merging idempotently into per-source Parquet.
dbt builds the warehouse in textbook layers — staging views per source, a
core layer that groups a tender's lifecycle notices (planning → tender →
award) by their shared `ocid`, and a single mart (`fct_tenders`) protected by
an enforced dbt contract. On top of that mart sit three consumers: a
hand-rolled semantic layer that compiles declared metrics to SQL, the MCP
server that exposes everything agents may do, and the cross-portal matcher
that links the same tender across UK portals. Deep dive: [ARCHITECTURE.md](ARCHITECTURE.md),
decisions: [docs/adr/](docs/adr/).

**Design invariants:**

1. **Governance lives in the server, not the agent.** There is no tool that
   accepts SQL, so no client — however prompted or jailbroken — can bypass
   the semantic layer ([ADR-0001](docs/adr/0001-governance-in-the-server.md)).
2. **The clock is injectable** (`TENDER_RADAR_TODAY`), so "open tender" and
   "deadline within 7 days" mean the same thing on live data and the frozen
   test fixture.
3. **Money is guarded.** Value metrics refuse to mix currencies and exclude
   framework ceilings by default — the YAML documents both rules.
4. **Tender text is data, not instructions.** Descriptions are third-party
   input; prompt-injection evals against a planted hostile tender verify the
   agent treats them that way.

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12, `uv` | Fast, reproducible env management |
| Ingestion | `httpx`, Pydantic | Typed unified schema at the edge |
| Storage | Parquet + DuckDB | Zero-infra analytical warehouse |
| Transform | dbt (`dbt-duckdb`) | Layered models, tests, contracts, source freshness |
| Semantic layer | Hand-rolled YAML + compiler | Governance legible in one file ([ADR-0003](docs/adr/0003-hand-rolled-semantic-layer.md)) |
| Agent interface | MCP Python SDK (stdio) | Works with Claude Desktop, Inspector, any MCP client |
| LLM | Gemini Flash via `google-genai` | Free tier; swappable behind a 3-method protocol |
| CI/CD | GitHub Actions | Tier-1 checks per push; on-demand data refresh + LLM evals |
| Data persistence | GitHub Release assets | No credentials, one-command download ([ADR-0004](docs/adr/0004-data-on-release-assets.md)) |
| Lint/test | ruff, pytest | 42 deterministic tests incl. the eval scorer itself |

## Project structure

```
tender-radar/
├── src/tender_radar/
│   ├── config.py            # paths + the injectable clock (TENDER_RADAR_TODAY)
│   ├── profiles.py          # Pydantic company profiles (YAML + generated JSON Schema)
│   ├── ingest/              # source clients, mappers, idempotent parquet store
│   │   ├── models.py        #   UnifiedNotice — the one schema everything maps into
│   │   ├── ocds.py          #   shared mapper for both UK portals
│   │   ├── ted.py           #   eForms → unified mapper (the cross-standard one)
│   │   └── store.py         #   keyed merge: reruns never duplicate
│   ├── dedupe/              # cross-portal matcher (blocking + scoring + links)
│   ├── semantic/            # layer.yaml (the governed surface) + SQL compiler
│   ├── mcp_server/          # stdio MCP server: 5 tools, semantic://layer resource
│   └── agent/               # ~100-line loop + swappable LLM provider
├── dbt/                     # staging → core → marts; CPV seed; contracts
├── profiles/                # company profiles as data (+ JSON Schema)
├── evals/                   # 52 questions, SQL golds, harness, dedupe labels
├── fixtures/                # frozen 511-notice eval fixture (script-built)
├── scripts/                 # fixture builder, matcher evaluation, schema gen
├── tests/                   # 42 deterministic tests (tier 1)
├── .github/workflows/       # ci.yml (every push) + data-refresh.yml (on demand)
├── ARCHITECTURE.md          # diagrams and component walkthrough
├── docs/adr/                # six architecture decision records
└── DATA_LICENSE.md          # OGL v3 / EU reuse attribution
```

## How to run it

Prerequisites: [uv](https://docs.astral.sh/uv/) (manages Python itself).
Everything below is idempotent — rerunning is always safe. Every step also
has a `make` shortcut — run `make help` for the list.

### 1. Install

```bash
git clone https://github.com/ZohaibAamer/tender-radar && cd tender-radar
uv sync
```

### 2. Get data and build the warehouse

```bash
# ingest live notices from all three portals (public APIs, no keys needed)
uv run python -m tender_radar.ingest --source all --since 2026-10-01

# build the DuckDB warehouse with dbt
DBT_PROFILES_DIR=dbt uv run dbt deps --project-dir dbt
DBT_PROFILES_DIR=dbt uv run dbt build --project-dir dbt

# compute cross-portal duplicate links
uv run python -m tender_radar.dedupe
```

(If a `data-latest` release has been published, you can skip ingestion:
`gh release download data-latest --dir data/raw`.)

### 3. Use it from an MCP client

Fastest look — the official Inspector UI:

```bash
npx @modelcontextprotocol/inspector uv run tender-radar-mcp
```

Claude Desktop / Claude Code (`mcpServers` config):

```json
{
  "tender-radar": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/tender-radar", "tender-radar-mcp"]
  }
}
```

Tools: `search_tenders` · `get_tender` · `match_profile` ·
`upcoming_deadlines` · `query_metric` · `list_company_profiles`. The
semantic layer is readable as the `semantic://layer` resource, so agents
discover metrics instead of guessing.

### 4. Ask the CLI agent

```bash
export GEMINI_API_KEY=...   # free tier: https://aistudio.google.com
uv run python -m tender_radar.agent \
  "Which open tenders fit a 50-person UK data consultancy?"
```

Company profiles are plain YAML — copy
[profiles/example-uk-data-consultancy.yaml](profiles/example-uk-data-consultancy.yaml)
and describe your own company.

### 5. Run the tests and evals

```bash
# tier 1 — deterministic, no LLM, what CI runs on every push
uv run ruff check . && uv run pytest

# the matcher's measured scorecard (precision/recall sweep)
uv run python scripts/evaluate_matcher.py

# tier 2 — the 52-question agent eval suite (needs GEMINI_API_KEY)
TENDER_RADAR_DATA_DIR=$PWD/fixtures DBT_PROFILES_DIR=dbt \
  uv run dbt build --project-dir dbt          # fixture warehouse, once
uv run python evals/harness.py                # responses cached per question
uv run python evals/harness.py --category injection
```

## Data refresh and storage

The **Data refresh & evals** workflow (Actions tab, run on demand) ingests
the last 7 days from all three sources, rebuilds the warehouse, runs
`dbt source freshness` as the pipeline health check, recomputes dedup links,
and uploads Parquet to the rolling [`data-latest` release](../../releases),
optionally cutting a dated snapshot. **Nothing runs unattended by design** —
this is a reference implementation, not an operated service. To run it
nightly on your own fork, add the `cron` trigger shown at the top of
[data-refresh.yml](.github/workflows/data-refresh.yml).

## Licensing

Code is [MIT](LICENSE). Tender data belongs to its sources and is reused
under their terms — Open Government Licence v3.0 (both UK portals declare it
in their API responses) and the EU's reuse policy for TED. Full attribution
and the synthetic-test-row disclosure: [DATA_LICENSE.md](DATA_LICENSE.md).

## Honest limitations

- The TED mapper carries a pragmatic field subset (title, buyer, CPV, value,
  deadline, links); eForms is far richer than any flat schema.
- Cross-portal matching is title-driven: a renamed re-publication scoring
  below the measured 0.75 threshold is missed — a trade-off that is measured
  (P 0.93 / R 0.89), not hidden.
- Disclosed values are floors, not market sizes: many notices omit value,
  and the semantic layer's metric descriptions say so.
