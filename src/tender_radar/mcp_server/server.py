"""The Tender Radar MCP server (stdio).

A thin shell: every tool delegates to tools.py, and the semantic layer's YAML
is published as a readable resource so agents can discover metrics before
calling query_metric. Notably absent: any tool that accepts SQL.

Run:  uv run tender-radar-mcp         (or: python -m tender_radar.mcp_server)
Try:  npx @modelcontextprotocol/inspector uv run tender-radar-mcp
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from tender_radar.profiles import list_profiles
from tender_radar.semantic import GovernanceError, layer_text

from . import tools

mcp = MCPServer(
    "tender-radar",
    instructions=(
        "Unified UK (Find a Tender, Contracts Finder) and EU (TED) public tender "
        "intelligence. Use search_tenders/get_tender for records, match_profile and "
        "upcoming_deadlines for fit, and query_metric for any aggregate number. "
        "Aggregates are governed: read the semantic://layer resource for what exists. "
        "Cite tenders by tender_ref and url."
    ),
)


@mcp.resource("semantic://layer")
def semantic_layer() -> str:
    """The governed metric surface: every queryable metric and dimension."""
    return layer_text()


@mcp.tool()
def search_tenders(
    query: str = "",
    source: str = "",
    country: str = "",
    cpv_division: str = "",
    open_only: bool = False,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search tenders by keyword and filters.

    Args:
        query: keyword matched against title and description.
        source: fts | contracts_finder | ted (empty = all).
        country: ISO alpha-2 buyer country, e.g. GB.
        cpv_division: 2-digit CPV division, e.g. 72.
        open_only: only tenders whose deadline has not passed.
        max_results: at most 50.
    """
    return tools.search_tenders(
        query=query,
        source=source or None,
        country=country or None,
        cpv_division=cpv_division or None,
        open_only=open_only,
        max_results=max_results,
    )


@mcp.tool()
def get_tender(tender_ref: str) -> dict[str, Any]:
    """Full detail for one tender by tender_ref, including cross-portal links."""
    return tools.get_tender(tender_ref)


@mcp.tool()
def match_profile(profile_name: str, open_only: bool = True, max_results: int = 20) -> dict:
    """Rank tenders fitting a company profile (profiles/*.yaml), with reasons.

    Available profiles can be listed by passing an unknown name.
    """
    return tools.match_profile(profile_name, open_only=open_only, max_results=max_results)


@mcp.tool()
def upcoming_deadlines(
    profile_name: str = "", horizon_days: int = 14, max_results: int = 20
) -> dict:
    """Open tenders with deadlines within horizon_days, optionally for a profile."""
    return tools.upcoming_deadlines(
        profile_name=profile_name or None,
        horizon_days=horizon_days,
        max_results=max_results,
    )


@mcp.tool()
def query_metric(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    horizon_days: int | None = None,
) -> dict[str, Any]:
    """Run a governed metric from the semantic layer (see semantic://layer).

    This is the only way to aggregate. Free SQL does not exist on this server.
    GovernanceError messages explain how to correct a refused query.
    """
    try:
        return tools.query_metric(
            metric, dimensions=dimensions, filters=filters,
            limit=limit, horizon_days=horizon_days,
        )
    except GovernanceError as exc:
        return {"governance_error": str(exc)}


@mcp.tool()
def list_company_profiles() -> list[str]:
    """Names of the company profiles available to match_profile."""
    return list_profiles()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
