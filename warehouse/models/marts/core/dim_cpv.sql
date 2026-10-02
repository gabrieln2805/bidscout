-- The primary CPV codes seen so far. Secondary codes are not landed yet.
select
    cpv_code,
    arg_max(cpv_name, published_at)                               as cpv_name,
    left(cpv_code, 2)                                             as cpv_division,
    count(*)                                                      as notices
from {{ ref('stg_sicap__notices') }}
where cpv_code is not null
group by cpv_code
