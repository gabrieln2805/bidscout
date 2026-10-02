-- The figures and sentences each verdict in `app_tenders` was measured on.
select
    c_notice_id,
    requirement_kind,
    amount_text,
    currency,
    quote,
    source_field,
    confidence
from {{ ref('fct_requirements') }}
