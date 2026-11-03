"""EU TED ingestion: the eForms → unified-schema mapper.

TED's Search API v3 returns eForms-derived fields rather than OCDS, so this is
the genuinely cross-standard mapper. Field correspondence follows the Open
Contracting Partnership's eForms→OCDS mapping guidance; see
https://standard.open-contracting.org/profiles/eforms/ for the standard.

Multilingual fields arrive as ``{lang: value}`` dicts; we prefer English and
fall back to the first available language.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

from .http import PAGE_PAUSE_SECONDS, request_json
from .models import NoticeType, UnifiedNotice

API_URL = "https://api.ted.europa.eu/v3/notices/search"
PAGE_SIZE = 100

FIELDS = [
    "publication-number",
    "notice-title",
    "description-lot",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "deadline-receipt-tender-date-lot",
    "publication-date",
    "estimated-value-glo",
    "estimated-value-cur-glo",
    "notice-type",
    "links",
]

# EU/EEA ISO 3166-1 alpha-3 → alpha-2 (TED reports buyer-country as alpha-3).
_ISO3_TO_ISO2 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE", "NOR": "NO", "ISL": "IS", "LIE": "LI",
    "CHE": "CH", "GBR": "GB",
}  # fmt: skip


def _pick_language(value: Any) -> str:
    """Resolve a TED multilingual dict to one string, preferring English."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chosen = value.get("eng")
        if chosen is None and value:
            chosen = next(iter(value.values()))
        return _pick_language(chosen)
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    return str(value)


def _parse_date(value: str | None) -> date | None:
    # TED dates look like "2026-11-13+01:00".
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _earliest_deadline(values: list[str] | None) -> date | None:
    dates = sorted(d for d in (_parse_date(v) for v in values or []) if d)
    return dates[0] if dates else None


def _notice_type(raw: str) -> NoticeType:
    if raw.startswith("pin"):
        return "planning"
    if raw.startswith("can") or raw.startswith("veat"):
        return "award"
    return "tender"


def _dedupe(codes: list[str] | None) -> list[str]:
    seen: list[str] = []
    for code in codes or []:
        if code not in seen:
            seen.append(code)
    return seen


def _notice_url(notice: dict[str, Any]) -> str:
    links = notice.get("links") or {}
    for kind in ("html", "htmlDirect"):
        urls = links.get(kind) or {}
        if "ENG" in urls:
            return urls["ENG"]
        if urls:
            return next(iter(urls.values()))
    return f"https://ted.europa.eu/en/notice/-/detail/{notice['publication-number']}"


def map_notice(notice: dict[str, Any]) -> UnifiedNotice | None:
    number = notice.get("publication-number")
    title = _pick_language(notice.get("notice-title"))
    published = _parse_date(notice.get("publication-date"))
    if not number or not title or not published:
        return None

    cpv_codes = _dedupe(notice.get("classification-cpv"))
    raw_type = str(notice.get("notice-type") or "")
    notice_type = _notice_type(raw_type)
    amount = notice.get("estimated-value-glo")
    countries = notice.get("buyer-country") or []
    country = _ISO3_TO_ISO2.get(str(countries[0]).upper(), "") if countries else ""

    return UnifiedNotice(
        source="ted",
        notice_id=str(number),
        ocid=None,
        tender_ref=f"ted:{number}",
        title=title,
        description=_pick_language(notice.get("description-lot")),
        buyer_name=_pick_language(notice.get("buyer-name")),
        country=country,
        cpv_codes=cpv_codes,
        main_cpv=cpv_codes[0] if cpv_codes else None,
        value_amount=float(amount) if amount is not None else None,
        value_currency=notice.get("estimated-value-cur-glo"),
        value_type="estimated" if amount is not None else "unknown",
        status={"planning": "planned", "tender": "active", "award": "complete"}[notice_type],
        notice_type=notice_type,
        published_date=published,
        deadline_date=_earliest_deadline(notice.get("deadline-receipt-tender-date-lot")),
        url=_notice_url(notice),
        fetched_at=datetime.now().astimezone(),
    )


def fetch(since: date, max_pages: int = 50) -> Iterator[UnifiedNotice]:
    query = (
        f"publication-date>={since.strftime('%Y%m%d')}"
        " AND notice-type IN (cn-standard cn-social can-standard can-social pin-only)"
    )
    for page in range(1, max_pages + 1):
        body = {"query": query, "fields": FIELDS, "page": page, "limit": PAGE_SIZE}
        result = request_json("POST", API_URL, json=body)
        notices = result.get("notices") or []
        for raw in notices:
            notice = map_notice(raw)
            if notice:
                yield notice
        if len(notices) < PAGE_SIZE:
            break
        time.sleep(PAGE_PAUSE_SECONDS)
