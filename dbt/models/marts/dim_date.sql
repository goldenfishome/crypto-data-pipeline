-- Date dimension covering 2024-01-01 through today.
-- Generated using a cross-join of digit tables — no external dependencies.

with digits as (
    select 0 as d union all select 1 union all select 2 union all select 3
    union all select 4 union all select 5 union all select 6 union all select 7
    union all select 8 union all select 9
),

-- Cross-join four digit tables to produce numbers 0–9999
numbers as (
    select (d1.d * 1000 + d2.d * 100 + d3.d * 10 + d4.d) as n
    from digits d1
    cross join digits d2
    cross join digits d3
    cross join digits d4
),

dates as (
    select dateadd(day, n, '2024-01-01'::date) as full_date
    from numbers
    where dateadd(day, n, '2024-01-01'::date) <= current_date
)

select
    {{ generate_surrogate_key(['full_date']) }}          as date_key,
    full_date,
    extract(year    from full_date)::int                 as year,
    extract(quarter from full_date)::int                 as quarter,
    extract(month   from full_date)::int                 as month,
    extract(week    from full_date)::int                 as week,
    extract(dow     from full_date)::int                 as day_of_week,
    case
        when extract(dow from full_date) in (0, 6) then true
        else false
    end                                                  as is_weekend
from dates
