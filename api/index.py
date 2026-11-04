"""Vercel entrypoint: the MCP server over HTTP at /api/index, aliased as /mcp."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tender_radar.mcp_server.remote import app  # noqa: E402, F401
