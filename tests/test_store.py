"""The merge must be idempotent: reruns never duplicate rows."""

from datetime import UTC, date, datetime, timedelta

from tender_radar.ingest.models import UnifiedNotice
from tender_radar.ingest.store import count_rows, merge_parquet


def make_notice(notice_id: str, title: str = "t", fetched_offset: int = 0) -> UnifiedNotice:
    return UnifiedNotice(
        source="fts",
        notice_id=notice_id,
        ocid=f"ocds-h6vhtk-{notice_id}",
        tender_ref=f"ocds-h6vhtk-{notice_id}",
        title=title,
        published_date=date(2026, 10, 1),
        url=f"https://example.org/{notice_id}",
        fetched_at=datetime(2026, 10, 2, tzinfo=UTC) + timedelta(hours=fetched_offset),
    )


def test_rerun_does_not_duplicate(tmp_path):
    notices = [make_notice("1"), make_notice("2")]
    path = merge_parquet(notices, "fts", tmp_path)
    assert count_rows(path) == 2
    merge_parquet(notices, "fts", tmp_path)  # identical rerun
    assert count_rows(path) == 2


def test_newer_fetch_wins(tmp_path):
    merge_parquet([make_notice("1", title="old")], "fts", tmp_path)
    path = merge_parquet([make_notice("1", title="new", fetched_offset=1)], "fts", tmp_path)
    import duckdb

    title = duckdb.sql(f"SELECT title FROM read_parquet('{path}')").fetchall()[0][0]
    assert title == "new"
    assert count_rows(path) == 1


def test_empty_batch_keeps_existing(tmp_path):
    merge_parquet([make_notice("1")], "fts", tmp_path)
    path = merge_parquet([], "fts", tmp_path)
    assert count_rows(path) == 1
