-- One row per file attached to a notice. `download_url` needs no sign-in.
select
    d.c_notice_id,
    n.notice_no,
    d.document_guid,
    d.document_name,
    d.document_code,
    d.document_group,
    d.file_extension,
    d.download_url
from {{ ref('stg_sicap__documents') }} as d
join {{ ref('stg_sicap__notices') }} as n on n.c_notice_id = d.c_notice_id
