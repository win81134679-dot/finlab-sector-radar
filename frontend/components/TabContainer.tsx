"use client";
// TabContainer.tsx — 板塊偵測 / 商品市場 / MAGA 追蹤 Tab 切換（Client Component）

import { useState } from "react";
import type { SignalSnapshot, HistoryIndex, CommoditySnapshot, MagaSnapshot } from "@/lib/types";
import { MacroPanel } from "@/components/MacroPanel";
import { MacroWarningBanner } from "@/components/MacroWarningBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { SectorGrid } from "@/components/SectorGrid";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TrendSection } from "@/components/TrendSection";
import { CommodityPanel } from "@/components/CommodityPanel";
import { MagaPanel } from "@/components/MagaPanel";
import { UpdateButton } from "@/components/UpdateButton";

interface Props {
  snapshot: Awaited<ReturnType<typeof import("@/lib/fetcher").fetchLatestSnapshot>>;
  historyIndex: HistoryIndex | null;
  commodities: CommoditySnapshot | null;
  magaData: MagaSnapshot | null;
}

type Tab = "sector" | "commodity" | "maga";

const TABS: { id: Tab; label: string }[] = [
  { id: "sector",    label: "板塊偵測 🔍" },
  { id: "commodity", label: "商品市場 📊" },
  { id: "maga",      label: "MAGA 追蹤 🇺🇸" },
];

export function TabContainer({ snapshot, historyIndex, commodities, magaData }: Props) {
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
        <div className="max-w-screen-xl mx-auto px-4 flex items-center gap-1 pt-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
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

        {activeTab === "commodity" && (
          <ErrorBoundary label="商品市場">
            <CommodityPanel data={commodities} />
          </ErrorBoundary>
        )}

        {activeTab === "maga" && (
          <ErrorBoundary label="MAGA 追蹤">
            <MagaPanel data={magaData} snapshot={snapshot} />
          </ErrorBoundary>
        )}
      </main>
    </>
  );
}
