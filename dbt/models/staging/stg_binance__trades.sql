with source as (
    select * from {{ source('raw', 'binance_trades') }}
),

cleaned as (
    select
        trade_id::bigint                                        as trade_id,
        upper(symbol)                                           as symbol,
        price::float                                            as price,
        quantity::float                                         as quantity,
        quote_qty::float                                        as quote_qty,
        -- trade_time_utc is ISO format: "2024-01-15T20:04:51.268000+00:00"
        cast(left(trade_time_utc, 19) as timestamp)             as trade_time_utc,
        cast(left(trade_time_utc, 10) as date)                  as trade_date,
        is_buyer_maker::boolean                                 as is_buyer_maker
    from source
    where trade_id is not null
      and price is not null
      and price > 0
)

select * from cleaned
