# Metabase Setup Guide

Metabase runs alongside Airflow via Docker Compose.

## Start

```bash
docker compose up -d
```

Open http://localhost:3000 (takes ~90 seconds on first boot).

## First-time setup (one-time UI steps)

### 1. Create admin account
Fill in name, email, and password when prompted.

### 2. Connect to Redshift
- Click **Add your data**
- Select **Amazon Redshift**
- Fill in:
  | Field | Value |
  |---|---|
  | Display name | crypto-pipeline |
  | Host | `<value from terraform output redshift_endpoint>` |
  | Port | 5439 |
  | Database name | crypto_pipeline |
  | Username | `<REDSHIFT_USER from .env>` |
  | Password | `<REDSHIFT_PASSWORD from .env>` |
- Click **Save**

### 3. Create the dashboard
- Go to **New → Dashboard** → name it `Crypto Pipeline`

### 4. Add charts (one per query in `queries/`)
For each chart: **New → Question → Native query** → paste the SQL → configure as described below → Save → pin to dashboard.

---

## Charts

### Chart 1 — Coin Price Over Time (`01_price_over_time.sql`)
- Visualization: **Line**
- X-axis: `full_date`
- Y-axis: `close_price`
- Series breakout: `symbol`

### Chart 2 — Fear & Greed Index (`02_fear_greed_over_time.sql`)
- Visualization: **Bar**
- X-axis: `score_date`
- Y-axis: `score`
- Color: `classification`

### Chart 3 — Daily Volume by Coin (`03_volume_by_coin.sql`)
- Visualization: **Bar** → enable **Stacking**
- X-axis: `full_date`
- Y-axis: `volume_usd`
- Series breakout: `symbol`

### Chart 4 — BTC Price vs 7-Day Rolling Avg (`04_rolling_avg_vs_price.sql`)
- Visualization: **Line**
- X-axis: `full_date`
- Y-axis: add both `close_price` and `rolling_avg_7d` as two series

### Chart 5 — Market Cap Share (`05_market_cap_share.sql`)
- Visualization: **Pie**
- Dimension: `symbol`
- Metric: `market_cap_usd`
