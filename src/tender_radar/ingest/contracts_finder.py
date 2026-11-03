"""UK Contracts Finder ingestion (OCDS search API, cursor-paginated).

Covers lower-value UK contracts that never reach Find a Tender — and overlaps
with it for many above-threshold notices, which is what makes cross-portal
deduplication meaningful.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from .http import request_json
from .models import UnifiedNotice
from .ocds import map_ocds_release

API_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
PAGE_SIZE = 100


def notice_url(release: dict[str, Any]) -> str:
    # Release ids look like "<notice-uuid>-<revision>"; the public page is keyed
    # by the uuid (first 36 chars).
    return f"https://www.contractsfinder.service.gov.uk/notice/{str(release['id'])[:36]}"


def map_release(release: dict[str, Any]) -> UnifiedNotice | None:
    return map_ocds_release(release, source="contracts_finder", url=notice_url(release))


def fetch(since: date, max_pages: int = 50) -> Iterator[UnifiedNotice]:
    url: str | None = API_URL
    params: dict[str, Any] | None = {
        "publishedFrom": f"{since.isoformat()}T00:00:00",
        "limit": PAGE_SIZE,
    }
    for _ in range(max_pages):
        if not url:
            break
        package = request_json("GET", url, params=params)
        params = None
        for release in package.get("releases") or []:
            notice = map_release(release)
            if notice:
                yield notice
        url = (package.get("links") or {}).get("next")
