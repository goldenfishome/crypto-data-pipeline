import argparse
import os
import time
from datetime import date, datetime, timezone

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

from utils.logger import get_logger
from utils.s3 import file_exists, write_parquet

load_dotenv()
logger = get_logger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def fetch_markets(coins_limit: int, vs_currency: str = "usd") -> list[dict]:
    """Fetch top-N coins by market cap with exponential backoff on rate limits."""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": coins_limit,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h",
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = BACKOFF_BASE**attempt
                logger.warning(f"Rate limited — retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = BACKOFF_BASE**attempt
            logger.warning(f"Request error: {e} — retrying in {wait}s")
            time.sleep(wait)

    raise RuntimeError("Max retries exceeded for CoinGecko /coins/markets")


def normalize(records: list[dict], run_date: date) -> pd.DataFrame:
    """Flatten CoinGecko API response into a clean, typed DataFrame."""
    rows = []
    for r in records:
        rows.append(
            {
                "coin_id": r["id"],
                "symbol": r["symbol"].upper(),
                "name": r["name"],
                "current_price_usd": r.get("current_price"),
                "market_cap_usd": r.get("market_cap"),
                "market_cap_rank": r.get("market_cap_rank"),
                "total_volume_usd": r.get("total_volume"),
                "high_24h_usd": r.get("high_24h"),
                "low_24h_usd": r.get("low_24h"),
                "price_change_24h": r.get("price_change_24h"),
                "price_change_pct_24h": r.get("price_change_percentage_24h"),
                "circulating_supply": r.get("circulating_supply"),
                "total_supply": r.get("total_supply"),
                "last_updated": r.get("last_updated"),
                "ingested_date": run_date.isoformat(),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def run(run_date: date, coins_limit: int, vs_currency: str) -> None:
    s3_key = f"coingecko/dt={run_date.isoformat()}/markets.parquet"

    if file_exists(s3_key):
        logger.info(f"Already exists, skipping: {s3_key}")
        return

    logger.info(f"Fetching top {coins_limit} coins ({vs_currency}) for {run_date}")
    records = fetch_markets(coins_limit, vs_currency)

    if not records:
        raise ValueError("CoinGecko returned 0 records — aborting to avoid empty write")

    df = normalize(records, run_date)
    dest = write_parquet(df, s3_key)
    logger.info(f"source=coingecko rows={len(df)} date={run_date} dest={dest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CoinGecko market data to S3")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()

    cfg = load_config()
    run(
        run_date=date.fromisoformat(args.date),
        coins_limit=int(os.getenv("COINS_LIMIT", cfg["coins"]["limit"])),
        vs_currency=cfg["coins"]["vs_currency"],
    )
