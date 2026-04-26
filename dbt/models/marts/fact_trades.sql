-- Daily grain fact table: one row per coin per day.
-- Combines CoinGecko market data (20 coins) enriched with Binance tick-derived
-- OHLCV (BTC/ETH/SOL) and joined to all three dimension tables.

with metrics as (
    select * from {{ ref('int_coin_daily_metrics') }}
),

dim_coin as (
    select coin_key, coin_id from {{ ref('dim_coin') }}
),

dim_date as (
    select date_key, full_date from {{ ref('dim_date') }}
),

dim_sentiment as (
    select sentiment_key, score_date from {{ ref('dim_sentiment') }}
),

final as (
    select
        {{ generate_surrogate_key(['m.coin_id', 'm.market_date::varchar']) }} as trade_id,
        dd.date_key,
        dc.coin_key,
        ds.sentiment_key,
        m.open_price,
        m.high_price,
        m.low_price,
        m.close_price,
        m.volume_usd,
        m.market_cap_usd,
        m.trade_count,
        m.vwap,
        m.rolling_7d_avg_price,
        current_timestamp as loaded_at
    from metrics m
    inner join dim_coin     dc on dc.coin_id   = m.coin_id
    inner join dim_date     dd on dd.full_date  = m.market_date
    left  join dim_sentiment ds on ds.score_date = m.market_date
)

select * from final
