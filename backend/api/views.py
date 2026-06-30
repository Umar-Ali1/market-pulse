"""
Market data API views.

Endpoints:
    GET /api/v1/candles/?asset=BTC&interval=1h&from=2024-01-01&to=2024-01-31
    GET /api/v1/assets/          — list available assets with latest price
    GET /api/v1/health/          — service health (ClickHouse + Redis ping)

Cache strategy:
    All candle requests go through the two-tier Redis cache.
    Cache miss → ClickHouse query → populate cache → return.
    Cache hit  → return directly, no DB touch.
"""

from __future__ import annotations

import logging

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.cache.redis_client import get_candles, set_candles
from backend.clickhouse.client import get_client, query_candles

logger = logging.getLogger(__name__)

VALID_ASSETS    = {"BTC", "ETH", "SOL", "BNB"}
VALID_INTERVALS = {"1m", "5m", "1h", "1d"}


class CandleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        asset    = request.query_params.get("asset", "").upper()
        interval = request.query_params.get("interval", "1h")
        from_ts  = request.query_params.get("from")
        to_ts    = request.query_params.get("to")

        # ── Validate ───────────────────────────────────────────
        errors = {}
        if asset not in VALID_ASSETS:
            errors["asset"] = f"Must be one of: {', '.join(sorted(VALID_ASSETS))}"
        if interval not in VALID_INTERVALS:
            errors["interval"] = f"Must be one of: {', '.join(sorted(VALID_INTERVALS))}"
        if not from_ts:
            errors["from"] = "Required."
        if not to_ts:
            errors["to"] = "Required."
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        # ── L1 cache check ─────────────────────────────────────
        cached = get_candles(asset, interval, from_ts, to_ts)
        if cached is not None:
            return Response({"asset": asset, "interval": interval, "candles": cached, "source": "cache"})

        # ── ClickHouse query ───────────────────────────────────
        try:
            candles = query_candles(asset, interval, from_ts, to_ts)
        except Exception as exc:
            logger.exception("ClickHouse query failed: %s", exc)
            return Response(
                {"error": "Data store unavailable. Retry shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # ── Populate cache ─────────────────────────────────────
        set_candles(asset, interval, from_ts, to_ts, candles)

        return Response({"asset": asset, "interval": interval, "candles": candles, "source": "db"})


class AssetListView(APIView):
    """Latest price snapshot for all tracked assets."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query = """
            SELECT
                asset,
                argMax(close, ts) AS price,
                max(ts)           AS last_updated
            FROM market_ticks
            WHERE ts >= now() - INTERVAL 1 HOUR
            GROUP BY asset
            ORDER BY asset
        """
        try:
            rows, cols = get_client().execute(query, with_column_types=True)
        except Exception as exc:
            logger.exception("AssetListView ClickHouse error: %s", exc)
            return Response({"error": "Data store unavailable."}, status=503)

        col_names = [c[0] for c in cols]
        data = [dict(zip(col_names, row)) for row in rows]
        return Response({"assets": data})


@method_decorator(never_cache, name="dispatch")
class HealthView(APIView):
    """
    Shallow health check for load balancer / uptime monitoring.
    Does NOT require auth — used by Railway health checks.
    """
    permission_classes = []

    def get(self, request: Request) -> Response:
        checks: dict[str, str] = {}

        # ClickHouse
        try:
            get_client().execute("SELECT 1")
            checks["clickhouse"] = "ok"
        except Exception:
            checks["clickhouse"] = "error"

        # Redis (L1)
        try:
            from backend.cache.redis_client import _l1
            _l1.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        return Response(
            {"status": "healthy" if all_ok else "degraded", "checks": checks},
            status=200 if all_ok else 503,
        )
