"""
DAG: ingest_binance
Schedule: every 15 minutes

Checks whether the Binance WebSocket ingester has written new Parquet files
to S3 for the current hour, then loads any new files into Redshift.

The WebSocket ingester (binance_ws.py) runs as a persistent background process
on EC2 — it writes files continuously. This DAG is responsible only for the
S3 → Redshift loading step.

  check_s3_files_exist ──▶  load_binance_to_redshift
                        (skips load if no new files found)
"""
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

sys.path.insert(0, "/opt/airflow/ingestion")

from callbacks import on_failure_alert  # noqa: E402

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": on_failure_alert,
}


def _check_s3_files_exist(**context) -> bool:
    """
    Returns True if Binance Parquet files exist in S3 for the current date/hour.
    ShortCircuitOperator skips all downstream tasks if this returns False.
    """
    import boto3
    from datetime import date, timezone

    bucket = os.environ["RAW_BUCKET_NAME"]
    pairs  = os.getenv("BINANCE_PAIRS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
    today  = date.today().isoformat()

    s3 = boto3.client("s3")

    for pair in pairs:
        prefix = f"binance/symbol={pair.strip().upper()}/dt={today}/"
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        if resp.get("KeyCount", 0) > 0:
            print(f"Found files under s3://{bucket}/{prefix} — proceeding with load")
            return True

    print(f"No Binance files found in S3 for {today} — skipping load")
    return False


def _load_binance(**context) -> None:
    from datetime import date
    import yaml
    from load_raw import load_binance

    with open("/opt/airflow/config.yaml") as f:
        cfg = yaml.safe_load(f)

    pairs_env = os.getenv("BINANCE_PAIRS")
    pairs = (
        [p.strip().upper() for p in pairs_env.split(",")]
        if pairs_env
        else [p.upper() for p in cfg["binance"]["pairs"]]
    )

    run_date = date.fromisoformat(context["ds"])

    for symbol in pairs:
        try:
            load_binance(run_date=run_date, symbol=symbol)
        except ValueError as e:
            # Log but don't fail — some symbols may not have traded that day
            print(f"Warning: {e}")


# ── DAG definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="ingest_binance",
    description="Check S3 for new Binance trade files and load into Redshift",
    schedule_interval="*/15 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["ingestion"],
) as dag:

    check_files = ShortCircuitOperator(
        task_id="check_s3_files_exist",
        python_callable=_check_s3_files_exist,
    )

    load_binance = PythonOperator(
        task_id="load_binance_to_redshift",
        python_callable=_load_binance,
    )

    check_files >> load_binance
