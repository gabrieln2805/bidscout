-- One row per notice: what the portal published, how far bidscout has read
-- it, and how many files it carries.
with documents as (
    select c_notice_id, count(*) as documents
    from {{ ref('stg_sicap__documents') }}
    group by c_notice_id
)

select
    n.c_notice_id,
    n.notice_no,
    n.notice_id,
    n.procedure_id,
    n.notice_type_id,
    n.notice_kind,
    n.title,
    coalesce(n.buyer_fiscal_code, n.buyer_name)                   as buyer_key,
    n.buyer_name,
    n.cpv_code,
    n.cpv_name,
    n.procedure_type,
    n.contract_type,
    n.assignment_type,
    n.procedure_state,
    n.estimated_value_ron,
    n.is_online,
    n.has_lots,
    n.has_appeal,
    n.errata_no,
    n.published_at,
    n.deadline_at,
    n.first_seen_at,
    n.last_seen_at,
    r.read_status,
    r.section3_fetched_at,
    coalesce(d.documents, 0)                                      as documents
from {{ ref('stg_sicap__notices') }} as n
left join {{ ref('int_notices__read_status') }} as r on r.c_notice_id = n.c_notice_id
left join documents as d on d.c_notice_id = n.c_notice_id
