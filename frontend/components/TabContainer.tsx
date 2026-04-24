"use client";
// TabContainer.tsx — 短線趨勢 / 最強訊號 / 長線趨勢 / 商品市場 Tab 切換（Client Component）

import { useState, useMemo } from "react";
import type { HistoryIndex, CommoditySnapshot, MagaSnapshot, CompositeSnapshot, HoldingsSnapshot, PnlSnapshot, SensitivitySnapshot, ExitAlertsSnapshot, UserHoldingsSnapshot } from "@/lib/types";
import type { StockNamesMap } from "@/lib/fetcher";
import { MacroPanel } from "@/components/MacroPanel";
import { CommodityAlertBanner } from "@/components/CommodityAlertBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { SectorGrid } from "@/components/SectorGrid";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TrendSection } from "@/components/TrendSection";
import { CommodityPanel } from "@/components/CommodityPanel";
import { ConvergencePanel } from "@/components/ConvergencePanel";
import { LongTermPanel } from "@/components/LongTermPanel";
import { TrumpFeedPanel } from "@/components/TrumpFeedPanel";
import { AccelerationPanel } from "@/components/AccelerationPanel";
import { HoldingsTab } from "@/components/HoldingsTab";
import { UpdateButton } from "@/components/UpdateButton";
import { ThemePanel } from "@/components/ThemePanel";

interface Props {
  snapshot:    Awaited<ReturnType<typeof import("@/lib/fetcher").fetchLatestSnapshot>>;
  historyIndex: HistoryIndex | null;
  commodities: CommoditySnapshot | null;
  magaData:    MagaSnapshot | null;
  composite:   CompositeSnapshot | null;
  sensitivity: SensitivitySnapshot | null;
  holdings:    HoldingsSnapshot | null;
  pnl:         PnlSnapshot | null;
  exitAlerts:  ExitAlertsSnapshot | null;
  userHoldings: UserHoldingsSnapshot | null;
  stockNames:   StockNamesMap | null;
}

type Tab = "sector" | "themes" | "convergence" | "acceleration" | "longterm" | "trumpfeed" | "commodity" | "holdings";

const TABS: { id: Tab; label: string }[] = [
  { id: "sector",       label: "短線趨勢 📊" },
  { id: "themes",       label: "風口選股 🎯" },
  { id: "convergence",  label: "雙線共振 🎯" },
  { id: "acceleration", label: "週期監控 🔄" },
  { id: "longterm",     label: "長線趨勢 📐" },
  { id: "trumpfeed",    label: "訊號來源 📡" },
  { id: "commodity",    label: "商品市場 🌐" },
  { id: "holdings",     label: "我的持倉 📌" },
];

function ResonanceBar({
  snapshot, composite, holdings, magaData,
}: {
  snapshot: Props["snapshot"];
  composite: CompositeSnapshot | null;
  holdings: HoldingsSnapshot | null;
  magaData: MagaSnapshot | null;
}) {
  const result = useMemo(() => {
    if (!snapshot?.sectors) return { hotSectors: [], dangerSectors: [] };

    const holdingStockIds = new Set(Object.keys(holdings?.positions ?? {}));
    const magaBeneSectors = new Set(
      (magaData?.stocks ?? [])
        .filter((s) => s.category === "beneficiary")
        .map((s) => s.sector_id)
        .filter((id): id is string => Boolean(id))
    );
    const magaVictimSectors = new Set(
      (magaData?.stocks ?? [])
        .filter((s) => s.category === "victim")
        .map((s) => s.sector_id)
        .filter((id): id is string => Boolean(id))
    );

    const hot:    Array<{ id: string; name: string; heat: number;   level: string; badges: string[] }> = [];
    const danger: Array<{ id: string; name: string; danger: number; level: string; badges: string[] }> = [];

    for (const [id, sector] of Object.entries(snapshot.sectors)) {
      const cd  = composite?.scores?.[id];
      const nlp = (cd as { nlp?: number } | undefined)?.nlp ?? 0;

      // ── 進攻側 ──
      let heat = 0;
      const hBadges: string[] = [];
      if (sector.level === "強烈關注") { heat += 3; hBadges.push(`短線 ${Math.round(sector.total)}燈`); }
      else if (sector.level === "觀察中") { heat += 1; }
      if (cd) {
        if (cd.signal === "強烈買入")  { heat += 3; hBadges.push("長線強買"); }
        else if (cd.signal === "買入") { heat += 2; hBadges.push("長線買入"); }
        else if (cd.signal === "賣出")       { heat -= 1; }
        else if (cd.signal === "強烈賣出")   { heat -= 2; }
      }
      if (sector.stocks.some((s) => holdingStockIds.has(s.id))) { heat += 1; hBadges.push("持倉"); }
      if (magaBeneSectors.has(id)) { heat += 1; hBadges.push("MAGA"); }
      if (heat >= 4 && sector.level !== "忽略") {
        hot.push({ id, name: sector.name_zh, heat, level: sector.level, badges: hBadges });
      }

      // ── 危險側 ──
      let dHeat = 0;
      const dBadges: string[] = [];
      if (cd) {
        if (cd.signal === "強烈賣出") { dHeat += 3; dBadges.push("長線強賣"); }
        else if (cd.signal === "賣出") { dHeat += 2; dBadges.push("長線賣出"); }
        if (nlp < -0.25) { dHeat += 1; dBadges.push("NLP空方"); }
      }
      if (sector.level === "觀察中" && dHeat >= 1) { dHeat += 1; dBadges.push("短線異動"); }
      if (magaVictimSectors.has(id)) { dHeat += 1; dBadges.push("MAGA受害"); }
      if (dHeat >= 2) {
        danger.push({ id, name: sector.name_zh, danger: dHeat, level: sector.level, badges: dBadges });
      }
    }

    return {
      hotSectors:    hot.sort((a, b) => b.heat - a.heat).slice(0, 5),
      dangerSectors: danger.sort((a, b) => b.danger - a.danger).slice(0, 4),
    };
  }, [snapshot, composite, holdings, magaData]);

  const { hotSectors, dangerSectors } = result;
  if (hotSectors.length === 0 && dangerSectors.length === 0) return null;

  return (
    <div className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40">
      <div className="max-w-7xl mx-auto px-4 py-1.5 flex items-center gap-2.5 overflow-x-auto">

        {/* 進攻側 */}
        {hotSectors.length > 0 && (
          <>
            <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 shrink-0">🔥 進攻機會</span>
            <div className="w-px h-3.5 bg-zinc-300 dark:bg-zinc-700 shrink-0" />
            <div className="flex gap-1.5">
              {hotSectors.map((s) => (
                <div
                  key={s.id}
                  className={`flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium border shrink-0 ${
                    s.heat >= 7
                      ? "bg-emerald-100/90 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 border-emerald-300/60 dark:border-emerald-700/50"
                      : s.heat >= 5
                      ? "bg-sky-100/90 dark:bg-sky-900/40 text-sky-800 dark:text-sky-200 border-sky-300/60 dark:border-sky-700/50"
                      : "bg-amber-100/90 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border-amber-300/60 dark:border-amber-700/50"
                  }`}
                >
                  {s.heat >= 7 ? "🔥" : s.heat >= 5 ? "⚡" : "↗️"}
                  <span>{s.name}</span>
                  {s.badges.map((b, i) => (
                    <span key={i} className="opacity-60 font-normal">· {b}</span>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}

        {/* 分隔 */}
        {hotSectors.length > 0 && dangerSectors.length > 0 && (
          <div className="w-px h-4 bg-zinc-300 dark:bg-zinc-600 shrink-0 mx-1" />
        )}

        {/* 危險側 */}
        {dangerSectors.length > 0 && (
          <>
            <span className="text-[11px] font-bold text-red-600 dark:text-red-400 shrink-0">🛡️ 警戒危險</span>
            <div className="w-px h-3.5 bg-zinc-300 dark:bg-zinc-700 shrink-0" />
            <div className="flex gap-1.5">
              {dangerSectors.map((s) => (
                <div
                  key={s.id}
                  className={`flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium border shrink-0 ${
                    s.danger >= 4
                      ? "bg-red-100/90 dark:bg-red-900/40 text-red-800 dark:text-red-200 border-red-300/60 dark:border-red-700/50"
                      : "bg-orange-100/90 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200 border-orange-300/60 dark:border-orange-700/50"
                  }`}
                >
                  {s.danger >= 4 ? "🚨" : "⚠️"}
                  <span>{s.name}</span>
                  {s.badges.map((b, i) => (
                    <span key={i} className="opacity-60 font-normal">· {b}</span>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function TabContainer({ snapshot, historyIndex, commodities, magaData, composite, sensitivity, holdings, pnl, exitAlerts, userHoldings, stockNames }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("sector");

  const runAt  = snapshot?.run_at  ?? "";
  const macro  = snapshot?.macro;
  const showMacroWarning = snapshot?.macro_warning === true || macro?.warning === true;

  return (
    <>
      {/* 商品市場警示橫幅（取代純文字宏觀警示）*/}
      <CommodityAlertBanner commodities={commodities} macroWarning={showMacroWarning} />
      {runAt && <StaleDataBanner runAt={runAt} />}

      {/* Tab 導航列 */}
      <div className="sticky top-(--header-h,56px) z-30 bg-(--bg-page)/90 header-glass border-b border-zinc-200/40 dark:border-white/6">
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-0.5 pt-1 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-500/5"
              }`}
            >
              {tab.label}
            </button>
          ))}
          {/* 立刻更新按鈕（密碼保護）*/}
          <UpdateButton currentRunAt={runAt} />
        </div>
      </div>

      {/* 全景共振袝 */}
      <ResonanceBar
        snapshot={snapshot}
        composite={composite}
        holdings={holdings}
        magaData={magaData}
      />

      {/* Tab 內容 */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 pb-12">
        {activeTab === "sector" && (
          <>
            <section className="mt-6" aria-label="宏觀經濟">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-3">宏觀環境</h2>
              <ErrorBoundary label="宏觀面板">
                <MacroPanel macro={macro ?? null} />
              </ErrorBoundary>
            </section>
            <ErrorBoundary label="板塊偵測">
              <SectorGrid data={snapshot} composite={composite} />
            </ErrorBoundary>
            <ErrorBoundary label="歷史圖表">
              <TrendSection historyIndex={historyIndex} snapshot={snapshot} />
            </ErrorBoundary>
          </>
        )}

        {activeTab === "themes" && snapshot?.sectors && (
          <ErrorBoundary label="風口選股">
            <ThemePanel sectors={snapshot.sectors} />
          </ErrorBoundary>
        )}

        {activeTab === "convergence" && (
          <ErrorBoundary label="最強訊號">
            <ConvergencePanel
              snapshot={snapshot}
              composite={composite}
              holdings={holdings}
              magaData={magaData}
            />
          </ErrorBoundary>
        )}

        {activeTab === "acceleration" && (
          <ErrorBoundary label="週期監控">
            <AccelerationPanel
              snapshot={snapshot}
              composite={composite}
              holdings={holdings}
              exitAlerts={exitAlerts}
              pnl={pnl}
            />
          </ErrorBoundary>
        )}

        {activeTab === "longterm" && (
          <ErrorBoundary label="長線趨勢">
            <LongTermPanel
              composite={composite}
              sensitivity={sensitivity}
              magaData={magaData}
              snapshot={snapshot}
              holdings={holdings}
              pnl={pnl}
              exitAlerts={exitAlerts}
              userHoldings={userHoldings}
            />
          </ErrorBoundary>
        )}

        {activeTab === "trumpfeed" && (
          <ErrorBoundary label="訊號來源">
            <TrumpFeedPanel />
          </ErrorBoundary>
        )}

        {activeTab === "commodity" && (
          <ErrorBoundary label="商品市場">
            <CommodityPanel data={commodities} />
          </ErrorBoundary>
        )}

        {activeTab === "holdings" && (
          <ErrorBoundary label="我的持倉">
            <HoldingsTab
              snapshot={snapshot}
              holdings={holdings}
              userHoldings={userHoldings}
              pnl={pnl}
              exitAlerts={exitAlerts}
              stockNames={stockNames}
            />
          </ErrorBoundary>
        )}
      </main>
    </>
  );
}
