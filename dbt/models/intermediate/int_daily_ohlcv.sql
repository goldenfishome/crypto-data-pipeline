-- Aggregates Binance trade ticks to daily OHLCV per symbol.
-- Open = first trade of the day, Close = last trade of the day.
-- VWAP = volume-weighted average price across all trades in the day.

with trades as (
    select * from {{ ref('stg_binance__trades') }}
),

ranked as (
    select
        symbol,
        trade_date,
        price,
        quantity,
        quote_qty,
        row_number() over (
            partition by symbol, trade_date order by trade_time_utc asc
        ) as rn_first,
        row_number() over (
            partition by symbol, trade_date order by trade_time_utc desc
        ) as rn_last
    from trades
),

daily as (
    select
        symbol,
        trade_date,
        max(case when rn_first = 1 then price end)  as open_price,
        max(price)                                   as high_price,
        min(price)                                   as low_price,
        max(case when rn_last  = 1 then price end)  as close_price,
        sum(quote_qty)                               as volume_usd,
        count(*)                                     as trade_count,
        sum(price * quantity) / nullif(sum(quantity), 0) as vwap
    from ranked
    group by 1, 2
)

select * from daily
