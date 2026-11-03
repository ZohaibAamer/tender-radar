"""The unified, OCDS-shaped notice record every source maps into.

One row per published notice. Notices belonging to the same procurement are
grouped later (in dbt) via `tender_ref`: the OCDS `ocid` where the source has
one, or a synthetic `ted:<publication-number>` key for TED.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["fts", "contracts_finder", "ted"]
NoticeType = Literal["planning", "tender", "award"]
ValueType = Literal["estimated", "awarded", "unknown"]


class UnifiedNotice(BaseModel):
    source: Source
    notice_id: str
    ocid: str | None = None
    tender_ref: str
    title: str
    description: str = ""
    buyer_name: str = ""
    country: str = ""  # ISO 3166-1 alpha-2
    cpv_codes: list[str] = Field(default_factory=list)
    main_cpv: str | None = None
    value_amount: float | None = None
    value_currency: str | None = None
    value_type: ValueType = "unknown"
    status: str = "unknown"
    notice_type: NoticeType = "tender"
    published_date: date
    deadline_date: date | None = None
    url: str
    fetched_at: datetime
