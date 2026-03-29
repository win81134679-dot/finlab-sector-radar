// LongTermPanel.tsx — 長線趨勢面板（3 子分頁）
// 子分頁：訊號分析 | MAGA 政策 | 建議持倉

"use client";

import { useState } from "react";
import type {
  CompositeSnapshot,
  SensitivitySnapshot,
  MagaSnapshot,
  SignalSnapshot,
  HoldingsSnapshot,
  PnlSnapshot,
} from "@/lib/types";
import { CompositePanel } from "@/components/CompositePanel";
import { MagaPanel } from "@/components/MagaPanel";
import { PortfolioPanel } from "@/components/PortfolioPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";

interface Props {
  composite:   CompositeSnapshot | null;
  sensitivity: SensitivitySnapshot | null;
  magaData:    MagaSnapshot | null;
  snapshot:    SignalSnapshot | null | undefined;
  holdings:    HoldingsSnapshot | null;
  pnl:         PnlSnapshot | null;
}

type SubTab = "signal" | "maga" | "portfolio";

const SUB_TABS: { id: SubTab; label: string }[] = [
  { id: "signal",    label: "訊號分析" },
  { id: "maga",      label: "MAGA 政策" },
  { id: "portfolio", label: "建議持倉" },
];

export function LongTermPanel({
  composite,
  sensitivity,
  magaData,
  snapshot,
  holdings,
  pnl,
}: Props) {
  const [subTab, setSubTab] = useState<SubTab>("signal");

  return (
    <div className="mt-6">
      {/* 子分頁導航 */}
      <div className="flex gap-1 p-1 rounded-lg bg-zinc-100/70 dark:bg-zinc-800/70 w-fit mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors font-medium ${
              subTab === tab.id
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 訊號分析 */}
      {subTab === "signal" && (
        <>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-1">長線訊號分析</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-5">
            NLP 分析 + 關稅矩陣複合評分，權重 50:50
          </p>
          <ErrorBoundary label="訊號分析">
            <CompositePanel data={composite} sensitivity={sensitivity} />
          </ErrorBoundary>
        </>
      )}

      {/* MAGA 政策 */}
      {subTab === "maga" && (
        <ErrorBoundary label="MAGA 政策">
          <MagaPanel data={magaData} snapshot={snapshot} />
        </ErrorBoundary>
      )}

      {/* 建議持倉 */}
      {subTab === "portfolio" && (
        <>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white mb-1">建議持倉</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-5">
            依複合評分建立的建議持倉與損益追蹤
          </p>
          <ErrorBoundary label="建議持倉">
            <PortfolioPanel
              holdings={holdings}
              pnl={pnl}
              hasComposite={composite !== null}
            />
          </ErrorBoundary>
        </>
      )}
    </div>
  );
}
