import os
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Make ingestion/ importable without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

from coingecko import fetch_markets, normalize, run  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_API_RESPONSE = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 65000.0,
        "market_cap": 1_280_000_000_000,
        "market_cap_rank": 1,
        "total_volume": 28_000_000_000,
        "high_24h": 66000.0,
        "low_24h": 64000.0,
        "price_change_24h": 500.0,
        "price_change_percentage_24h": 0.77,
        "circulating_supply": 19_700_000.0,
        "total_supply": 21_000_000.0,
        "last_updated": "2024-01-15T12:00:00.000Z",
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3400.0,
        "market_cap": 408_000_000_000,
        "market_cap_rank": 2,
        "total_volume": 15_000_000_000,
        "high_24h": 3450.0,
        "low_24h": 3350.0,
        "price_change_24h": -20.0,
        "price_change_percentage_24h": -0.58,
        "circulating_supply": 120_000_000.0,
        "total_supply": None,
        "last_updated": "2024-01-15T12:00:00.000Z",
    },
]

RUN_DATE = date(2024, 1, 15)


# ── normalize() ───────────────────────────────────────────────────────────────

def test_normalize_row_count():
    df = normalize(SAMPLE_API_RESPONSE, RUN_DATE)
    assert len(df) == 2


def test_normalize_symbol_uppercased():
    df = normalize(SAMPLE_API_RESPONSE, RUN_DATE)
    assert df.loc[df["coin_id"] == "bitcoin", "symbol"].iloc[0] == "BTC"
    assert df.loc[df["coin_id"] == "ethereum", "symbol"].iloc[0] == "ETH"


def test_normalize_ingested_date():
    df = normalize(SAMPLE_API_RESPONSE, RUN_DATE)
    assert (df["ingested_date"] == "2024-01-15").all()


def test_normalize_null_total_supply_preserved():
    df = normalize(SAMPLE_API_RESPONSE, RUN_DATE)
    eth_row = df[df["coin_id"] == "ethereum"].iloc[0]
    assert pd.isna(eth_row["total_supply"])


def test_normalize_expected_columns():
    df = normalize(SAMPLE_API_RESPONSE, RUN_DATE)
    expected = {
        "coin_id", "symbol", "name", "current_price_usd", "market_cap_usd",
        "market_cap_rank", "total_volume_usd", "high_24h_usd", "low_24h_usd",
        "price_change_24h", "price_change_pct_24h", "circulating_supply",
        "total_supply", "last_updated", "ingested_date", "ingested_at",
    }
    assert expected.issubset(set(df.columns))


# ── fetch_markets() ───────────────────────────────────────────────────────────

def test_fetch_markets_returns_records():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_API_RESPONSE

    with patch("coingecko.requests.get", return_value=mock_resp):
        result = fetch_markets(coins_limit=2)

    assert result == SAMPLE_API_RESPONSE


def test_fetch_markets_retries_on_429():
    rate_limited = MagicMock(status_code=429)
    ok_resp = MagicMock(status_code=200)
    ok_resp.json.return_value = SAMPLE_API_RESPONSE

    with patch("coingecko.requests.get", side_effect=[rate_limited, ok_resp]):
        with patch("coingecko.time.sleep"):  # don't actually sleep in tests
            result = fetch_markets(coins_limit=2)

    assert result == SAMPLE_API_RESPONSE


# ── run() (integration-style, local filesystem) ───────────────────────────────

def test_run_writes_parquet_locally(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    # Reload s3 module so it picks up the new env var
    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import coingecko as cg_module
    importlib.reload(cg_module)

    with patch("coingecko.fetch_markets", return_value=SAMPLE_API_RESPONSE):
        cg_module.run(run_date=RUN_DATE, coins_limit=2, vs_currency="usd")

    expected = tmp_path / "coingecko" / "dt=2024-01-15" / "markets.parquet"
    assert expected.exists()
    df = pd.read_parquet(expected)
    assert len(df) == 2


def test_run_is_idempotent(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import coingecko as cg_module
    importlib.reload(cg_module)

    with patch("coingecko.fetch_markets", return_value=SAMPLE_API_RESPONSE) as mock_fetch:
        cg_module.run(run_date=RUN_DATE, coins_limit=2, vs_currency="usd")
        cg_module.run(run_date=RUN_DATE, coins_limit=2, vs_currency="usd")

    # fetch_markets should only be called once — second run skips due to idempotency check
    assert mock_fetch.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# Fear & Greed
# ═════════════════════════════════════════════════════════════════════════════

from fear_greed import fetch_fng, normalize as fng_normalize, run as fng_run  # noqa: E402

FNG_RUN_DATE = date(2024, 1, 15)

SAMPLE_FNG_RESPONSE = [
    # newest first (API order)
    {"value": "52", "value_classification": "Neutral", "timestamp": "1705622400"},   # 2024-01-19
    {"value": "48", "value_classification": "Neutral", "timestamp": "1705536000"},   # 2024-01-18
    {"value": "35", "value_classification": "Fear",    "timestamp": "1705449600"},   # 2024-01-17
    {"value": "25", "value_classification": "Extreme Fear", "timestamp": "1705276800"},  # 2024-01-15
]


# ── normalize() ───────────────────────────────────────────────────────────────

def test_fng_normalize_shape():
    df = fng_normalize(SAMPLE_FNG_RESPONSE[3], FNG_RUN_DATE)
    assert df.shape == (1, 5)


def test_fng_normalize_score_is_int():
    df = fng_normalize(SAMPLE_FNG_RESPONSE[3], FNG_RUN_DATE)
    assert df["score"].dtype == "int64"
    assert df["score"].iloc[0] == 25


def test_fng_normalize_classification():
    df = fng_normalize(SAMPLE_FNG_RESPONSE[3], FNG_RUN_DATE)
    assert df["classification"].iloc[0] == "Extreme Fear"


def test_fng_normalize_score_date():
    df = fng_normalize(SAMPLE_FNG_RESPONSE[3], FNG_RUN_DATE)
    assert df["score_date"].iloc[0] == "2024-01-15"


# ── fetch_fng() ───────────────────────────────────────────────────────────────

def test_fetch_fng_returns_records():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": SAMPLE_FNG_RESPONSE, "metadata": {"error": None}}

    with patch("fear_greed.requests.get", return_value=mock_resp):
        result = fetch_fng(limit=4)

    assert result == SAMPLE_FNG_RESPONSE


# ── run() ─────────────────────────────────────────────────────────────────────

def test_fng_run_writes_parquet_locally(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import fear_greed as fg_module
    importlib.reload(fg_module)

    with patch("fear_greed.fetch_fng", return_value=SAMPLE_FNG_RESPONSE):
        fg_module.run(run_date=FNG_RUN_DATE)

    expected = tmp_path / "fear_greed" / "dt=2024-01-15" / "index.parquet"
    assert expected.exists()
    df = pd.read_parquet(expected)
    assert len(df) == 1
    assert df["score"].iloc[0] == 25


def test_fng_run_raises_if_date_not_in_response(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import fear_greed as fg_module
    importlib.reload(fg_module)

    with patch("fear_greed.fetch_fng", return_value=SAMPLE_FNG_RESPONSE):
        with pytest.raises(ValueError, match="No Fear & Greed record found"):
            fg_module.run(run_date=date(2023, 1, 1))


def test_fng_run_is_idempotent(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import fear_greed as fg_module
    importlib.reload(fg_module)

    with patch("fear_greed.fetch_fng", return_value=SAMPLE_FNG_RESPONSE) as mock_fetch:
        fg_module.run(run_date=FNG_RUN_DATE)
        fg_module.run(run_date=FNG_RUN_DATE)

    assert mock_fetch.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# Binance WebSocket
# ═════════════════════════════════════════════════════════════════════════════

from binance_ws import _flush_all, flush_symbol, normalize_trade  # noqa: E402
from datetime import datetime  # noqa: E402 (already imported above, harmless re-import)

# A realistic Binance combined-stream trade message
SAMPLE_WS_MSG = {
    "stream": "btcusdt@trade",
    "data": {
        "e": "trade",
        "E": 1705276900000,
        "s": "BTCUSDT",
        "t": 3001,
        "p": "42000.50",
        "q": "0.01500",
        "T": 1705276899000,
        "m": False,
        "M": True,
    },
}


# ── normalize_trade() ─────────────────────────────────────────────────────────

def test_binance_normalize_fields():
    trade = normalize_trade(SAMPLE_WS_MSG)
    assert trade["trade_id"] == 3001
    assert trade["symbol"] == "BTCUSDT"
    assert trade["price"] == 42000.50
    assert trade["quantity"] == 0.015
    assert trade["is_buyer_maker"] is False


def test_binance_normalize_quote_qty():
    trade = normalize_trade(SAMPLE_WS_MSG)
    assert abs(trade["quote_qty"] - (42000.50 * 0.015)) < 0.0001


def test_binance_normalize_trade_time_utc_is_iso():
    trade = normalize_trade(SAMPLE_WS_MSG)
    datetime.fromisoformat(trade["trade_time_utc"])


def test_binance_normalize_unwraps_data_key():
    trade = normalize_trade(SAMPLE_WS_MSG)
    assert trade["symbol"] == "BTCUSDT"


# ── flush_symbol() ────────────────────────────────────────────────────────────

def _make_trades(symbol: str, trade_ids: list[int]) -> list[dict]:
    base = normalize_trade(SAMPLE_WS_MSG)
    trades = []
    for tid in trade_ids:
        t = base.copy()
        t["trade_id"] = tid
        t["symbol"] = symbol
        trades.append(t)
    return trades


def test_flush_symbol_writes_parquet(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import binance_ws as bws
    importlib.reload(bws)

    trades = _make_trades("BTCUSDT", [1, 2, 3])
    dest = bws.flush_symbol(trades, "BTCUSDT")

    assert dest is not None
    df = pd.read_parquet(dest)
    assert len(df) == 3


def test_flush_symbol_deduplicates_on_merge(tmp_path):
    """Second flush with overlapping trade_ids must not create duplicate rows."""
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import binance_ws as bws
    importlib.reload(bws)

    bws.flush_symbol(_make_trades("BTCUSDT", [1, 2, 3]), "BTCUSDT")
    bws.flush_symbol(_make_trades("BTCUSDT", [3, 4, 5]), "BTCUSDT")  # trade 3 overlaps

    files = list(tmp_path.rglob("*.parquet"))
    assert len(files) == 1
    df = pd.read_parquet(files[0])
    assert len(df) == 5
    assert df["trade_id"].nunique() == 5


def test_flush_symbol_returns_none_for_empty_buffer(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import binance_ws as bws
    importlib.reload(bws)

    assert bws.flush_symbol([], "BTCUSDT") is None


# ── _flush_all() ──────────────────────────────────────────────────────────────

def test_flush_all_clears_buffer_and_writes_per_symbol(tmp_path):
    os.environ["LOCAL_RAW_PATH"] = str(tmp_path)
    os.environ.pop("RAW_BUCKET_NAME", None)

    import importlib
    from collections import defaultdict
    import utils.s3 as s3_module
    importlib.reload(s3_module)
    import binance_ws as bws
    importlib.reload(bws)

    buffer = defaultdict(list)
    buffer["BTCUSDT"].extend(_make_trades("BTCUSDT", [10, 11]))
    buffer["ETHUSDT"].extend(_make_trades("ETHUSDT", [20, 21]))

    bws._flush_all(buffer)

    assert buffer["BTCUSDT"] == []
    assert buffer["ETHUSDT"] == []
    files = list(tmp_path.rglob("*.parquet"))
    assert len(files) == 2


# ═════════════════════════════════════════════════════════════════════════════
# load_raw — Redshift loader (unit tests with mocked DB connection)
# ═════════════════════════════════════════════════════════════════════════════

from unittest.mock import call, MagicMock  # noqa: E402 (already imported above)
import load_raw  # noqa: E402


@pytest.fixture
def mock_conn():
    """A mock psycopg2 connection with a cursor that returns controllable results."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture(autouse=False)
def loader_env(monkeypatch):
    monkeypatch.setenv("RAW_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("REDSHIFT_IAM_ROLE", "arn:aws:iam::123:role/test-role")


# ── load_coingecko ────────────────────────────────────────────────────────────

def test_load_coingecko_runs_copy(mock_conn, loader_env):
    conn, cursor = mock_conn
    # fetchone returns 0 first (not loaded yet), then row count after COPY
    cursor.fetchone.side_effect = [
        (0,),   # _row_count: 0 rows exist → proceed
        (20,),  # pg_last_copy_count → 20 rows loaded
    ]

    with patch("load_raw.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        load_raw.load_coingecko(date(2024, 1, 15))

    # Verify a COPY statement was executed
    executed_sqls = [str(c.args[0]) for c in cursor.execute.call_args_list]
    assert any("COPY" in sql and "coingecko_markets" in sql for sql in executed_sqls)


def test_load_coingecko_skips_if_already_loaded(mock_conn, loader_env):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = (20,)  # rows already exist

    with patch("load_raw.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        load_raw.load_coingecko(date(2024, 1, 15))

    executed_sqls = [str(c.args[0]) for c in cursor.execute.call_args_list]
    assert not any("COPY" in sql for sql in executed_sqls)


def test_load_coingecko_raises_on_zero_rows(mock_conn, loader_env):
    conn, cursor = mock_conn
    cursor.fetchone.side_effect = [
        (0,),  # not loaded yet
        (0,),  # COPY loaded 0 rows → should raise
    ]

    with patch("load_raw.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        with pytest.raises(ValueError, match="COPY loaded 0 rows"):
            load_raw.load_coingecko(date(2024, 1, 15))


# ── load_fear_greed ───────────────────────────────────────────────────────────

def test_load_fear_greed_runs_copy(mock_conn, loader_env):
    conn, cursor = mock_conn
    cursor.fetchone.side_effect = [(0,), (1,)]

    with patch("load_raw.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        load_raw.load_fear_greed(date(2024, 1, 15))

    executed_sqls = [str(c.args[0]) for c in cursor.execute.call_args_list]
    assert any("COPY" in sql and "fear_greed_index" in sql for sql in executed_sqls)


# ── load_binance ──────────────────────────────────────────────────────────────

def test_load_binance_uses_correct_s3_prefix(mock_conn, loader_env):
    conn, cursor = mock_conn
    cursor.fetchone.side_effect = [(0,), (150,)]

    with patch("load_raw.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        load_raw.load_binance(date(2024, 1, 15), "BTCUSDT")

    executed_sqls = [str(c.args[0]) for c in cursor.execute.call_args_list]
    copy_sql = next(sql for sql in executed_sqls if "COPY" in sql)
    assert "symbol=BTCUSDT" in copy_sql
    assert "dt=2024-01-15" in copy_sql
