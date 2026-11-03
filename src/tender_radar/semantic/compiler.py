"""Compile governed metric queries to SQL.

This module is the only path from an agent's question to SQL. Everything an
agent may do is declared in layer.yaml; everything else raises a
GovernanceError whose message is written for the agent to read and correct
itself. Filter *values* are always bound as parameters — nothing a caller
sends is ever interpolated into SQL text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import duckdb
import yaml

from tender_radar import config


class GovernanceError(ValueError):
    """The request fell outside the governed surface."""


def load_layer() -> dict[str, Any]:
    source = resources.files("tender_radar.semantic").joinpath("layer.yaml")
    return yaml.safe_load(source.read_text())


def layer_text() -> str:
    """The raw YAML, published to MCP clients as the semantic://layer resource."""
    return resources.files("tender_radar.semantic").joinpath("layer.yaml").read_text()


@dataclass
class CompiledQuery:
    sql: str
    parameters: list[Any] = field(default_factory=list)


def _known(names: dict[str, Any], kind: str, name: str) -> dict[str, Any]:
    if name not in names:
        raise GovernanceError(
            f"unknown {kind} '{name}'. Available {kind}s: {', '.join(sorted(names))}. "
            "Read the semantic://layer resource for descriptions."
        )
    return names[name]


def _dimension_sql(layer: dict[str, Any], name: str) -> str:
    dim = layer["dimensions"][name]
    return dim.get("column") or dim["expr"]


def compile_query(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    horizon_days: int | None = None,
    layer: dict[str, Any] | None = None,
) -> CompiledQuery:
    layer = layer or load_layer()
    dimensions = dimensions or []
    filters = dict(filters or {})
    governance = layer["governance"]

    metric_spec = _known(layer["metrics"], "metric", metric)
    for name in dimensions:
        _known(layer["dimensions"], "dimension", name)
    for name in filters:
        _known(layer["dimensions"], "dimension", name)

    # --- value-metric guards -------------------------------------------------
    if metric_spec.get("value_metric"):
        touched = set(dimensions) | set(filters)
        if governance["value_metrics"]["require_currency"] and "currency" not in touched:
            raise GovernanceError(
                f"'{metric}' aggregates money across currencies (TED publishes EUR, "
                "UK portals GBP). Group by 'currency' or filter it, e.g. "
                "filters={'currency': 'GBP'}."
            )
        if "value_type" not in touched:
            # a framework ceiling is not a contract value; default to estimates
            filters["value_type"] = governance["value_metrics"]["default_value_type"]

    # --- high-cardinality guard ----------------------------------------------
    effective_limit = limit if limit is not None else governance["default_limit"]
    max_limit = governance["max_limit"]
    for name in dimensions:
        dim_max = layer["dimensions"][name].get("max_limit")
        if layer["dimensions"][name].get("high_cardinality") and limit is None:
            raise GovernanceError(
                f"dimension '{name}' is high-cardinality: pass an explicit limit "
                f"(top-N) of at most {dim_max}."
            )
        if dim_max is not None:
            max_limit = min(max_limit, dim_max)
    if not 1 <= effective_limit <= max_limit:
        raise GovernanceError(f"limit must be between 1 and {max_limit} for this query.")

    # --- clock injection -----------------------------------------------------
    agg = metric_spec["agg"]
    if metric_spec.get("uses_clock"):
        horizon = horizon_days or metric_spec.get("params", {}).get("horizon_days", 14)
        if not 1 <= int(horizon) <= 365:
            raise GovernanceError("horizon_days must be between 1 and 365.")
        agg = agg.format(today=config.today().isoformat(), horizon_days=int(horizon))
    elif horizon_days is not None:
        raise GovernanceError(f"metric '{metric}' does not take horizon_days.")

    # --- assemble ------------------------------------------------------------
    select_parts = [f"{_dimension_sql(layer, d)} AS {d}" for d in dimensions]
    select_parts.append(f"{agg} AS {metric}")
    sql = f"SELECT {', '.join(select_parts)} FROM {layer['table']}"

    parameters: list[Any] = []
    where_parts: list[str] = []
    for name, value in filters.items():
        expr = _dimension_sql(layer, name)
        if isinstance(value, list):
            placeholders = ", ".join("?" for _ in value)
            where_parts.append(f"{expr} IN ({placeholders})")
            parameters.extend(value)
        else:
            where_parts.append(f"{expr} = ?")
            parameters.append(value)
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)

    if dimensions:
        group_cols = ", ".join(str(i + 1) for i in range(len(dimensions)))
        sql += f" GROUP BY {group_cols} ORDER BY {metric} DESC NULLS LAST"
        sql += f" LIMIT {int(effective_limit)}"

    return CompiledQuery(sql=sql, parameters=parameters)


def run_query(compiled: CompiledQuery, warehouse: Path | None = None) -> list[dict[str, Any]]:
    con = duckdb.connect(str(warehouse or config.WAREHOUSE_PATH), read_only=True)
    try:
        cursor = con.execute(compiled.sql, compiled.parameters)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()
