# Tender Radar

[![CI](https://github.com/ZohaibAamer/tender-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/ZohaibAamer/tender-radar/actions/workflows/ci.yml)

A **Public Tender Intelligence Agent**. SMEs miss relevant public contracts
because notices are scattered across portals in different formats. Tender
Radar unifies UK and EU tender notices into one governed dataset and exposes
it to AI agents through an MCP server — with an eval suite that proves the
agent answers correctly.

**Flagship question:** *"Which open tenders fit a 50-person UK data
consultancy?"* — answered with cited sources, by any MCP client or the
bundled CLI agent.

## What this demonstrates

- **One unified schema from two standards.** UK Find a Tender and Contracts
  Finder publish OCDS; EU TED publishes eForms. One OCDS-shaped schema, one
  mapper per standard ([ADR-0006](docs/adr/0006-ocds-shaped-schema-and-sources.md)).
- **Governance that can't be bypassed.** Agents aggregate only through a
  semantic layer declared in [one YAML file](src/tender_radar/semantic/layer.yaml);
  the MCP server offers **no free-SQL tool at all**, so the rule holds for
  every client ([ADR-0001](docs/adr/0001-governance-in-the-server.md)). The
  layer refuses cross-currency sums, defaults framework ceilings out of
  averages, and caps high-cardinality group-bys.
- **Measured deduplication.** Lifecycle dedup is keyed on OCDS `ocid`
  (honestly: that part is keyed, not clever). Cross-portal FTS↔Contracts
  Finder matching is heuristic — and measured: **precision 0.93 / recall
  0.89** on [55 hand-labeled pairs](evals/dedupe_labels.csv), threshold
  chosen from the sweep, links emitted with confidence and reasons, never
  silently merged.
- **Evals as evidence, not vibes.** 52 agent questions with **SQL-derived
  gold answers** against a [frozen 511-notice fixture](fixtures/manifest.json)
  with a pinned clock — including governance negatives ("write me SQL") and
  **prompt-injection tests** against a planted hostile tender
  ([ADR-0005](docs/adr/0005-frozen-fixture-evals.md)). Deterministic tests run
  on every commit; LLM evals run nightly with cached responses.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). All data commands are idempotent.

```bash
uv sync

# 1. Ingest real data (or skip — tests and evals use the committed fixture)
uv run python -m tender_radar.ingest --source all --since 2026-10-01

# 2. Build the warehouse
DBT_PROFILES_DIR=dbt uv run dbt deps --project-dir dbt
DBT_PROFILES_DIR=dbt uv run dbt build --project-dir dbt

# 3. Cross-portal dedup links
uv run python -m tender_radar.dedupe

# 4. Tier-1 checks (what CI runs)
uv run ruff check . && uv run pytest
```

### Try the MCP server

No setup needed beyond the warehouse — the quickest look is MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run tender-radar-mcp
```

Or wire it into Claude Desktop / Claude Code (`mcpServers` config):

```json
{
  "tender-radar": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/tender-radar", "tender-radar-mcp"]
  }
}
```

Tools: `search_tenders`, `get_tender`, `match_profile`, `upcoming_deadlines`,
`query_metric`, `list_company_profiles`. The semantic layer is published as
the `semantic://layer` resource so agents discover metrics instead of
guessing. Deadline "alerts" are pull-based by design.

### Ask the agent

```bash
export GEMINI_API_KEY=...   # free tier: https://aistudio.google.com
uv run python -m tender_radar.agent \
  "Which open tenders fit a 50-person UK data consultancy?"
```

Company profiles are data: see
[profiles/example-uk-data-consultancy.yaml](profiles/example-uk-data-consultancy.yaml),
validated by a JSON Schema generated from the Pydantic model.

### Run the eval suite

```bash
# build the fixture warehouse once
TENDER_RADAR_DATA_DIR=$PWD/fixtures DBT_PROFILES_DIR=dbt \
  uv run dbt build --project-dir dbt

uv run python evals/harness.py            # all 52, cached
uv run python evals/harness.py --category injection
```

The matcher's own scorecard: `uv run python scripts/evaluate_matcher.py`.

## Data

Nightly GitHub Actions ingest the last 7 days from all three sources, rebuild
the warehouse, check `dbt source freshness`, and upload Parquet to the
rolling [`data-latest` release](../../releases), with monthly dated snapshots.
Grab the current dataset with:

```bash
gh release download data-latest --dir data/raw
```

Tender data is reused under the sources' terms — OGL v3 (UK) and the EU's
reuse policy (TED). Details and the synthetic-row disclosure:
[DATA_LICENSE.md](DATA_LICENSE.md).

## Honest limitations

- The TED mapper carries a pragmatic field subset (title, buyer, CPV, value,
  deadlines, links); eForms is much richer than any flat schema.
- Cross-portal matching is title-driven; a renamed re-publication below the
  0.75 threshold will be missed — that trade-off is measured, not hidden.
- Value metrics are floors, not market sizes: many notices disclose no value,
  and the semantic layer's descriptions say so.
