"use client";

import clsx from "clsx";
import type { Interval } from "@/lib/api";

interface IntervalSelectorProps {
  value:    Interval;
  onChange: (interval: Interval) => void;
}

const INTERVALS: { label: string; value: Interval }[] = [
  { label: "1m",  value: "1m" },
  { label: "5m",  value: "5m" },
  { label: "1h",  value: "1h" },
  { label: "1D",  value: "1d" },
];

export default function IntervalSelector({
  value,
  onChange,
}: IntervalSelectorProps) {
  return (
    <div className="flex gap-1 rounded-lg border border-gray-800 bg-gray-900 p-1">
      {INTERVALS.map((interval) => (
        <button
          key={interval.value}
          onClick={() => onChange(interval.value)}
          className={clsx(
            "rounded-md px-3 py-1 text-sm font-medium transition-colors",
            value === interval.value
              ? "bg-blue-600 text-white"
              : "text-gray-400 hover:text-white",
          )}
        >
          {interval.label}
        </button>
      ))}
    </div>
  );
}
