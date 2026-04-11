// MacroPanel.tsx — 4個宏觀大卡（美債/工業生產/SOX/台股）
"use client";

import type { MacroData } from "@/lib/types";

interface MacroCardProps {
  title: string;
  value: string | null;
  subtitle: string;
  trend?: "up" | "down" | "unknown" | null;
  positive?: boolean;
  icon: string;
}

function MacroCard({ title, value, subtitle, trend, positive, icon }: MacroCardProps) {
  const trendArrow = trend === "up" ? "▲" : trend === "down" ? "▼" : null;
  const trendColor =
    positive === true ? "text-emerald-400" :
    positive === false ? "text-red-400" :
    "text-zinc-400";

  return (
    <div className="glass-card-sm relative p-4 flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{title}</span>
        <span className="text-2xl">{icon}</span>
      </div>

      <div className="flex items-end gap-2">
        <span className="text-3xl font-bold text-zinc-900 dark:text-white tracking-tight">
          {value ?? "—"}
        </span>
        {trendArrow && (
          <span className={`text-lg font-semibold mb-0.5 ${trendColor}`}>
            {trendArrow}
          </span>
        )}
      </div>

      <p className={`text-xs font-medium ${trendColor}`}>
        {subtitle}
      </p>

      {/* 底部裝飾條 */}
      <div className={`absolute bottom-0 left-0 right-0 h-0.5 ${
        positive === true ? "bg-emerald-400/50" :
        positive === false ? "bg-red-400/50" :
        "bg-zinc-500/30"
      }`} />
    </div>
  );
}

interface MacroPanelProps {
  macro: MacroData | null;
}

export function MacroPanel({ macro }: MacroPanelProps) {
  if (!macro) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 opacity-30 pointer-events-none">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 rounded-2xl bg-zinc-200 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }
  return (
    <section aria-label="宏觀經濟指標" className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {/* 美國10年公債殖利率 */}
      <MacroCard
        title="美債 10Y 殖利率"
        value={macro.us_bond_10y != null ? `${macro.us_bond_10y.toFixed(2)}%` : null}
        subtitle={
          macro.bond_trend === "down"
            ? "下行趨勢 ✅ 利率寬鬆信號"
            : macro.bond_trend === "up"
            ? "上行趨勢 ❌ 利率走升"
            : macro.details?.bond ?? "資料載入中"
        }
        trend={macro.bond_trend}
        positive={macro.bond_trend === "down"}
        icon="🏛️"
      />

      {/* 美國工業生產指數 */}
      <MacroCard
        title="美國工業生產指數"
        value={macro.ip_index != null ? macro.ip_index.toFixed(1) : null}
        subtitle={
          macro.ip_trend === "up"
            ? "站上 12M 均線 ✅ 擴張期"
            : macro.ip_trend === "down"
            ? "低於 12M 均線 ❌ 收縮"
            : macro.details?.pmi ?? "資料載入中"
        }
        trend={macro.ip_trend}
        positive={macro.ip_trend === "up"}
        icon="🏭"
      />

      {/* 費半 SOXX */}
      <MacroCard
        title="費半 SOXX"
        value={macro.sox_price != null ? `$${macro.sox_price.toFixed(2)}` : null}
        subtitle={
          macro.sox_trend === "up"
            ? "站上 20MA ✅ 科技週期上行"
            : macro.sox_trend === "down"
            ? "低於 20MA ❌ 週期下行"
            : macro.details?.sox ?? "資料載入中"
        }
        trend={macro.sox_trend}
        positive={macro.sox_trend === "up"}
        icon="💾"
      />

      {/* 宏觀燈號摘要 */}
      <MacroCard
        title="宏觀環境評分"
        value={`${macro.positive_count}/${macro.total_available}`}
        subtitle={
          macro.warning
            ? "⚠️ 宏觀警示啟動 — 謹慎評估"
            : "✅ 宏觀環境正面"
        }
        positive={!macro.warning}
        icon="🌐"
      />
    </section>
  );
}
