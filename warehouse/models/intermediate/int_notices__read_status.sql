-- How far each notice has got through the pipeline, for the company the app
-- shows. A notice that is not 'scored' was not judged, and the app says so
-- instead of letting it look like a notice that asks for nothing.
with notices as (
    select c_notice_id, notice_type_id, notice_no from {{ ref('stg_sicap__notices') }}
),

sections as (
    select c_notice_id, is_portal_error, fetched_at from {{ ref('stg_sicap__sections') }}
),

verdicts as (
    select c_notice_id from {{ ref('stg_bidscout__scores') }}
    where company = '{{ var("company") }}'
)

select
    n.c_notice_id,
    s.fetched_at                                                  as section3_fetched_at,
    case
        -- A verdict counts only over a real section: one left over from before
        -- a section turned out to be the portal's "not found" does not.
        when v.c_notice_id is not null and s.c_notice_id is not null and not s.is_portal_error
            then 'scored'
        when s.c_notice_id is not null and not s.is_portal_error
            then 'read, not scored'
        when s.is_portal_error
            then 'portal refused'
        -- Only full contract notices (type 2) have a known detail endpoint.
        when n.notice_type_id is distinct from 2 or upper(n.notice_no) like 'SCN%'
            then 'no known endpoint'
        else 'awaiting fetch'
    end                                                           as read_status
from notices as n
left join sections as s using (c_notice_id)
left join verdicts as v using (c_notice_id)
