"""
WSGI config for MarketPulse.

Note: In production, Daphne (ASGI) is the primary server — it handles
both HTTP and WebSocket. This WSGI file exists for compatibility with
tools that expect a standard WSGI application (e.g., health check
scripts, some CI integrations).

For WebSocket support, always use the ASGI app (config/asgi.py).
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
