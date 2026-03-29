"use client";
// TabContainer.tsx — 短線趨勢 / 最強訊號 / 長線趨勢 / 商品市場 Tab 切換（Client Component）

import { useState } from "react";
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

type Tab = "sector" | "convergence" | "longterm" | "commodity";

const TABS: { id: Tab; label: string }[] = [
  { id: "sector",      label: "短線趨勢 📊" },
  { id: "convergence", label: "雙線共振 🎯" },
  { id: "longterm",    label: "長線趨勢 📐" },
  { id: "commodity",   label: "商品市場 🌐" },
];

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
              <SectorGrid data={snapshot} />
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

        {activeTab === "commodity" && (
          <ErrorBoundary label="商品市場">
            <CommodityPanel data={commodities} />
          </ErrorBoundary>
        )}
      </main>
    </>
  );
}
