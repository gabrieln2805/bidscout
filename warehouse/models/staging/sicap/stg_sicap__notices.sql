-- One row per notice, typed. Every column comes from the portal's own search
-- item (`raw`), not from the convenience columns, so a parser fix here never
-- needs a new request to the portal.
with source as (
    select * from {{ source('sicap', 'notices') }}
),

parsed as (
    select
        c_notice_id,
        first_seen,
        last_seen,
        cast(raw as json) as item
    from source
)

select
    c_notice_id,
    item ->> '$.noticeNo'                                         as notice_no,
    cast(item ->> '$.noticeId' as bigint)                         as notice_id,
    cast(item ->> '$.procedureId' as bigint)                      as procedure_id,
    cast(item ->> '$.sysNoticeTypeId' as integer)                 as notice_type_id,
    case cast(item ->> '$.sysNoticeTypeId' as integer)
        when 2 then 'contract notice'
        when 17 then 'simplified notice'
        when 7 then 'concession notice'
        else 'other'
    end                                                           as notice_kind,
    item ->> '$.contractTitle'                                    as title,
    -- "13683878 - UNITATEA MILITARA 02384", "RO 1683483 - Compania de Apa ...":
    -- the fiscal code (CUI), then the name. The CUI is kept as digits only, so
    -- "RO 1683483", "RO1683483" and "1683483" are one buyer.
    nullif(regexp_extract(
        item ->> '$.contractingAuthorityNameAndFN', '^\s*(?:RO)?\s*(\d{2,10})\s+-\s+', 1), '')
                                                                  as buyer_fiscal_code,
    coalesce(
        nullif(trim(regexp_extract(
            item ->> '$.contractingAuthorityNameAndFN',
            '^\s*(?:RO)?\s*\d{2,10}\s+-\s+(.+)$', 1)), ''),
        trim(item ->> '$.contractingAuthorityNameAndFN')
    )                                                             as buyer_name,
    -- "45310000-3 - Lucrari de instalatii electrice (Rev.2)"
    nullif(regexp_extract(item ->> '$.cpvCodeAndName', '^(\d{8})', 1), '')
                                                                  as cpv_code,
    nullif(trim(regexp_extract(item ->> '$.cpvCodeAndName', '^\S+\s+-\s+(.+)$', 1)), '')
                                                                  as cpv_name,
    item ->> '$.sysProcedureType.text'                            as procedure_type,
    item ->> '$.sysAcquisitionContractType.text'                  as contract_type,
    item ->> '$.sysContractAssigmentType.text'                    as assignment_type,
    item ->> '$.sysProcedureState.text'                           as procedure_state,
    item ->> '$.sysNoticeState.text'                              as notice_state,
    -- A JSON number in the portal; read through its text so it is never a float.
    cast(item ->> '$.estimatedValueRon' as decimal(18, 2))        as estimated_value_ron,
    cast(item ->> '$.isOnline' as boolean)                        as is_online,
    coalesce(cast(item ->> '$.hasLots' as boolean), false)        as has_lots,
    coalesce(cast(item ->> '$.hasAppeal' as boolean), false)      as has_appeal,
    cast(item ->> '$.errataNo' as integer)                        as errata_no,
    cast(item ->> '$.noticeStateDate' as timestamptz)             as published_at,
    cast(item ->> '$.minTenderReceiptDeadline' as timestamptz)    as deadline_at,
    cast(first_seen as timestamptz)                               as first_seen_at,
    cast(last_seen as timestamptz)                                as last_seen_at
from parsed
