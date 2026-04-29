-- Chart 2: Fear & Greed Index Over Time
-- Type: Bar chart (color-coded by classification)
-- X-axis: score_date  |  Y-axis: score  |  Color: classification
-- Extreme Fear (<25) red, Fear (25-45) orange, Neutral (46-54) yellow,
-- Greed (55-75) light green, Extreme Greed (>75) dark green.

SELECT
    s.score_date,
    s.score,
    s.classification
FROM marts.dim_sentiment s
ORDER BY s.score_date;
