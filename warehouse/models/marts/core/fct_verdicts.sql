-- One row per (notice, company): the decision the rules engine reached.
select
    s.c_notice_id,
    n.notice_no,
    s.company,
    s.decision,
    s.score,
    cast(s.unresolved as varchar[])                               as unresolved,
    json_array_length(s.unresolved)                               as unresolved_gates,
    s.scored_at
from {{ ref('stg_bidscout__scores') }} as s
join {{ ref('stg_sicap__notices') }} as n on n.c_notice_id = s.c_notice_id
