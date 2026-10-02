-- One row per requirement read from a Section 3, with the buyer's sentence.
-- Company-independent: what the buyer asks for does not depend on who reads it.
select
    r.c_notice_id,
    n.notice_no,
    r.requirement_kind,
    r.amount_text,
    r.amount,
    r.currency,
    r.quote,
    r.source_field,
    r.confidence,
    r.extracted_at
from {{ ref('stg_bidscout__requirements') }} as r
join {{ ref('stg_sicap__notices') }} as n on n.c_notice_id = r.c_notice_id
