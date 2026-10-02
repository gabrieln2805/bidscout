select
    c_notice_id,
    kind                                                          as requirement_kind,
    -- Exactly the text bidscout stored. The page shows this one.
    amount                                                        as amount_text,
    cast(amount as decimal(18, 2))                                as amount,
    currency,
    quote,
    source_field,
    confidence,
    cast(extracted_at as timestamptz)                             as extracted_at
from {{ source('bidscout', 'requirements') }}
