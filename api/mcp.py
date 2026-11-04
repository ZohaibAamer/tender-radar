"""Vercel entrypoint: serves the MCP server over Streamable HTTP at /api/mcp (also aliased as /mcp)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tender_radar.mcp_server.remote import app  # noqa: E402, F401
