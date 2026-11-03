# ADR-0005: Two-tier evals, scored on evidence, against a frozen fixture

Status: accepted

## Context

"50+ evals scored on every commit" collides with two realities: free-tier
LLM rate limits would break CI, and live tender data changes nightly, so any
eval asserting specific answers against it goes stale by design.

## Decision

Two tiers:

1. **Every commit, no LLM**: ruff, pytest (mappers, store, matcher, semantic
   governance, MCP tools, the eval *scorer* itself), and a dbt build with
   tests against the committed fixture.
2. **Nightly / on demand, LLM**: `evals/harness.py` runs the 52-question
   suite with responses cached per (question, model, fixture) and skips
   gracefully when no API key is available (fork PRs).

Both LLM evals and deterministic dbt checks run against a **frozen fixture**
(`fixtures/`, 511 notices, script-built by `scripts/build_fixture.py`) with
the clock pinned via `TENDER_RADAR_TODAY` from the fixture manifest. Gold
answers are **SQL against the fixture**, declared per question in
`evals/questions.yaml` — never an LLM's opinion. An LLM-judge quality score
can be layered on later; it is explicitly not the headline number.

## Consequences

- Eval results are reproducible: same fixture, same clock, same golds.
- Live data health is checked separately (`dbt source freshness`, nightly
  pipeline run) without asserting specific answers.
- The fixture must be regenerated deliberately when the schema or eval needs
  change; the manifest records when and from what it was built.
- Citation integrity is absolute: any cited tender not in the fixture fails
  the eval, which is what makes hallucinated sources visible.
