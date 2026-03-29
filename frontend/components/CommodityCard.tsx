"use client";
// CommodityCard.tsx — 單一商品資產卡片（含 K 線展開 + 學術信號）

import type { CommodityAsset } from "@/lib/types";
import { CommodityKLine } from "@/components/CommodityKLine";
import type { OHLCBar } from "@/lib/types";

interface Props {
  asset: CommodityAsset;
  isExpanded: boolean;
  onToggle: () => void;
}

const CATEGORY_ICONS: Record<string, string> = {
  precious_metal: "🥇",
  energy:         "⛽",
  industrial:     "🏭",
  crypto:         "₿",
  index:          "📊",
  bonds:          "📋",
};

const SEVERITY_STYLE: Record<string, string> = {
  high:   "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  low:    "bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border-zinc-500/20",
};

export function CommodityCard({ asset, isExpanded, onToggle }: Props) {
  const { name_zh, category, price, change_1d_pct, change_7d_pct, signals } = asset;
  const icon = CATEGORY_ICONS[category] ?? "📌";
  const triggeredSignals = signals.filter(s => s.triggered);

  function fmtPct(v: number | null) {
    if (v === null) return "—";
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(2)}%`;
  }
  function pctColor(v: number | null) {
    if (v === null) return "text-zinc-400";
    return v > 0 ? "text-emerald-500 dark:text-emerald-400" : v < 0 ? "text-red-500 dark:text-red-400" : "text-zinc-400";
  }

  return (
    <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-700/40 bg-white/60 dark:bg-zinc-800/40 backdrop-blur overflow-hidden">
      {/* 卡片頭部 */}
      <div
        className="flex items-center justify-between px-3 py-2.5 cursor-pointer hover:bg-zinc-50/80 dark:hover:bg-zinc-700/30 transition-colors"
        onClick={() => onToggle()}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0">{icon}</span>
          <span className="font-medium text-sm text-zinc-900 dark:text-white truncate">{name_zh}</span>
          {triggeredSignals.length > 0 && (
            <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 font-medium">
              {triggeredSignals.length} 訊號
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-2">
          <div className="text-right">
            <div className="text-sm font-mono font-medium text-zinc-900 dark:text-white">
              {price !== null ? price.toPrecision(5) : "—"}
            </div>
            <div className={`text-[10px] font-mono ${pctColor(change_1d_pct)}`}>
              {fmtPct(change_1d_pct)} 日
            </div>
          </div>
          <div className="text-right">
            <div className={`text-xs font-mono ${pctColor(change_7d_pct)}`}>
              {fmtPct(change_7d_pct)}
            </div>
            <div className="text-[9px] text-zinc-400">7日</div>
          </div>
          <span className="text-zinc-400 dark:text-zinc-500 text-xs">
            {isExpanded ? "▲" : "▼"}
          </span>
        </div>
      </div>

      {/* 展開：K 線圖 + 學術信號 */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-zinc-100/80 dark:border-zinc-700/40">
          {/* K 線圖（無初始 OHLCV，全靠懶載入）*/}
          <div className="mt-2">
            <CommodityKLine data={[] as OHLCBar[]} slug={asset.slug} nameZh={name_zh} />
          </div>

          {/* 學術信號說明 */}
          {signals.length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                學術信號
              </div>
              {signals.map(sig => (
                <div
                  key={sig.key}
                  className={`rounded-lg border px-3 py-2 text-[11px] ${SEVERITY_STYLE[sig.severity] ?? SEVERITY_STYLE.low}`}
                >
                  <div className="flex items-start gap-2">
                    <span className="shrink-0 mt-0.5">{sig.triggered ? "🔔" : "○"}</span>
                    <div>
                      <p className="leading-relaxed">{sig.commentary}</p>
                      <p className="mt-1 opacity-60 text-[10px]">{sig.source}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
