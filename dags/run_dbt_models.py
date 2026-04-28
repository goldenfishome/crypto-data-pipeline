"""
DAG: run_dbt_models
Schedule: 03:00 UTC daily (2 hours after ingest_daily completes)

Runs the full dbt transformation pipeline in layer order,
then runs all dbt tests. Alerts on any failure.

  dbt_run_staging
    ──▶ dbt_run_intermediate
          ──▶ dbt_run_marts
                ──▶ dbt_test
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from callbacks import on_failure_alert

# dbt project lives at /opt/airflow/dbt on the EC2 instance.
# profiles.yml must be at /opt/airflow/dbt/profiles.yml
# (copied from profiles.yml.example and filled in with Redshift credentials).
DBT_DIR      = "/opt/airflow/dbt"
DBT_PROFILES = "/opt/airflow/dbt"


def _dbt(command: str) -> str:
    """Build a dbt CLI command with consistent flags."""
    return f"cd {DBT_DIR} && dbt {command} --profiles-dir {DBT_PROFILES} --no-use-colors"


default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": on_failure_alert,
}

with DAG(
    dag_id="run_dbt_models",
    description="Run dbt staging → intermediate → marts, then test",
    schedule_interval="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["transformation"],
) as dag:

    run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=_dbt("run --select staging"),
    )

    run_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=_dbt("run --select intermediate"),
    )

    run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=_dbt("run --select marts"),
    )

    test_models = BashOperator(
        task_id="dbt_test",
        bash_command=_dbt("test"),
    )

    run_staging >> run_intermediate >> run_marts >> test_models
