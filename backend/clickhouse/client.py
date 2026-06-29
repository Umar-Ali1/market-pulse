"""
ClickHouse client wrapper.

Thin abstraction over clickhouse-driver that handles:
- Connection pooling (one client per thread via threading.local)
- Query logging with execution time
- Typed insert helpers for market_ticks

Why not use the HTTP interface?
The binary TCP protocol (clickhouse-driver) is ~3x faster for bulk inserts
and supports native types without JSON serialisation overhead.
For read-heavy REST endpoints the difference is negligible, but inserts
happen every 10 seconds across multiple Celery workers — it adds up.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any

from clickhouse_driver import Client
from django.conf import settings

logger = logging.getLogger(__name__)

_local = threading.local()


def get_client() -> Client:
    """Return a thread-local ClickHouse client, creating one if needed."""
    if not hasattr(_local, "client"):
        _local.client = Client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            database=settings.CLICKHOUSE_DB,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            settings={
                "use_numpy": False,
                "insert_block_size": 1_000_000,
            },
            compression=True,
        )
    return _local.client


@contextmanager
def timed_query(label: str):
    """Context manager that logs query label and wall-clock time."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("[ClickHouse] %s — %.1fms", label, elapsed_ms)


def insert_ticks(rows: list[dict[str, Any]]) -> int:
    """
    Bulk-insert tick rows into market_ticks.

    Args:
        rows: List of dicts with keys matching the table columns.

    Returns:
        Number of rows inserted.

    Raises:
        clickhouse_driver.errors.Error on insert failure.
    """
    if not rows:
        return 0

    columns = ["asset", "ts", "open", "high", "low", "close", "volume_24h", "market_cap"]
    data = [[r[c] for c in columns] for r in rows]

    with timed_query(f"insert_ticks({len(rows)} rows)"):
        get_client().execute(
            f"INSERT INTO market_ticks ({', '.join(columns)}) VALUES",
            data,
        )

    return len(rows)


def query_candles(
    asset: str,
    interval: str,
    from_ts: str,
    to_ts: str,
) -> list[dict[str, Any]]:
    """
    Fetch OHLCV candles for a given asset and time range.

    Args:
        asset:    e.g. "BTC"
        interval: "1m" | "5m" | "1h" | "1d"
        from_ts:  ISO-8601 string, UTC
        to_ts:    ISO-8601 string, UTC

    Returns:
        List of dicts: {ts, open, high, low, close, volume}
    """
    interval_map = {
        "1m":  "toStartOfMinute",
        "5m":  "toStartOfFiveMinutes",
        "1h":  "toStartOfHour",
        "1d":  "toStartOfDay",
    }
    bucket_fn = interval_map.get(interval, "toStartOfMinute")

    query = f"""
        SELECT
            {bucket_fn}(ts)     AS ts_bucket,
            argMin(open, ts)    AS open,
            max(high)           AS high,
            min(low)            AS low,
            argMax(close, ts)   AS close,
            sum(volume_24h)     AS volume
        FROM market_ticks
        WHERE asset = %(asset)s
          AND ts BETWEEN %(from_ts)s AND %(to_ts)s
        GROUP BY ts_bucket
        ORDER BY ts_bucket
    """

    with timed_query(f"query_candles({asset}, {interval})"):
        rows, columns = get_client().execute(
            query,
            {"asset": asset, "from_ts": from_ts, "to_ts": to_ts},
            with_column_types=True,
        )

    col_names = [c[0] for c in columns]
    return [dict(zip(col_names, row)) for row in rows]
