with source as (
    select * from {{ source('raw', 'coingecko_markets') }}
),

cleaned as (
    select
        coin_id,
        upper(symbol)                       as symbol,
        name,
        current_price_usd::float            as current_price_usd,
        market_cap_usd::bigint              as market_cap_usd,
        market_cap_rank::int                as market_cap_rank,
        total_volume_usd::bigint            as total_volume_usd,
        high_24h_usd::float                 as high_24h_usd,
        low_24h_usd::float                  as low_24h_usd,
        price_change_24h::float             as price_change_24h,
        price_change_pct_24h::float         as price_change_pct_24h,
        circulating_supply::float           as circulating_supply,
        total_supply::float                 as total_supply,
        cast(ingested_date as date)         as market_date,
        cast(ingested_at as varchar(50))    as ingested_at,
        row_number() over (
            partition by coin_id, ingested_date
            order by ingested_at desc
        ) as _row_num
    from source
    where coin_id is not null
      and current_price_usd is not null
      and ingested_date is not null
)

select * from cleaned
where _row_num = 1
