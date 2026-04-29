-- Chart 3: Daily Trading Volume by Coin
-- Type: Stacked bar chart
-- X-axis: full_date  |  Y-axis: volume_usd  |  Stack: symbol
-- Shows how much USD volume each coin contributed each day.

SELECT
    d.full_date,
    c.symbol,
    f.volume_usd
FROM marts.fact_trades f
JOIN marts.dim_date d ON f.date_key = d.date_key
JOIN marts.dim_coin c ON f.coin_key = c.coin_key
WHERE c.symbol IN ('BTC', 'ETH', 'SOL')
  AND f.volume_usd IS NOT NULL
ORDER BY d.full_date, c.symbol;
