"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetchCandles, fetchAssets, type Interval } from "@/lib/api";
import { useMarketWebSocket } from "./hooks/useMarketWebSocket";
import PriceChart from "./components/PriceChart";
import AssetCard from "./components/AssetCard";
import IntervalSelector from "./components/IntervalSelector";
import ConnectionBadge from "./components/ConnectionBadge";
import { subDays, formatISO } from "date-fns";

const ASSETS = ["BTC", "ETH", "SOL", "BNB"];

export default function DashboardPage() {
  const [selectedAsset, setSelectedAsset] = useState("BTC");
  const [interval, setSelectedInterval] = useState<Interval>("1h");

  const to   = formatISO(new Date());
  const from = formatISO(subDays(new Date(), interval === "1d" ? 365 : interval === "1h" ? 90 : 7));

  // Live asset prices via WebSocket
  const { ticks, connected, lastUpdated } = useMarketWebSocket(ASSETS);

  // Historical candles via SWR (refetches when asset/interval changes)
  const { data: candleData, isLoading } = useSWR(
    ["candles", selectedAsset, interval, from, to],
    () => fetchCandles(selectedAsset, interval, from, to),
    { refreshInterval: 30_000 },
  );

  // Asset summary cards — live price overlaid on REST data
  const { data: assetData } = useSWR("assets", fetchAssets, {
    refreshInterval: 15_000,
  });

  const assets = (assetData?.assets ?? []).map((a) => ({
    ...a,
    price: ticks[a.asset]?.close ?? a.price,
  }));

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">MarketPulse</h1>
          <p className="text-gray-400 text-sm mt-1">
            Real-time crypto analytics · Updates every 10s
          </p>
        </div>
        <ConnectionBadge connected={connected} lastUpdated={lastUpdated} />
      </div>

      {/* Asset cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {ASSETS.map((symbol) => {
          const asset = assets.find((a) => a.asset === symbol);
          return (
            <AssetCard
              key={symbol}
              symbol={symbol}
              price={asset?.price ?? null}
              selected={selectedAsset === symbol}
              liveTick={ticks[symbol] ?? null}
              onClick={() => setSelectedAsset(symbol)}
            />
          );
        })}
      </div>

      {/* Chart controls */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">
          {selectedAsset} / USD
        </h2>
        <IntervalSelector value={interval} onChange={setSelectedInterval} />
      </div>

      {/* Candlestick chart */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        {isLoading ? (
          <div className="h-96 flex items-center justify-center text-gray-500">
            Loading chart data...
          </div>
        ) : (
          <PriceChart
            candles={candleData?.candles ?? []}
            asset={selectedAsset}
            interval={interval}
          />
        )}
      </div>

      {/* Data source footer */}
      <p className="text-xs text-gray-600 text-center mt-4">
        Market data via CoinGecko · Stored in ClickHouse · Cached in Redis
      </p>
    </main>
  );
}
