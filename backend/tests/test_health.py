"""
Tests for GET /api/v1/health/

The health endpoint is unauthenticated and used by Railway's
load balancer. It must return 200 when all dependencies are up
and 503 when any dependency is down.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse


@pytest.mark.django_db
class TestHealthView:

    def test_healthy_returns_200(self, api_client):
        """Both ClickHouse and Redis responsive → 200 healthy."""
        with patch("backend.api.views.get_client") as mock_ch, \
             patch("backend.cache.redis_client._l1") as mock_redis:

            mock_ch.return_value.execute.return_value = [[1]]
            mock_redis.ping.return_value = True

            response = api_client.get("/api/v1/health/")

        assert response.status_code == 200
        assert response.data["status"] == "healthy"
        assert response.data["checks"]["clickhouse"] == "ok"
        assert response.data["checks"]["redis"] == "ok"

    def test_clickhouse_down_returns_503(self, api_client):
        """ClickHouse unreachable → 503 degraded."""
        with patch("backend.api.views.get_client") as mock_ch, \
             patch("backend.cache.redis_client._l1") as mock_redis:

            mock_ch.return_value.execute.side_effect = Exception("Connection refused")
            mock_redis.ping.return_value = True

            response = api_client.get("/api/v1/health/")

        assert response.status_code == 503
        assert response.data["status"] == "degraded"
        assert response.data["checks"]["clickhouse"] == "error"
        assert response.data["checks"]["redis"] == "ok"

    def test_redis_down_returns_503(self, api_client):
        """Redis unreachable → 503 degraded."""
        with patch("backend.api.views.get_client") as mock_ch, \
             patch("backend.cache.redis_client._l1") as mock_redis:

            mock_ch.return_value.execute.return_value = [[1]]
            mock_redis.ping.side_effect = Exception("NOAUTH")

            response = api_client.get("/api/v1/health/")

        assert response.status_code == 503
        assert response.data["checks"]["redis"] == "error"

    def test_health_requires_no_auth(self, api_client):
        """Health endpoint must be reachable without a JWT."""
        with patch("backend.api.views.get_client") as mock_ch, \
             patch("backend.cache.redis_client._l1") as mock_redis:

            mock_ch.return_value.execute.return_value = [[1]]
            mock_redis.ping.return_value = True

            # No credentials set on api_client
            response = api_client.get("/api/v1/health/")

        assert response.status_code == 200
