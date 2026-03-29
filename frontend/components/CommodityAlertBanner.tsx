// CommodityAlertBanner.tsx — 商品市場訊號整合橫幅（取代純文字宏觀警示）
"use client";

import { useState } from "react";
import type { CommoditySnapshot } from "@/lib/types";

interface Props {
  commodities:  CommoditySnapshot | null;
  macroWarning: boolean;
}

const LEVEL_CONFIG = {
  risk_off: {
    icon:      "🚨",
    label:     "高度警戒",
    bg:        "bg-red-500/10 dark:bg-red-950/30 border-red-400/40 dark:border-red-800/50",
    text:      "text-red-700 dark:text-red-300",
    pill:      "bg-red-100/80 dark:bg-red-900/30 border-red-300/50 dark:border-red-700/40 text-red-700 dark:text-red-300",
    highPill:  "bg-red-200/80 dark:bg-red-800/40 border-red-400/60 dark:border-red-600/50 text-red-800 dark:text-red-200 font-bold",
  },
  caution: {
    icon:      "⚠️",
    label:     "注意",
    bg:        "bg-amber-500/10 dark:bg-amber-950/30 border-amber-400/40 dark:border-amber-800/50",
    text:      "text-amber-700 dark:text-amber-300",
    pill:      "bg-amber-100/80 dark:bg-amber-900/30 border-amber-300/50 dark:border-amber-700/40 text-amber-700 dark:text-amber-300",
    highPill:  "bg-amber-200/80 dark:bg-amber-800/40 border-amber-400/60 dark:border-amber-600/50 text-amber-800 dark:text-amber-200 font-bold",
  },
} as const;

export function CommodityAlertBanner({ commodities, macroWarning }: Props) {
  const [expanded, setExpanded] = useState(false);

  const summary  = commodities?.market_summary;
  const overall  = summary?.overall ?? "neutral";

  // 決定是否顯示
  const hasHighAlert = (summary?.high_count ?? 0) > 0 || overall === "risk_off";
  const hasCaution   = overall === "caution" || macroWarning;
  const shouldShow   = hasHighAlert || hasCaution;
  if (!shouldShow) return null;

  const cfg = hasHighAlert ? LEVEL_CONFIG.risk_off : LEVEL_CONFIG.caution;

  // 優先用 market_summary headline；fallback 到宏觀警示文字
  const headline =
    summary?.headline ??
    (macroWarning ? "宏觀環境燈7觸發，已出現異常信號，請提高風險意識" : "");

  const keyAlerts = summary?.key_alerts ?? [];

  return (
    <div role="alert" className={`w-full border-y ${cfg.bg}`}>
      <div className="max-w-screen-xl mx-auto px-4">

        {/* ── 主列 ── */}
        <div className="flex items-center gap-2.5 py-2 flex-wrap min-h-[2.25rem]">

          {/* 等級圖示 + 標籤 */}
          <span className="text-sm leading-none">{cfg.icon}</span>
          <span className={`text-xs font-bold shrink-0 ${cfg.text}`}>{cfg.label}</span>

          {summary && (
            <>
              <div className={`w-px h-3 ${cfg.text} opacity-20 shrink-0`} />

              {/* 統計丸 */}
              <div className="flex gap-1.5 items-center shrink-0 flex-wrap">
                <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${cfg.pill}`}>
                  觸發 {summary.total_triggered}
                </span>
                {summary.high_count > 0 && (
                  <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${cfg.highPill}`}>
                    高危 {summary.high_count}
                  </span>
                )}
                {summary.medium_count > 0 && (
                  <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${cfg.pill}`}>
                    中危 {summary.medium_count}
                  </span>
                )}
              </div>

              <div className={`w-px h-3 ${cfg.text} opacity-20 shrink-0`} />
            </>
          )}

          {/* 標題文字 */}
          {headline && (
            <span className={`text-xs ${cfg.text} opacity-80 flex-1 min-w-0 truncate`}>
              {headline}
            </span>
          )}

          {/* 展開按鈕 */}
          {keyAlerts.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className={`shrink-0 text-[11px] font-medium ${cfg.text} opacity-60 hover:opacity-100 transition-opacity whitespace-nowrap ml-auto`}
            >
              {expanded ? "收起 ▲" : `商品詳情 (${keyAlerts.length}) ▼`}
            </button>
          )}
        </div>

        {/* ── 展開的 key_alerts ── */}
        {expanded && keyAlerts.length > 0 && (
          <div className={`pb-3 pt-2 border-t ${cfg.text} border-current/10 space-y-1.5`}>
            {keyAlerts.slice(0, 6).map((alert, i) => (
              <div key={i} className="flex gap-2 text-xs">
                <span className={`${cfg.text} opacity-50 shrink-0 mt-0.5`}>▲</span>
                <span className={`${cfg.text} opacity-75 leading-snug`}>{alert}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
