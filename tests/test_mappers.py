"""Mapper tests against real, committed API responses (one per source)."""

import json
from datetime import date
from pathlib import Path

from tender_radar.ingest import contracts_finder, fts, ted

DATA = Path(__file__).parent / "data"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def test_fts_release_maps_to_unified_notice():
    release = load("fts_sample.json")["releases"][0]
    notice = fts.map_release(release)
    assert notice is not None
    assert notice.source == "fts"
    assert notice.ocid == "ocds-h6vhtk-079716"
    assert notice.tender_ref == notice.ocid
    assert notice.title == "Simitive WAMS"
    assert notice.buyer_name == "Coventry University"
    assert notice.country == "GB"
    assert "48000000" in notice.cpv_codes
    assert notice.main_cpv == "48000000"
    # no tender-level estimate in this release, so the awarded value is used
    assert notice.value_type == "awarded"
    assert notice.value_currency == "GBP"
    assert notice.notice_type == "award"
    assert notice.url.endswith(release["id"])


def test_cf_release_maps_to_unified_notice():
    release = load("cf_sample.json")["releases"][0]
    notice = contracts_finder.map_release(release)
    assert notice is not None
    assert notice.source == "contracts_finder"
    assert notice.ocid.startswith("ocds-b5fd17-")
    assert notice.title == "Evaluation Scoping Studies (2 Lots)"
    assert notice.main_cpv == "73110000"
    assert "79419000" in notice.cpv_codes
    assert notice.notice_type == "tender"
    assert notice.status == "active"
    # public page is keyed by the 36-char uuid prefix of the release id
    assert notice.url == (
        "https://www.contractsfinder.service.gov.uk/notice/"
        "8d6ee322-4f9f-4343-af0a-9769ed660d8e"
    )


def test_ted_notice_maps_to_unified_notice():
    raw = load("ted_sample.json")["notices"][0]
    notice = ted.map_notice(raw)
    assert notice is not None
    assert notice.source == "ted"
    assert notice.notice_id == "756373-2026"
    assert notice.ocid is None
    assert notice.tender_ref == "ted:756373-2026"
    assert notice.title  # multilingual dict resolved to one string
    assert notice.country == "PL"
    assert notice.cpv_codes[0] == "39810000"
    assert len(notice.cpv_codes) == len(set(notice.cpv_codes))  # deduped
    assert notice.notice_type == "tender"
    assert notice.deadline_date == date(2026, 11, 13)
    assert notice.published_date == date(2026, 11, 2)
    assert "ted.europa.eu" in notice.url


def test_ted_language_fallback_prefers_english():
    assert ted._pick_language({"pol": "po polsku", "eng": "in English"}) == "in English"
    assert ted._pick_language({"pol": ["a", "b"]}) == "a | b"
    assert ted._pick_language(None) == ""
