import os
from contextlib import contextmanager

import psycopg2

from utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def get_conn():
    """Context manager — commits on success, rolls back on exception, always closes."""
    conn = psycopg2.connect(
        host=os.environ["REDSHIFT_HOST"],
        port=int(os.environ.get("REDSHIFT_PORT", 5439)),
        dbname=os.environ["REDSHIFT_DB"],
        user=os.environ["REDSHIFT_USER"],
        password=os.environ["REDSHIFT_PASSWORD"],
        connect_timeout=30,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(conn, sql: str, params=None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params)


def fetchone(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
