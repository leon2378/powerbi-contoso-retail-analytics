{# Small generic tests kept in-repo so the project has no package dependencies. #}

{% test unique_combination(model, columns) %}
    select {{ columns | join(', ') }}, count(*) as duplicate_rows
    from {{ model }}
    group by {{ columns | join(', ') }}
    having count(*) > 1
{% endtest %}


{% test accepted_range(model, column_name, min_value=none, max_value=none) %}
    select {{ column_name }}
    from {{ model }}
    where {{ column_name }} is not null
      and (
        1 = 0
        {% if min_value is not none %} or {{ column_name }} < {{ min_value }} {% endif %}
        {% if max_value is not none %} or {{ column_name }} > {{ max_value }} {% endif %}
      )
{% endtest %}
