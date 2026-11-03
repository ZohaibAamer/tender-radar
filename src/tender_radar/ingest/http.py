"""Shared HTTP helper: one client, bounded retries, no surprises."""

from __future__ import annotations

import time
from typing import Any

import httpx

USER_AGENT = "tender-radar/0.1 (open-source tender aggregation)"
TIMEOUT = 30.0
RETRIES = 5

# Pause between successive page fetches; both UK portals rate-limit eagerly.
PAGE_PAUSE_SECONDS = 1.0


def _retry_delay(exc: Exception, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None when the error is permanent."""
    if isinstance(exc, httpx.TransportError):
        return float(2**attempt)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return float(retry_after)
            return float(2**attempt * 10)
        if status >= 500:
            return float(2**attempt)
    return None


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
            delay = _retry_delay(exc, attempt)
            if delay is None:
                raise  # permanent client error; retrying won't heal it
            time.sleep(delay)
    raise RuntimeError(f"{method} {url} failed after {RETRIES} attempts") from last_error
