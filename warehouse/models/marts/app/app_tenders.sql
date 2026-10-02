-- THE table the frontend reads: every landed notice, once, with the verdict
-- for the company the app shows when there is one. `read_status` says why a
-- notice has no verdict, so the page can list it rather than hide it.
select
    n.c_notice_id,
    n.notice_no,
    n.title,
    n.buyer_name                                                  as buyer,
    n.buyer_key,
    n.cpv_code                                                    as cpv,
    n.cpv_name,
    n.notice_kind,
    n.procedure_type,
    n.contract_type,
    n.estimated_value_ron,
    n.published_at,
    n.deadline_at,
    n.has_lots,
    n.notice_kind = 'simplified notice'                           as is_simplified,
    n.documents,
    n.read_status,
    v.decision,
    v.score,
    v.unresolved,
    v.scored_at
from {{ ref('fct_notices') }} as n
left join {{ ref('fct_verdicts') }} as v
    on v.c_notice_id = n.c_notice_id
    and v.company = '{{ var("company") }}'
    and n.read_status = 'scored'
