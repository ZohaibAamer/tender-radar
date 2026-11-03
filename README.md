# Tender Radar

A **Public Tender Intelligence Agent**: SMEs miss relevant public contracts because
notices are scattered across portals in different formats. Tender Radar unifies UK and
EU tender notices into one governed dataset and exposes it to AI agents through an MCP
server — with an eval suite that proves the agent answers correctly.

**Flagship question:** *"Which open tenders fit a 50-person data consultancy in the UK?"* —
answered with cited sources.

## What it demonstrates

- **One unified schema from two standards** — OCDS (UK Find a Tender, Contracts Finder)
  and eForms (EU TED), mapped per official OCP guidance.
- **Governed data access** — agents query through a semantic layer (metrics + dimensions
  compiled to SQL by the server). There is no free-SQL tool to bypass.
- **Measured deduplication** — cross-portal matching with precision/recall reported
  against hand-labeled pairs.
- **Evals in CI** — deterministic tests on every commit; 50+ evidence-scored agent evals
  (including prompt-injection and governance tests) against a frozen fixture.

## Stack

Python 3.12+ · DuckDB · dbt · hand-rolled Cube-style semantic layer · MCP server (stdio) ·
Gemini Flash (swappable provider)

## Status

🚧 Early development. See [PLAN.md](PLAN.md) for the full agreed design and build plan.

## License

Code is MIT-licensed. Tender data belongs to its source portals — see the data
attribution section (to be added with the first committed fixture).
