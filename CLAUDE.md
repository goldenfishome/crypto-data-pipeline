# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

End-to-end data engineering portfolio project. Ingests live cryptocurrency data from three sources (CoinGecko REST, Binance WebSocket, Fear & Greed Index), lands raw Parquet files in S3, loads into Redshift, transforms via dbt (Kimball star schema), orchestrates with Airflow, and visualizes in Metabase. All infrastructure provisioned with Terraform on AWS.

See [REQUIREMENTS.md](REQUIREMENTS.md) for full spec.

## Virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate    # or .venv/bin/python3 / .venv/bin/pytest directly
pip install -r requirements-dev.txt
```

## Commands

```bash
# Local development (Airflow + dependencies)
docker-compose up -d            # Start local Airflow
docker-compose down             # Stop local Airflow
docker-compose logs -f          # Tail logs

# Ingestion scripts (run locally or via Airflow)
python ingestion/coingecko.py --date 2024-01-15   # Backfill a specific date
python ingestion/fear_greed.py
python ingestion/binance_ws.py

# dbt (run from dbt/ directory)
dbt run                          # Run all models
dbt run --select staging         # Run staging layer only
dbt run --select marts           # Run marts layer only
dbt test                         # Run all dbt tests
dbt test --select fact_trades    # Test a specific model
dbt compile                      # Validate SQL without running

# Python tests
pytest tests/                    # Run all unit tests
pytest tests/test_ingestion.py::test_coingecko  # Run a single test

# Linting
black ingestion/ dags/           # Format Python
sqlfluff lint dbt/models/        # Lint SQL
pre-commit run --all-files       # Run all pre-commit hooks

# Terraform
cd terraform && terraform init
terraform plan
terraform apply
terraform destroy
```

## Architecture

```
CoinGecko API  ─┐
Binance WS     ─┼─→ S3 raw (Parquet) ─→ Redshift raw ─→ dbt ─→ Redshift marts ─→ Metabase
Fear & Greed   ─┘
                         ↑ Airflow DAGs orchestrate all steps ↑
                         ↑ Terraform provisions all AWS infra  ↑
```

### Data flow

1. Python ingestion scripts write partitioned Parquet to `s3://crypto-pipeline-raw/`
2. Redshift COPY loads raw Parquet into the `raw` schema
3. dbt transforms: `raw` → `staging` (views) → `intermediate` (views/ephemeral) → `marts` (tables)
4. Airflow DAGs schedule and sequence all steps; MWAA in production, Docker Compose locally

### dbt layer responsibilities

- **staging**: rename to snake_case, cast types, filter nulls, deduplicate. No business logic. Uses `{{ source() }}` macros.
- **intermediate**: cross-source joins, rolling averages, VWAP, daily OHLCV aggregates from trade ticks.
- **marts**: Kimball star schema. `fact_trades` with FKs to `dim_coin`, `dim_date`, `dim_sentiment`. Materialized as tables.

### Airflow DAGs

- `ingest_daily` — 01:00 UTC daily: ingest CoinGecko + Fear & Greed → load to Redshift
- `ingest_binance` — every 15 min: check S3 files → load Binance trades to Redshift
- `run_dbt_models` — 03:00 UTC daily (after `ingest_daily`): staging → intermediate → marts → dbt test → alert on failure

All DAGs: `catchup=False`, `retries=2`, `retry_delay=timedelta(minutes=5)`, `on_failure_callback` set.

Airflow runs on EC2 t3.micro via Docker Compose — identical setup to local dev. Deployed via `terraform/ec2.tf` with a `user_data` bootstrap script.

### S3 partitioning scheme

```
s3://crypto-pipeline-raw/
  coingecko/dt=YYYY-MM-DD/markets.parquet
  binance/symbol=BTCUSDT/dt=YYYY-MM-DD/trades_HH.parquet
  fear_greed/dt=YYYY-MM-DD/index.parquet
```

### Redshift schemas

| Schema | Contents |
|---|---|
| `raw` | Direct COPY from S3, untransformed |
| `staging` | dbt staging views |
| `intermediate` | dbt intermediate views/ephemeral |
| `marts` | Final fact + dimension tables (materialized) |

## Key design decisions

- **Idempotency**: all ingestion scripts are safe to re-run for the same date — check before writing.
- **Binance WebSocket**: buffers in memory, flushes to Parquet every 5 minutes. Not true streaming — batched by design to avoid Kafka complexity in a portfolio context.
- **Redshift Serverless**: chosen over provisioned cluster to avoid idle costs.
- **No MWAA**: Airflow runs self-hosted on EC2 t3.micro via Docker Compose — same `docker-compose.yml` used locally and on the instance. Saves ~$430/month vs. MWAA.
- **No NAT Gateway**: VPC uses public subnets. Security groups restrict Redshift (5439) to EC2 only, and EC2 SSH/UI (22/8080) to developer IP only.
- **Secrets**: all credentials via environment variables only. `.env` copied from `.env.example`, never committed.

## Environment setup

Copy `.env.example` → `.env` and fill in AWS + Redshift credentials. Required vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `REDSHIFT_HOST`, `REDSHIFT_PORT`, `REDSHIFT_DB`, `REDSHIFT_USER`, `REDSHIFT_PASSWORD`, `RAW_BUCKET_NAME`, `COINS_LIMIT`, `BINANCE_PAIRS`.
