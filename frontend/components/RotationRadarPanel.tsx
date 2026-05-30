"use client";
// RotationRadarPanel.tsx — 輪動雷達：中長期板塊輪動偵測（L1 景氣 + L2 產業RSI + L3 法人籌碼）

import { useMemo } from "react";
import type { SignalSnapshot } from "@/lib/types";

interface Props {
  snapshot: SignalSnapshot | null;
}

const PHASE_STYLE: Record<string, { label: string; cls: string }> = {
  recovery:   { label: "復甦", cls: "text-sky-600 dark:text-sky-400" },
  expansion:  { label: "擴張", cls: "text-emerald-600 dark:text-emerald-400" },
  slowdown:   { label: "趨緩", cls: "text-amber-600 dark:text-amber-400" },
  recession:  { label: "衰退", cls: "text-red-600 dark:text-red-400" },
  unknown:    { label: "數據不足", cls: "text-zinc-500" },
};

function rsiColor(state: string): string {
  if (state === "超買") return "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300";
  if (state === "偏多") return "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300";
  if (state === "偏空") return "bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300";
  if (state === "超賣") return "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300";
  return "bg-zinc-100 dark:bg-zinc-800 text-zinc-500";
}

export function RotationRadarPanel({ snapshot }: Props) {
  const { ranked, handoffs, cycle } = useMemo(() => {
    const sectors = snapshot?.sectors ?? {};
    const rows = Object.entries(sectors)
      .map(([id, s]) => ({
        id,
        name: s.name_zh,
        score: s.rotation?.rotation_score ?? null,
        rsi: s.rotation?.rsi_60 ?? null,
        rsiState: s.rotation?.rsi_state ?? "資料不足",
        rsiPctl: s.rotation?.rsi_percentile ?? null,
        mom: s.rotation?.sector_momentum_pct ?? null,
        chipLevel: s.rotation?.chip_flow?.level ?? "",
        chipScore: s.rotation?.chip_flow?.score ?? 0,
        level: s.level,
        handoff: s.rotation_handoff ?? null,
      }))
      .filter((r) => r.score !== null)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

    const hf = Object.entries(sectors)
      .filter(([, s]) => s.rotation_handoff)
      .map(([id, s]) => ({ id, name: s.name_zh, ...s.rotation_handoff! }));

    return { ranked: rows, handoffs: hf, cycle: snapshot?.cycle_clock ?? null };
  }, [snapshot]);

  if (!snapshot?.sectors) {
    return <p className="mt-6 text-zinc-500">📡 資料更新中</p>;
  }

  const phase = cycle ? PHASE_STYLE[cycle.phase] ?? PHASE_STYLE.unknown : null;

  return (
    <div className="mt-6 space-y-6">
      {/* L1 景氣象限 */}
      {cycle && (
        <section aria-label="景氣循環">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-2">景氣循環時鐘</h2>
          <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 p-4 bg-zinc-50/60 dark:bg-zinc-900/40">
            <div className="flex items-baseline gap-3">
              <span className={`text-2xl font-bold ${phase?.cls}`}>{cycle.phase_zh}</span>
              <span className="text-xs text-zinc-400">
                {cycle.source === "ndc_official" ? "國發會景氣燈號" : "代理指標"}
                {cycle.ndc_score != null ? `（${cycle.ndc_score}分）` : ""}
              </span>
            </div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">{cycle.details}</p>
            {cycle.favored_sectors.length > 0 && (
              <p className="text-xs text-zinc-500 mt-2">
                超配方向：{cycle.favored_sectors.join("、")}
              </p>
            )}
          </div>
        </section>
      )}

      {/* 接棒訊號 */}
      {handoffs.length > 0 && (
        <section aria-label="接棒訊號">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-2">🤝 接棒候選</h2>
          <div className="space-y-2">
            {handoffs.map((h) => (
              <div key={h.id} className="rounded-lg border border-amber-300/50 dark:border-amber-700/40 bg-amber-50/60 dark:bg-amber-900/20 px-3 py-2 text-sm">
                <span className="font-medium text-amber-700 dark:text-amber-300">
                  {h.from_name ?? h.from} → {h.name}
                </span>
                <span className="text-zinc-500 ml-2">
                  領先板塊過熱，{h.name} 可能接棒
                  {h.lag_days != null ? `（歷史滯後約 ${h.lag_days} 日）` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* L2+L3 輪動排名 */}
      <section aria-label="板塊輪動排名">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-2">板塊輪動強度排名</h2>
        <p className="text-xs text-zinc-500 mb-3">
          綜合強度 = 產業動能 + RSI 斜率 + 法人籌碼（標準化）。正值＝資金輪入。
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500 border-b border-zinc-200/60 dark:border-zinc-800/60">
                <th className="py-2 pr-3">板塊</th>
                <th className="py-2 px-2 text-right">綜合強度</th>
                <th className="py-2 px-2 text-right">RSI</th>
                <th className="py-2 px-2">狀態</th>
                <th className="py-2 px-2 text-right">動能</th>
                <th className="py-2 px-2">法人籌碼</th>
              </tr>
            </thead>
            <tbody>
              {ranked.slice(0, 25).map((r) => (
                <tr key={r.id} className="border-b border-zinc-100/60 dark:border-zinc-800/30">
                  <td className="py-1.5 pr-3 font-medium text-zinc-800 dark:text-zinc-200">{r.name}</td>
                  <td className={`py-1.5 px-2 text-right font-mono ${(r.score ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400"}`}>
                    {r.score != null ? r.score.toFixed(2) : "—"}
                  </td>
                  <td className="py-1.5 px-2 text-right font-mono text-zinc-600 dark:text-zinc-400">
                    {r.rsi != null ? r.rsi.toFixed(0) : "—"}
                  </td>
                  <td className="py-1.5 px-2">
                    <span className={`px-1.5 py-0.5 rounded text-[11px] ${rsiColor(r.rsiState)}`}>{r.rsiState}</span>
                  </td>
                  <td className={`py-1.5 px-2 text-right font-mono ${(r.mom ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}>
                    {r.mom != null ? `${r.mom > 0 ? "+" : ""}${r.mom.toFixed(1)}%` : "—"}
                  </td>
                  <td className="py-1.5 px-2 text-zinc-600 dark:text-zinc-400 text-[12px]">
                    {(r.chipScore ?? 0) >= 3 ? r.chipLevel : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
