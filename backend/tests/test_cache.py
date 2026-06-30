"""
Tests for backend/cache/redis_client.py

Cache invalidation is the most failure-prone part of the caching layer —
a bug here means stale data persists indefinitely. These tests verify
that the invalidation logic correctly identifies and deletes the right keys.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.mark.django_db
class TestCacheInvalidation:

    def test_invalidate_deletes_all_l1_keys_for_asset(self):
        """invalidate_asset_cache deletes all L1 keys matching the asset prefix."""
        from backend.cache.redis_client import invalidate_asset_cache

        with patch("backend.cache.redis_client._l1") as mock_redis:
            mock_redis.scan_iter.return_value = [
                "market:candles:BTC:1h:2024-01-01:2024-01-31",
                "market:candles:BTC:1d:2024-01-01:2024-01-31",
                "market:candles:BTC:1m:2024-01-01:2024-01-02",
            ]
            mock_redis.delete.return_value = 3

            deleted = invalidate_asset_cache("BTC")

        assert deleted == 3
        mock_redis.scan_iter.assert_called_once_with("market:candles:BTC:*")
        mock_redis.delete.assert_called_once()

    def test_invalidate_does_not_touch_other_assets(self):
        """Invalidating BTC must not affect ETH cache keys."""
        from backend.cache.redis_client import invalidate_asset_cache

        with patch("backend.cache.redis_client._l1") as mock_redis:
            # scan_iter returns only BTC keys (correct — pattern is asset-scoped)
            mock_redis.scan_iter.return_value = [
                "market:candles:BTC:1h:2024-01-01:2024-01-31",
            ]
            mock_redis.delete.return_value = 1

            invalidate_asset_cache("BTC")

        # Pattern must be scoped to BTC only
        call_args = mock_redis.scan_iter.call_args[0][0]
        assert "BTC" in call_args
        assert "ETH" not in call_args

    def test_invalidate_returns_zero_when_no_keys_exist(self):
        """No matching keys → returns 0, no delete call."""
        from backend.cache.redis_client import invalidate_asset_cache

        with patch("backend.cache.redis_client._l1") as mock_redis:
            mock_redis.scan_iter.return_value = []  # no keys

            deleted = invalidate_asset_cache("SOL")

        assert deleted == 0
        mock_redis.delete.assert_not_called()

    def test_get_candles_returns_none_on_cache_miss(self):
        """Cache miss returns None — caller must query ClickHouse."""
        from backend.cache.redis_client import get_candles

        with patch("backend.cache.redis_client._l1") as mock_redis:
            mock_redis.get.return_value = None

            result = get_candles("BTC", "1h", "2024-01-01", "2024-01-31")

        assert result is None

    def test_get_candles_deserialises_json_on_hit(self):
        """Cache hit returns deserialised list, not raw JSON string."""
        from backend.cache.redis_client import get_candles

        cached_data = [{"ts_bucket": "2024-01-01T01:00:00", "close": 42000.0}]

        with patch("backend.cache.redis_client._l1") as mock_redis:
            mock_redis.get.return_value = json.dumps(cached_data)

            result = get_candles("BTC", "1h", "2024-01-01", "2024-01-31")

        assert result == cached_data
        assert isinstance(result, list)
        assert result[0]["close"] == 42000.0

    def test_set_candles_uses_correct_ttl(self):
        """L1 candles are cached with the configured TTL (10 seconds)."""
        from backend.cache.redis_client import set_candles, L1_TTL

        data = [{"ts_bucket": "2024-01-01T01:00:00", "close": 42000.0}]

        with patch("backend.cache.redis_client._l1") as mock_redis:
            set_candles("BTC", "1h", "2024-01-01", "2024-01-31", data)

        # setex(key, ttl, value) — verify TTL is correct
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == L1_TTL  # second arg is TTL
        assert call_args[0][1] == 10      # must be 10 seconds
