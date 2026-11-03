# ADR-0004: Data lives in GitHub Release assets

Status: accepted

## Context

GitHub Actions runners are wiped per run, so nightly incremental ingest needs
persistent storage. Options: commit parquet to the repo (history bloat), git
LFS (quota), an object store (credentials and signup in the reviewer's path),
or GitHub Release assets.

## Decision

A rolling `data-latest` release holds the per-source parquet plus the dedup
links; the nightly job downloads it, merges new notices (idempotent, keyed),
and re-uploads with `--clobber`. On the first of each month a dated
`data-YYYY-MM` snapshot release is created so one bad nightly cannot erase
history.

## Consequences

- Zero extra credentials: the workflow's own `GITHUB_TOKEN` suffices, and a
  reviewer fetches the full dataset with one `gh release download`.
- Git history stays clean — no data commits, no LFS pointers.
- Release assets are not a database: the merge window means a missed night
  is healed by the next run, and anything older than the ingest window is
  preserved by the monthly snapshots.
- The repo works without any release: `python -m tender_radar.ingest`
  bootstraps from the live APIs, and the committed fixture serves tests.
