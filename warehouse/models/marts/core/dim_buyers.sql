-- One row per contracting authority. Keyed by the fiscal code (CUI) the portal
-- prints before the name; a buyer listed without one is keyed by its name.
select
    coalesce(buyer_fiscal_code, buyer_name)                       as buyer_key,
    any_value(buyer_fiscal_code)                                  as buyer_fiscal_code,
    arg_max(buyer_name, published_at)                             as buyer_name,
    count(*)                                                      as notices,
    sum(estimated_value_ron)                                      as estimated_value_ron,
    min(published_at)                                             as first_published_at,
    max(published_at)                                             as last_published_at
from {{ ref('stg_sicap__notices') }}
where coalesce(buyer_fiscal_code, buyer_name) is not null
group by 1
