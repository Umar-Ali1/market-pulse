"use client";

import { type MarketTick } from "../hooks/useMarketWebSocket";
import clsx from "clsx";

interface AssetCardProps {
  symbol:    string;
  price:     number | null;
  selected:  boolean;
  liveTick:  MarketTick | null;
  onClick:   () => void;
}

const ASSET_COLORS: Record<string, string> = {
  BTC: "text-amber-400",
  ETH: "text-indigo-400",
  SOL: "text-purple-400",
  BNB: "text-yellow-400",
};

export default function AssetCard({
  symbol,
  price,
  selected,
  liveTick,
  onClick,
}: AssetCardProps) {
  const colorClass = ASSET_COLORS[symbol] ?? "text-blue-400";

  return (
    <button
      onClick={onClick}
      className={clsx(
        "rounded-xl border p-4 text-left transition-all duration-150",
        selected
          ? "border-blue-500 bg-blue-950/40"
          : "border-gray-800 bg-gray-900 hover:border-gray-600",
      )}
    >
      <div className={clsx("text-sm font-semibold", colorClass)}>{symbol}</div>
      <div className="mt-1 text-xl font-bold text-white">
        {price !== null
          ? `$${price.toLocaleString("en-US", { maximumFractionDigits: 2 })}`
          : "—"}
      </div>
      {liveTick && (
        <div className="mt-1 text-xs text-gray-500">
          Vol:{" "}
          {liveTick.volume >= 1e9
            ? `$${(liveTick.volume / 1e9).toFixed(1)}B`
            : `$${(liveTick.volume / 1e6).toFixed(0)}M`}
        </div>
      )}
    </button>
  );
}
