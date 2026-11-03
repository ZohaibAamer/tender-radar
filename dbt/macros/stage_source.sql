{% macro stage_source(source_name) %}
-- The Python mappers already emit the unified schema, so staging is thin:
-- stable column order, trimmed text, and the CPV division prefix.
select
    source,
    notice_id,
    ocid,
    tender_ref,
    trim(title) as title,
    coalesce(description, '') as description,
    trim(coalesce(buyer_name, '')) as buyer_name,
    upper(coalesce(country, '')) as country,
    cpv_codes,
    main_cpv,
    left(main_cpv, 2) as cpv_division,
    value_amount,
    value_currency,
    value_type,
    status,
    notice_type,
    published_date,
    deadline_date,
    url,
    fetched_at
from {{ source('raw', source_name) }}
{% endmacro %}
