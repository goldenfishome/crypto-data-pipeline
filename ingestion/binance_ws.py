"""
Binance WebSocket trade ingester.

Connects to Binance combined stream, buffers trade events per symbol in memory,
and flushes to Parquet every FLUSH_INTERVAL seconds. Each flush merges into the
current hour's file (e.g. trades_14.parquet) and deduplicates by trade_id.

Reconnects automatically on disconnect. Performs a final flush on SIGINT/SIGTERM.
"""
import asyncio
import json
import os
import signal
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
import websockets
import yaml
from dotenv import load_dotenv

from utils.logger import get_logger
from utils.s3 import read_parquet_if_exists, write_parquet

load_dotenv()
logger = get_logger(__name__)

# binance.us for US users; swap to stream.binance.com:9443 if deploying outside the US
BINANCE_WS_BASE = os.getenv("BINANCE_WS_BASE", "wss://stream.binance.us:9443/stream")
RECONNECT_DELAY = 5   # seconds between reconnect attempts
MAX_RECONNECT_DELAY = 60


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def normalize_trade(msg: dict) -> dict:
    """Extract and rename fields from a Binance combined-stream trade event."""
    data = msg.get("data", msg)  # combined stream wraps payload under "data"
    return {
        "trade_id": data["t"],
        "symbol": data["s"],
        "price": float(data["p"]),
        "quantity": float(data["q"]),
        "quote_qty": float(data["p"]) * float(data["q"]),
        "trade_time_ms": data["T"],
        "trade_time_utc": datetime.fromtimestamp(
            data["T"] / 1000, tz=timezone.utc
        ).isoformat(),
        "is_buyer_maker": data["m"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def flush_symbol(trades: list[dict], symbol: str) -> str | None:
    """
    Write buffered trades for one symbol to its hourly Parquet file.
    Merges with any existing rows in that file and deduplicates by trade_id.
    Returns destination path, or None if buffer was empty.
    """
    if not trades:
        return None

    now = datetime.now(timezone.utc)
    s3_key = (
        f"binance/symbol={symbol}"
        f"/dt={now.date().isoformat()}"
        f"/trades_{now.hour:02d}.parquet"
    )

    new_df = pd.DataFrame(trades)

    existing = read_parquet_if_exists(s3_key)
    if existing is not None:
        df = pd.concat([existing, new_df], ignore_index=True)
        df = df.drop_duplicates(subset=["trade_id"], keep="last")
    else:
        df = new_df

    return write_parquet(df, s3_key)


async def stream_trades(
    pairs: list[str],
    buffer: dict,
    stop_event: asyncio.Event,
) -> None:
    """Open Binance combined WebSocket stream and buffer incoming trade events."""
    streams = "/".join(f"{p.lower()}@trade" for p in pairs)
    url = f"{BINANCE_WS_BASE}?streams={streams}"

    async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
        logger.info(f"Connected — streams: {streams}")
        async for raw_msg in ws:
            if stop_event.is_set():
                break
            try:
                msg = json.loads(raw_msg)
                trade = normalize_trade(msg)
                buffer[trade["symbol"]].append(trade)
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed message: {e}")


async def flush_loop(
    buffer: dict,
    stop_event: asyncio.Event,
    flush_interval: int,
) -> None:
    """Flush all symbol buffers to Parquet on a fixed interval."""
    while not stop_event.is_set():
        await asyncio.sleep(flush_interval)
        _flush_all(buffer)


def _flush_all(buffer: dict) -> None:
    """Flush every symbol's buffer. Separated from the async loop so tests can call it directly."""
    for symbol in list(buffer.keys()):
        trades = buffer[symbol].copy()
        buffer[symbol].clear()
        if not trades:
            continue
        dest = flush_symbol(trades, symbol)
        if dest:
            logger.info(
                f"source=binance symbol={symbol} rows={len(trades)} dest={dest}"
            )


async def run_forever(pairs: list[str], flush_interval: int) -> None:
    """Main loop — reconnects automatically on WebSocket disconnect."""
    buffer: dict = defaultdict(list)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    flush_task = asyncio.create_task(
        flush_loop(buffer, stop_event, flush_interval)
    )

    delay = RECONNECT_DELAY
    while not stop_event.is_set():
        try:
            await stream_trades(pairs, buffer, stop_event)
            delay = RECONNECT_DELAY  # reset backoff on clean connection
        except websockets.ConnectionClosed as e:
            if stop_event.is_set():
                break
            logger.warning(f"Connection closed: {e} — reconnecting in {delay}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)
        except OSError as e:
            if stop_event.is_set():
                break
            logger.warning(f"Network error: {e} — reconnecting in {delay}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    flush_task.cancel()

    # Final flush before exit so no buffered trades are lost
    logger.info("Shutting down — performing final flush")
    _flush_all(buffer)
    logger.info("Binance ingester stopped")


if __name__ == "__main__":
    cfg = load_config()

    pairs_env = os.getenv("BINANCE_PAIRS")
    pairs = (
        [p.strip().upper() for p in pairs_env.split(",")]
        if pairs_env
        else [p.upper() for p in cfg["binance"]["pairs"]]
    )

    flush_interval = int(
        os.getenv("FLUSH_INTERVAL_SECONDS", cfg["binance"]["flush_interval_seconds"])
    )

    logger.info(f"Starting Binance ingester | pairs={pairs} | flush_interval={flush_interval}s")
    asyncio.run(run_forever(pairs, flush_interval))
