-- The CPV hierarchy is encoded in the code's prefixes: 2 digits = division,
-- 3 = group, 4 = class, 5 = category. One row per distinct observed code.
with observed as (
    select distinct unnest(cpv_codes) as cpv_code
    from {{ ref('notices') }}
)

select
    observed.cpv_code,
    left(observed.cpv_code, 2) as division,
    left(observed.cpv_code, 3) as "group",
    left(observed.cpv_code, 4) as class,
    left(observed.cpv_code, 5) as category,
    divisions.label as division_label
from observed
left join {{ ref('cpv_divisions') }} as divisions
    on left(observed.cpv_code, 2) = divisions.division
