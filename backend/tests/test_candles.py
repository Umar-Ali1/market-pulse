"""
Tests for GET /api/v1/candles/

Critical paths:
  - Valid request hits cache first, falls back to ClickHouse on miss
  - Cache hit returns without touching ClickHouse
  - Invalid parameters return 400 with field-level errors
  - Unauthenticated requests are rejected with 401
  - ClickHouse failure returns 503, not 500
"""

import pytest
from unittest.mock import patch


VALID_PARAMS = {
    "asset":    "BTC",
    "interval": "1h",
    "from":     "2024-01-01T00:00:00Z",
    "to":       "2024-01-31T23:59:59Z",
}

MOCK_CANDLES = [
    {
        "ts_bucket": "2024-01-01T01:00:00",
        "open":  42000.0,
        "high":  42500.0,
        "low":   41800.0,
        "close": 42300.0,
        "volume": 1_800_000_000.0,
    }
]


@pytest.mark.django_db
class TestCandleView:

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/candles/", VALID_PARAMS)
        assert response.status_code == 401

    def test_cache_hit_does_not_query_clickhouse(self, auth_client):
        """L1 cache hit → ClickHouse never called."""
        with patch("backend.api.views.get_candles") as mock_cache, \
             patch("backend.api.views.query_candles") as mock_db:

            mock_cache.return_value = MOCK_CANDLES  # cache hit

            response = auth_client.get("/api/v1/candles/", VALID_PARAMS)

        assert response.status_code == 200
        assert response.data["source"] == "cache"
        assert len(response.data["candles"]) == 1
        mock_db.assert_not_called()  # ClickHouse never touched

    def test_cache_miss_queries_clickhouse_and_populates_cache(self, auth_client):
        """L1 miss → ClickHouse queried → cache populated → data returned."""
        with patch("backend.api.views.get_candles") as mock_cache_get, \
             patch("backend.api.views.set_candles") as mock_cache_set, \
             patch("backend.api.views.query_candles") as mock_db:

            mock_cache_get.return_value = None        # cache miss
            mock_db.return_value = MOCK_CANDLES       # DB returns data

            response = auth_client.get("/api/v1/candles/", VALID_PARAMS)

        assert response.status_code == 200
        assert response.data["source"] == "db"
        mock_db.assert_called_once()
        mock_cache_set.assert_called_once()           # cache populated

    def test_invalid_asset_returns_400(self, auth_client):
        params = {**VALID_PARAMS, "asset": "DOGE"}
        response = auth_client.get("/api/v1/candles/", params)
        assert response.status_code == 400
        assert "asset" in response.data["errors"]

    def test_invalid_interval_returns_400(self, auth_client):
        params = {**VALID_PARAMS, "interval": "3h"}
        response = auth_client.get("/api/v1/candles/", params)
        assert response.status_code == 400
        assert "interval" in response.data["errors"]

    def test_missing_from_returns_400(self, auth_client):
        params = {k: v for k, v in VALID_PARAMS.items() if k != "from"}
        response = auth_client.get("/api/v1/candles/", params)
        assert response.status_code == 400
        assert "from" in response.data["errors"]

    def test_clickhouse_failure_returns_503(self, auth_client):
        """DB failure → 503 Service Unavailable, not 500."""
        with patch("backend.api.views.get_candles") as mock_cache, \
             patch("backend.api.views.query_candles") as mock_db:

            mock_cache.return_value = None
            mock_db.side_effect = Exception("ClickHouse connection timeout")

            response = auth_client.get("/api/v1/candles/", VALID_PARAMS)

        assert response.status_code == 503
        assert "error" in response.data

    def test_response_includes_asset_and_interval(self, auth_client):
        """Response envelope includes asset and interval for client convenience."""
        with patch("backend.api.views.get_candles") as mock_cache, \
             patch("backend.api.views.query_candles"):

            mock_cache.return_value = MOCK_CANDLES

            response = auth_client.get("/api/v1/candles/", VALID_PARAMS)

        assert response.data["asset"] == "BTC"
        assert response.data["interval"] == "1h"
