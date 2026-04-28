"""
DAG: ingest_daily
Schedule: 01:00 UTC daily

Ingests CoinGecko and Fear & Greed data for the execution date,
then loads both into the Redshift raw schema.

CoinGecko and Fear & Greed run in parallel, each followed by
their own Redshift load step.

  ingest_coingecko  ──▶  load_coingecko_to_redshift
  ingest_fear_greed ──▶  load_fear_greed_to_redshift
"""
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow/ingestion")

from callbacks import on_failure_alert  # noqa: E402

# ── Default args applied to every task in this DAG ───────────────────────────

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": on_failure_alert,
}

# ── Task callables ────────────────────────────────────────────────────────────
# Imports are inside functions so Airflow's DAG parser doesn't execute them
# on every 30-second parse cycle.


def _ingest_coingecko(**context) -> None:
    from datetime import date
    import os
    import yaml
    from coingecko import run

    with open("/opt/airflow/config.yaml") as f:
        cfg = yaml.safe_load(f)

    run(
        run_date=date.fromisoformat(context["ds"]),
        coins_limit=int(os.getenv("COINS_LIMIT", cfg["coins"]["limit"])),
        vs_currency=cfg["coins"]["vs_currency"],
    )


def _ingest_fear_greed(**context) -> None:
    from datetime import date
    from fear_greed import run

    run(run_date=date.fromisoformat(context["ds"]))


def _load_coingecko(**context) -> None:
    from datetime import date
    from load_raw import load_coingecko

    load_coingecko(run_date=date.fromisoformat(context["ds"]))


def _load_fear_greed(**context) -> None:
    from datetime import date
    from load_raw import load_fear_greed

    load_fear_greed(run_date=date.fromisoformat(context["ds"]))


# ── DAG definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="ingest_daily",
    description="Ingest CoinGecko + Fear & Greed and load into Redshift raw schema",
    schedule_interval="0 1 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["ingestion"],
) as dag:

    ingest_coingecko = PythonOperator(
        task_id="ingest_coingecko",
        python_callable=_ingest_coingecko,
    )

    ingest_fear_greed = PythonOperator(
        task_id="ingest_fear_greed",
        python_callable=_ingest_fear_greed,
    )

    load_coingecko = PythonOperator(
        task_id="load_coingecko_to_redshift",
        python_callable=_load_coingecko,
    )

    load_fear_greed = PythonOperator(
        task_id="load_fear_greed_to_redshift",
        python_callable=_load_fear_greed,
    )

    # Both source pairs run in parallel
    ingest_coingecko  >> load_coingecko
    ingest_fear_greed >> load_fear_greed
