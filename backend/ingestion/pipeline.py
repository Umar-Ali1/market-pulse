"""
Ingestion pipeline — Celery tasks.

Beat schedule (configured in settings.py):
    fetch_and_store_ticks  every 10 seconds

Flow:
    1. Fetch OHLCV snapshot from CoinGecko /coins/markets
    2. Parse + validate each asset row
    3. Bulk-insert into ClickHouse
    4. Invalidate stale Redis cache keys
    5. Broadcast update event to WebSocket group

Error strategy:
    - CoinGecko 429 / 5xx → Celery retry with exponential backoff (max 3 retries)
    - ClickHouse insert failure → log + alert, do NOT retry (avoid duplicate rows)
    - Redis failure → log warning, continue (cache miss is acceptable; DB is source of truth)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from backend.clickhouse.client import insert_ticks
from backend.cache.redis_client import invalidate_asset_cache

logger = get_task_logger(__name__)

ASSETS = ["bitcoin", "ethereum", "solana", "binancecoin"]
ASSET_SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
}

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_PARAMS = {
    "vs_currency": "usd",
    "ids": ",".join(ASSETS),
    "order": "market_cap_desc",
    "per_page": 10,
    "sparkline": False,
    "price_change_percentage": "1h,24h",
}


@shared_task(
    bind=True,
    autoretry_for=(httpx.HTTPStatusError, httpx.TimeoutException),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    name="ingestion.fetch_and_store_ticks",
)
def fetch_and_store_ticks(self) -> dict[str, Any]:
    """
    Fetch live market data, persist to ClickHouse, invalidate cache.
    Returns a summary dict for Flower monitoring visibility.
    """
    now = datetime.now(timezone.utc)

    # ── 1. Fetch ───────────────────────────────────────────────
    with httpx.Client(timeout=8.0) as client:
        response = client.get(COINGECKO_URL, params=COINGECKO_PARAMS)
        response.raise_for_status()
        raw = response.json()

    # ── 2. Parse ───────────────────────────────────────────────
    rows = []
    for item in raw:
        coin_id = item.get("id")
        symbol = ASSET_SYMBOLS.get(coin_id)
        if not symbol:
            continue

        # CoinGecko /markets doesn't return open; we use current price
        # as a proxy for the tick-level open within each 10s window.
        # This is a known approximation — documented in ARCHITECTURE.md.
        price = item.get("current_price") or 0.0
        rows.append({
            "asset":       symbol,
            "ts":          now,
            "open":        price,
            "high":        item.get("high_24h") or price,
            "low":         item.get("low_24h") or price,
            "close":       price,
            "volume_24h":  item.get("total_volume") or 0.0,
            "market_cap":  item.get("market_cap") or 0.0,
        })

    if not rows:
        logger.warning("fetch_and_store_ticks: no rows parsed from CoinGecko response")
        return {"inserted": 0, "ts": now.isoformat()}

    # ── 3. Insert ──────────────────────────────────────────────
    inserted = insert_ticks(rows)
    logger.info("Inserted %d tick rows at %s", inserted, now.isoformat())

    # ── 4. Invalidate cache ────────────────────────────────────
    symbols = [r["asset"] for r in rows]
    for symbol in symbols:
        try:
            invalidate_asset_cache(symbol)
        except Exception as exc:  # noqa: BLE001
            # Cache failure is non-fatal — DB is source of truth
            logger.warning("Cache invalidation failed for %s: %s", symbol, exc)

    # ── 5. WebSocket broadcast ─────────────────────────────────
    channel_layer = get_channel_layer()
    tick_payload = {
        "type": "market.tick",
        "data": [
            {
                "asset":  r["asset"],
                "ts":     r["ts"].isoformat(),
                "close":  r["close"],
                "volume": r["volume_24h"],
            }
            for r in rows
        ],
    }
    try:
        async_to_sync(channel_layer.group_send)("market_updates", tick_payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket broadcast failed: %s", exc)

    return {"inserted": inserted, "ts": now.isoformat(), "assets": symbols}
