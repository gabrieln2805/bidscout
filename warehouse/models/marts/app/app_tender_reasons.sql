-- The explanation lines behind each verdict in `app_tenders`.
select
    c_notice_id,
    reason_index,
    reason_text,
    quote,
    source_field,
    outcome
from {{ ref('fct_verdict_reasons') }}
where company = '{{ var("company") }}'
