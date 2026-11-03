"""Governance tests: what the semantic layer must allow, refuse, and guard."""

from datetime import date

import duckdb
import pytest

from tender_radar.semantic import GovernanceError, compile_query, run_query

PINNED_TODAY = "2026-11-01"


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
            ('t1', 'fts',  'GBP', 100000.0, 'estimated', 'Buyer A', 'GB',
             'Construction work', DATE '2026-11-10', DATE '2026-10-01', 'active'),
            ('t2', 'fts',  'GBP', 900000.0, 'awarded',   'Buyer A', 'GB',
             'Construction work', NULL,              DATE '2026-10-05', 'complete'),
            ('t3', 'ted',  'EUR', 200000.0, 'estimated', 'Buyer B', 'DE',
             'IT services: consulting, software development, Internet and support',
             DATE '2026-11-05', DATE '2026-10-10', 'active'),
            ('t4', 'contracts_finder', NULL, NULL, 'unknown', 'Buyer C', 'GB',
             'IT services: consulting, software development, Internet and support',
             DATE '2026-10-20', DATE '2026-09-20', 'active')
        ) AS v(tender_ref, source, value_currency, value_amount, value_type, buyer_name,
               country, cpv_division_label, deadline_date, last_published_date, status)
    """)
    con.close()
    return path


def test_plain_count(warehouse):
    rows = run_query(compile_query("tender_count"), warehouse)
    assert rows == [{"tender_count": 4}]


def test_group_by_source(warehouse):
    rows = run_query(compile_query("tender_count", dimensions=["source"]), warehouse)
    assert {r["source"]: r["tender_count"] for r in rows} == {
        "fts": 2, "ted": 1, "contracts_finder": 1,
    }


def test_open_count_uses_pinned_clock(warehouse):
    rows = run_query(compile_query("open_tender_count"), warehouse)
    # deadlines on/after 2026-11-01: t1 (11-10) and t3 (11-05); t4 already passed
    assert rows == [{"open_tender_count": 2}]


def test_expiring_soon_horizon(warehouse):
    rows = run_query(compile_query("expiring_soon_count", horizon_days=5), warehouse)
    assert rows == [{"expiring_soon_count": 1}]  # only t3 within 5 days


def test_value_metric_requires_currency(warehouse):
    with pytest.raises(GovernanceError, match="currency"):
        compile_query("total_contract_value")


def test_value_metric_defaults_to_estimated(warehouse):
    rows = run_query(
        compile_query("total_contract_value", filters={"currency": "GBP"}), warehouse
    )
    # t2 is 'awarded' and excluded by the default value_type guard
    assert rows == [{"total_contract_value": 100000.0}]


def test_value_type_filter_overrides_default(warehouse):
    rows = run_query(
        compile_query(
            "total_contract_value", filters={"currency": "GBP", "value_type": "awarded"}
        ),
        warehouse,
    )
    assert rows == [{"total_contract_value": 900000.0}]


def test_buyer_requires_explicit_limit(warehouse):
    with pytest.raises(GovernanceError, match="high-cardinality"):
        compile_query("tender_count", dimensions=["buyer"])
    rows = run_query(compile_query("tender_count", dimensions=["buyer"], limit=2), warehouse)
    assert len(rows) == 2  # top-N enforced


def test_buyer_limit_cap(warehouse):
    with pytest.raises(GovernanceError, match="limit"):
        compile_query("tender_count", dimensions=["buyer"], limit=51)


def test_unknown_metric_and_dimension_are_refused():
    with pytest.raises(GovernanceError, match="unknown metric"):
        compile_query("profit_margin")
    with pytest.raises(GovernanceError, match="unknown dimension"):
        compile_query("tender_count", dimensions=["supplier"])


def test_filter_values_are_parameterized_not_interpolated():
    hostile = "GB'; DROP TABLE fct_tenders; --"
    compiled = compile_query("tender_count", filters={"country": hostile})
    assert hostile not in compiled.sql
    assert compiled.parameters == [hostile]


def test_horizon_days_rejected_on_clockless_metric():
    with pytest.raises(GovernanceError, match="horizon_days"):
        compile_query("tender_count", horizon_days=7)


def test_clock_is_injected_not_wall_time():
    compiled = compile_query("open_tender_count")
    assert PINNED_TODAY in compiled.sql
    assert date.today().isoformat() not in compiled.sql or date.today().isoformat() == PINNED_TODAY
