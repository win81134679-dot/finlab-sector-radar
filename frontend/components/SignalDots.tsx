// SignalDots.tsx — 7燈視覺化元件（支援半亮 + 色盲無障礙 aria-label）
"use client";

import { signalState, SIGNAL_NAMES } from "@/lib/signals";

interface SignalDotsProps {
  signals: number[];
  size?: "sm" | "md" | "lg";
}

const SIZE_MAP = {
  sm: "w-3 h-3",
  md: "w-4 h-4",
  lg: "w-5 h-5",
};

const STATE_STYLES = {
  on:   "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]",
  half: "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.7)]",
  off:  "bg-zinc-700 dark:bg-zinc-800",
};

const STATE_ARIA = {
  on:   "亮燈",
  half: "半亮",
  off:  "未亮",
};

export function SignalDots({ signals, size = "md" }: SignalDotsProps) {
  const dotSize = SIZE_MAP[size];

  return (
    <div className="flex items-center gap-1" role="list" aria-label="7燈信號">
      {signals.map((val, i) => {
        const state = signalState(val);
        const name  = SIGNAL_NAMES[i] ?? `燈${i + 1}`;
        return (
          <div
            key={i}
            role="listitem"
            aria-label={`${name}：${STATE_ARIA[state]}`}
            title={`${name}：${STATE_ARIA[state]}`}
            className={`${dotSize} rounded-full transition-all duration-200 ${STATE_STYLES[state]}`}
          />
        );
      })}
    </div>
  );
}
