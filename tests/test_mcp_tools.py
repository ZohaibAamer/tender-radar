"""MCP tool behavior against a small, known warehouse."""

from pathlib import Path

import duckdb
import pytest

from tender_radar.mcp_server import tools

PINNED_TODAY = "2026-11-01"
PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setenv("TENDER_RADAR_TODAY", PINNED_TODAY)


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE fct_tenders AS
        SELECT * FROM (VALUES
            ('ocds-h6vhtk-1', 'fts', 'ocds-h6vhtk-1', 'n1',
             'Data analytics platform for NHS trust',
             'A data warehouse and dashboard build', 'NHS England', 'GB',
             ['72000000'], '72000000', '72',
             'IT services: consulting, software development, Internet and support',
             300000.0, 'GBP', 'estimated', 'active', 'tender', 1::BIGINT,
             DATE '2026-10-20', DATE '2026-10-20', DATE '2026-11-09', false,
             'https://example.org/1'),
            ('ocds-b5fd17-2', 'contracts_finder', 'ocds-b5fd17-2', 'n2',
             'Grounds maintenance', 'Mowing and planting', 'Leeds City Council', 'GB',
             ['77314000'], '77314000', '77',
             'Agricultural, forestry, horticultural, aquacultural and apicultural services',
             80000.0, 'GBP', 'estimated', 'active', 'tender', 1::BIGINT,
             DATE '2026-10-22', DATE '2026-10-22', DATE '2026-12-01', false,
             'https://example.org/2'),
            ('ted:3', 'ted', NULL, 'n3',
             'Research study on digital evaluation', 'Analytics research', 'EU Body', 'DE',
             ['73110000'], '73110000', '73',
             'Research and development services and related consultancy services',
             NULL, NULL, 'unknown', 'active', 'tender', 1::BIGINT,
             DATE '2026-10-25', DATE '2026-10-25', DATE '2026-10-30', false,
             'https://example.org/3')
        ) AS v(tender_ref, source, ocid, latest_notice_id, title, description,
               buyer_name, country, cpv_codes, main_cpv, cpv_division,
               cpv_division_label, value_amount, value_currency, value_type,
               status, latest_notice_type, notice_count, first_published_date,
               last_published_date, deadline_date, has_award, url)
    """)
    con.close()
    return path


def test_search_by_keyword_and_source(warehouse):
    rows = tools.search_tenders(query="analytics", warehouse=warehouse)
    assert {r["tender_ref"] for r in rows} == {"ocds-h6vhtk-1", "ted:3"}
    rows = tools.search_tenders(query="analytics", source="ted", warehouse=warehouse)
    assert [r["tender_ref"] for r in rows] == ["ted:3"]


def test_search_open_only_uses_pinned_clock(warehouse):
    rows = tools.search_tenders(open_only=True, warehouse=warehouse)
    # ted:3's deadline (10-30) is before pinned today (11-01)
    assert {r["tender_ref"] for r in rows} == {"ocds-h6vhtk-1", "ocds-b5fd17-2"}


def test_get_tender_detail_and_missing(warehouse, tmp_path):
    missing_links = tmp_path / "links" / "none.parquet"
    tender = tools.get_tender("ocds-h6vhtk-1", warehouse=warehouse, links_path=missing_links)
    assert tender["title"] == "Data analytics platform for NHS trust"
    assert tools.get_tender("nope", warehouse=warehouse, links_path=missing_links)["error"]


def test_match_profile_ranks_and_reasons(warehouse):
    result = tools.match_profile(
        "example-uk-data-consultancy",
        warehouse=warehouse,
        profiles_dir=PROFILES_DIR,
    )
    refs = [m["tender_ref"] for m in result["matches"]]
    assert refs == ["ocds-h6vhtk-1"]  # GB + CPV 72; grounds maintenance filtered out
    assert result["matches"][0]["match_reasons"]
    assert result["as_of"] == PINNED_TODAY


def test_match_profile_unknown_name_lists_available(warehouse):
    result = tools.match_profile("missing", warehouse=warehouse, profiles_dir=PROFILES_DIR)
    assert "example-uk-data-consultancy" in result["error"]


def test_upcoming_deadlines_horizon(warehouse):
    result = tools.upcoming_deadlines(horizon_days=10, warehouse=warehouse)
    assert [r["tender_ref"] for r in result["deadlines"]] == ["ocds-h6vhtk-1"]
    assert result["as_of"] == PINNED_TODAY


def test_query_metric_round_trip(warehouse):
    result = tools.query_metric("tender_count", dimensions=["source"], warehouse=warehouse)
    assert {r["source"]: r["tender_count"] for r in result["rows"]} == {
        "fts": 1, "contracts_finder": 1, "ted": 1,
    }
    assert "SELECT" in result["compiled_sql"]


def test_no_tool_accepts_sql():
    """The governance claim, as a test: no tool parameter accepts SQL."""
    import inspect

    for name in ("search_tenders", "get_tender", "match_profile",
                 "upcoming_deadlines", "query_metric"):
        signature = inspect.signature(getattr(tools, name))
        assert "sql" not in {p.lower() for p in signature.parameters}
