"use client";

/**
 * PriceChart — ECharts candlestick + volume chart.
 *
 * Rendering decisions:
 *   - Canvas renderer (not SVG): handles 50,000+ points at 60fps
 *   - progressive: 2000 / progressiveThreshold: 3000: renders in batches,
 *     user sees chart appear within one frame, not after full render completes
 *   - large: true on volume series: ECharts large-data mode, trades
 *     per-point hover for throughput (correct tradeoff at this data density)
 *   - dataset API: single data source shared across candlestick + volume,
 *     halves memory footprint vs duplicating data in series.data
 */

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import type { Candle, Interval } from "@/lib/api";
import { format } from "date-fns";

interface PriceChartProps {
  candles:  Candle[];
  asset:    string;
  interval: Interval;
}

const INTERVAL_FORMAT: Record<Interval, string> = {
  "1m": "HH:mm",
  "5m": "HH:mm",
  "1h": "MMM d HH:mm",
  "1d": "MMM d yyyy",
};

export default function PriceChart({ candles, asset, interval }: PriceChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const fmt = INTERVAL_FORMAT[interval];

    // Transform to ECharts dataset format
    // Columns: [timestamp_label, open, close, low, high, volume]
    const source = candles.map((c) => [
      format(new Date(c.ts_bucket), fmt),
      c.open,
      c.close,
      c.low,
      c.high,
      c.volume,
    ]);

    return {
      backgroundColor: "transparent",
      animation: false,          // disable for large datasets — causes jank
      progressive: 2000,
      progressiveThreshold: 3000,

      dataset: { source },

      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: "#1f2937",
        borderColor: "#374151",
        textStyle: { color: "#f9fafb", fontSize: 12 },
      },

      legend: {
        data: [asset],
        textStyle: { color: "#9ca3af" },
        top: 0,
      },

      grid: [
        { left: "10%", right: "8%", top: "8%",  height: "60%" },  // candlestick
        { left: "10%", right: "8%", top: "73%", height: "16%" },  // volume
      ],

      xAxis: [
        {
          type: "category",
          gridIndex: 0,
          axisLabel: { color: "#6b7280", fontSize: 11 },
          axisLine: { lineStyle: { color: "#374151" } },
          splitLine: { show: false },
        },
        {
          type: "category",
          gridIndex: 1,
          axisLabel: { show: false },
          axisLine: { lineStyle: { color: "#374151" } },
        },
      ],

      yAxis: [
        {
          scale: true,
          gridIndex: 0,
          axisLabel: {
            color: "#6b7280",
            fontSize: 11,
            formatter: (v: number) =>
              v >= 1_000 ? `$${(v / 1_000).toFixed(1)}k` : `$${v.toFixed(2)}`,
          },
          splitLine: { lineStyle: { color: "#1f2937" } },
        },
        {
          scale: true,
          gridIndex: 1,
          axisLabel: {
            color: "#6b7280",
            fontSize: 10,
            formatter: (v: number) =>
              v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : `${(v / 1e6).toFixed(0)}M`,
          },
          splitLine: { show: false },
        },
      ],

      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], start: 70, end: 100 },
        {
          type: "slider",
          xAxisIndex: [0, 1],
          bottom: 0,
          height: 20,
          borderColor: "#374151",
          fillerColor: "rgba(59,130,246,0.1)",
          handleStyle: { color: "#3b82f6" },
          textStyle: { color: "#6b7280" },
        },
      ],

      series: [
        {
          name: asset,
          type: "candlestick",
          datasetIndex: 0,
          encode: { x: 0, open: 1, close: 2, low: 3, high: 4 },
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color:        "#22c55e",   // bullish (close > open)
            color0:       "#ef4444",   // bearish
            borderColor:  "#22c55e",
            borderColor0: "#ef4444",
          },
        },
        {
          name: "Volume",
          type: "bar",
          datasetIndex: 0,
          encode: { x: 0, y: 5 },
          xAxisIndex: 1,
          yAxisIndex: 1,
          large: true,
          itemStyle: { color: "rgba(59,130,246,0.4)" },
        },
      ],
    };
  }, [candles, asset, interval]);

  return (
    <ReactECharts
      option={option}
      style={{ height: "480px", width: "100%" }}
      opts={{ renderer: "canvas" }}    // explicit Canvas — never SVG
      notMerge                         // full replace on data change, not merge
    />
  );
}
