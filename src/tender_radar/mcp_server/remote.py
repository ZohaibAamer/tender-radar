"""Remote entrypoint: the same MCP server over Streamable HTTP.

Built for serverless hosting (Vercel Fluid Compute): stateless sessions,
JSON responses, and a cold-start data bootstrap — when no warehouse exists
locally (fresh instance), it is downloaded once from the repo's data release
into the writable data dir. Instance reuse amortizes that download.

Local use stays on stdio (`tender-radar-mcp`); this module is only imported
by the hosted deployment (api/index.py).
"""

from __future__ import annotations

import os
import urllib.request

# Prefer a warehouse bundled with the deployment (read-only is fine: every
# query connection is read-only). Fall back to /tmp + release download only
# when nothing was bundled. Must run before tender_radar.config is imported.
_BUNDLED = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "warehouse.duckdb")
if (
    os.environ.get("VERCEL")
    and not os.environ.get("TENDER_RADAR_DATA_DIR")
    and not os.path.exists(_BUNDLED)
):
    os.environ["TENDER_RADAR_DATA_DIR"] = "/tmp/tender-radar-data"

from tender_radar import config  # noqa: E402

WAREHOUSE_URL = os.environ.get(
    "TENDER_RADAR_WAREHOUSE_URL",
    "https://github.com/ZohaibAamer/tender-radar/releases/download/data-latest/warehouse.duckdb",
)


def ensure_warehouse() -> None:
    if config.WAREHOUSE_PATH.exists():
        return
    config.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = config.WAREHOUSE_PATH.with_name("warehouse.duckdb.download")
    urllib.request.urlretrieve(WAREHOUSE_URL, temp)  # noqa: S310 - fixed https URL
    temp.replace(config.WAREHOUSE_PATH)


def create_app():
    from mcp.server.transport_security import TransportSecuritySettings

    from .ratelimit import RateLimitMiddleware
    from .server import mcp

    ensure_warehouse()
    app = mcp.streamable_http_app(
        streamable_http_path="/api/index",
        # Serverless instances share nothing: every request must stand alone.
        stateless_http=True,
        json_response=True,
        # The platform terminates TLS and rewrites Host headers; DNS-rebinding
        # protection is meaningless behind it and only causes 421s.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    # Public, unauthenticated endpoint: cap per-client request rate so one
    # looping client cannot exhaust the free-tier quota for everyone else.
    return RateLimitMiddleware(app)


app = create_app()
