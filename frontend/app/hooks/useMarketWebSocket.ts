"use client";

/**
 * useMarketWebSocket
 *
 * Connects to the Django Channels WebSocket endpoint and streams
 * live market tick updates. Handles reconnection with exponential
 * backoff — the server pushes a new message every 10 seconds on
 * successful ingestion.
 *
 * Usage:
 *   const { ticks, connected } = useMarketWebSocket(["BTC", "ETH"]);
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface MarketTick {
  asset: string;
  ts: string;
  close: number;
  volume: number;
}

interface UseMarketWebSocketReturn {
  ticks: Record<string, MarketTick>;   // keyed by asset symbol
  connected: boolean;
  lastUpdated: Date | null;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/market/";
const MAX_BACKOFF_MS = 30_000;

export function useMarketWebSocket(
  assets: string[]
): UseMarketWebSocketReturn {
  const [ticks, setTicks] = useState<Record<string, MarketTick>>({});
  const [connected, setConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1_000);
  const mountedRef = useRef(true);
  const assetsRef = useRef(new Set(assets));

  // Keep assetsRef current without triggering reconnect
  useEffect(() => {
    assetsRef.current = new Set(assets);
  }, [assets]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      setConnected(true);
      backoffRef.current = 1_000;   // reset on successful connect
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string);
        if (message.type !== "market.tick") return;

        const incoming: MarketTick[] = message.data ?? [];
        const filtered = incoming.filter((t) => assetsRef.current.has(t.asset));
        if (!filtered.length) return;

        setTicks((prev) => {
          const next = { ...prev };
          for (const tick of filtered) next[tick.asset] = tick;
          return next;
        });
        setLastUpdated(new Date());
      } catch {
        // Malformed frame — ignore silently
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);

      // Exponential backoff reconnect
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();   // triggers onclose → reconnect
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { ticks, connected, lastUpdated };
}
