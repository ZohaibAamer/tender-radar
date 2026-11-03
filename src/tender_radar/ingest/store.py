"""Idempotent parquet storage: one file per source, merge on re-run.

A rerun of the same window must not create duplicates: rows are keyed by
(source, notice_id) and the most recently fetched version wins. Writes go to a
temp file first, then replace the old file atomically.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from .models import UnifiedNotice

COLUMNS = list(UnifiedNotice.model_fields)


def merge_parquet(notices: list[UnifiedNotice], source: str, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"{source}.parquet"
    temp = target.with_suffix(".parquet.tmp")

    rows = [[getattr(n, c) for c in COLUMNS] for n in notices]
    placeholders = ", ".join("?" * len(COLUMNS))

    con = duckdb.connect()
    try:
        con.execute("""
            CREATE TABLE incoming (
                source VARCHAR, notice_id VARCHAR, ocid VARCHAR, tender_ref VARCHAR,
                title VARCHAR, description VARCHAR, buyer_name VARCHAR, country VARCHAR,
                cpv_codes VARCHAR[], main_cpv VARCHAR,
                value_amount DOUBLE, value_currency VARCHAR, value_type VARCHAR,
                status VARCHAR, notice_type VARCHAR,
                published_date DATE, deadline_date DATE,
                url VARCHAR, fetched_at TIMESTAMPTZ
            )
        """)
        if rows:
            con.executemany(f"INSERT INTO incoming VALUES ({placeholders})", rows)
        union = "SELECT * FROM incoming"
        if target.exists():
            union += f" UNION ALL BY NAME SELECT * FROM read_parquet('{target}')"
        con.execute(f"""
            COPY (
                SELECT * EXCLUDE (rn) FROM (
                    SELECT *, row_number() OVER (
                        PARTITION BY source, notice_id ORDER BY fetched_at DESC
                    ) AS rn
                    FROM ({union})
                ) WHERE rn = 1
            ) TO '{temp}' (FORMAT PARQUET)
        """)
    finally:
        con.close()
    temp.replace(target)
    return target


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    con = duckdb.connect()
    try:
        return con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    finally:
        con.close()
