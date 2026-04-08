// TrendSection.tsx — 包含 HistoryNav + TrendChart 的 Client 組件容器
"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { HistoryIndex, SignalSnapshot } from "@/lib/types";
import { sortedSectors, CYCLE_STAGE_CONFIG, type CycleStageKey } from "@/lib/signals";
import { HistoryNav } from "./HistoryNav";

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

        {/* 当前週期階段摘要 */}
        {snapshot && topSectors.length > 0 && (
          <div className="mt-3 pt-3 border-t border-zinc-200/40 dark:border-zinc-700/30">
            <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mb-2">目前週期階段</p>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {topSectors.map((id) => {
                const sec = snapshot.sectors[id];
                if (!sec?.cycle_stage) return null;
                const cfg = CYCLE_STAGE_CONFIG[sec.cycle_stage as CycleStageKey];
                if (!cfg) return null;
                return (
                  <span key={id} className="flex items-center gap-1.5">
                    <span className="text-[11px] text-zinc-500 dark:text-zinc-400">{sec.name_zh}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ${cfg.chipCls}`}
                      title={cfg.tooltip}
                    >
                      {cfg.emoji} {cfg.label}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
