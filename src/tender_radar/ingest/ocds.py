"""Mapping of OCDS releases (Find a Tender, Contracts Finder) to UnifiedNotice.

Both UK portals publish OCDS release packages, so they share one mapper; only
the source tag and the public notice URL differ.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .models import NoticeType, Source, UnifiedNotice


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _notice_type(tags: list[str]) -> NoticeType:
    if any(t.startswith("planning") for t in tags):
        return "planning"
    if any(t in ("award", "contract", "contractUpdate") or t.startswith("award") for t in tags):
        return "award"
    return "tender"


def _collect_cpv(release: dict[str, Any]) -> list[str]:
    """CPV codes appear as classifications on the tender, its items, and award items."""
    codes: list[str] = []

    def add(classification: dict[str, Any] | None) -> None:
        if classification and classification.get("scheme") == "CPV":
            code = str(classification.get("id", "")).strip()
            if code and code not in codes:
                codes.append(code)

    tender = release.get("tender") or {}
    add(tender.get("classification"))
    for extra in tender.get("additionalClassifications") or []:
        add(extra)
    item_holders = [tender] + list(release.get("awards") or [])
    for holder in item_holders:
        for item in holder.get("items") or []:
            add(item.get("classification"))
            for extra in item.get("additionalClassifications") or []:
                add(extra)
    return codes


def _buyer_country(release: dict[str, Any]) -> str:
    buyer_id = (release.get("buyer") or {}).get("id")
    for party in release.get("parties") or []:
        if "buyer" in (party.get("roles") or []) or party.get("id") == buyer_id:
            country = (party.get("address") or {}).get("country")
            if country:
                return str(country)[:2].upper()
    return "GB"  # both portals are UK-only


def _value(release: dict[str, Any]) -> tuple[float | None, str | None, str]:
    """Prefer the tender's estimate; fall back to awarded amounts."""
    tender_value = (release.get("tender") or {}).get("value") or {}
    if tender_value.get("amount") is not None:
        return float(tender_value["amount"]), tender_value.get("currency"), "estimated"
    for holder in list(release.get("awards") or []) + list(release.get("contracts") or []):
        value = holder.get("value") or {}
        if value.get("amount") is not None:
            return float(value["amount"]), value.get("currency"), "awarded"
    return None, None, "unknown"


def map_ocds_release(release: dict[str, Any], source: Source, url: str) -> UnifiedNotice | None:
    tender = release.get("tender") or {}
    title = tender.get("title")
    ocid = release.get("ocid")
    if not title or not ocid:
        return None  # not a usable notice

    cpv_codes = _collect_cpv(release)
    amount, currency, value_type = _value(release)
    deadline = _parse_date((tender.get("tenderPeriod") or {}).get("endDate"))

    return UnifiedNotice(
        source=source,
        notice_id=str(release["id"]),
        ocid=ocid,
        tender_ref=ocid,
        title=title,
        description=tender.get("description") or "",
        buyer_name=(release.get("buyer") or {}).get("name") or "",
        country=_buyer_country(release),
        cpv_codes=cpv_codes,
        main_cpv=cpv_codes[0] if cpv_codes else None,
        value_amount=amount,
        value_currency=currency,
        value_type=value_type,
        status=tender.get("status") or "unknown",
        notice_type=_notice_type(release.get("tag") or []),
        published_date=_parse_date(release.get("date")) or date.today(),
        deadline_date=deadline,
        url=url,
        fetched_at=datetime.now().astimezone(),
    )
