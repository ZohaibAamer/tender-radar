"""Central configuration: paths and the injectable clock.

Every component that needs "today" must call `today()` instead of reading the
wall clock. The TENDER_RADAR_TODAY env var (YYYY-MM-DD) pins the date so that
deadline logic is deterministic in tests and evals, inside the MCP server as
well as in the eval harness.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Where ingested parquet lives. Overridable so evals can point everything at
# the frozen fixture instead of live data.
DATA_DIR = Path(os.environ.get("TENDER_RADAR_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"
LINKS_PATH = DATA_DIR / "links" / "tender_links.parquet"
PROFILES_DIR = Path(os.environ.get("TENDER_RADAR_PROFILES_DIR", REPO_ROOT / "profiles"))

SOURCES = ("fts", "contracts_finder", "ted")


def today() -> date:
    """The pinned date if TENDER_RADAR_TODAY is set, else the real date."""
    pinned = os.environ.get("TENDER_RADAR_TODAY")
    if pinned:
        return date.fromisoformat(pinned)
    return date.today()
