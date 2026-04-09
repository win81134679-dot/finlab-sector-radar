// AccelerationPanel.tsx — 週期監控面板（加速期 / 過熱期板塊出場風險追蹤）
// 學術依據：de Kempenaer (2014), Grinblatt et al. (1995), Da et al. (2014)
"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { SignalSnapshot, CompositeSnapshot, HoldingsSnapshot, PnlSnapshot, ExitAlertsSnapshot, ExitRisk, OHLCBar, UserHoldingsSnapshot } from "@/lib/types";
import type { StockNamesMap } from "@/lib/fetcher";
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
import { ExitAlertPanel } from "./ExitAlertPanel";
import { PortfolioPanel } from "./PortfolioPanel";

const GITHUB_RAW_BASE = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

function useOHLCV(stockId: string, enabled: boolean) {
  const [fullData, setFullData] = useState<OHLCBar[]>([]);
  const [loading, setLoading]   = useState(false);
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
  {
    ssr: false,
    loading: () => (
      <div className="h-50 flex items-center justify-center text-zinc-400 text-xs">載入中...</div>
    ),
  }
);

interface Props {
  snapshot:  SignalSnapshot | null | undefined;
  composite: CompositeSnapshot | null;
  holdings:  HoldingsSnapshot | null;
  exitAlerts?: ExitAlertsSnapshot | null;
  pnl?:       PnlSnapshot | null;
  userHoldings?: UserHoldingsSnapshot | null;
  stockNames?:    StockNamesMap | null;
}

type AccSubTab = "monitor" | "holdings";

const ACC_SUB_TABS: { id: AccSubTab; label: string }[] = [
  { id: "monitor",  label: "板塊監控 🔄" },
  { id: "holdings", label: "我的持倉 📌" },
];

interface AccStock {
  id: string;
  nameZh: string;
  score: number | null;
  grade: string;
  changePct: number | null;
  priceFlag: string;
  triggered: string[];
  ohlcv7d?: OHLCBar[];
  breakdown?: { fundamental: number; technical: number; chipset: number; bonus: number };
  isHolding: boolean;
  exitAlert: boolean;
}

interface AccSector {
  sectorId: string;
  nameZh: string;
  total: number;
  level: string;
  cycleStage: string;
  exitRisk: ExitRisk | null;
  rsMomentum: number | null;
  constituentCount: number;
  signals: number[];
  stocks: AccStock[];
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

function AccStockCard({ stock, sectorLevel, exitRisk, cycleStage, macroWarning, expanded }: {
  stock: AccStock;
  sectorLevel: string;
  exitRisk: ExitRisk | null;
  cycleStage: string;
  macroWarning?: boolean;
  expanded: boolean;
}) {
  const [shouldRender, setShouldRender] = useState(expanded);
  if (expanded && !shouldRender) setShouldRender(true);

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
            {stock.nameZh && (
              <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-20">{stock.nameZh}</span>
            )}
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

      {/* Expanded detail (controlled by sector-level toggle) */}
      {(hasKLine || hasBreakdown) && (
        <div
          className={`grid transition-[grid-template-rows,opacity] duration-300 ${expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
          onTransitionEnd={(e) => { if (!expanded && e.target === e.currentTarget) setShouldRender(false); }}
        >
          <div className="overflow-hidden min-h-0">
            {shouldRender && (
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
        </div>
      )}
    </div>
  );
}

export function AccelerationPanel({ snapshot, holdings, exitAlerts, pnl, userHoldings, stockNames }: Props) {
  const macroWarning = snapshot?.macro_warning === true || snapshot?.macro?.warning === true;
  const [expandedSectors, setExpandedSectors] = useState<Record<string, boolean>>({});
  const [accSubTab, setAccSubTab] = useState<AccSubTab>("monitor");

  // 完整 stockLookup：stockNames.json（全部股票）+ snapshot（即時資料優先）
  const stockLookup = useMemo(() => {
    const lookup: Record<string, { name_zh: string; sector: string }> = {};
    // 1. 先填入完整對照表（stock_names.json）
    if (stockNames) {
      for (const [id, entry] of Object.entries(stockNames)) {
        lookup[id] = { name_zh: entry.name_zh, sector: entry.sector };
      }
    }
    // 2. snapshot 資料覆蓋（更即時）
    if (snapshot?.sectors) {
      for (const [sectorId, sec] of Object.entries(snapshot.sectors)) {
        for (const stock of sec.stocks) {
          lookup[stock.id] = { name_zh: stock.name_zh ?? stock.id, sector: sectorId };
        }
      }
    }
    return lookup;
  }, [snapshot, stockNames]);

  const toggleSector = (sectorId: string) => {
    setExpandedSectors((prev) => ({ ...prev, [sectorId]: !prev[sectorId] }));
  };

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
        constituentCount: sec.constituent_count ?? sec.stocks?.length ?? 0,
        signals: sec.signals,
        stocks: (sec.stocks ?? [])
          .slice()
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
          .map((s) => ({
            id: s.id,
            nameZh: s.name_zh ?? "",
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
      .sort((a, b) => {
        // 加速期(0) 排在過熱期(1) 前面：安心持有 → 準備出場
        const cw: Record<string, number> = { "加速期": 0, "過熱期": 1 };
        const ca = cw[a.cycleStage] ?? 2;
        const cb = cw[b.cycleStage] ?? 2;
        if (ca !== cb) return ca - cb;
        // 同週期：低出場風險優先
        const ea = a.exitRisk?.score ?? 0;
        const eb = b.exitRisk?.score ?? 0;
        if (ea !== eb) return ea - eb;
        // 同風險：總分高優先
        return b.total - a.total;
      });
  }, [snapshot, holdings]);

  // 統計
  const totalStocks = accSectors.reduce((sum, s) => sum + s.stocks.length, 0);
  const holdingCount = accSectors.reduce((sum, s) => sum + s.stocks.filter(st => st.isHolding).length, 0);
  const avgRisk = accSectors.length > 0
    ? Math.round(accSectors.reduce((sum, s) => sum + (s.exitRisk?.score ?? 0), 0) / accSectors.length)
    : 0;
  const allExpanded = accSectors.length > 0 && accSectors.every((s) => expandedSectors[s.sectorId]);

  const toggleAll = () => {
    const nextVal = !allExpanded;
    const next: Record<string, boolean> = {};
    for (const s of accSectors) next[s.sectorId] = nextVal;
    setExpandedSectors(next);
  };

  // 空狀態（板塊監控子標籤仍可切到持倉）
  const monitorEmpty = accSectors.length === 0;

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
            {totalStocks} 個股
          </span>
          {holdingCount > 0 && (
            <span className="px-2.5 py-1 rounded-full bg-amber-100/70 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-medium border border-amber-200/60 dark:border-amber-800/40">
              💼 {holdingCount} 持倉
            </span>
          )}
        </div>
      </div>

      {/* 子分頁導航 */}
      <div className="flex gap-1 p-1 rounded-lg bg-zinc-100/70 dark:bg-zinc-800/70 w-fit">
        {ACC_SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setAccSubTab(tab.id)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors font-medium ${
              accSubTab === tab.id
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── 板塊監控子標籤 ── */}
      {accSubTab === "monitor" && (
        <>
          {monitorEmpty ? (
            <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-600">
              <span className="text-4xl mb-3">🔄</span>
              <p className="text-sm font-medium">目前無加速期板塊</p>
              <p className="text-xs mt-1 opacity-60">所有板塊尚未進入加速期或過熱期，無需出場監控</p>
            </div>
          ) : (
            <>
      {/* Summary bar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-700/40">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500 dark:text-zinc-400">平均風險分</span>
          <span className={`font-bold ${avgRisk >= 56 ? "text-red-500" : avgRisk >= 31 ? "text-amber-500" : "text-emerald-500"}`}>
            {avgRisk}
          </span>
        </div>
        <div className="h-4 w-px bg-zinc-200 dark:bg-zinc-700" />
        {accSectors.map((sec) => {
          const eCfg = sec.exitRisk ? EXIT_RISK_CONFIG[sec.exitRisk.action as ExitRiskAction] : null;
          return (
            <span key={sec.sectorId} className="flex items-center gap-1 text-xs">
              <span className="font-medium text-zinc-700 dark:text-zinc-300">{sec.nameZh}</span>
              {eCfg && <span className={`px-1.5 py-0.5 rounded ${eCfg.chipCls}`}>{eCfg.emoji}{sec.exitRisk?.score}</span>}
            </span>
          );
        })}
        <div className="flex-1" />
        <button
          onClick={toggleAll}
          className="text-xs text-blue-500 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
        >
          📊 {allExpanded ? "全部收起" : "全部展開分析"}
        </button>
      </div>

      {/* Sectors */}
      {accSectors.map((sec) => {
        const stageCfg = CYCLE_STAGE_CONFIG[sec.cycleStage as CycleStageKey];
        const isExpanded = !!expandedSectors[sec.sectorId];
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
                  <span className="text-xs text-zinc-400">· {sec.stocks.length}/{sec.constituentCount} 檔{sec.constituentCount > sec.stocks.length ? ` (${sec.constituentCount - sec.stocks.length} 檔未達門檻)` : ''}</span>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <SignalDots signals={sec.signals} size="sm" />
                  <button
                    onClick={() => toggleSector(sec.sectorId)}
                    className={`px-2.5 py-1 rounded-lg transition-colors ${
                      isExpanded
                        ? "bg-blue-100/80 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                        : "text-zinc-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                    }`}
                  >
                    📊 {isExpanded ? "收起" : "展開分析"}
                  </button>
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
                {sec.exitRisk?.rs_quadrant && (
                  <span className="px-2 py-0.5 rounded-full bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-300 border border-purple-200 dark:border-purple-800/40">
                    RRG: {sec.exitRisk.rs_quadrant}
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
                      expanded={isExpanded}
                    />
                  ))}
                </div>
              )}
            </div>
          </section>
        );
      })}

      {/* ── 持倉隔日操作建議（獨立區塊） ── */}
      {exitAlerts && (
        <div className="border-t border-zinc-200/60 dark:border-zinc-700/40 pt-5">
          <div className="mb-3">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">📋 持倉隔日操作建議</h3>
            <p className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-0.5">
              💡 根據 RRG 動能、籌碼、量價等五因子模型產生，僅供參考
            </p>
          </div>
          <ExitAlertPanel exitAlerts={exitAlerts} pnl={pnl ?? null} />
        </div>
      )}

      {/* Citation */}
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 text-center pt-1 leading-relaxed">
        出場風險模型：de Kempenaer (2014) RRG Weakening · Grinblatt, Titman &amp; Wermers (1995) 籌碼反轉 · Da, Gurun &amp; Warachka (2014) Frog in the Pan
      </p>
            </>
          )}
        </>
      )}

      {/* ── 我的持倉子標籤 ── */}
      {accSubTab === "holdings" && (
        <PortfolioPanel
          holdings={holdings}
          pnl={pnl ?? null}
          exitAlerts={exitAlerts}
          userHoldings={userHoldings}
          stockLookup={stockLookup}
        />
      )}
    </div>
  );
}
