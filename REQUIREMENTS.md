# Crypto Market Data Pipeline — Project Requirements

> End-to-end data engineering portfolio project.  
> Ingests live cryptocurrency data, transforms it into a Kimball-style analytical model,
> orchestrates workflows with Airflow, and provisions all infrastructure with Terraform on AWS.

---

## Table of Contents

1. [Project Goals](#1-project-goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Sources](#3-data-sources)
4. [Technology Stack](#4-technology-stack)
5. [Infrastructure Requirements](#5-infrastructure-requirements-terraform--aws)
6. [Ingestion Requirements](#6-ingestion-requirements)
7. [Data Modeling Requirements](#7-data-modeling-requirements-dbt)
8. [Orchestration Requirements](#8-orchestration-requirements-airflow)
9. [Dashboard Requirements](#9-dashboard-requirements)
10. [Data Quality Requirements](#10-data-quality-requirements)
11. [Repository Structure](#11-repository-structure)
12. [Environment & Credentials](#12-environment--credentials)
13. [Non-Functional Requirements](#13-non-functional-requirements)
14. [Out of Scope](#14-out-of-scope)
15. [Milestones](#15-milestones)

---

## 1. Project Goals

### Primary goal
Build a production-grade, end-to-end data pipeline that demonstrates core data engineering skills in a realistic, Finance/Crypto domain context — suitable for a mid-level data engineering job search portfolio.

### Skills demonstrated
| Skill | Tool |
|---|---|
| Data modeling (Kimball) | dbt |
| Pipeline orchestration | Apache Airflow (AWS MWAA) |
| Infrastructure as code | Terraform |
| Cloud data warehouse | AWS Redshift |
| Data lake storage | AWS S3 |
| Ingestion (REST + WebSocket) | Python |
| Data quality testing | dbt tests |
| Visualization | Metabase or Grafana |

---

## 2. Architecture Overview

```
[Data Sources]          [Storage]              [Transform]           [Serve]
CoinGecko API    →                          
Binance WS       →   S3 (raw) → Redshift   →   dbt models    →   Dashboard
Fear & Greed API →                                                 (Metabase)

                        ↑ All orchestrated by Airflow ↑
                        ↑ All infrastructure via Terraform ↑
```

### Data flow (high level)
1. Python ingestion scripts pull data from three sources on a schedule.
2. Raw data lands in S3 as partitioned Parquet files (immutable raw zone).
3. Redshift COPY command loads raw data into a staging schema.
4. dbt transforms staging → intermediate → marts (Kimball star schema).
5. Airflow DAGs orchestrate and schedule all steps end-to-end.
6. Dashboard reads from Redshift marts for visualization.
7. Terraform provisions and manages all AWS infrastructure.

---

## 3. Data Sources

### 3.1 CoinGecko API
- **URL:** `https://api.coingecko.com/api/v3/`
- **Auth:** None required for free tier
- **Endpoints used:**
  - `/coins/markets` — OHLCV prices, market cap, volume per coin
  - `/coins/{id}/market_chart` — historical price series
- **Format:** JSON
- **Cadence:** Every 1 hour (respects free tier rate limit: 10–30 calls/min)
- **Coins tracked:** Top 20 by market cap (configurable via `config.yaml`)

### 3.2 Binance WebSocket API
- **URL:** `wss://stream.binance.com:9443/ws/`
- **Auth:** None required for public streams
- **Streams used:**
  - `<symbol>@trade` — individual trade events (price, quantity, timestamp)
  - `<symbol>@bookTicker` — best bid/ask prices
- **Format:** JSON over WebSocket
- **Pairs tracked:** BTC/USDT, ETH/USDT, SOL/USDT (configurable)
- **Cadence:** Continuous stream; batched and written to S3 every 5 minutes

### 3.3 Fear & Greed Index (Alternative.me)
- **URL:** `https://api.alternative.me/fng/`
- **Auth:** None required
- **Data:** Daily sentiment score (0–100) + classification label
- **Format:** JSON
- **Cadence:** Once daily (score updates at midnight UTC)

---

## 4. Technology Stack

### Core tools
| Layer | Tool | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Transformation | dbt-core + dbt-redshift | 1.7+ |
| Orchestration | Apache Airflow | 2.8+ |
| Infrastructure | Terraform | 1.6+ |
| Data warehouse | AWS Redshift (Serverless) | — |
| Data lake | AWS S3 | — |
| Managed Airflow | AWS MWAA | — |
| Dashboard | Metabase (self-hosted) or Grafana | — |
| Containerization | Docker + Docker Compose (local dev) | — |

### Python libraries
| Library | Purpose |
|---|---|
| `requests` | CoinGecko REST calls |
| `websockets` | Binance WebSocket stream |
| `pandas` | Data manipulation before writing |
| `pyarrow` | Writing Parquet files |
| `boto3` | S3 interaction |
| `psycopg2` | Redshift connection |
| `pydantic` | Config validation |
| `loguru` | Structured logging |

### Dev tools
| Tool | Purpose |
|---|---|
| `pre-commit` | Linting hooks (black, flake8, sqlfluff) |
| `pytest` | Unit tests for ingestion scripts |
| `dotenv` | Local secrets management |
| `make` | Task runner (Makefile) |

---

## 5. Infrastructure Requirements (Terraform + AWS)

### 5.1 S3 buckets
| Bucket | Purpose | Versioning | Lifecycle |
|---|---|---|---|
| `crypto-pipeline-raw` | Raw Parquet landing zone | Enabled | Move to Glacier after 90 days |
| `crypto-pipeline-tf-state` | Terraform remote state | Enabled | Never expire |
| `crypto-pipeline-logs` | Airflow & pipeline logs | Disabled | Delete after 30 days |

**Folder structure inside raw bucket:**
```
s3://crypto-pipeline-raw/
  coingecko/
    dt=YYYY-MM-DD/
      markets.parquet
  binance/
    symbol=BTCUSDT/
      dt=YYYY-MM-DD/
        trades_HH.parquet
  fear_greed/
    dt=YYYY-MM-DD/
      index.parquet
```

### 5.2 AWS Redshift
- Type: Redshift Serverless (cost-efficient for portfolio)
- Schemas:
  - `raw` — direct COPY from S3, no transformation
  - `staging` — dbt staging models
  - `intermediate` — dbt intermediate models
  - `marts` — final Kimball fact and dimension tables
- IAM role: Allow Redshift to read from S3

### 5.3 Airflow (self-hosted on EC2)
- Instance type: `t3.micro` (sufficient for portfolio-scale DAGs)
- Airflow runs inside Docker Compose on the EC2 instance (same `docker-compose.yml` used locally)
- Replaces AWS MWAA — saves ~$430/month
- IAM instance profile grants EC2 → S3 and Redshift access
- SSH access restricted to developer IP via security group

### 5.4 IAM
- Role for Redshift → S3 read access
- Instance profile for EC2 (Airflow) → S3, Redshift, CloudWatch access
- Principle of least privilege on all roles

### 5.5 Networking
- VPC with **public subnets** for Redshift and EC2 (no NAT Gateway — saves ~$32/month)
- Security groups:
  - Redshift port 5439: allow from EC2 security group only
  - EC2 SSH (22): allow from developer IP only
  - EC2 Airflow UI (8080): allow from developer IP only

### 5.6 Terraform structure
```
terraform/
  main.tf           # Provider config, backend
  variables.tf      # Input variables
  outputs.tf        # Output values (e.g. Redshift endpoint, EC2 public IP)
  s3.tf             # S3 bucket resources
  redshift.tf       # Redshift serverless namespace + workgroup
  iam.tf            # IAM roles, policies, EC2 instance profile
  vpc.tf            # VPC, public subnets, security groups
  ec2.tf            # Airflow EC2 instance + user_data bootstrap script
```

---

## 6. Ingestion Requirements

### 6.1 General rules
- All ingestion scripts are **idempotent** — re-running for the same date must not create duplicates.
- All raw files written to S3 must be **Parquet format** (not CSV).
- All scripts must log run metadata: source, rows written, S3 path, timestamp.
- API keys and secrets must never be hardcoded — loaded from environment variables only.

### 6.2 CoinGecko ingester (`ingestion/coingecko.py`)
- Accepts `--date` argument for backfilling historical data
- Fetches top N coins (configurable, default 20)
- Writes one Parquet file per run to `s3://crypto-pipeline-raw/coingecko/dt=YYYY-MM-DD/`
- Handles rate limiting with exponential backoff

### 6.3 Binance WebSocket ingester (`ingestion/binance_ws.py`)
- Maintains persistent WebSocket connection
- Buffers incoming trade events in memory
- Flushes to Parquet in S3 every 5 minutes
- Reconnects automatically on disconnect
- Tracks last written offset for recovery

### 6.4 Fear & Greed ingester (`ingestion/fear_greed.py`)
- Runs once daily
- Fetches current + last 30 days of history on first run
- Subsequent runs fetch only today's value
- Writes to `s3://crypto-pipeline-raw/fear_greed/dt=YYYY-MM-DD/`

---

## 7. Data Modeling Requirements (dbt)

### 7.1 Staging layer (`models/staging/`)
- One staging model per source table (e.g. `stg_coingecko__markets.sql`)
- Responsibilities: rename columns to snake_case, cast data types, filter nulls, deduplicate
- All staging models use `{{ source() }}` macro referencing `sources.yml`
- No business logic in staging

### 7.2 Intermediate layer (`models/intermediate/`)
- Joins across staging models where needed
- Applies business logic: rolling 7-day average price, volume-weighted average price (VWAP)
- Computes daily OHLCV aggregates from raw trade ticks

### 7.3 Marts layer (`models/marts/`) — Kimball star schema

**Fact table:**
```
fact_trades
  trade_id          (surrogate key)
  date_key          (FK → dim_date)
  coin_key          (FK → dim_coin)
  sentiment_key     (FK → dim_sentiment)
  open_price        FLOAT
  high_price        FLOAT
  low_price         FLOAT
  close_price       FLOAT
  volume_usd        FLOAT
  market_cap_usd    FLOAT
  trade_count       INT
  vwap              FLOAT
  loaded_at         TIMESTAMP
```

**Dimension tables:**
```
dim_coin
  coin_key          (surrogate key)
  coin_id           (natural key, e.g. "bitcoin")
  symbol            (e.g. "BTC")
  name
  category
  first_seen_date

dim_date
  date_key          (surrogate key)
  full_date
  year, quarter, month, week, day_of_week
  is_weekend        BOOLEAN

dim_sentiment
  sentiment_key     (surrogate key)
  score_date
  score             INT (0-100)
  classification    (Extreme Fear / Fear / Neutral / Greed / Extreme Greed)
```

### 7.4 dbt project requirements
- `dbt_project.yml` must define all model materializations explicitly
  - Staging: `view`
  - Intermediate: `ephemeral` or `view`
  - Marts: `table`
- `schema.yml` tests required on all mart models:
  - `not_null` on all keys and critical measures
  - `unique` on all surrogate keys
  - `accepted_values` on `dim_sentiment.classification`
  - `relationships` between fact and dimension tables
- At least one dbt macro for reusable logic (e.g. `generate_surrogate_key`)
- `exposures.yml` declaring the dashboard as a downstream consumer

---

## 8. Orchestration Requirements (Airflow)

### 8.1 DAG: `ingest_daily` (runs daily at 01:00 UTC)
```
start
  → ingest_coingecko
  → ingest_fear_greed
  → load_coingecko_to_redshift
  → load_fear_greed_to_redshift
end
```

### 8.2 DAG: `ingest_binance` (runs every 15 minutes)
```
start
  → check_s3_files_exist
  → load_binance_to_redshift
end
```

### 8.3 DAG: `run_dbt_models` (runs daily at 03:00 UTC, after ingest_daily)
```
start
  → dbt_run_staging
  → dbt_run_intermediate
  → dbt_run_marts
  → dbt_test
  → notify_on_failure (email/Slack alert)
end
```

### 8.4 DAG requirements
- All DAGs must have `catchup=False` unless backfill is explicitly intended
- All DAGs must define `on_failure_callback` with an alert
- All DAGs must set `retries=2`, `retry_delay=timedelta(minutes=5)`
- Connections stored in Airflow connections (not hardcoded)
- Variables stored in Airflow Variables or AWS Secrets Manager

---

## 9. Dashboard Requirements

### Tool
Metabase (self-hosted via Docker) connected to Redshift marts schema.

### Required charts
| Chart | Description |
|---|---|
| Price over time | Line chart — daily close price per coin, date range filter |
| Volume by coin | Bar chart — total USD volume per coin per week |
| Market cap trend | Area chart — top 5 coins by market cap over time |
| Sentiment vs price | Dual-axis line — Fear & Greed score vs BTC price |
| Daily OHLCV table | Sortable table with filters for coin and date range |

---

## 10. Data Quality Requirements

### dbt tests (minimum)
- `not_null` on all surrogate and foreign keys in marts
- `unique` on all surrogate keys
- `accepted_values` on classification columns
- `relationships` between fact and all dimension tables

### Pipeline-level checks
- Row count validation after each Redshift COPY (fail DAG if 0 rows loaded)
- Schema validation on raw Parquet files before loading (reject files with unexpected columns)
- Alert on data freshness: if `fact_trades` has no rows for today by 05:00 UTC, trigger alert

---

## 11. Repository Structure

```
crypto-pipeline/
├── terraform/                  # All AWS infrastructure as code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── s3.tf
│   ├── redshift.tf
│   ├── iam.tf
│   ├── vpc.tf
│   └── mwaa.tf
├── ingestion/                  # Python ingestion scripts
│   ├── coingecko.py
│   ├── binance_ws.py
│   ├── fear_greed.py
│   └── utils/
│       ├── s3.py               # S3 helper functions
│       └── logger.py           # Logging config
├── dags/                       # Airflow DAGs
│   ├── ingest_daily.py
│   ├── ingest_binance.py
│   └── run_dbt_models.py
├── dbt/                        # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── macros/
│   ├── tests/
│   └── exposures.yml
├── tests/                      # Python unit tests
│   └── test_ingestion.py
├── docker-compose.yml          # Local Airflow dev environment
├── Makefile                    # Task runner shortcuts
├── config.yaml                 # Coins list, schedule config
├── .env.example                # Environment variable template
├── .pre-commit-config.yaml     # Linting hooks
├── REQUIREMENTS.md             # This file
└── README.md                   # Architecture, setup guide, decisions
```

---

## 12. Environment & Credentials

All secrets loaded via environment variables. Never committed to Git.

### Required environment variables
```bash
# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Redshift
REDSHIFT_HOST=
REDSHIFT_PORT=5439
REDSHIFT_DB=crypto_pipeline
REDSHIFT_USER=
REDSHIFT_PASSWORD=

# S3
RAW_BUCKET_NAME=crypto-pipeline-raw

# Pipeline config
COINS_LIMIT=20                    # Number of top coins to track
BINANCE_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT
```

Copy `.env.example` to `.env` for local development. `.env` is in `.gitignore`.

---

## 13. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Idempotency | All ingestion and load scripts safe to re-run |
| Cost | Target ~$30–40/month: EC2 t3.micro (~$7.50) + Redshift Serverless paused when idle (~$0) + S3 (~$3) + CloudWatch (~$3); no MWAA, no NAT Gateway |
| Observability | All DAG steps log to CloudWatch; dbt artifacts stored in S3 |
| Code quality | All Python formatted with `black`; SQL formatted with `sqlfluff` |
| Documentation | Every dbt model has a description in `schema.yml` |
| Secrets hygiene | No secrets in code or Git history |
| Portability | Full local dev possible via Docker Compose (no AWS required to test logic) |

---

## 14. Out of Scope

The following are intentionally excluded to keep the project focused:

- AWS MWAA (replaced by self-hosted Airflow on EC2 t3.micro for cost reasons)
- NAT Gateway (replaced by public subnets with tight security groups)
- Real-time streaming with Kafka or Kinesis (Binance batched to S3 instead)
- ML / predictive modeling on the data
- CI/CD pipeline (GitHub Actions) — nice to add later
- Multi-environment setup (dev/staging/prod) — single environment only
- dbt Cloud (using dbt Core locally / in Airflow)
- Unit testing dbt models with `dbt-unit-testing`

---

## 15. Milestones

| # | Milestone | Deliverable |
|---|---|---|
| 1 | Infrastructure | Terraform applies cleanly; S3 buckets and Redshift cluster provisioned |
| 2 | Ingestion | All three sources writing Parquet to S3 successfully |
| 3 | Loading | Raw data loading into Redshift `raw` schema via COPY |
| 4 | dbt modeling | All staging, intermediate, and mart models passing `dbt test` |
| 5 | Orchestration | All three Airflow DAGs running end-to-end without errors |
| 6 | Dashboard | 5 charts live in Metabase reading from Redshift marts |
| 7 | Polish | README with architecture diagram, decisions, and setup guide complete |
