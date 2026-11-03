"""End-to-end loop test: a scripted provider drives the real MCP server.

No LLM involved — the FakeProvider plays the model's role, so this exercises
the stdio transport, tool execution, and citation collection for real.
"""

import asyncio
import sys
from typing import Any

import duckdb
import pytest
from mcp import StdioServerParameters
from mcp.client.stdio import get_default_environment

from tender_radar.agent.loop import run_agent
from tender_radar.agent.provider import ModelTurn, ToolCall, _clean_schema

PINNED_TODAY = "2026-11-01"


class FakeProvider:
    """Plays back a script: one search call, then a final answer."""

    def __init__(self):
        self.turns = [
            ModelTurn(tool_calls=[ToolCall(name="search_tenders", arguments={"query": "data"})]),
            ModelTurn(text="One match: analytics platform [ocds-h6vhtk-1]."),
        ]
        self.seen_tool_results: list[Any] = []

    def generate(self, system, history, tools):
        assert any(t["name"] == "query_metric" for t in tools)  # server exposes 6 tools
        return self.turns.pop(0)

    def user_message(self, text):
        return {"role": "user", "text": text}

    def tool_results(self, turn, results):
        self.seen_tool_results.extend(results)
        return [{"role": "tool", "results": results}]


@pytest.fixture
def data_dir(tmp_path):
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    con.execute("""
        CREATE TABLE fct_tenders AS
        SELECT 'ocds-h6vhtk-1' AS tender_ref, 'fts' AS source, 'ocds-h6vhtk-1' AS ocid,
               'n1' AS latest_notice_id, 'Data analytics platform' AS title,
               'warehouse build' AS description, 'NHS England' AS buyer_name,
               'GB' AS country, ['72000000'] AS cpv_codes, '72000000' AS main_cpv,
               '72' AS cpv_division, 'IT services' AS cpv_division_label,
               300000.0 AS value_amount, 'GBP' AS value_currency,
               'estimated' AS value_type, 'active' AS status,
               'tender' AS latest_notice_type, 1::BIGINT AS notice_count,
               DATE '2026-10-20' AS first_published_date,
               DATE '2026-10-20' AS last_published_date,
               DATE '2026-11-09' AS deadline_date, false AS has_award,
               'https://example.org/1' AS url
    """)
    con.close()
    return tmp_path


def test_loop_executes_tools_and_collects_citations(data_dir):
    env = get_default_environment()
    env["TENDER_RADAR_DATA_DIR"] = str(data_dir)
    env["TENDER_RADAR_TODAY"] = PINNED_TODAY
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "tender_radar.mcp_server"], env=env
    )
    provider = FakeProvider()
    result = asyncio.run(run_agent("any data tenders?", provider, params=params))

    assert "analytics platform" in result.answer
    assert result.tool_calls == [{"tool": "search_tenders", "arguments": {"query": "data"}}]
    assert result.citations == [
        {
            "tender_ref": "ocds-h6vhtk-1",
            "url": "https://example.org/1",
            "title": "Data analytics platform",
        }
    ]
    assert provider.seen_tool_results  # the tool's JSON reached the model


def test_clean_schema_strips_unsupported_keys():
    schema = {
        "$schema": "x", "title": "T", "type": "object", "additionalProperties": False,
        "properties": {
            "limit": {"type": ["integer", "null"], "title": "Limit"},
            "filters": {"anyOf": [{"type": "object"}, {"type": "null"}]},
        },
        "required": ["limit"],
    }
    cleaned = _clean_schema(schema)
    assert "$schema" not in cleaned and "additionalProperties" not in cleaned
    assert cleaned["properties"]["limit"] == {"type": "integer"}
    assert cleaned["properties"]["filters"]["type"] == "string"  # unions collapse
    assert cleaned["required"] == ["limit"]
