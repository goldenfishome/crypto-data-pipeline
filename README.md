# Crypto Data Pipeline

End-to-end data engineering portfolio project. Ingests live cryptocurrency data from three sources, transforms it into a Kimball-style analytical model, orchestrates workflows with Airflow, and provisions all infrastructure with Terraform on AWS.

## Architecture

```
CoinGecko API  ─┐
Binance WS     ─┼──▶ S3 (Parquet) ──▶ Redshift raw ──▶ dbt ──▶ Redshift marts ──▶ Metabase
Fear & Greed   ─┘

         ↑ Airflow DAGs orchestrate all steps
         ↑ Terraform provisions all AWS infrastructure
```

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | Python (requests, websockets, pyarrow) |
| Storage | AWS S3 (Parquet, Hive-partitioned) |
| Data warehouse | AWS Redshift Serverless |
| Transformation | dbt Core (Kimball star schema) |
| Orchestration | Apache Airflow (self-hosted on EC2) |
| Infrastructure | Terraform |
| Visualization | Metabase |
| Testing | pytest, dbt tests |
| CI/CD | GitHub Actions |

## Project Structure

```
├── ingestion/       # Python ingestion scripts + Redshift loader
├── dags/            # Airflow DAGs
├── dbt/             # dbt project (staging → intermediate → marts)
├── terraform/       # AWS infrastructure as code
├── tests/           # Python unit tests
├── docker-compose.yml
└── Makefile
```

## Setup

See [REQUIREMENTS.md](REQUIREMENTS.md) for full specification and [DEVELOPMENT.md](DEVELOPMENT.md) for local dev commands.
