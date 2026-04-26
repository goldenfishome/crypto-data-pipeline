with source as (
    select * from {{ source('raw', 'fear_greed_index') }}
),

cleaned as (
    select
        cast(score_date as date)    as score_date,
        score::int                  as score,
        classification,
        ingested_at,
        row_number() over (
            partition by score_date
            order by ingested_at desc
        ) as _row_num
    from source
    where score_date is not null
      and score is not null
)

select * from cleaned
where _row_num = 1
