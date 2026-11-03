"""CLI: incremental, idempotent ingest into per-source parquet files.

    uv run python -m tender_radar.ingest --source all --since 2026-10-01
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from tender_radar import config

from . import contracts_finder, fts, ted
from .store import count_rows, merge_parquet

FETCHERS = {
    "fts": fts.fetch,
    "contracts_finder": contracts_finder.fetch,
    "ted": ted.fetch,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tender_radar.ingest")
    parser.add_argument("--source", choices=[*FETCHERS, "all"], default="all")
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=config.today() - timedelta(days=7),
        help="fetch notices published/updated on or after this date (default: 7 days ago)",
    )
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args(argv)

    sources = list(FETCHERS) if args.source == "all" else [args.source]
    for source in sources:
        print(f"[{source}] fetching since {args.since} ...", flush=True)
        notices = list(FETCHERS[source](args.since, max_pages=args.max_pages))
        path = merge_parquet(notices, source, config.RAW_DIR)
        print(f"[{source}] fetched {len(notices)} notices; {count_rows(path)} total in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
