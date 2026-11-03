"""Shared HTTP helper: one client, bounded retries, no surprises."""

from __future__ import annotations

import time
from typing import Any

import httpx

USER_AGENT = "tender-radar/0.1 (open-source tender aggregation)"
TIMEOUT = 30.0
RETRIES = 3


def request_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                response = client.request(method, url, params=params, json=json)
                response.raise_for_status()
                return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise  # client errors won't heal on retry
            time.sleep(2**attempt)
    raise RuntimeError(f"{method} {url} failed after {RETRIES} attempts") from last_error
