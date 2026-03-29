// AccelerationPanel.tsx — 週期監控面板（加速期 / 過熱期板塊出場風險追蹤）
// 學術依據：de Kempenaer (2014), Grinblatt et al. (1995), Da et al. (2014)
"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { SignalSnapshot, CompositeSnapshot, HoldingsSnapshot, ExitRisk, OHLCBar } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";
import {
  changePctColor, formatChangePct,
  CYCLE_STAGE_CONFIG, type CycleStageKey,
  EXIT_RISK_CONFIG, type ExitRiskAction,
  SIGNAL_NAMES,
} from "@/lib/signals";

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
  const [loading, setLoading]   = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!enabled || fetchedRef.current || !GITHUB_RAW_BASE) return;
    fetchedRef.current = true;
    let cancelled = false;
    setLoading(true);
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
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] flex items-center justify-center text-zinc-400 text-xs">載入中...</div>
    ),
  }
);

interface Props {
  snapshot:  SignalSnapshot | null | undefined;
  composite: CompositeSnapshot | null;
  holdings:  HoldingsSnapshot | null;
}

interface AccSector {
  sectorId: string;
  nameZh: string;
  total: number;
  level: string;
  cycleStage: string;
  exitRisk: ExitRisk | null;
  rsMomentum: number | null;
  signals: number[];
  stocks: Array<{
    id: string;
    score: number | null;
    grade: string;
    changePct: number | null;
    priceFlag: string;
    triggered: string[];
    ohlcv7d?: OHLCBar[];
    breakdown?: { fundamental: number; technical: number; chipset: number; bonus: number };
    isHolding: boolean;
    exitAlert: boolean;
  }>;
}

// 風險進度條
function RiskBar({ score, action }: { score: number; action: string }) {
  const cfg = EXIT_RISK_CONFIG[action as ExitRiskAction] ?? EXIT_RISK_CONFIG["持有"];
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${cfg.barColor}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${cfg.chipCls}`}>
        {cfg.emoji} {score}分 · {cfg.label}
      </span>
    </div>
  );
}

function AccStockCard({ stock, sectorLevel, exitRisk, cycleStage, macroWarning }: {
  stock: AccSector["stocks"][number];
  sectorLevel: string;
  exitRisk: ExitRisk | null;
  cycleStage: string;
  macroWarning?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { fullData, loading } = useOHLCV(stock.id, expanded);
  const displayBars = fullData.length >= 2 ? fullData : (stock.ohlcv7d ?? []);
  const hasKLine = (stock.ohlcv7d?.length ?? 0) >= 2;
  const hasBreakdown = !!(stock.breakdown && (
    stock.breakdown.fundamental > 0 || stock.breakdown.technical > 0 ||
    stock.breakdown.chipset > 0 || stock.breakdown.bonus > 0
  ));

  const exitCfg = exitRisk ? EXIT_RISK_CONFIG[exitRisk.action as ExitRiskAction] : null;

  return (
    <div className={`rounded-xl border overflow-hidden ${
      stock.exitAlert
        ? "border-red-300/60 dark:border-red-700/50 bg-red-50/30 dark:bg-red-950/20"
        : "border-zinc-200/60 dark:border-zinc-700/50 bg-white/70 dark:bg-zinc-900/50"
    }`}>
      <div className="px-3.5 pt-3 pb-2.5 space-y-2">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[15px] font-bold text-zinc-900 dark:text-zinc-100">{stock.id}</span>
            <span className={`text-xs font-bold ${
              stock.grade === "A+" || stock.grade === "A" ? "text-emerald-600 dark:text-emerald-400"
              : stock.grade === "B" ? "text-blue-500" : "text-zinc-400"
            }`}>{stock.grade}</span>
            {stock.isHolding && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700/40">💼持倉</span>
            )}
            {stock.exitAlert && exitCfg && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${exitCfg.chipCls}`}>
                {exitCfg.emoji} {exitRisk?.action}
              </span>
            )}
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {hasKLine && <MiniSparkline bars={stock.ohlcv7d!} />}
            <span className={`text-sm font-bold ${changePctColor(stock.changePct)}`}>
              {formatChangePct(stock.changePct)}
            </span>
          </div>
        </div>

        {/* Triggered signals */}
        {stock.triggered.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {stock.triggered.slice(0, 4).map((t, i) => (
              <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                {(SIGNAL_NAMES[t] ?? t).slice(0, 3)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Expand */}
      {(hasKLine || hasBreakdown) && (
        <button
          onClick={() => setExpanded(!expanded)}
          className={`w-full flex items-center justify-center gap-1.5 py-1.5 text-[11px] border-t transition-colors ${
            expanded
              ? "border-blue-200/60 dark:border-blue-800/40 bg-blue-50/60 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
              : "border-zinc-100 dark:border-zinc-800/50 text-zinc-400 hover:text-blue-500"
          }`}
        >
          📊 {expanded ? "收起分析" : "展開分析"}
        </button>
      )}
      {expanded && (
        <div className="border-t border-zinc-100 dark:border-zinc-800/50">
          <StockSummary
            data={fullData.length > 0 ? fullData : (stock.ohlcv7d ?? [])}
            grade={stock.grade}
            breakdown={stock.breakdown}
            loading={loading}
            triggered={stock.triggered}
            score={stock.score}
            sectorLevel={sectorLevel}
            macroWarning={macroWarning}
            cycleStage={cycleStage}
          />
          {hasBreakdown && stock.breakdown && <FactorRadar breakdown={stock.breakdown} grade={stock.grade} />}
          <CandlePatternBadges bars={displayBars} />
          <RsiGauge data={fullData} loading={loading} />
          <MacdChart data={fullData} loading={loading} />
          {hasKLine && (
            <div className="px-1 py-1">
              <StockKLine data={stock.ohlcv7d!} stockId={stock.id} fullData={fullData.length > 0 ? fullData : undefined} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function AccelerationPanel({ snapshot, composite, holdings }: Props) {
  const macroWarning = snapshot?.macro_warning === true || snapshot?.macro?.warning === true;

  const accSectors = useMemo<AccSector[]>(() => {
    if (!snapshot?.sectors) return [];
    const holdingIds = new Set(Object.keys(holdings?.positions ?? {}));

    return Object.entries(snapshot.sectors)
      .filter(([, sec]) => sec.cycle_stage === "加速期" || sec.cycle_stage === "過熱期")
      .map(([sectorId, sec]) => ({
        sectorId,
        nameZh: sec.name_zh,
        total: sec.total,
        level: sec.level,
        cycleStage: sec.cycle_stage!,
        exitRisk: sec.exit_risk ?? null,
        rsMomentum: sec.rs_momentum ?? null,
        signals: sec.signals,
        stocks: (sec.stocks ?? [])
          .slice()
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
          .map((s) => ({
            id: s.id,
            score: s.score ?? null,
            grade: s.grade,
            changePct: s.change_pct ?? null,
            priceFlag: s.price_flag ?? "normal",
            triggered: s.triggered ?? [],
            ohlcv7d: s.ohlcv_7d,
            breakdown: s.breakdown,
            isHolding: holdingIds.has(s.id),
            exitAlert: sec.exit_risk?.action === "減碼" || sec.exit_risk?.action === "出場",
          })),
      }))
      .sort((a, b) => (b.exitRisk?.score ?? 0) - (a.exitRisk?.score ?? 0));
  }, [snapshot, holdings]);

  // 空狀態
  if (accSectors.length === 0) {
    return (
      <div className="mt-6">
        <div className="mb-5">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">週期監控 🔄</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">追蹤加速期 / 過熱期板塊的出場風險</p>
        </div>
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-600">
          <span className="text-4xl mb-3">🔄</span>
          <p className="text-sm font-medium">目前無加速期板塊</p>
          <p className="text-xs mt-1 opacity-60">所有板塊尚未進入加速期或過熱期，無需出場監控</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">週期監控 🔄</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            追蹤加速期 / 過熱期板塊 · 出場風險分由 RRG 象限 + 籌碼 + 宏觀 綜合評估
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs shrink-0">
          <span className="px-2.5 py-1 rounded-full bg-green-100/70 dark:bg-green-900/30 text-green-700 dark:text-green-300 font-medium border border-green-200/60 dark:border-green-800/40">
            {accSectors.length} 板塊
          </span>
          <span className="px-2.5 py-1 rounded-full bg-blue-100/70 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200/60 dark:border-blue-800/40">
            {accSectors.reduce((sum, s) => sum + s.stocks.length, 0)} 個股
          </span>
        </div>
      </div>

      {/* Sectors */}
      {accSectors.map((sec) => {
        const stageCfg = CYCLE_STAGE_CONFIG[sec.cycleStage as CycleStageKey];
        return (
          <section
            key={sec.sectorId}
            className="rounded-2xl border border-zinc-200/50 dark:border-zinc-700/40 bg-white/60 dark:bg-zinc-900/40 overflow-hidden"
          >
            {/* Sector header */}
            <div className="px-4 py-3.5 space-y-2.5 border-b border-zinc-100 dark:border-zinc-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-base font-bold text-zinc-900 dark:text-white">{sec.nameZh}</h3>
                  {stageCfg && (
                    <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium ${stageCfg.chipCls}`} title={stageCfg.tooltip}>
                      {stageCfg.emoji} {stageCfg.label}
                    </span>
                  )}
                  <span className="text-xs text-zinc-500">{sec.total.toFixed(1)} / 7 燈</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <SignalDots signals={sec.signals} size="sm" />
                </div>
              </div>

              {/* Exit risk bar */}
              {sec.exitRisk && (
                <RiskBar score={sec.exitRisk.score} action={sec.exitRisk.action} />
              )}

              {/* Triggers + RS info */}
              <div className="flex flex-wrap gap-2 text-[11px]">
                {sec.rsMomentum !== null && (
                  <span className={`px-2 py-0.5 rounded-full border ${
                    sec.rsMomentum >= 0
                      ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/40"
                      : "bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-300 border-red-200 dark:border-red-800/40"
                  }`}>
                    RS-Mom: {sec.rsMomentum >= 0 ? "+" : ""}{(sec.rsMomentum * 100).toFixed(2)}%
                  </span>
                )}
                {sec.exitRisk?.triggers.map((t, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-200/60 dark:border-zinc-700/40">
                    {t}
                  </span>
                ))}
              </div>
            </div>

            {/* Stocks grid */}
            <div className="p-3">
              {sec.stocks.length === 0 ? (
                <p className="text-sm text-zinc-400 text-center py-4">此板塊無個股資料</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {sec.stocks.map((stock) => (
                    <AccStockCard
                      key={stock.id}
                      stock={stock}
                      sectorLevel={sec.level}
                      exitRisk={sec.exitRisk}
                      cycleStage={sec.cycleStage}
                      macroWarning={macroWarning}
                    />
                  ))}
                </div>
              )}
            </div>
          </section>
        );
      })}

      {/* Citation */}
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 text-center pt-1 leading-relaxed">
        出場風險模型：de Kempenaer (2014) RRG Weakening · Grinblatt, Titman &amp; Wermers (1995) 籌碼反轉 · Da, Gurun &amp; Warachka (2014) Frog in the Pan
      </p>
    </div>
  );
}
