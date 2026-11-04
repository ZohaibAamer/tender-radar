"""Per-client rate limiting for the hosted MCP endpoint.

The hosted deployment is public and unauthenticated; without a ceiling, one
looping client could exhaust the free-tier compute quota and take the service
down for everyone else. Costs are never at stake (the plan has no payment
method), only availability.

The counter is in-memory and per-instance. The platform runs several
instances, so the effective global ceiling is a small multiple of LIMIT —
acceptable for abuse protection, where the goal is stopping runaway loops,
not precise quota accounting.
"""

from __future__ import annotations

import os
import time
from typing import Any

DEFAULT_LIMIT = int(os.environ.get("TENDER_RADAR_RATE_LIMIT", "100"))
WINDOW_SECONDS = 60
_MAX_TRACKED_CLIENTS = 10_000


class RateLimitMiddleware:
    """ASGI middleware: fixed-window request counter per client IP."""

    def __init__(self, app: Any, limit: int = DEFAULT_LIMIT, window: int = WINDOW_SECONDS):
        self.app = app
        self.limit = limit
        self.window = window
        self._hits: dict[str, tuple[int, int]] = {}  # ip -> (window index, count)

    def _client_ip(self, scope: dict[str, Any]) -> str:
        headers = dict(scope.get("headers") or [])
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            # Platform-appended header; the first hop is the real client.
            return forwarded.decode("latin-1").split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        now = int(time.time())
        window_index = now // self.window
        ip = self._client_ip(scope)
        start, count = self._hits.get(ip, (window_index, 0))
        if start != window_index:
            start, count = window_index, 0
        count += 1
        self._hits[ip] = (start, count)

        if len(self._hits) > _MAX_TRACKED_CLIENTS:
            self._hits = {k: v for k, v in self._hits.items() if v[0] == window_index}

        if count > self.limit:
            retry_after = (start + 1) * self.window - now
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(max(retry_after, 1)).encode()),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"rate limit exceeded, retry shortly"}',
                }
            )
            return

        await self.app(scope, receive, send)
