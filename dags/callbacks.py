"""
Shared Airflow callbacks used by all DAGs.
"""
import os


def on_failure_alert(context) -> None:
    """
    Called automatically by Airflow when any task fails.
    Always logs to the task log. Sends a Slack message if SLACK_WEBHOOK_URL is set.
    """
    dag_id        = context["dag"].dag_id
    task_id       = context["task_instance"].task_id
    execution_date = context["execution_date"]
    log_url       = context["task_instance"].log_url
    exception     = context.get("exception", "unknown error")

    message = (
        f":red_circle: *Pipeline failure*\n"
        f"*DAG:*  {dag_id}\n"
        f"*Task:* {task_id}\n"
        f"*Date:* {execution_date}\n"
        f"*Error:* {exception}\n"
        f"*Logs:* {log_url}"
    )

    # Always visible in Airflow task logs
    print(message)

    # Optional Slack alert — set SLACK_WEBHOOK_URL in Airflow Variables or .env
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests
            requests.post(webhook_url, json={"text": message}, timeout=10)
        except Exception as e:
            print(f"Slack notification failed: {e}")
