-- Where every landed notice stands. Sums to the number of notices in landing,
-- and the page prints it as "where this data comes from".
select
    read_status,
    count(*)                                                      as notices
from {{ ref('fct_notices') }}
group by read_status
