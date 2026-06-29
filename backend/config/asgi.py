"""
ASGI config — handles both HTTP (Django) and WebSocket (Channels).

Routing:
    /ws/market/  → MarketConsumer (live tick stream)
    /*           → Django ASGI app (REST API)
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from backend.api.consumers import MarketConsumer  # noqa: E402 — must import after setup

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r"^ws/market/$", MarketConsumer.as_asgi()),
        ])
    ),
})
