"""
Loads raw Parquet files from S3 into Redshift raw schema via COPY command.

Run after ingestion scripts have written files to S3:
    python load_raw.py --source coingecko  --date 2024-01-15
    python load_raw.py --source fear_greed --date 2024-01-15
    python load_raw.py --source binance    --date 2024-01-15 --symbol BTCUSDT
"""
import argparse
import os
from datetime import date

from dotenv import load_dotenv

from utils.logger import get_logger
from utils.redshift import execute, fetchone, get_conn

load_dotenv()
logger = get_logger(__name__)


def _cfg() -> tuple[str, str]:
    """Read config at call time so tests can set env vars before importing."""
    return os.environ["RAW_BUCKET_NAME"], os.environ["REDSHIFT_IAM_ROLE"]


# ── DDL: create raw schema and tables once ────────────────────────────────────
# Columns mirror the Parquet files written by the ingestion scripts exactly.

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS raw",

    """CREATE TABLE IF NOT EXISTS raw.coingecko_markets (
        coin_id              VARCHAR(100),
        symbol               VARCHAR(20),
        name                 VARCHAR(200),
        current_price_usd    FLOAT8,
        market_cap_usd       BIGINT,
        market_cap_rank      INT,
        total_volume_usd     BIGINT,
        high_24h_usd         FLOAT8,
        low_24h_usd          FLOAT8,
        price_change_24h     FLOAT8,
        price_change_pct_24h FLOAT8,
        circulating_supply   FLOAT8,
        total_supply         FLOAT8,
        last_updated         VARCHAR(50),
        ingested_date        VARCHAR(10),
        ingested_at          VARCHAR(50)
    )""",

    """CREATE TABLE IF NOT EXISTS raw.fear_greed_index (
        score_date     VARCHAR(10),
        score          INT,
        classification VARCHAR(50),
        timestamp_utc  VARCHAR(50),
        ingested_at    VARCHAR(50)
    )""",

    """CREATE TABLE IF NOT EXISTS raw.binance_trades (
        trade_id       BIGINT,
        symbol         VARCHAR(20),
        price          FLOAT8,
        quantity       FLOAT8,
        quote_qty      FLOAT8,
        trade_time_ms  BIGINT,
        trade_time_utc VARCHAR(50),
        is_buyer_maker BOOLEAN,
        ingested_at    VARCHAR(50)
    )""",
]


def setup_raw_schema(conn) -> None:
    for ddl in _DDL:
        execute(conn, ddl)
    logger.info("Raw schema ready")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _row_count(conn, table: str, where_col: str, where_val: str) -> int:
    row = fetchone(
        conn,
        f"SELECT COUNT(1) FROM {table} WHERE {where_col} = %s",
        (where_val,),
    )
    return row[0] if row else 0


def _copy(conn, table: str, s3_prefix: str) -> int:
    """Run COPY from an S3 prefix (Parquet). Returns the number of rows loaded."""
    _, iam_role = _cfg()
    execute(
        conn,
        f"""
        COPY {table}
        FROM '{s3_prefix}'
        IAM_ROLE '{iam_role}'
        FORMAT AS PARQUET
        COMPUPDATE OFF
        STATUPDATE OFF
        """,
    )
    row = fetchone(conn, "SELECT pg_last_copy_count()")
    return row[0] if row else 0


# ── Per-source loaders ────────────────────────────────────────────────────────

def load_coingecko(run_date: date) -> None:
    raw_bucket, _ = _cfg()
    date_str = run_date.isoformat()
    s3_prefix = f"s3://{raw_bucket}/coingecko/dt={date_str}/"

    with get_conn() as conn:
        setup_raw_schema(conn)

        if _row_count(conn, "raw.coingecko_markets", "ingested_date", date_str) > 0:
            logger.info(f"coingecko already loaded for {date_str} — skipping")
            return

        rows = _copy(conn, "raw.coingecko_markets", s3_prefix)
        if rows == 0:
            raise ValueError(f"COPY loaded 0 rows from {s3_prefix} — aborting")

        logger.info(f"source=coingecko date={date_str} rows_loaded={rows}")


def load_fear_greed(run_date: date) -> None:
    raw_bucket, _ = _cfg()
    date_str = run_date.isoformat()
    s3_prefix = f"s3://{raw_bucket}/fear_greed/dt={date_str}/"

    with get_conn() as conn:
        setup_raw_schema(conn)

        if _row_count(conn, "raw.fear_greed_index", "score_date", date_str) > 0:
            logger.info(f"fear_greed already loaded for {date_str} — skipping")
            return

        rows = _copy(conn, "raw.fear_greed_index", s3_prefix)
        if rows == 0:
            raise ValueError(f"COPY loaded 0 rows from {s3_prefix} — aborting")

        logger.info(f"source=fear_greed date={date_str} rows_loaded={rows}")


def load_binance(run_date: date, symbol: str) -> None:
    raw_bucket, _ = _cfg()
    date_str = run_date.isoformat()
    symbol = symbol.upper()
    s3_prefix = f"s3://{raw_bucket}/binance/symbol={symbol}/dt={date_str}/"

    with get_conn() as conn:
        setup_raw_schema(conn)

        # trade_time_utc is ISO format: "2024-01-15T14:30:00+00:00" — check first 10 chars
        row = fetchone(
            conn,
            "SELECT COUNT(1) FROM raw.binance_trades"
            " WHERE symbol = %s AND LEFT(trade_time_utc, 10) = %s",
            (symbol, date_str),
        )
        if row and row[0] > 0:
            logger.info(f"binance {symbol} already loaded for {date_str} — skipping")
            return

        rows = _copy(conn, "raw.binance_trades", s3_prefix)
        if rows == 0:
            raise ValueError(f"COPY loaded 0 rows from {s3_prefix} — aborting")

        logger.info(f"source=binance symbol={symbol} date={date_str} rows_loaded={rows}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COPY raw Parquet from S3 into Redshift raw schema"
    )
    parser.add_argument("--source", required=True, choices=["coingecko", "fear_greed", "binance"])
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument(
        "--symbol", default="BTCUSDT", help="Binance pair (only used with --source binance)"
    )
    args = parser.parse_args()

    run_date = date.fromisoformat(args.date)

    if args.source == "coingecko":
        load_coingecko(run_date)
    elif args.source == "fear_greed":
        load_fear_greed(run_date)
    elif args.source == "binance":
        load_binance(run_date, args.symbol)
