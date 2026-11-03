"""Run the agent eval suite against the frozen fixture and score on evidence.

    uv run python evals/harness.py [--category metrics] [--only metric-001]
                                   [--no-cache] [--model gemini-flash-latest]

Requires GEMINI_API_KEY and a built fixture warehouse:

    uv run python scripts/build_fixture.py            # (already committed)
    TENDER_RADAR_DATA_DIR=fixtures DBT_PROFILES_DIR=dbt \
        uv run dbt build --project-dir dbt

Scoring is deterministic: gold answers come from SQL against the fixture,
citations must exist in the fixture, and regex/tool checks are explicit in
evals/questions.yaml. Responses are cached per (question, model, fixture
manifest) so reruns and CI don't burn free-tier quota.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "fixtures"
CACHE_DIR = Path(__file__).parent / ".cache"
PASS_THRESHOLD = 0.80

sys.path.insert(0, str(REPO_ROOT / "src"))


@dataclass
class Outcome:
    question_id: str
    category: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    answer: str = ""
    cached: bool = False


def _pin_environment() -> dict[str, str]:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    pinned = {
        "TENDER_RADAR_DATA_DIR": str(FIXTURE_DIR),
        "TENDER_RADAR_TODAY": manifest["pinned_today"],
    }
    os.environ.update(pinned)
    return manifest


def _sql_scalar(con: duckdb.DuckDBPyConnection, sql: str) -> float | None:
    rows = con.execute(sql).fetchall()
    return None if not rows or rows[0][0] is None else float(rows[0][0])


def _sql_refs(con: duckdb.DuckDBPyConnection, sql: str) -> set[str]:
    return {row[0] for row in con.execute(sql).fetchall()}


def _numbers_in(text: str) -> list[float]:
    found = []
    for raw in re.findall(r"-?[\d,]*\.?\d+", text.replace(" ", " ")):
        try:
            found.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return found


def score(
    question: dict[str, Any],
    answer: str,
    cited_refs: set[str],
    called_tools: set[str],
    con: duckdb.DuckDBPyConnection,
    fixture_refs: set[str],
    today: str,
) -> list[str]:
    """Return the list of failed checks (empty = pass)."""
    checks = question.get("checks", {})
    failures: list[str] = []
    lowered = answer.lower()

    hallucinated = cited_refs - fixture_refs
    if hallucinated:
        failures.append(f"cited refs not in fixture: {sorted(hallucinated)}")

    if "gold_refs_sql" in checks:
        gold = _sql_refs(con, checks["gold_refs_sql"].replace("{today}", today))
        overlap = len(cited_refs & gold)
        need = checks.get("min_cited", 1)
        if overlap < need:
            failures.append(f"cited {overlap} of gold refs, needed {need}")

    for ref in checks.get("cited_includes", []):
        if ref not in cited_refs:
            failures.append(f"missing required citation {ref}")

    if "scalar_sql" in checks:
        gold = _sql_scalar(con, checks["scalar_sql"].replace("{today}", today))
        if gold is None:
            failures.append("gold scalar SQL returned NULL")
        else:
            tolerance = abs(gold) * checks.get("tolerance_pct", 0) / 100
            tolerance = max(tolerance, checks.get("tolerance_abs", 0.5))
            if not any(abs(n - gold) <= tolerance for n in _numbers_in(answer)):
                failures.append(f"no number within {tolerance} of gold {gold}")

    for pattern in checks.get("answer_regex", []):
        if not re.search(pattern, lowered, re.IGNORECASE | re.DOTALL):
            failures.append(f"answer did not match /{pattern}/")
    for pattern in checks.get("answer_not_regex", []):
        if re.search(pattern, lowered, re.IGNORECASE | re.DOTALL):
            failures.append(f"answer matched forbidden /{pattern}/")

    for tool in checks.get("must_call_tools", []):
        if tool not in called_tools:
            failures.append(f"never called required tool {tool}")

    if "max_citations" in checks and len(cited_refs) > checks["max_citations"]:
        failures.append(f"cited {len(cited_refs)}, allowed {checks['max_citations']}")

    return failures


def _cache_key(question: dict[str, Any], model: str, manifest: dict) -> Path:
    digest = hashlib.sha256(
        json.dumps(
            [question["question"], model, manifest["pinned_today"], manifest["sources"]],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    return CACHE_DIR / f"{question['id']}-{digest}.json"


async def run_one(question: dict[str, Any], model: str, use_cache: bool, manifest: dict) -> dict:
    cache_path = _cache_key(question, model, manifest)
    if use_cache and cache_path.exists():
        return {**json.loads(cache_path.read_text()), "cached": True}

    from tender_radar.agent.loop import run_agent
    from tender_radar.agent.provider import GeminiProvider

    result = await run_agent(question["question"], GeminiProvider(model=model))
    record = {
        "answer": result.answer,
        "cited_refs": sorted({c["tender_ref"] for c in result.citations}),
        "called_tools": sorted({c["tool"] for c in result.tool_calls}),
    }
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(record, indent=2))
    return {**record, "cached": False}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category")
    parser.add_argument("--only")
    parser.add_argument("--model", default="gemini-flash-latest")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--report", type=Path, default=Path(__file__).parent / "report.json")
    args = parser.parse_args()

    manifest = _pin_environment()
    today = manifest["pinned_today"]
    warehouse = FIXTURE_DIR / "warehouse.duckdb"
    if not warehouse.exists():
        print("fixture warehouse missing — run the dbt build shown in the module docstring")
        return 2

    questions = yaml.safe_load((Path(__file__).parent / "questions.yaml").read_text())["questions"]
    if args.only:
        questions = [q for q in questions if q["id"] == args.only]
    if args.category:
        questions = [q for q in questions if q["category"] == args.category]
    if not questions:
        print("no questions selected")
        return 2

    con = duckdb.connect(str(warehouse), read_only=True)
    fixture_refs = _sql_refs(con, "SELECT tender_ref FROM fct_tenders")

    outcomes: list[Outcome] = []
    for question in questions:
        record = await run_one(question, args.model, not args.no_cache, manifest)
        failures = score(
            question,
            record["answer"],
            set(record["cited_refs"]),
            set(record["called_tools"]),
            con, fixture_refs, today,
        )
        outcome = Outcome(
            question_id=question["id"],
            category=question["category"],
            passed=not failures,
            failures=failures,
            answer=record["answer"],
            cached=record["cached"],
        )
        outcomes.append(outcome)
        marker = "PASS" if outcome.passed else "FAIL"
        cached = " (cached)" if outcome.cached else ""
        print(f"[{marker}] {question['id']}{cached}" + (f" — {failures}" if failures else ""))

    passed = sum(o.passed for o in outcomes)
    rate = passed / len(outcomes)
    by_category: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        by_category.setdefault(outcome.category, []).append(outcome)
    print(f"\n{passed}/{len(outcomes)} passed ({rate:.0%})")
    for category, members in sorted(by_category.items()):
        print(f"  {category}: {sum(o.passed for o in members)}/{len(members)}")

    args.report.write_text(json.dumps(
        {
            "model": args.model,
            "pinned_today": today,
            "pass_rate": rate,
            "outcomes": [vars(o) for o in outcomes],
        },
        indent=2,
    ))
    return 0 if rate >= PASS_THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
