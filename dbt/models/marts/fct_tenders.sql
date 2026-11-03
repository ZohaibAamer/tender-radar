-- The semantic layer's one entry point. Clock-free on purpose: openness is
-- derived at query time from deadline_date and the injectable clock, so the
-- same mart serves live data and the frozen eval fixture.
select
    tenders.tender_ref,
    tenders.source,
    tenders.ocid,
    tenders.latest_notice_id,
    tenders.title,
    tenders.description,
    tenders.buyer_name,
    tenders.country,
    tenders.cpv_codes,
    tenders.main_cpv,
    tenders.cpv_division,
    divisions.label as cpv_division_label,
    tenders.value_amount,
    tenders.value_currency,
    tenders.value_type,
    tenders.status,
    tenders.latest_notice_type,
    tenders.notice_count,
    tenders.first_published_date,
    tenders.last_published_date,
    tenders.deadline_date,
    tenders.has_award,
    tenders.url
from {{ ref('tenders') }} as tenders
left join {{ ref('cpv_divisions') }} as divisions
    on tenders.cpv_division = divisions.division
