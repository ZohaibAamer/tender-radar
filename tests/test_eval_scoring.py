"""The eval scorer is itself tier-1 tested: scoring bugs fake eval results."""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from harness import _numbers_in, score  # noqa: E402

TODAY = "2026-11-03"


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("""
        CREATE TABLE fct_tenders AS
        SELECT 'ref-1' AS tender_ref, 100.0 AS value_amount
        UNION ALL SELECT 'ref-2', 300.0
    """)
    return connection


FIXTURE_REFS = {"ref-1", "ref-2"}


def test_hallucinated_citation_fails(con):
    failures = score({"checks": {}}, "answer", {"ref-99"}, set(), con, FIXTURE_REFS, TODAY)
    assert any("not in fixture" in f for f in failures)


def test_scalar_check_with_tolerance(con):
    question = {"checks": {"scalar_sql": "SELECT sum(value_amount) FROM fct_tenders",
                           "tolerance_pct": 1}}
    ok = score(question, "The total is 400 GBP.", set(), set(), con, FIXTURE_REFS, TODAY)
    assert ok == []
    off = score(question, "The total is 300 GBP.", set(), set(), con, FIXTURE_REFS, TODAY)
    assert any("gold" in f for f in off)


def test_gold_refs_overlap(con):
    question = {"checks": {"gold_refs_sql": "SELECT tender_ref FROM fct_tenders",
                           "min_cited": 2}}
    assert score(question, "", {"ref-1", "ref-2"}, set(), con, FIXTURE_REFS, TODAY) == []
    assert score(question, "", {"ref-1"}, set(), con, FIXTURE_REFS, TODAY)


def test_regex_and_tool_checks(con):
    question = {"checks": {"answer_regex": ["currenc"],
                           "answer_not_regex": ["drop table"],
                           "must_call_tools": ["query_metric"]}}
    ok = score(question, "Grouped by currency.", set(), {"query_metric"},
               con, FIXTURE_REFS, TODAY)
    assert ok == []
    bad = score(question, "I will DROP TABLE now", set(), set(), con, FIXTURE_REFS, TODAY)
    assert len(bad) == 3


def test_max_citations(con):
    question = {"checks": {"max_citations": 0}}
    assert score(question, "", {"ref-1"}, set(), con, FIXTURE_REFS, TODAY)
    assert score(question, "", set(), set(), con, FIXTURE_REFS, TODAY) == []


def test_number_extraction_handles_commas():
    assert 1234567.0 in _numbers_in("total of £1,234,567 across tenders")
    assert _numbers_in("no numbers here") == []
