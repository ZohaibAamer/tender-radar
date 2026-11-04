"""Tool implementations behind the MCP server, as plain testable functions.

Governance lives HERE, in the server layer — not in any agent loop. There is
no tool that accepts SQL, so no client (desktop AI apps, the CLI agent, MCP
Inspector) can bypass the semantic layer, however it is driven. Search
filters are parameterized; aggregates go through the semantic compiler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from tender_radar import config
from tender_radar.profiles import CompanyProfile, load_profile
from tender_radar.semantic import compile_query, run_query

_SUMMARY_COLUMNS = (
    "tender_ref, source, title, buyer_name, country, main_cpv, cpv_division_label, "
    "value_amount, value_currency, value_type, status, deadline_date, "
    "last_published_date, url"
)
MAX_RESULTS = 50


def _connect(warehouse: Path | None) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(warehouse or config.WAREHOUSE_PATH), read_only=True)


def _rows_to_dicts(cursor: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _clamp(max_results: int) -> int:
    return max(1, min(int(max_results), MAX_RESULTS))


def search_tenders(
    query: str = "",
    source: str | None = None,
    country: str | None = None,
    cpv_division: str | None = None,
    open_only: bool = False,
    max_results: int = 20,
    warehouse: Path | None = None,
) -> list[dict[str, Any]]:
    """Keyword + filter search over unified tenders. No SQL accepted."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if query:
        clauses.append("(title ILIKE ? OR description ILIKE ?)")
        parameters += [f"%{query}%", f"%{query}%"]
    if source:
        clauses.append("source = ?")
        parameters.append(source)
    if country:
        clauses.append("country = ?")
        parameters.append(country.upper())
    if cpv_division:
        clauses.append("cpv_division = ?")
        parameters.append(cpv_division)
    if open_only:
        clauses.append("deadline_date >= ?")
        parameters.append(config.today().isoformat())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT {_SUMMARY_COLUMNS} FROM fct_tenders {where} "
        f"ORDER BY last_published_date DESC LIMIT {_clamp(max_results)}"
    )
    con = _connect(warehouse)
    try:
        return _rows_to_dicts(con.execute(sql, parameters))
    finally:
        con.close()


def get_tender(
    tender_ref: str,
    warehouse: Path | None = None,
    links_path: Path | None = None,
) -> dict[str, Any]:
    """Full detail for one tender, with any cross-portal links."""
    con = _connect(warehouse)
    try:
        rows = _rows_to_dicts(
            con.execute("SELECT * FROM fct_tenders WHERE tender_ref = ?", [tender_ref])
        )
        if not rows:
            return {"error": f"no tender with ref '{tender_ref}'. Use search_tenders first."}
        tender = rows[0]
        links_file = links_path or config.LINKS_PATH
        if links_file.exists():
            tender["cross_portal_links"] = _rows_to_dicts(
                con.execute(
                    f"SELECT * FROM read_parquet('{links_file}') "
                    "WHERE fts_ref = ? OR cf_ref = ?",
                    [tender_ref, tender_ref],
                )
            )
        return tender
    finally:
        con.close()


def _profile_match_sql(profile: CompanyProfile) -> tuple[str, list[Any]]:
    """Rank tenders for a profile: CPV division, country, value bounds, keywords."""
    keyword_hits = (
        "("
        + " + ".join(
            "CASE WHEN title ILIKE ? OR description ILIKE ? THEN 1 ELSE 0 END"
            for _ in profile.keywords
        )
        + ")"
        if profile.keywords
        else "0"
    )
    parameters: list[Any] = []
    for keyword in profile.keywords:
        parameters += [f"%{keyword}%", f"%{keyword}%"]

    division_list = ", ".join("?" for _ in profile.cpv_divisions)
    country_list = ", ".join("?" for _ in profile.countries)
    sql = f"""
        SELECT {_SUMMARY_COLUMNS},
               {keyword_hits} AS keyword_hits,
               (cpv_division IN ({division_list})) AS cpv_match
        FROM fct_tenders
        WHERE country IN ({country_list})
          AND (cpv_division IN ({division_list}) OR {keyword_hits} >= 2)
    """
    parameters += profile.cpv_divisions
    parameters += [c.upper() for c in profile.countries]
    parameters += profile.cpv_divisions
    for keyword in profile.keywords:
        parameters += [f"%{keyword}%", f"%{keyword}%"]

    if profile.min_value is not None:
        sql += " AND (value_amount IS NULL OR value_amount >= ?)"
        parameters.append(profile.min_value)
    if profile.max_value is not None:
        sql += " AND (value_amount IS NULL OR value_amount <= ?)"
        parameters.append(profile.max_value)
    return sql, parameters


def match_profile(
    profile_name: str,
    open_only: bool = True,
    max_results: int = 20,
    warehouse: Path | None = None,
    profiles_dir: Path | None = None,
) -> dict[str, Any]:
    """Tenders fitting a company profile, ranked, each with match reasons."""
    try:
        profile = load_profile(profile_name, profiles_dir)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    sql, parameters = _profile_match_sql(profile)
    if open_only:
        sql += " AND deadline_date >= ?"
        parameters.append(config.today().isoformat())
    sql += f"""
        ORDER BY cpv_match DESC, keyword_hits DESC, last_published_date DESC
        LIMIT {_clamp(max_results)}
    """
    con = _connect(warehouse)
    try:
        matches = _rows_to_dicts(con.execute(sql, parameters))
    finally:
        con.close()

    for match in matches:
        reasons = []
        if match.pop("cpv_match", False):
            reasons.append(
                f"CPV division {match['main_cpv'][:2] if match['main_cpv'] else '?'} "
                "is in the profile"
            )
        hits = match.pop("keyword_hits", 0)
        if hits:
            reasons.append(f"{hits} profile keyword(s) in title/description")
        match["match_reasons"] = reasons
    return {
        "profile": profile.name,
        "open_only": open_only,
        "as_of": config.today().isoformat(),
        "matches": matches,
    }


def upcoming_deadlines(
    profile_name: str | None = None,
    horizon_days: int = 14,
    max_results: int = 20,
    warehouse: Path | None = None,
    profiles_dir: Path | None = None,
) -> dict[str, Any]:
    """Open tenders whose deadline falls within the horizon (pull, not push)."""
    horizon_days = max(1, min(int(horizon_days), 365))
    today = config.today().isoformat()
    if profile_name:
        result = match_profile(
            profile_name, open_only=True, max_results=MAX_RESULTS,
            warehouse=warehouse, profiles_dir=profiles_dir,
        )
        if "error" in result:
            return result
        matches = [
            m for m in result["matches"]
            if m["deadline_date"] is not None
            and (m["deadline_date"] - config.today()).days <= horizon_days
        ]
        matches.sort(key=lambda m: m["deadline_date"])
        return {
            "as_of": today,
            "horizon_days": horizon_days,
            "profile": profile_name,
            "deadlines": matches[: _clamp(max_results)],
        }
    sql = (
        f"SELECT {_SUMMARY_COLUMNS} FROM fct_tenders "
        "WHERE deadline_date >= CAST(? AS DATE) "
        "AND deadline_date <= CAST(? AS DATE) + INTERVAL (?) DAY "
        f"ORDER BY deadline_date ASC LIMIT {_clamp(max_results)}"
    )
    con = _connect(warehouse)
    try:
        rows = _rows_to_dicts(con.execute(sql, [today, today, horizon_days]))
    finally:
        con.close()
    return {"as_of": today, "horizon_days": horizon_days, "deadlines": rows}


def query_metric(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    horizon_days: int | None = None,
    warehouse: Path | None = None,
) -> dict[str, Any]:
    """The only aggregate path: compiled from layer.yaml, never free SQL."""
    compiled = compile_query(
        metric, dimensions=dimensions, filters=filters, limit=limit, horizon_days=horizon_days
    )
    return {
        "metric": metric,
        "as_of": config.today().isoformat(),
        "compiled_sql": compiled.sql,  # transparency: show what governance produced
        "rows": run_query(compiled, warehouse),
    }
