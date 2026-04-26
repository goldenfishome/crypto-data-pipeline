-- One row per unique coin. Natural key is coin_id (CoinGecko identifier).
-- first_seen_date = earliest market_date observed in the pipeline.

with coins as (
    select
        coin_id,
        symbol,
        name,
        min(market_date) as first_seen_date
    from {{ ref('stg_coingecko__markets') }}
    group by 1, 2, 3
)

select
    {{ generate_surrogate_key(['coin_id']) }}    as coin_key,
    coin_id,
    symbol,
    name,
    first_seen_date
from coins
