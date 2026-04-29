-- Chart 4: BTC Price vs 7-Day Rolling Average
-- Type: Combo chart (line + line)
-- X-axis: full_date  |  Y-axis: close_price and rolling_avg_7d
-- Shows when price crosses above/below its 7-day average — a simple
-- momentum signal. Useful for demonstrating the intermediate dbt layer.

SELECT
    d.full_date,
    f.close_price,
    f.rolling_avg_7d
FROM marts.fact_trades f
JOIN marts.dim_date d ON f.date_key = d.date_key
JOIN marts.dim_coin c ON f.coin_key = c.coin_key
WHERE c.symbol = 'BTC'
  AND f.rolling_avg_7d IS NOT NULL
ORDER BY d.full_date;
