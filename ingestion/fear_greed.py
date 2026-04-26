import argparse
from datetime import date, datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

from utils.logger import get_logger
from utils.s3 import file_exists, write_parquet

load_dotenv()
logger = get_logger(__name__)

FNG_URL = "https://api.alternative.me/fng/"
# Fetch 31 days so any --date within the past month can be resolved from one API call
HISTORY_LIMIT = 31


def fetch_fng(limit: int) -> list[dict]:
    resp = requests.get(FNG_URL, params={"limit": limit, "format": "json"}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("metadata", {}).get("error"):
        raise ValueError(f"FNG API error: {payload['metadata']['error']}")
    return payload["data"]


def normalize(record: dict, score_date: date) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "score_date": score_date.isoformat(),
                "score": int(record["value"]),
                "classification": record["value_classification"],
                "timestamp_utc": datetime.fromtimestamp(
                    int(record["timestamp"]), tz=timezone.utc
                ).isoformat(),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )


def run(run_date: date) -> None:
    s3_key = f"fear_greed/dt={run_date.isoformat()}/index.parquet"

    if file_exists(s3_key):
        logger.info(f"Already exists, skipping: {s3_key}")
        return

    logger.info(f"Fetching Fear & Greed index for {run_date}")
    records = fetch_fng(limit=HISTORY_LIMIT)

    # API returns records newest-first; find the one matching run_date
    target = None
    for rec in records:
        rec_date = datetime.fromtimestamp(int(rec["timestamp"]), tz=timezone.utc).date()
        if rec_date == run_date:
            target = rec
            break

    if target is None:
        raise ValueError(
            f"No Fear & Greed record found for {run_date} in last {HISTORY_LIMIT} days"
        )

    df = normalize(target, run_date)
    dest = write_parquet(df, s3_key)
    logger.info(
        f"source=fear_greed rows={len(df)} date={run_date} "
        f"score={df['score'].iloc[0]} classification={df['classification'].iloc[0]} "
        f"dest={dest}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Fear & Greed index to S3")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()
    run(run_date=date.fromisoformat(args.date))
