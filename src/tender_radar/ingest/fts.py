"""UK Find a Tender ingestion (OCDS release packages, cursor-paginated)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from .http import request_json
from .models import UnifiedNotice
from .ocds import map_ocds_release

API_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
PAGE_SIZE = 100


def notice_url(release: dict[str, Any]) -> str:
    return f"https://www.find-tender.service.gov.uk/Notice/{release['id']}"


def map_release(release: dict[str, Any]) -> UnifiedNotice | None:
    return map_ocds_release(release, source="fts", url=notice_url(release))


def fetch(since: date, max_pages: int = 50) -> Iterator[UnifiedNotice]:
    url: str | None = API_URL
    params: dict[str, Any] | None = {
        "updatedFrom": f"{since.isoformat()}T00:00:00",
        "limit": PAGE_SIZE,
    }
    for _ in range(max_pages):
        if not url:
            break
        package = request_json("GET", url, params=params)
        params = None  # the `next` link already carries the query string
        for release in package.get("releases") or []:
            notice = map_release(release)
            if notice:
                yield notice
        url = (package.get("links") or {}).get("next")
