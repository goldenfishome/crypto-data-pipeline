-- Joins CoinGecko daily market data with Binance tick-derived OHLCV.
-- For BTC/ETH/SOL: uses Binance prices (more precise, tick-level).
-- For all other coins: falls back to CoinGecko snapshot prices.
-- Also computes 7-day rolling average close price per coin.

with coingecko as (
    select * from {{ ref('stg_coingecko__markets') }}
),

binance_ohlcv as (
    select * from {{ ref('int_daily_ohlcv') }}
),

-- Map Binance USDT pairs to CoinGecko coin_ids for joining
binance_mapped as (
    select
        case
            when symbol = 'BTCUSDT'  then 'bitcoin'
            when symbol = 'ETHUSDT'  then 'ethereum'
            when symbol = 'SOLUSDT'  then 'solana'
        end                 as coin_id,
        trade_date          as market_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume_usd          as binance_volume_usd,
        trade_count,
        vwap
    from binance_ohlcv
    where symbol in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
),

joined as (
    select
        c.coin_id,
        c.symbol,
        c.name,
        c.market_date,
        -- Prices: prefer Binance tick data, fall back to CoinGecko snapshot
        coalesce(b.open_price,  c.current_price_usd)            as open_price,
        coalesce(b.high_price,  c.high_24h_usd)                 as high_price,
        coalesce(b.low_price,   c.low_24h_usd)                  as low_price,
        coalesce(b.close_price, c.current_price_usd)            as close_price,
        coalesce(b.binance_volume_usd,
                 c.total_volume_usd::float)                     as volume_usd,
        c.market_cap_usd,
        coalesce(b.trade_count, 0)                              as trade_count,
        b.vwap,
        -- 7-day rolling average close price
        avg(coalesce(b.close_price, c.current_price_usd)) over (
            partition by c.coin_id
            order by c.market_date
            rows between 6 preceding and current row
        )                                                       as rolling_7d_avg_price
    from coingecko c
    left join binance_mapped b
        on  b.coin_id     = c.coin_id
        and b.market_date = c.market_date
)

select * from joined
