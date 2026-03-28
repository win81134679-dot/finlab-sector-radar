// HistoryNav.tsx — 歷史區間切換標籤 (7d / 14d / 30d / 90d)
"use client";

import { HISTORY_RANGE_LABELS, HISTORY_RANGE_DAYS } from "@/lib/signals";

interface HistoryNavProps {
  selected: number;
  onChange: (days: number) => void;
}

export function HistoryNav({ selected, onChange }: HistoryNavProps) {
  return (
    <nav
      className="inline-flex rounded-xl border border-zinc-200 dark:border-zinc-700
                 bg-zinc-100/80 dark:bg-zinc-800/60 p-1 gap-1"
      aria-label="歷史區間"
    >
      {HISTORY_RANGE_DAYS.map((days) => {
        const label = HISTORY_RANGE_LABELS[days] ?? `${days}d`;
        const isActive = selected === days;
        return (
          <button
            key={days}
            onClick={() => onChange(days)}
            className={`
              px-3 py-1.5 rounded-lg text-sm font-medium
              transition-all duration-150
              ${isActive
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
              }
            `}
            aria-pressed={isActive}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}
