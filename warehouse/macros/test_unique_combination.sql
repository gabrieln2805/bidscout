{#-
  The grain test, without pulling in the dbt_utils package (and a network
  call on every fresh checkout) for one macro. Fails on every duplicate key.
-#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as rows_with_this_key
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
