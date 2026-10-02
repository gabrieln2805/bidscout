select
    c_notice_id,
    company,
    decision,
    score,
    cast(reasons as json)                                         as reasons,
    cast(unresolved as json)                                      as unresolved,
    cast(scored_at as timestamptz)                                as scored_at
from {{ source('bidscout', 'scores') }}
