-- Chart 5: Market Cap Share (Latest Day)
-- Type: Pie or donut chart
-- Shows each coin's share of total tracked market cap as of the most recent date.
-- Good at-a-glance summary card for the top of the dashboard.

SELECT
    c.symbol,
    c.name,
    f.market_cap_usd,
    ROUND(
        100.0 * f.market_cap_usd
        / SUM(f.market_cap_usd) OVER (),
        1
    ) AS pct_of_total
FROM marts.fact_trades f
JOIN marts.dim_coin c ON f.coin_key = c.coin_key
JOIN marts.dim_date d ON f.date_key = d.date_key
WHERE d.full_date = (SELECT MAX(full_date) FROM marts.dim_date d2
                     JOIN marts.fact_trades f2 ON f2.date_key = d2.date_key)
  AND f.market_cap_usd IS NOT NULL
ORDER BY f.market_cap_usd DESC;
