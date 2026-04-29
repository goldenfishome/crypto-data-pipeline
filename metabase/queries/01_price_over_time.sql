-- Chart 1: Coin Price Over Time
-- Type: Line chart
-- X-axis: full_date  |  Y-axis: close_price  |  Series: symbol
-- Shows daily closing price for BTC, ETH, SOL on the same chart.

SELECT
    d.full_date,
    c.symbol,
    f.close_price
FROM marts.fact_trades f
JOIN marts.dim_date    d ON f.date_key = d.date_key
JOIN marts.dim_coin    c ON f.coin_key = c.coin_key
WHERE c.symbol IN ('BTC', 'ETH', 'SOL')
ORDER BY d.full_date, c.symbol;
