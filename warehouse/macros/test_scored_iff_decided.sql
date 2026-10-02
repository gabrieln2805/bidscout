{#-
  Ground rule 2 at the warehouse boundary: a decision appears only on a notice
  that was read and scored, and every scored notice has one. A row breaking
  either half is a notice the page would mislabel.
-#}
{% test scored_iff_decided(model) %}
select c_notice_id, read_status, decision
from {{ model }}
where (read_status = 'scored') <> (decision is not null)
{% endtest %}
