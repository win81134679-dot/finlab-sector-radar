"use client";
// MagaWatchlist.tsx — 受益 / 受害股票清單，點擊展開 K 線

import { useState } from "react";
import type { MagaStock } from "@/lib/types";
import { ImpactBadge } from "@/components/ImpactBadge";
import { StockKLine } from "@/components/StockKLine";

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function pctColor(v: number | null): string {
  if (v === null) return "text-zinc-400";
  return v > 0
    ? "text-emerald-600 dark:text-emerald-400"
    : v < 0
    ? "text-red-600 dark:text-red-400"
    : "text-zinc-500";
}

function StockRow({ stock }: { stock: MagaStock }) {
  const [expanded, setExpanded] = useState(false);
  const hasChart = (stock.ohlcv_7d?.length ?? 0) > 0;

  return (
    <div className="border border-zinc-200/40 dark:border-zinc-800/40 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs text-zinc-400 shrink-0">{stock.id}</span>
            <span className="text-sm font-medium text-zinc-900 dark:text-white">{stock.name_zh}</span>
            <span className="text-xs text-zinc-400 truncate">{stock.sector_name}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {stock.price !== null && (
            <span className="text-sm font-mono text-zinc-700 dark:text-zinc-300 hidden sm:block">
              {stock.price.toLocaleString()}
            </span>
          )}
          <span className={`text-xs font-medium ${pctColor(stock.change_1d_pct)}`}>
            {fmtPct(stock.change_1d_pct)}
          </span>
          <span className={`text-xs ${pctColor(stock.change_7d_pct)} hidden sm:block`}>
            7d {fmtPct(stock.change_7d_pct)}
          </span>
          <ImpactBadge score={stock.impact_score} category={stock.category} />
          {hasChart && (
            <span className="text-zinc-400 text-xs">{expanded ? "▲" : "▼"}</span>
          )}
        </div>
      </button>

      {expanded && hasChart && (
        <div className="border-t border-zinc-200/40 dark:border-zinc-800/40 p-3 bg-zinc-50/50 dark:bg-zinc-900/30">
          <StockKLine data={stock.ohlcv_7d!} stockId={stock.id} />
        </div>
      )}
    </div>
  );
}

interface Props {
  stocks: MagaStock[];
}

export function MagaWatchlist({ stocks }: Props) {
  const beneficiary = [...stocks.filter(s => s.category === "beneficiary")]
    .sort((a, b) => b.impact_score - a.impact_score);
  const victim = [...stocks.filter(s => s.category === "victim")]
    .sort((a, b) => a.impact_score - b.impact_score);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 受益 */}
      <div>
        <h3 className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mb-3 flex items-center gap-2">
          ▲ 受益股票
          <span className="text-xs text-zinc-400 font-normal">({beneficiary.length} 支)</span>
        </h3>
        <div className="space-y-2">
          {beneficiary.map(s => <StockRow key={s.id} stock={s} />)}
          {beneficiary.length === 0 && (
            <p className="text-sm text-zinc-400 py-6 text-center">暫無資料</p>
          )}
        </div>
      </div>

      {/* 受害 */}
      <div>
        <h3 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-3 flex items-center gap-2">
          ▼ 受害股票
          <span className="text-xs text-zinc-400 font-normal">({victim.length} 支)</span>
        </h3>
        <div className="space-y-2">
          {victim.map(s => <StockRow key={s.id} stock={s} />)}
          {victim.length === 0 && (
            <p className="text-sm text-zinc-400 py-6 text-center">暫無資料</p>
          )}
        </div>
      </div>
    </div>
  );
}
