select
    c_notice_id,
    guid                                                          as document_guid,
    name                                                          as document_name,
    code                                                          as document_code,
    doc_group                                                     as document_group,
    lower(nullif(regexp_extract(name, '\.([A-Za-z0-9]{1,5})$', 1), ''))
                                                                  as file_extension,
    'https://www.e-licitatie.ro/api-pub/files/noticedoc/' || guid as download_url
from {{ source('sicap', 'documents') }}
