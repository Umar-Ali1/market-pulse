"use client";

import clsx from "clsx";
import { formatDistanceToNow } from "date-fns";

interface ConnectionBadgeProps {
  connected:   boolean;
  lastUpdated: Date | null;
}

export default function ConnectionBadge({
  connected,
  lastUpdated,
}: ConnectionBadgeProps) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-gray-800 bg-gray-900 px-3 py-1.5">
      {/* Pulsing dot */}
      <span className="relative flex h-2 w-2">
        {connected && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
        )}
        <span
          className={clsx(
            "relative inline-flex h-2 w-2 rounded-full",
            connected ? "bg-green-500" : "bg-red-500",
          )}
        />
      </span>

      <span className="text-xs text-gray-400">
        {connected ? "Live" : "Reconnecting…"}
        {lastUpdated && connected && (
          <span className="ml-1 text-gray-600">
            · {formatDistanceToNow(lastUpdated, { addSuffix: true })}
          </span>
        )}
      </span>
    </div>
  );
}
