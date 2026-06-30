"""
MarketConsumer — WebSocket endpoint at /ws/market/

Clients connect and are added to the "market_updates" group.
The ingestion pipeline (pipeline.py) broadcasts to this group
after each successful ClickHouse insert.

Message format (server → client):
    {
        "type": "market.tick",
        "data": [
            {"asset": "BTC", "ts": "2024-01-01T00:00:10Z", "close": 42000.0, "volume": 18500000000},
            ...
        ]
    }

Auth: JWT token passed as query param ?token=<access_token>
      Validated on connect — unauthenticated connections are rejected.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

logger = logging.getLogger(__name__)

GROUP_NAME = "market_updates"


class MarketConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Validate JWT from query string
        token_key = self._get_token_from_scope()
        if not token_key or not self._is_valid_token(token_key):
            logger.warning("WebSocket rejected: invalid or missing token")
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        logger.info("WebSocket connected: %s", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)
        logger.info("WebSocket disconnected: %s (code %s)", self.channel_name, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send data in this implementation.
        # Extend here to support asset filter subscriptions.
        pass

    async def market_tick(self, event):
        """Called by channel layer when ingestion pipeline broadcasts a tick."""
        await self.send(text_data=json.dumps({
            "type": "market.tick",
            "data": event.get("data", []),
        }))

    # ── Helpers ───────────────────────────────────────────────

    def _get_token_from_scope(self) -> str | None:
        query_string = self.scope.get("query_string", b"").decode()
        for part in query_string.split("&"):
            if part.startswith("token="):
                return part[len("token="):]
        return None

    @staticmethod
    def _is_valid_token(token_key: str) -> bool:
        try:
            AccessToken(token_key)
            return True
        except TokenError:
            return False
