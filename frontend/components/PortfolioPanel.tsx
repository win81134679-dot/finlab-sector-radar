// PortfolioPanel.tsx — 建議持倉 + 損益面板（Tab #5）

"use client";

import { useState } from "react";
import type { HoldingsSnapshot, PnlSnapshot, ExitAlertsSnapshot, UserHoldingsSnapshot } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";
import { ExitAlertPanel } from "@/components/ExitAlertPanel";
import { UserHoldingsManager } from "@/components/UserHoldingsManager";

interface Props {
  holdings:      HoldingsSnapshot | null;
  pnl:           PnlSnapshot | null;
  hasComposite?: boolean;
  exitAlerts?:   ExitAlertsSnapshot | null;
  userHoldings?: UserHoldingsSnapshot | null;
}

function PnlBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-zinc-400">—</span>;
  const color = pct > 0 ? "text-emerald-500 dark:text-emerald-400" : pct < 0 ? "text-red-500 dark:text-red-400" : "text-zinc-400";
  return <span className={`font-semibold ${color}`}>{pct > 0 ? "+" : ""}{pct.toFixed(2)}%</span>;
}

export function PortfolioPanel({ holdings, pnl, hasComposite, exitAlerts, userHoldings }: Props) {
  const [view, setView] = useState<"user" | "algo">(userHoldings?.positions && Object.keys(userHoldings.positions).length > 0 ? "user" : "algo");
  const [refreshKey, setRefreshKey] = useState(0);

  if (!holdings && !userHoldings) {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-6">
        {/* Step 1 */}
        <div className={`flex items-center gap-3 px-5 py-3.5 rounded-xl border w-full max-w-sm ${
          hasComposite
            ? "border-emerald-300/60 dark:border-emerald-700/40 bg-emerald-50/60 dark:bg-emerald-900/20"
            : "border-zinc-200/40 dark:border-zinc-700/40 bg-zinc-50/60 dark:bg-zinc-900/30"
        }`}>
          <span className="text-xl">{hasComposite ? "✅" : "⬜"}</span>
          <div>
            <p className={`text-sm font-semibold ${
              hasComposite ? "text-emerald-700 dark:text-emerald-300" : "text-zinc-500 dark:text-zinc-400"
            }`}>Step 1：複合評分分析</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500">
              {hasComposite ? "NLP + 關稅矩陣評分已完成" : "尚未執行——請先執行 --auto"}
            </p>
          </div>
        </div>

        {/* 箭頭 */}
        <div className="text-zinc-300 dark:text-zinc-600 text-xl">↓</div>

        {/* Step 2 */}
        <div className="flex items-center gap-3 px-5 py-3.5 rounded-xl border border-zinc-200/40 dark:border-zinc-700/40 bg-zinc-50/60 dark:bg-zinc-900/30 w-full max-w-sm">
          <span className="text-xl">{hasComposite ? "⏳" : "⬜"}</span>
          <div>
            <p className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">Step 2：建議持倉生成</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500">
              {hasComposite
                ? "待下次 --auto 執行後即可顯示"
                : "需先完成 Step 1"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const positions = holdings?.positions ?? {};
  const tickers = Object.keys(positions).sort(
    (a, b) => (positions[b]?.composite_score ?? 0) - (positions[a]?.composite_score ?? 0)
  );

  const portfolioPnl = pnl?.portfolio_pnl_pct ?? null;
  const hasUserPositions = userHoldings?.positions && Object.keys(userHoldings.positions).length > 0;

  return (
    <div className="space-y-5">
      {/* ── 視圖切換 ── */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setView("user")}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
            view === "user"
              ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
              : "border-zinc-200/60 dark:border-zinc-700/40 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
          }`}
        >
          📌 我的持倉{hasUserPositions ? ` (${Object.keys(userHoldings!.positions).length})` : ""}
        </button>
        <button
          onClick={() => setView("algo")}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
            view === "algo"
              ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
              : "border-zinc-200/60 dark:border-zinc-700/40 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
          }`}
        >
          💡 演算法建議{tickers.length > 0 ? ` (${tickers.length})` : ""}
        </button>
      </div>

      {/* ── 我的持倉視圖 ── */}
      {view === "user" && (
        <UserHoldingsManager
          key={refreshKey}
          userHoldings={userHoldings ?? null}
          algoHoldings={holdings}
          onSaved={() => setRefreshKey(k => k + 1)}
        />
      )}

      {/* ── 演算法建議視圖 ── */}
      {view === "algo" && (
        <>
      {/* ── 隔日出場訊號提醒 ── */}
      <ExitAlertPanel exitAlerts={exitAlerts ?? null} pnl={pnl} />

      {/* ── 摘要列 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="持倉數" value={tickers.length.toString()} />
        <Stat label="總配重" value={`${Math.round((holdings?.total_weight ?? 0) * 100)}%`} />
        <Stat
          label="組合損益"
          value={portfolioPnl != null ? `${portfolioPnl > 0 ? "+" : ""}${portfolioPnl.toFixed(2)}%` : "—"}
          valueColor={portfolioPnl != null ? (portfolioPnl > 0 ? "text-emerald-500" : portfolioPnl < 0 ? "text-red-500" : undefined) : undefined}
        />
        <Stat label="更新時間" value={holdings?.updated_at ? new Date(holdings.updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"} />
      </div>

      {/* ── 持倉表格 ── */}
      <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/80 dark:bg-zinc-900/60">
                <th className="text-left px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">代號</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">名稱</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">板塊</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">複合分</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">配重</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">損益</th>
                <th className="text-right px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">持有天</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100/60 dark:divide-zinc-800/40">
              {tickers.map(ticker => {
                const pos = positions[ticker];
                const pnlPos = pnl?.positions[ticker];
                return (
                  <tr key={ticker} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/20 transition-colors">
                    <td className="px-4 py-2 font-mono font-semibold text-zinc-800 dark:text-zinc-200">{ticker}</td>
                    <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300 truncate max-w-28">{pos.name_zh}</td>
                    <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400 truncate max-w-24">{getSectorName(pos.sector)}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      <span className={pos.composite_score >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}>
                        {pos.composite_score >= 0 ? "+" : ""}{pos.composite_score.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-zinc-600 dark:text-zinc-400">
                      {Math.round(pos.weight * 100)}%
                    </td>
                    <td className="px-3 py-2 text-right">
                      <PnlBadge pct={pnlPos?.pnl_pct ?? null} />
                    </td>
                    <td className="px-4 py-2 text-right text-zinc-500 dark:text-zinc-400">
                      {pnlPos?.days_held ?? 0}d
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── 板塊分佈 ── */}
      {holdings && Object.keys(holdings.sector_weights).length > 0 && (
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-2">板塊配置</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(holdings.sector_weights)
              .sort((a, b) => b[1] - a[1])
              .map(([sector, w]) => (
                <div key={sector} className="text-xs px-2 py-1 rounded-lg border border-zinc-200/40 dark:border-zinc-700/40 bg-white/60 dark:bg-zinc-800/40">
                  <span className="text-zinc-500 dark:text-zinc-400">{sector}</span>
                  <span className="ml-1.5 font-semibold text-zinc-700 dark:text-zinc-300">{Math.round(w * 100)}%</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {pnl && (pnl.best_position || pnl.worst_position) && (
        <div className="flex flex-wrap gap-3 text-xs">
          {pnl.best_position && (
            <span className="text-emerald-600 dark:text-emerald-400">
              🏆 最佳：{pnl.best_position} <PnlBadge pct={pnl.positions[pnl.best_position]?.pnl_pct ?? null} />
            </span>
          )}
          {pnl.worst_position && (
            <span className="text-red-500 dark:text-red-400">
              ⚠️ 最差：{pnl.worst_position} <PnlBadge pct={pnl.positions[pnl.worst_position]?.pnl_pct ?? null} />
            </span>
          )}
        </div>
      )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold ${valueColor ?? "text-zinc-800 dark:text-zinc-200"}`}>{value}</p>
    </div>
  );
}
