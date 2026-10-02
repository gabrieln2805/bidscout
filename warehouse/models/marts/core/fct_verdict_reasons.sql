-- One row per line of a verdict's explanation, in the order the engine wrote
-- them. `outcome` is what the gate did; nothing downstream parses `reason_text`.
with reasons as (
    select
        c_notice_id,
        company,
        cast(reasons as json[])                                   as reason_list
    from {{ ref('stg_bidscout__scores') }}
),

unnested as (
    select
        c_notice_id,
        company,
        generate_subscripts(reason_list, 1)                       as reason_index,
        unnest(reason_list)                                       as reason
    from reasons
)

select
    c_notice_id,
    company,
    reason_index,
    reason ->> '$.text'                                           as reason_text,
    reason ->> '$.quote'                                          as quote,
    reason ->> '$.source_field'                                   as source_field,
    reason ->> '$.outcome'                                        as outcome
from unnested
