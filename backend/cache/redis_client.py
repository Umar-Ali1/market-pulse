"""
Redis cache abstraction — two-tier strategy.

L1 (db=0): Pre-aggregated candles by interval.
    Key:  market:candles:{asset}:{interval}:{from_date}:{to_date}
    TTL:  10s (matches ingestion frequency)
    Hit rate target: >90% of candle API requests

L2 (db=1): Raw tick ranges.
    Key:  market:ticks:{asset}:{from_ts}:{to_ts}
    TTL:  60s
    Hit rate target: >70% on repeated range queries

On cache miss: L1 miss → check L2 → miss → query ClickHouse → populate both.
On ingestion: invalidate all L1 keys for the affected asset.
              L2 keys are left to expire naturally (stale-while-revalidate).

Why two Redis databases instead of key namespacing?
    Separate DBs allow FLUSHDB per tier without cross-contaminating.
    Useful during debugging and for independent monitoring via redis-cli INFO.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_l1: redis.Redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True,
)

_l2: redis.Redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=1,
    decode_responses=True,
)

L1_TTL = 10   # seconds
L2_TTL = 60   # seconds


def _candle_key(asset: str, interval: str, from_date: str, to_date: str) -> str:
    return f"market:candles:{asset}:{interval}:{from_date}:{to_date}"


def _tick_key(asset: str, from_ts: str, to_ts: str) -> str:
    return f"market:ticks:{asset}:{from_ts}:{to_ts}"


def get_candles(
    asset: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> list[dict] | None:
    """Return cached candles or None on miss."""
    key = _candle_key(asset, interval, from_date, to_date)
    raw = _l1.get(key)
    if raw:
        logger.debug("[Cache L1 HIT] %s", key)
        return json.loads(raw)
    logger.debug("[Cache L1 MISS] %s", key)
    return None


def set_candles(
    asset: str,
    interval: str,
    from_date: str,
    to_date: str,
    data: list[dict],
) -> None:
    """Populate L1 candle cache."""
    key = _candle_key(asset, interval, from_date, to_date)
    _l1.setex(key, L1_TTL, json.dumps(data, default=str))


def get_ticks(asset: str, from_ts: str, to_ts: str) -> list[dict] | None:
    """Return cached raw ticks or None on miss."""
    key = _tick_key(asset, from_ts, to_ts)
    raw = _l2.get(key)
    if raw:
        logger.debug("[Cache L2 HIT] %s", key)
        return json.loads(raw)
    logger.debug("[Cache L2 MISS] %s", key)
    return None


def set_ticks(asset: str, from_ts: str, to_ts: str, data: list[dict]) -> None:
    """Populate L2 tick cache."""
    key = _tick_key(asset, from_ts, to_ts)
    _l2.setex(key, L2_TTL, json.dumps(data, default=str))


def invalidate_asset_cache(asset: str) -> int:
    """
    Delete all L1 keys for a given asset.
    Called by the ingestion pipeline after each successful insert.
    Returns number of keys deleted.
    """
    pattern = f"market:candles:{asset}:*"
    keys = list(_l1.scan_iter(pattern))
    if keys:
        deleted = _l1.delete(*keys)
        logger.debug("[Cache INVALIDATE] %s — deleted %d keys", asset, deleted)
        return deleted
    return 0
