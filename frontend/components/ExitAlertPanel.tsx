// ExitAlertPanel.tsx — 隔日出場訊號提醒面板

"use client";

import { useState } from "react";
import type { ExitAlertsSnapshot, PnlSnapshot } from "@/lib/types";
import { EXIT_ALERT_CONFIG, type ExitAlertActionKey } from "@/lib/signals";

interface Props {
  exitAlerts: ExitAlertsSnapshot | null;
  pnl: PnlSnapshot | null;
}

function DeltaArrow({ delta }: { delta: number | null }) {
  if (delta == null) return <span className="text-zinc-400 text-[10px]">—</span>;
  if (delta >= 15) return <span className="text-red-500 font-bold text-xs">↑ +{delta}</span>;
  if (delta > 0) return <span className="text-orange-500 text-xs">↑ +{delta}</span>;
  if (delta < 0) return <span className="text-emerald-500 text-xs">↓ {delta}</span>;
  return <span className="text-zinc-400 text-xs">→ 0</span>;
}

function AlertBar({ score, action }: { score: number; action: string }) {
  const cfg = EXIT_ALERT_CONFIG[action as ExitAlertActionKey];
  const barColor = cfg?.barColor ?? "bg-zinc-400";
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-2 rounded-full bg-zinc-200/60 dark:bg-zinc-700/40 overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${Math.min(score, 100)}%` }} />
      </div>
      <span className="text-xs font-mono font-semibold text-zinc-600 dark:text-zinc-300 w-8 text-right">{score}</span>
    </div>
  );
}

function PnlBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-zinc-400">—</span>;
  const color = pct > 0 ? "text-emerald-500" : pct < 0 ? "text-red-500" : "text-zinc-400";
  return <span className={`font-semibold ${color}`}>{pct > 0 ? "+" : ""}{pct.toFixed(2)}%</span>;
}

export function ExitAlertPanel({ exitAlerts, pnl }: Props) {
  const [showMethodology, setShowMethodology] = useState(false);

  if (!exitAlerts) {
    return (
      <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-base">🛡️</span>
          <div>
            <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">隔日出場訊號</p>
            <p className="text-[11px] text-zinc-400 dark:text-zinc-500">尚未生成——待下次分析執行後更新</p>
          </div>
        </div>
      </div>
    );
  }

  const { summary, position_alerts, system_risk_level, systemic_sector_count } = exitAlerts;
  const hasAlerts = summary.exit_count + summary.reduce_count + summary.watch_count > 0;
  const totalPositions = summary.exit_count + summary.reduce_count + summary.watch_count + summary.safe_count;
  const updatedLabel = new Date(exitAlerts.updated_at).toLocaleString("zh-TW", {
    timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  // ── 全持倉安全狀態 ──
  if (!hasAlerts) {
    return (
      <div className="rounded-xl border border-emerald-200/60 dark:border-emerald-800/40 bg-gradient-to-r from-emerald-50/80 via-emerald-50/40 to-transparent dark:from-emerald-900/20 dark:via-emerald-900/10 dark:to-transparent px-4 py-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-emerald-100/80 dark:bg-emerald-900/40">
              <span className="text-lg">🛡️</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
                全持倉安全 — 無離場訊號
              </p>
              <p className="text-[11px] text-emerald-600/70 dark:text-emerald-400/60 mt-0.5">
                {totalPositions} 檔持倉皆通過五因子出場檢測，明日無需操作
              </p>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-100/60 dark:bg-emerald-900/30">
              <span className="text-xs">✅</span>
              <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">{summary.safe_count} 檔安全</span>
            </div>
            <span className="text-[10px] text-zinc-400 dark:text-zinc-500">{updatedLabel}</span>
          </div>
        </div>
        {/* 手機版：第二行摘要 */}
        <div className="flex sm:hidden items-center gap-3 mt-2 ml-12">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-100/60 dark:bg-emerald-900/30">
            <span className="text-xs">✅</span>
            <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">{summary.safe_count} 檔安全</span>
          </div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500">{updatedLabel}</span>
        </div>
      </div>
    );
  }

  // 排序：出場 > 減碼 > 留意
  const ACTION_PRIORITY: Record<string, number> = { "出場": 0, "減碼": 1, "留意": 2 };
  const sortedAlerts = Object.entries(position_alerts)
    .sort(([, a], [, b]) => (ACTION_PRIORITY[a.action] ?? 9) - (ACTION_PRIORITY[b.action] ?? 9) || b.score - a.score);

  return (
    <div className="space-y-4 mb-6">
      {/* ── 系統風險橫幅 ── */}
      {system_risk_level === "elevated" && (
        <div className="rounded-xl border border-red-300/60 dark:border-red-700/40 bg-red-50/80 dark:bg-red-900/20 px-4 py-3 flex items-center gap-2">
          <span className="text-lg">⚠️</span>
          <div>
            <p className="text-sm font-bold text-red-700 dark:text-red-300">系統性風險升溫</p>
            <p className="text-xs text-red-600/80 dark:text-red-400/80">
              {systemic_sector_count} 個板塊同時觸發出場警戒（Condorcet 多數決理論）
            </p>
          </div>
        </div>
      )}

      {/* ── 隔日操作摘要 ── */}
      <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3">
        <div className="flex items-center justify-between mb-2.5">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">📋 隔日操作提醒</p>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500">{updatedLabel}</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {summary.exit_count > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-50/80 dark:bg-red-900/20 border border-red-200/60 dark:border-red-700/30">
              <span>🚨</span>
              <span className="text-xs font-semibold text-red-700 dark:text-red-300">出場 {summary.exit_count} 檔</span>
            </div>
          )}
          {summary.reduce_count > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-orange-50/80 dark:bg-orange-900/20 border border-orange-200/60 dark:border-orange-700/30">
              <span>🔶</span>
              <span className="text-xs font-semibold text-orange-700 dark:text-orange-300">減碼 {summary.reduce_count} 檔</span>
            </div>
          )}
          {summary.watch_count > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-yellow-50/80 dark:bg-yellow-900/20 border border-yellow-200/60 dark:border-yellow-700/30">
              <span>⚡</span>
              <span className="text-xs font-semibold text-yellow-700 dark:text-yellow-300">留意 {summary.watch_count} 檔</span>
            </div>
          )}
          {summary.safe_count > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50/80 dark:bg-emerald-900/20 border border-emerald-200/60 dark:border-emerald-700/30">
              <span>✅</span>
              <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">安全 {summary.safe_count} 檔</span>
            </div>
          )}
        </div>
      </div>

      {/* ── 持倉警報清單 ── */}
      <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/80 dark:bg-zinc-900/60">
                <th className="text-left px-4 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">操作</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">代號</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">板塊</th>
                <th className="px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400 text-center">警報分數</th>
                <th className="px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400 text-center">趨勢</th>
                <th className="text-right px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400">損益</th>
                <th className="text-left px-3 py-2.5 font-medium text-zinc-500 dark:text-zinc-400 hidden sm:table-cell">觸發因子</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100/60 dark:divide-zinc-800/40">
              {sortedAlerts.map(([ticker, alert]) => {
                const cfg = EXIT_ALERT_CONFIG[alert.action as ExitAlertActionKey];
                const pnlPct = pnl?.positions[ticker]?.pnl_pct ?? null;
                return (
                  <tr key={ticker} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/20 transition-colors">
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold ${cfg?.chipCls ?? ""}`}>
                        {cfg?.emoji} {cfg?.label}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">{ticker}</span>
                      <span className="ml-1.5 text-zinc-500 dark:text-zinc-400">{alert.name_zh}</span>
                    </td>
                    <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400 truncate max-w-24">{alert.sector_name}</td>
                    <td className="px-3 py-2.5 w-32">
                      <AlertBar score={alert.score} action={alert.action} />
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <DeltaArrow delta={alert.delta} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <PnlBadge pct={pnlPct} />
                    </td>
                    <td className="px-3 py-2.5 hidden sm:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {alert.triggers.slice(0, 3).map((t, i) => (
                          <span key={i} className="inline-block px-1.5 py-0.5 text-[10px] rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 truncate max-w-40" title={t}>
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── 學術方法論折疊區 ── */}
      <button
        onClick={() => setShowMethodology(!showMethodology)}
        className="text-[11px] text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
      >
        {showMethodology ? "▼" : "▶"} 學術方法論：五因子出場警報模型
      </button>
      {showMethodology && (
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3 text-[11px] text-zinc-600 dark:text-zinc-400 space-y-1.5">
          <p className="font-semibold text-zinc-700 dark:text-zinc-300">五因子加權模型（權重按學術預測力排序）</p>
          <ul className="list-disc ml-4 space-y-0.5">
            <li><strong>RRG 象限衰退 (30%)</strong> — de Kempenaer (2014) J. Technical Analysis</li>
            <li><strong>出場風險加速度 (25%)</strong> — Da, Engelberg &amp; Gao (2014) Review of Financial Studies</li>
            <li><strong>籌碼信號熄滅 (20%)</strong> — Grinblatt, Titman &amp; Wermers (1995) AER</li>
            <li><strong>量價背離 (15%)</strong> — Lo, Mamaysky &amp; Wang (2000) Journal of Finance</li>
            <li><strong>多板塊共振衰退 (10%)</strong> — Condorcet (1785) 多數決理論</li>
          </ul>
          <p className="text-zinc-500 dark:text-zinc-500 mt-1">
            ※ 權重反映學術文獻中各因子的預測顯著性，無回測最佳化。
          </p>
        </div>
      )}
    </div>
  );
}
