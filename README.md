# Crypto Data Pipeline

Pulls live market data from three sources, loads it into Redshift, transforms it with dbt, and serves it through a Metabase dashboard. Runs on AWS, orchestrated by Airflow, provisioned with Terraform.

## Architecture

```
CoinGecko API  ─┐
Binance WS     ─┼──▶  S3 (Parquet)  ──▶  Redshift  ──▶  dbt  ──▶  Metabase
Fear & Greed   ─┘

Airflow schedules every step. Terraform provisions all AWS infrastructure.
```

**Data sources:**
- CoinGecko REST API — daily prices and market cap for top 20 coins
- Binance WebSocket — real-time trade stream, flushed to S3 every 5 minutes
- Alternative.me Fear & Greed Index — daily sentiment score

**dbt layers:** staging (views) → intermediate (joins, VWAP, rolling averages) → marts (Kimball star schema: `fact_trades`, `dim_coin`, `dim_date`, `dim_sentiment`)

## Stack

| | |
|---|---|
| Cloud | AWS (S3, Redshift Serverless, EC2) |
| Orchestration | Apache Airflow |
| Transformation | dbt Core |
| Infrastructure | Terraform |
| Visualization | Metabase |
| CI/CD | GitHub Actions |

## Running locally

```bash
cp .env.example .env        # fill in credentials
docker compose up -d        # starts Airflow + Metabase
```

Airflow UI at `http://localhost:8080`, Metabase at `http://localhost:3000`.

To run ingestion or dbt manually:
```bash
python ingestion/coingecko.py --date 2024-01-15
cd dbt && dbt run
```

## Deploying to AWS

```bash
cd terraform
terraform init && terraform apply
```

After apply, copy the outputs (`ec2_public_ip`, `redshift_endpoint`) into your `.env` and SSH into the instance — Docker Compose is already running via the bootstrap script.

## Tests

```bash
pytest tests/        # 30 unit tests covering ingestion and Redshift loader
```

CI runs on every push via GitHub Actions (lint + tests + dbt parse).
