"""The rate limiter must throttle a single looping client without touching others."""

from __future__ import annotations

import asyncio
from typing import Any

from tender_radar.mcp_server.ratelimit import RateLimitMiddleware


async def _ok_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _request(middleware: RateLimitMiddleware, ip: str) -> int:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "headers": [(b"x-forwarded-for", ip.encode())], "client": None}
    asyncio.run(middleware(scope, None, send))
    return sent[0]["status"]


def test_allows_up_to_limit_then_429():
    mw = RateLimitMiddleware(_ok_app, limit=5)
    statuses = [_request(mw, "1.2.3.4") for _ in range(7)]
    assert statuses[:5] == [200] * 5
    assert statuses[5:] == [429, 429]


def test_clients_are_counted_independently():
    mw = RateLimitMiddleware(_ok_app, limit=2)
    assert [_request(mw, "1.1.1.1") for _ in range(3)] == [200, 200, 429]
    assert _request(mw, "2.2.2.2") == 200


def test_window_reset_allows_again(monkeypatch):
    clock = {"now": 1_000_000}
    monkeypatch.setattr("tender_radar.mcp_server.ratelimit.time.time", lambda: clock["now"])
    mw = RateLimitMiddleware(_ok_app, limit=1, window=60)
    assert _request(mw, "1.2.3.4") == 200
    assert _request(mw, "1.2.3.4") == 429
    clock["now"] += 60
    assert _request(mw, "1.2.3.4") == 200


def test_non_http_scopes_pass_through():
    called = {}

    async def app(scope, receive, send):
        called["yes"] = True

    mw = RateLimitMiddleware(app, limit=0)
    asyncio.run(mw({"type": "lifespan"}, None, None))
    assert called.get("yes")
