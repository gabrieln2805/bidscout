-- One row per landed Section 3. `is_portal_error` marks the portal's "not
-- found" answer (HTTP 200, hasError: true), which is not a section and must
-- never be read as one: every criterion in it is null, which would look like a
-- buyer who asks for nothing.
with source as (
    select c_notice_id, fetched_at, cast(section3_raw as json) as section
    from {{ source('sicap', 'sections') }}
)

select
    c_notice_id,
    cast(fetched_at as timestamptz)                               as fetched_at,
    coalesce(cast(section ->> '$.hasError' as boolean), false)    as is_portal_error,
    section ->> '$.responseMessage'                               as portal_message,
    -- The prose fields the extractor reads, still as HTML. Python strips and
    -- parses them; these are here so a person can query what the buyer wrote.
    section ->> '$.efCriteriaMin'                                 as turnover_html,
    section ->> '$.tpCriteriaQAStandardMin'                       as experience_html,
    section ->> '$.depositsAndWarranties'                         as deposit_html,
    section ->> '$.personalSituation'                             as personal_situation_html,
    -- A flag on the live portal, not prose.
    cast(section ->> '$.mandatoryProfesionalQualif' as boolean)   as requires_professional_qualification,
    cast(section ->> '$.isReservedContract' as boolean)           as is_reserved_contract
from source
