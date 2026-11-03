"""Heuristic cross-portal matcher: FTS ↔ Contracts Finder.

Many above-threshold UK notices appear on both portals with different ids, so
there is no shared key. The matcher is deliberately transparent:

1. **Blocking** — candidate pairs must share a normalized buyer name and have
   published within 90 days of each other.
2. **Scoring** — a weighted similarity over title, main CPV, and disclosed
   value. Every emitted link carries its confidence and a human-readable
   match reason; records are never silently merged.

Thresholds are not guessed: `scripts/evaluate_matcher.py` sweeps them against
hand-labeled pairs and reports precision/recall.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

# Suffixes that differ between portals for the same organisation.
_NOISE_WORDS = {"ltd", "limited", "plc", "llp", "the", "of"}
BLOCK_WINDOW_DAYS = 90
# Measured on evals/dedupe_labels.csv (55 pairs): precision 0.93, recall 0.89,
# F1 0.91 — the best point of the sweep in scripts/evaluate_matcher.py.
DEFAULT_THRESHOLD = 0.75


def normalize_buyer(name: str) -> str:
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [w for w in text.split() if w not in _NOISE_WORDS]
    return " ".join(words)


@dataclass
class Candidate:
    fts_ref: str
    cf_ref: str
    title_similarity: float
    cpv_match: bool
    value_similarity: float | None
    confidence: float
    match_reason: str


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _value_similarity(a: float | None, b: float | None) -> float | None:
    if not a or not b or a <= 0 or b <= 0:
        return None
    return min(a, b) / max(a, b)


def score_pair(
    fts_ref: str,
    cf_ref: str,
    fts_title: str,
    cf_title: str,
    fts_cpv: str | None,
    cf_cpv: str | None,
    fts_value: float | None,
    cf_value: float | None,
) -> Candidate:
    title_sim = _title_similarity(fts_title, cf_title)
    cpv_match = bool(fts_cpv and cf_cpv and fts_cpv[:4] == cf_cpv[:4])
    value_sim = _value_similarity(fts_value, cf_value)

    # Title dominates; CPV agreement and value proximity corroborate. When a
    # value is missing on either side it neither helps nor hurts.
    confidence = 0.75 * title_sim + 0.15 * (1.0 if cpv_match else 0.0)
    confidence += 0.10 * value_sim if value_sim is not None else 0.10 * title_sim

    reasons = [f"title {title_sim:.2f}"]
    if cpv_match:
        reasons.append("cpv class match")
    if value_sim is not None:
        reasons.append(f"value ratio {value_sim:.2f}")
    return Candidate(
        fts_ref=fts_ref,
        cf_ref=cf_ref,
        title_similarity=round(title_sim, 4),
        cpv_match=cpv_match,
        value_similarity=round(value_sim, 4) if value_sim is not None else None,
        confidence=round(min(confidence, 1.0), 4),
        match_reason=", ".join(reasons),
    )


_UK_ROWS_SQL = """
    SELECT tender_ref, source, title, buyer_name, main_cpv,
           value_amount, first_published_date
    FROM fct_tenders
    WHERE source IN ('fts', 'contracts_finder') AND buyer_name <> ''
"""


def find_candidates(warehouse: Path, window_days: int = BLOCK_WINDOW_DAYS) -> list[Candidate]:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(_UK_ROWS_SQL).fetchall()
    finally:
        con.close()

    # Blocking in Python: same normalized buyer, published within the window.
    by_buyer: dict[str, dict[str, list[tuple]]] = {}
    for ref, source, title, buyer, cpv, value, published in rows:
        bucket = by_buyer.setdefault(normalize_buyer(buyer), {"fts": [], "contracts_finder": []})
        bucket[source].append((ref, title, cpv, value, published))

    candidates: list[Candidate] = []
    for bucket in by_buyer.values():
        for fts_ref, fts_title, fts_cpv, fts_value, fts_date in bucket["fts"]:
            for cf_ref, cf_title, cf_cpv, cf_value, cf_date in bucket["contracts_finder"]:
                if abs((fts_date - cf_date).days) > window_days:
                    continue
                candidates.append(
                    score_pair(
                        fts_ref, cf_ref, fts_title, cf_title,
                        fts_cpv, cf_cpv, fts_value, cf_value,
                    )
                )
    return candidates


def write_links(
    candidates: list[Candidate],
    out_path: Path,
    threshold: float = DEFAULT_THRESHOLD,
    matched_on: date | None = None,
) -> int:
    """Persist links at or above the confidence threshold."""
    links = [c for c in candidates if c.confidence >= threshold]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute("""
            CREATE TABLE links (
                fts_ref VARCHAR, cf_ref VARCHAR,
                title_similarity DOUBLE, cpv_match BOOLEAN, value_similarity DOUBLE,
                confidence DOUBLE, match_reason VARCHAR, matched_on DATE
            )
        """)
        if links:
            con.executemany(
                "INSERT INTO links VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    [
                        c.fts_ref, c.cf_ref, c.title_similarity, c.cpv_match,
                        c.value_similarity, c.confidence, c.match_reason,
                        matched_on or date.today(),
                    ]
                    for c in links
                ],
            )
        con.execute(f"COPY links TO '{out_path}' (FORMAT PARQUET)")
    finally:
        con.close()
    return len(links)
