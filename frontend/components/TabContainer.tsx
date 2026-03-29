"use client";
// TabContainer.tsx — 板塊偵測 / 商品市場 / MAGA 追蹤 / 訊號雷達 / 組合管理 / 回測 Tab 切換（Client Component）

import { useState } from "react";
import type { SignalSnapshot, HistoryIndex, CommoditySnapshot, MagaSnapshot, CompositeSnapshot, HoldingsSnapshot, PnlSnapshot, BacktestSnapshot, SensitivitySnapshot } from "@/lib/types";
import { MacroPanel } from "@/components/MacroPanel";
import { MacroWarningBanner } from "@/components/MacroWarningBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { SectorGrid } from "@/components/SectorGrid";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TrendSection } from "@/components/TrendSection";
import { CommodityPanel } from "@/components/CommodityPanel";
import { MagaPanel } from "@/components/MagaPanel";
import { CompositePanel } from "@/components/CompositePanel";
import { PortfolioPanel } from "@/components/PortfolioPanel";
import { BacktestPanel } from "@/components/BacktestPanel";
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
  backtest:    BacktestSnapshot | null;
}

type Tab = "sector" | "commodity" | "maga" | "signal" | "portfolio" | "backtest";

const TABS: { id: Tab; label: string }[] = [
  { id: "sector",    label: "板塊偵測 🔍" },
  { id: "commodity", label: "商品市場 📊" },
  { id: "maga",      label: "MAGA 追蹤 🌐" },
  { id: "signal",    label: "訊號雷達 🎯" },
  { id: "portfolio", label: "組合管理 💼" },
  { id: "backtest",  label: "策略回測 📈" },
];

export function TabContainer({ snapshot, historyIndex, commodities, magaData, composite, sensitivity, holdings, pnl, backtest }: Props) {
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

        {activeTab === "signal" && (
          <div className="mt-6">
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-1">訊號雷達</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-5">NLP 分析 + 關稅矩陣複合評分，權重 50:50</p>
            <ErrorBoundary label="訊號雷達">
              <CompositePanel data={composite} sensitivity={sensitivity} />
            </ErrorBoundary>
          </div>
        )}

        {activeTab === "portfolio" && (
          <div className="mt-6">
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-1">組合管理</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-5">依複合評分建立的建議持倉與損益追蹤</p>
            <ErrorBoundary label="組合管理">
              <PortfolioPanel holdings={holdings} pnl={pnl} hasComposite={composite !== null} />
            </ErrorBoundary>
          </div>
        )}

        {activeTab === "backtest" && (
          <div className="mt-6">
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-1">策略回測</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-5">基於複合訊號閾值的歷史回測結果</p>
            <ErrorBoundary label="策略回測">
              <BacktestPanel data={backtest} />
            </ErrorBoundary>
          </div>
        )}
      </main>
    </>
  );
}
