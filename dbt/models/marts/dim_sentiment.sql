-- One row per day of Fear & Greed sentiment data.

select
    {{ generate_surrogate_key(['score_date']) }}     as sentiment_key,
    score_date,
    score,
    classification
from {{ ref('stg_fear_greed__index') }}
