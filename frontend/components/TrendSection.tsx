// TrendSection.tsx — 包含 HistoryNav + TrendChart 的 Client 組件容器
"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { HistoryIndex, SignalSnapshot } from "@/lib/types";
import { HISTORY_RANGE_DAYS, sortedSectors } from "@/lib/signals";
import { HistoryNav } from "./HistoryNav";
import { SkeletonCard } from "./SkeletonCard";

// TrendChart 只在 Client 端渲染（Recharts 不支援 SSR）
const TrendChartDynamic = dynamic(
  () => import("./TrendChart").then((m) => m.TrendChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-72 flex items-center justify-center text-zinc-400 text-sm animate-pulse">
        載入圖表…
      </div>
    ),
  }
);

interface TrendSectionProps {
  historyIndex: HistoryIndex | null;
  snapshot: SignalSnapshot | null;
}

export function TrendSection({ historyIndex, snapshot }: TrendSectionProps) {
  const [range, setRange] = useState<number>(30);

  // 取前5個最高評分板塊的 id
  const topSectors = snapshot
    ? sortedSectors(snapshot.sectors)
        .slice(0, 5)
        .map((s) => s.id)
    : [];

  return (
    <section className="mt-8" aria-label="歷史趨勢">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-white">
          板塊趨勢
        </h2>
        <HistoryNav selected={range} onChange={setRange} />
      </div>

      <div className="rounded-2xl border border-zinc-200/60 dark:border-zinc-700/50
                      bg-white/80 dark:bg-zinc-800/60 backdrop-blur-sm p-4">
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
          顯示前 5 強板塊評分走勢（燈數 / 7）
        </p>
        {historyIndex ? (
          <TrendChartDynamic
            historyIndex={historyIndex}
            range={range}
            topSectors={topSectors}
          />
        ) : (
          <div className="h-72 flex items-center justify-center text-zinc-400 text-sm">
            無歷史資料
          </div>
        )}
      </div>
    </section>
  );
}
