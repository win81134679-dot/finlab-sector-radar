// HoldingCard.tsx — 個股持倉分析卡片（含 5 級行動 badge、PnL、K 線、RSI、MACD）
"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { OHLCBar } from "@/lib/types";
import type { MergedHolding } from "@/lib/holdings-utils";
import { ACTION_CONFIG, type HoldingAction } from "@/lib/holdings-utils";
import {
  changePctColor, formatChangePct,
  SIGNAL_NAMES, CYCLE_STAGE_CONFIG, type CycleStageKey,
} from "@/lib/signals";
import { getSectorName } from "@/lib/sectors";

import { SignalDots } from "./SignalDots";
import { MiniSparkline } from "./MiniSparkline";
import { StockSummary } from "./StockSummary";
import { FactorRadar } from "./FactorRadar";
import { RsiGauge } from "./RsiGauge";
import { MacdChart } from "./MacdChart";
import { CandlePatternBadges } from "./CandlePatternBadges";

const GITHUB_RAW_BASE = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

function useOHLCV(stockId: string, enabled: boolean) {
  const [fullData, setFullData] = useState<OHLCBar[]>([]);
  const [loading, setLoading] = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!enabled || fetchedRef.current || !GITHUB_RAW_BASE) return;
    fetchedRef.current = true;
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) setLoading(true); });
    fetch(`${GITHUB_RAW_BASE}/output/ohlcv/${stockId}.json`, { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then((d: OHLCBar[] | null) => { if (!cancelled && d && d.length > 0) setFullData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [stockId, enabled]);

  return { fullData, loading };
}

const StockKLine = dynamic<{ data: OHLCBar[]; stockId: string; fullData?: OHLCBar[] }>(
  () => import("./StockKLine").then((m) => m.StockKLine),
  { ssr: false, loading: () => <div className="h-50 flex items-center justify-center text-zinc-400 text-xs">載入中...</div> }
);

// ── 交易成本試算 ────────────────────────────────────────────────────────
const BROKER_FEE_RATE = 0.001425;
const BROKER_FEE_MIN = 20;
const TAX_RATE = 0.003;

function calcTradeCost(price: number | null, shares: number | null) {
  if (!price || !shares) return null;
  const amount = price * shares;
  const buyFee = Math.max(Math.round(amount * BROKER_FEE_RATE), BROKER_FEE_MIN);
  const sellFee = Math.max(Math.round(amount * BROKER_FEE_RATE), BROKER_FEE_MIN);
  const tax = Math.round(amount * TAX_RATE);
  return { amount, buyFee, sellFee, tax, total: buyFee + sellFee + tax };
}

// ── PnL badge ───────────────────────────────────────────────────────────
function PnlBadge({ pct, abs }: { pct: number | null; abs: number | null }) {
  if (pct == null) return <span className="text-zinc-400 text-xs">—</span>;
  const color = pct > 0
    ? "text-emerald-600 dark:text-emerald-400"
    : pct < 0
    ? "text-red-600 dark:text-red-400"
    : "text-zinc-500";
  return (
    <span className={`text-sm font-bold ${color}`}>
      {pct > 0 ? "+" : ""}{pct.toFixed(2)}%
      {abs != null && (
        <span className="text-[10px] font-normal ml-1 opacity-70">
          ({abs > 0 ? "+" : ""}{abs.toLocaleString("zh-TW")}元)
        </span>
      )}
    </span>
  );
}

// ── 來源 badge ──────────────────────────────────────────────────────────
function SourceBadge({ source }: { source: "user" | "algo" | "both" }) {
  const cfg = {
    user: { label: "手動", cls: "bg-blue-100/80 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 border-blue-200 dark:border-blue-700/40" },
    algo: { label: "演算法", cls: "bg-purple-100/80 dark:bg-purple-900/30 text-purple-600 dark:text-purple-300 border-purple-200 dark:border-purple-700/40" },
    both: { label: "手動+演算法", cls: "bg-indigo-100/80 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 border-indigo-200 dark:border-indigo-700/40" },
  }[source];
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

// ── 主卡片 ──────────────────────────────────────────────────────────────

interface HoldingCardProps {
  holding: MergedHolding;
  onRemove?: (stockId: string) => void;
  showManagement?: boolean;
}

export function HoldingCard({ holding, onRemove, showManagement }: HoldingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
  if (expanded && !shouldRender) setShouldRender(true);

  const h = holding;
  const actionCfg = ACTION_CONFIG[h.action];
  const { fullData, loading } = useOHLCV(h.stockId, expanded);
  const displayBars = fullData.length >= 2 ? fullData : h.ohlcv7d;
  const hasKLine = h.ohlcv7d.length >= 2;
  const hasBreakdown = !!(h.breakdown && (
    h.breakdown.fundamental > 0 || h.breakdown.technical > 0 ||
    h.breakdown.chipset > 0 || h.breakdown.bonus > 0
  ));
  const cycleCfg = h.cycleStage ? CYCLE_STAGE_CONFIG[h.cycleStage as CycleStageKey] : null;
  const cost = calcTradeCost(h.entryPrice, h.shares);

  // 卡片外框色彩依行動等級
  const borderCls =
    h.action === "出場" ? "border-red-300/60 dark:border-red-700/50 bg-red-50/20 dark:bg-red-950/15"
    : h.action === "減碼" ? "border-orange-300/60 dark:border-orange-700/50 bg-orange-50/20 dark:bg-orange-950/15"
    : h.action === "加碼" ? "border-emerald-200/60 dark:border-emerald-700/50 bg-emerald-50/20 dark:bg-emerald-950/15"
    : "border-zinc-200/60 dark:border-zinc-700/50 bg-white/70 dark:bg-zinc-900/50";

  return (
    <div className={`rounded-xl border overflow-hidden transition-shadow hover:shadow-md ${borderCls}`}>
      {/* ── Header ── */}
      <div className="px-3.5 pt-3 pb-2.5 space-y-2">
        {/* Row 1: ID + Name + Action badge */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0 flex-wrap">
            {/* 行動 badge */}
            <span className={`text-[11px] px-2 py-0.5 rounded-full font-bold ${actionCfg.chipCls}`}>
              {actionCfg.emoji} {actionCfg.label}
            </span>
            <span className="text-[15px] font-bold text-zinc-900 dark:text-zinc-100">{h.stockId}</span>
            {h.nameZh && h.nameZh !== h.stockId && (
              <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-24">{h.nameZh}</span>
            )}
            <span className={`text-xs font-bold ${
              h.grade === "A+" || h.grade === "A" ? "text-emerald-600 dark:text-emerald-400"
              : h.grade === "B" ? "text-blue-500" : "text-zinc-400"
            }`}>{h.grade}</span>
            <SourceBadge source={h.source} />
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {hasKLine && <MiniSparkline bars={h.ohlcv7d} />}
            <span className={`text-sm font-bold ${changePctColor(h.changePct)}`}>
              {formatChangePct(h.changePct)}
            </span>
          </div>
        </div>

        {/* Row 2: PnL + Sector + Cycle */}
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <PnlBadge pct={h.pnlPct} abs={h.pnlAbs} />
          {h.currentPrice != null && (
            <span className="text-zinc-400">現價 {h.currentPrice.toFixed(2)}</span>
          )}
          {h.daysHeld != null && (
            <span className="text-zinc-400">持有 {h.daysHeld} 天</span>
          )}
          {h.sectorName && (
            <span className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400">
              {h.sectorName}
            </span>
          )}
          {cycleCfg && (
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${cycleCfg.chipCls}`}>
              {cycleCfg.emoji} {cycleCfg.label}
            </span>
          )}
        </div>

        {/* Row 3: Signal dots + triggered tags */}
        {h.signals.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <SignalDots signals={h.signals} size="sm" />
            {h.triggered.slice(0, 4).map((t, i) => (
              <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                {(SIGNAL_NAMES[t] ?? t).slice(0, 3)}
              </span>
            ))}
          </div>
        )}

        {/* Row 4: Exit alert triggers */}
        {h.exitAlertTriggers.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {h.exitAlertScore != null && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${actionCfg.chipCls}`}>
                風險 {h.exitAlertScore}分
              </span>
            )}
            {h.exitAlertTriggers.map((t, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200/60 dark:border-red-700/40">
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Row 5: 進場資訊（所有來源都顯示） */}
        {(h.entryPrice != null || h.entryDate) && (
          <div className="flex items-center gap-3 text-[11px] text-zinc-500 dark:text-zinc-400">
            {h.entryPrice != null && <span>進場 {h.entryPrice.toFixed(2)}</span>}
            {h.entryDate && <span>📅 {h.entryDate}</span>}
            {h.shares != null && h.shares > 0 && <span>{h.shares.toLocaleString()} 股</span>}
            {cost && (
              <span className="text-red-500 dark:text-red-400">
                成本 ${cost.total.toLocaleString()}
              </span>
            )}
          </div>
        )}

        {/* Row 6: 演算法建議 */}
        {h.compositeScore != null && (
          <div className="flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
            <span className="font-medium">複合分 {h.compositeScore.toFixed(2)}</span>
            {h.weight != null && <span>權重 {(h.weight * 100).toFixed(0)}%</span>}
            {h.reason && <span className="truncate max-w-40 opacity-70">{h.reason}</span>}
          </div>
        )}

        {/* 展開按鈕 */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setExpanded(!expanded)}
            className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
              expanded
                ? "bg-blue-100/80 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                : "text-zinc-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20"
            }`}
          >
            📊 {expanded ? "收起分析" : "展開分析"}
          </button>
          {/* 管理按鈕（卡片底部） */}
          {showManagement && onRemove && h.source !== "algo" && (
            <button
              onClick={() => onRemove(h.stockId)}
              className="text-[11px] px-2 py-1 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              🗑 移除
            </button>
          )}
        </div>
      </div>

      {/* ── 展開分析區 ── */}
      {(hasKLine || hasBreakdown) && (
        <div
          className={`grid transition-[grid-template-rows,opacity] duration-300 ${expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
          onTransitionEnd={(e) => { if (!expanded && e.target === e.currentTarget) setShouldRender(false); }}
        >
          <div className="overflow-hidden min-h-0">
            {shouldRender && (
              <div className="border-t border-zinc-100 dark:border-zinc-800/50">
                <StockSummary
                  data={fullData.length > 0 ? fullData : h.ohlcv7d}
                  grade={h.grade}
                  breakdown={h.breakdown ?? undefined}
                  loading={loading}
                  triggered={h.triggered}
                  score={h.score}
                  sectorLevel={h.sectorLevel ?? undefined}
                  cycleStage={h.cycleStage ?? undefined}
                />
                {hasBreakdown && h.breakdown && <FactorRadar breakdown={h.breakdown} grade={h.grade} />}
                <CandlePatternBadges bars={displayBars} />
                <RsiGauge data={fullData} loading={loading} />
                <MacdChart data={fullData} loading={loading} />
                {hasKLine && (
                  <div className="px-1 py-1">
                    <StockKLine data={h.ohlcv7d} stockId={h.stockId} fullData={fullData.length > 0 ? fullData : undefined} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
