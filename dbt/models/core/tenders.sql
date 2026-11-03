-- One row per procurement. Notices for the same tender (planning → tender →
-- award) share a tender_ref: the OCDS ocid, or ted:<number> for TED. This is
-- the lifecycle dedup — keyed, not fuzzy, and we say so in the README.
with ranked as (
    select
        *,
        row_number() over (
            partition by tender_ref
            order by published_date desc, fetched_at desc
        ) as recency
    from {{ ref('notices') }}
),

latest as (
    select * from ranked where recency = 1
),

lifecycle as (
    select
        tender_ref,
        count(*) as notice_count,
        min(published_date) as first_published_date,
        -- the deadline can live on an earlier notice than the latest one
        max(deadline_date) as deadline_date,
        bool_or(notice_type = 'award') as has_award
    from {{ ref('notices') }}
    group by tender_ref
)

select
    latest.tender_ref,
    latest.source,
    latest.ocid,
    latest.notice_id as latest_notice_id,
    latest.title,
    latest.description,
    latest.buyer_name,
    latest.country,
    latest.cpv_codes,
    latest.main_cpv,
    latest.cpv_division,
    latest.value_amount,
    latest.value_currency,
    latest.value_type,
    latest.status,
    latest.notice_type as latest_notice_type,
    lifecycle.notice_count,
    lifecycle.first_published_date,
    latest.published_date as last_published_date,
    lifecycle.deadline_date,
    lifecycle.has_award,
    latest.url
from latest
join lifecycle using (tender_ref)
