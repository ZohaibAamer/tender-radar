-- Every notice from every source, in one unified relation.
select * from {{ ref('stg_fts') }}
union all by name
select * from {{ ref('stg_contracts_finder') }}
union all by name
select * from {{ ref('stg_ted') }}
