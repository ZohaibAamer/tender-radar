"""Measure the matcher against hand-labeled pairs and sweep thresholds.

    uv run python scripts/evaluate_matcher.py [--labels evals/dedupe_labels.csv]

The labels file is the ground truth: pairs a human has looked at and marked
as duplicate or not. Precision/recall are reported per threshold so the
production threshold is a measured choice, not a guess.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from tender_radar import config
from tender_radar.dedupe.matcher import find_candidates

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, default=REPO_ROOT / "evals" / "dedupe_labels.csv")
    args = parser.parse_args(argv)

    with open(args.labels, newline="") as f:
        labels = {
            (row["fts_ref"], row["cf_ref"]): row["is_duplicate"] == "true"
            for row in csv.DictReader(f)
        }
    if not labels:
        print("no labels found", file=sys.stderr)
        return 1

    scored = {
        (c.fts_ref, c.cf_ref): c.confidence for c in find_candidates(config.WAREHOUSE_PATH)
    }
    positives = sum(labels.values())
    print(f"{len(labels)} labeled pairs ({positives} true duplicates)")
    print(f"{'threshold':>9} {'precision':>9} {'recall':>7} {'f1':>5}")

    best = (0.0, 0.0)
    for threshold in [t / 100 for t in range(50, 100, 5)]:
        tp = fp = fn = 0
        for pair, is_dup in labels.items():
            # a labeled pair the blocker never produced scores 0
            predicted = scored.get(pair, 0.0) >= threshold
            tp += predicted and is_dup
            fp += predicted and not is_dup
            fn += (not predicted) and is_dup
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best[1]:
            best = (threshold, f1)
        print(f"{threshold:>9.2f} {precision:>9.2f} {recall:>7.2f} {f1:>5.2f}")

    print(f"\nbest f1 {best[1]:.2f} at threshold {best[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
