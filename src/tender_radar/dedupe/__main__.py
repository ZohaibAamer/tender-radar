"""CLI: find cross-portal duplicates and write the tender_links parquet.

    uv run python -m tender_radar.dedupe [--threshold 0.8]
"""

from __future__ import annotations

import argparse
import sys

from tender_radar import config

from .matcher import DEFAULT_THRESHOLD, find_candidates, write_links


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tender_radar.dedupe")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    candidates = find_candidates(config.WAREHOUSE_PATH)
    out = config.DATA_DIR / "links" / "tender_links.parquet"
    kept = write_links(candidates, out, threshold=args.threshold, matched_on=config.today())
    print(
        f"{len(candidates)} candidate pairs after blocking; "
        f"{kept} links at confidence >= {args.threshold} written to {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
