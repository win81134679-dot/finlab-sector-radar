"use client";
// TabContainer.tsx — 短線趨勢 / 最強訊號 / 長線趨勢 / 商品市場 Tab 切換（Client Component）

import { useState, useMemo } from "react";
import type { SignalSnapshot, HistoryIndex, CommoditySnapshot, MagaSnapshot, CompositeSnapshot, HoldingsSnapshot, PnlSnapshot, SensitivitySnapshot } from "@/lib/types";
import { MacroPanel } from "@/components/MacroPanel";
import { MacroWarningBanner } from "@/components/MacroWarningBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { SectorGrid } from "@/components/SectorGrid";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TrendSection } from "@/components/TrendSection";
import { CommodityPanel } from "@/components/CommodityPanel";
import { ConvergencePanel } from "@/components/ConvergencePanel";
import { LongTermPanel } from "@/components/LongTermPanel";
import { TrumpFeedPanel } from "@/components/TrumpFeedPanel";
import { UpdateButton } from "@/components/UpdateButton";

interface Props {
  snapshot:    Awaited<ReturnType<typeof import("@/lib/fetcher").fetchLatestSnapshot>>;
  historyIndex: HistoryIndex | null;
  commodities: CommoditySnapshot | null;
  magaData:    MagaSnapshot | null;
  composite:   CompositeSnapshot | null;
  sensitivity: SensitivitySnapshot | null;
  holdings:    HoldingsSnapshot | null;
  pnl:         PnlSnapshot | null;
}

type Tab = "sector" | "convergence" | "longterm" | "trumpfeed" | "commodity";

const TABS: { id: Tab; label: string }[] = [
  { id: "sector",      label: "短線趨勢 📊" },
  { id: "convergence", label: "雙線共振 🎯" },
  { id: "longterm",    label: "長線趨勢 📐" },
  { id: "trumpfeed",   label: "訊號來源 📡" },
  { id: "commodity",   label: "商品市場 🌐" },
];

function ResonanceBar({
  snapshot, composite, holdings, magaData,
}: {
  snapshot: Props["snapshot"];
  composite: CompositeSnapshot | null;
  holdings: HoldingsSnapshot | null;
  magaData: MagaSnapshot | null;
}) {
  const hotSectors = useMemo(() => {
    if (!snapshot?.sectors) return [];
    const holdingStockIds = new Set(Object.keys(holdings?.positions ?? {}));
    const magaBeneSectors = new Set(
      (magaData?.stocks ?? [])
        .filter((s) => s.category === "beneficiary")
        .map((s) => s.sector_id)
        .filter((id): id is string => Boolean(id))
    );
    return Object.entries(snapshot.sectors)
      .map(([id, sector]) => {
        let heat = 0;
        const badges: string[] = [];
        if (sector.level === "強烈關注") { heat += 3; badges.push(`短線 ${Math.round(sector.total)}燈`); }
        else if (sector.level === "觀察中") { heat += 1; }
        const cd = composite?.scores?.[id];
        if (cd) {
          if (cd.signal === "強烈買入")  { heat += 3; badges.push("長線強買"); }
          else if (cd.signal === "買入") { heat += 2; badges.push("長線買入"); }
          else if (cd.signal === "賣出")      { heat -= 1; }
          else if (cd.signal === "強烈賣出")  { heat -= 2; }
        }
        if (sector.stocks.some((s) => holdingStockIds.has(s.id))) { heat += 1; badges.push("持倉"); }
        if (magaBeneSectors.has(id)) { heat += 1; badges.push("MAGA"); }
        return { id, name: sector.name_zh, heat, level: sector.level, badges };
      })
      .filter((s) => s.heat >= 4 && s.level !== "忽略")
      .sort((a, b) => b.heat - a.heat)
      .slice(0, 6);
  }, [snapshot, composite, holdings, magaData]);

  if (hotSectors.length === 0) return null;

  return (
    <div className="border-b border-rose-200/50 dark:border-rose-900/40 bg-gradient-to-r from-rose-50/80 via-amber-50/50 to-transparent dark:from-rose-950/30 dark:via-amber-950/20 dark:to-transparent">
      <div className="max-w-screen-xl mx-auto px-4 py-2 flex items-center gap-3 overflow-x-auto">
        <span className="text-xs font-bold text-rose-600 dark:text-rose-400 shrink-0">🔥 全景共振</span>
        <div className="w-px h-3.5 bg-rose-200/80 dark:bg-rose-800/50 shrink-0" />
        <div className="flex gap-2">
          {hotSectors.map((s) => (
            <div
              key={s.id}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border shrink-0 ${
                s.heat >= 6
                  ? "bg-rose-100/90 dark:bg-rose-900/40 text-rose-800 dark:text-rose-200 border-rose-300/60 dark:border-rose-700/50"
                  : "bg-amber-100/90 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border-amber-300/60 dark:border-amber-700/50"
              }`}
            >
              {s.heat >= 6 ? "🔥" : "⚡"}
              <span>{s.name}</span>
              {s.badges.map((b, i) => (
                <span key={i} className="opacity-70 font-normal">· {b}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function TabContainer({ snapshot, historyIndex, commodities, magaData, composite, sensitivity, holdings, pnl }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("sector");

  const runAt  = snapshot?.run_at  ?? "";
  const date   = snapshot?.date    ?? "";
  const macro  = snapshot?.macro;
  const showMacroWarning = snapshot?.macro_warning === true || macro?.warning === true;

  return (
    <>
      {/* 橫幅（全局，不受 tab 影響）*/}
      {showMacroWarning && <MacroWarningBanner />}
      {runAt && <StaleDataBanner runAt={runAt} />}

      {/* Tab 導航列 */}
      <div className="sticky top-[var(--header-h,56px)] z-30 bg-[var(--bg-page)]/90 backdrop-blur-sm border-b border-zinc-200/40 dark:border-zinc-800/40">
        <div className="max-w-screen-xl mx-auto px-4 flex items-center gap-0.5 pt-1 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-500/5"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
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
      <main className="flex-1 max-w-screen-xl mx-auto w-full px-4 pb-12">
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

        {activeTab === "longterm" && (
          <ErrorBoundary label="長線趨勢">
            <LongTermPanel
              composite={composite}
              sensitivity={sensitivity}
              magaData={magaData}
              snapshot={snapshot}
              holdings={holdings}
              pnl={pnl}
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
      </main>
    </>
  );
}
