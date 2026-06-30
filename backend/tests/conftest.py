"""
Shared pytest fixtures for MarketPulse backend tests.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from unittest.mock import patch, MagicMock


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )


@pytest.fixture
def auth_client(api_client, user):
    """APIClient with a valid JWT for the test user."""
    token = AccessToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return api_client


@pytest.fixture
def mock_clickhouse():
    """Mock the ClickHouse client — tests never touch a real DB."""
    with patch("backend.clickhouse.client.get_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_redis_l1():
    """Mock Redis L1 cache."""
    with patch("backend.cache.redis_client._l1") as mock:
        yield mock


@pytest.fixture
def mock_redis_l2():
    """Mock Redis L2 cache."""
    with patch("backend.cache.redis_client._l2") as mock:
        yield mock
