# Crypto Market Data Pipeline — Requirements

End-to-end data pipeline that ingests live cryptocurrency data from three sources,
transforms it into a Kimball-style analytical model, orchestrates workflows with
Airflow, and provisions all infrastructure with Terraform on AWS.

---

## Table of Contents

1. [Architecture Overview](#2-architecture-overview)
2. [Data Sources](#3-data-sources)
3. [Technology Stack](#4-technology-stack)
4. [Infrastructure Requirements](#5-infrastructure-requirements-terraform--aws)
5. [Ingestion Requirements](#6-ingestion-requirements)
6. [Data Modeling Requirements](#7-data-modeling-requirements-dbt)
7. [Orchestration Requirements](#8-orchestration-requirements-airflow)
8. [Dashboard Requirements](#9-dashboard-requirements)
9. [Data Quality Requirements](#10-data-quality-requirements)
10. [Non-Functional Requirements](#13-non-functional-requirements)
11. [Out of Scope](#14-out-of-scope)

---

## 1. Architecture Overview

```
[Data Sources]          [Storage]              [Transform]           [Serve]
CoinGecko API    →
Binance WS       →   S3 (raw) → Redshift   →   dbt models    →   Metabase
Fear & Greed API →

                        ↑ All orchestrated by Airflow ↑
                        ↑ All infrastructure via Terraform ↑
```

### Data flow
1. Python ingestion scripts pull data from three sources on a schedule.
2. Raw data lands in S3 as partitioned Parquet files (immutable raw zone).
3. Redshift COPY command loads raw data into the raw schema.
4. dbt transforms staging → intermediate → marts (Kimball star schema).
5. Airflow DAGs orchestrate and schedule all steps end-to-end.
6. Metabase reads from Redshift marts for visualization.
7. Terraform provisions and manages all AWS infrastructure.

---

## 2. Data Sources

### 2.1 CoinGecko API
- **URL:** `https://api.coingecko.com/api/v3/`
- **Auth:** None required for free tier
- **Endpoint:** `/coins/markets` — daily prices, market cap, volume per coin
- **Format:** JSON
- **Cadence:** Daily (respects free tier rate limit: 10–30 calls/min)
- **Coins tracked:** Top 20 by market cap (configurable via `config.yaml`)

### 2.2 Binance WebSocket API
- **URL:** `wss://stream.binance.us:9443/stream` (Binance.US for US users)
- **Auth:** None required for public streams
- **Streams:** `<symbol>@trade` — individual trade events (price, quantity, timestamp)
- **Format:** JSON over WebSocket
- **Pairs tracked:** BTC/USDT, ETH/USDT, SOL/USDT (configurable)
- **Cadence:** Continuous stream; batched and written to S3 every 5 minutes

### 2.3 Fear & Greed Index (Alternative.me)
- **URL:** `https://api.alternative.me/fng/`
- **Auth:** None required
- **Data:** Daily sentiment score (0–100) + classification label
- **Format:** JSON
- **Cadence:** Once daily (score updates at midnight UTC)

---

## 3. Technology Stack

| Layer | Tool | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Transformation | dbt-core + dbt-redshift | 1.9+ |
| Orchestration | Apache Airflow | 2.8+ |
| Infrastructure | Terraform | 1.6+ |
| Data warehouse | AWS Redshift Serverless | — |
| Data lake | AWS S3 | — |
| Visualization | Metabase (self-hosted) | — |
| Containerization | Docker + Docker Compose | — |
| CI/CD | GitHub Actions | — |

### Python libraries
| Library | Purpose |
|---|---|
| `requests` | CoinGecko REST calls |
| `websockets` | Binance WebSocket stream |
| `pandas` | Data manipulation |
| `pyarrow` | Writing Parquet files |
| `boto3` | S3 interaction |
| `psycopg2` | Redshift connection |
| `loguru` | Structured logging |

---

## 4. Infrastructure Requirements (Terraform + AWS)

### 4.1 S3 buckets
| Bucket | Purpose | Versioning | Lifecycle |
|---|---|---|---|
| `crypto-pipeline-raw` | Raw Parquet landing zone | Enabled | Glacier after 90 days |
| `crypto-pipeline-tf-state` | Terraform remote state | Enabled | Never expire |
| `crypto-pipeline-logs` | Pipeline logs | Disabled | Delete after 30 days |

**S3 folder structure:**
```
s3://crypto-pipeline-raw/
  coingecko/dt=YYYY-MM-DD/markets.parquet
  binance/symbol=BTCUSDT/dt=YYYY-MM-DD/trades_HH.parquet
  fear_greed/dt=YYYY-MM-DD/index.parquet
```

### 4.2 Redshift Serverless
- Schemas: `raw`, `staging`, `intermediate`, `marts`
- IAM role grants Redshift read access to S3

### 4.3 Airflow on EC2
- Instance: `t3.micro`
- Runs Docker Compose (same `docker-compose.yml` as local dev)
- IAM instance profile: S3 read/write + CloudWatch logs
- SSH and Airflow UI (8080) restricted to developer IP via security group

### 4.4 Networking
- VPC with public subnets (no NAT Gateway)
- Security groups: Redshift port 5439 accessible from EC2 only; EC2 ports 22/8080 from developer IP only

### 4.5 Terraform structure
```
terraform/
  main.tf       variables.tf    outputs.tf
  s3.tf         redshift.tf     iam.tf
  vpc.tf        ec2.tf
```

---

## 5. Ingestion Requirements

- All ingestion scripts are **idempotent** — re-running for the same date must not create duplicates.
- All raw files written to S3 must be **Parquet format**.
- All scripts log: source, rows written, S3 path, timestamp.
- Secrets loaded from environment variables only — never hardcoded.

### Per-source
| Source | Key behaviour |
|---|---|
| CoinGecko | `--date` argument for backfill; exponential backoff on 429 |
| Binance WS | Persistent connection; 5-min flush to S3; auto-reconnect on disconnect |
| Fear & Greed | Fetches 31 days on first run; idempotency check before write |

---

## 6. Data Modeling Requirements (dbt)

### Layers
| Layer | Materialization | Responsibility |
|---|---|---|
| staging | view | Rename columns, cast types, deduplicate. No business logic. |
| intermediate | view | Cross-source joins, rolling averages, VWAP, daily OHLCV |
| marts | table | Kimball star schema — fact + dimensions |

### Marts schema
```
fact_trades          dim_coin             dim_date             dim_sentiment
────────────         ────────────         ────────────         ────────────────
trade_id (SK)        coin_key (SK)        date_key (SK)        sentiment_key (SK)
date_key (FK)        coin_id              full_date            score_date
coin_key (FK)        symbol               year/month/day       score
sentiment_key (FK)   name                 is_weekend           classification
open/high/low/close  first_seen_date
volume_usd
market_cap_usd
vwap
```

### dbt tests required
- `not_null` on all keys and critical measures
- `unique` on all surrogate keys
- `accepted_values` on `classification`
- `relationships` between fact and all dimension tables

---

## 7. Orchestration Requirements (Airflow)

| DAG | Schedule | Tasks |
|---|---|---|
| `ingest_daily` | 01:00 UTC daily | ingest CoinGecko → load; ingest Fear & Greed → load (parallel) |
| `ingest_binance` | every 15 min | check S3 files exist → load to Redshift |
| `run_dbt_models` | 03:00 UTC daily | staging → intermediate → marts → dbt test |

All DAGs: `catchup=False`, `retries=2`, `retry_delay=5min`, `on_failure_callback` (Slack if webhook set).

---

## 8. Dashboard Requirements

Metabase (self-hosted, Docker) connected to Redshift `marts` schema.

| Chart | Type |
|---|---|
| Coin price over time | Line — BTC/ETH/SOL daily close |
| Fear & Greed over time | Bar — score + classification |
| Volume by coin | Stacked bar — USD volume per day |
| BTC price vs 7-day rolling average | Combo line |
| Market cap share (latest day) | Pie |

---

## 9. Data Quality Requirements

- Row count validation after each Redshift COPY — fail DAG task if 0 rows loaded
- dbt tests run after every mart build
- All dbt models have a description in `schema.yml`

---

## 10. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Idempotency | All ingestion and load scripts safe to re-run |
| Cost | ~$30–40/month: EC2 t3.micro + Redshift Serverless + S3 + CloudWatch |
| Code quality | Python formatted with `black`; SQL formatted with `sqlfluff` |
| Secrets hygiene | No secrets in code or Git history |
| Local dev | Full stack runnable via Docker Compose without AWS |

---

## 11. Out of Scope

- AWS MWAA (self-hosted Airflow on EC2 used instead)
- NAT Gateway (public subnets with security groups used instead)
- Real-time streaming with Kafka or Kinesis
- ML / predictive modeling
- Multi-environment setup (dev/staging/prod)
- dbt Cloud
