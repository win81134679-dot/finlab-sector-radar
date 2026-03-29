// BacktestPanel.tsx — 回測結果面板（Tab #6）

"use client";

import type { BacktestSnapshot } from "@/lib/types";

interface Props {
  data: BacktestSnapshot | null;
}

export function BacktestPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">📊</span>
        <p className="text-sm">回測資料尚未生成</p>
        <p className="text-xs mt-1 opacity-60">需先完成複合評分分析</p>
      </div>
    );
  }

  const { results, portfolio_summary, strategy } = data;
  const tickers = Object.keys(results).sort(
    (a, b) => results[b].total_return_pct - results[a].total_return_pct
  );

  const returnColor = (v: number) =>
    v > 0 ? "text-emerald-600 dark:text-emerald-400" : v < 0 ? "text-red-500 dark:text-red-400" : "text-zinc-400";

  return (
    <div className="space-y-5">
      {/* ── 策略參數 ── */}
      <div className="flex flex-wrap gap-2">
        {[
          ["進場門檻", `${strategy.entry_threshold}`],
          ["出場門檻", `${strategy.exit_threshold}`],
          ["回測天數", `${strategy.lookback_days} 天`],
          ["初始資金", `${(strategy.initial_capital / 10000).toFixed(0)} 萬`],
          ["測試標的", `${data.tickers_tested} 支`],
        ].map(([label, val]) => (
          <div key={label} className="text-xs px-3 py-1.5 rounded-lg border border-zinc-200/40 dark:border-zinc-700/40 bg-zinc-50/60 dark:bg-zinc-900/40">
            <span className="text-zinc-400">{label}：</span>
            <span className="font-semibold text-zinc-700 dark:text-zinc-300">{val}</span>
          </div>
        ))}
      </div>

      {/* ── 組合摘要 ── */}
      {portfolio_summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="平均回報" value={`${portfolio_summary.avg_return_pct >= 0 ? "+" : ""}${portfolio_summary.avg_return_pct.toFixed(2)}%`}
            color={returnColor(portfolio_summary.avg_return_pct)} />
          <Stat label="平均勝率" value={`${Math.round(portfolio_summary.avg_win_rate * 100)}%`} />
          <Stat label="最佳標的" value={portfolio_summary.best_ticker} />
          <Stat label="最差標的" value={portfolio_summary.worst_ticker} />
        </div>
      )}

      {/* ── 個股回測表 ── */}
      <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/80 dark:bg-zinc-900/60">
                <th className="text-left px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">代號</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">名稱</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">總回報</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">勝率</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">交易次</th>
                <th className="text-right px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">最大回撤</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100/60 dark:divide-zinc-800/40">
              {tickers.map(ticker => {
                const r = results[ticker];
                return (
                  <tr key={ticker} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/20 transition-colors">
                    <td className="px-4 py-2 font-mono font-semibold text-zinc-800 dark:text-zinc-200">{ticker}</td>
                    <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400 truncate max-w-[8rem]">{r.name_zh}</td>
                    <td className={`px-3 py-2 text-right font-semibold ${returnColor(r.total_return_pct)}`}>
                      {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right text-zinc-600 dark:text-zinc-400">
                      {Math.round(r.win_rate * 100)}%
                    </td>
                    <td className="px-3 py-2 text-right text-zinc-500 dark:text-zinc-400">{r.trade_count}</td>
                    <td className={`px-4 py-2 text-right ${r.max_drawdown_pct < 0 ? "text-red-500 dark:text-red-400" : "text-zinc-400"}`}>
                      {r.max_drawdown_pct.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-[10px] text-zinc-400 dark:text-zinc-600 text-right">
        回測基準：複合評分 ≥ {strategy.entry_threshold} 進場，&lt; {strategy.exit_threshold} 出場 ·
        回測完成：{new Date(data.ran_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
      </p>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-lg font-bold ${color ?? "text-zinc-800 dark:text-zinc-200"}`}>{value}</p>
    </div>
  );
}
