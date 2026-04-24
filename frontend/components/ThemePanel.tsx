"use client";
// ThemePanel.tsx — 風口主題選股面板（主題分組 + 綜合排名）

import { useState, useMemo } from "react";
import type { SectorData, StockData } from "@/lib/types";
import { THEMES } from "@/lib/themes";
import { changePctColor, formatChangePct } from "@/lib/signals";

interface ThemePanelProps {
  sectors: Record<string, SectorData>;
}

interface RankedStock extends StockData {
  sectorId: string;
  sectorName: string;
  sectorLevel: SectorData["level"];
  sectorTotal: number;
}

type ViewMode = "theme" | "overall";

// ── 產業等級 badge 樣式 ──────────────────────────────────────────────────
const LEVEL_BADGE: Record<string, string> = {
  "強烈關注": "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200/60 dark:border-red-700/40",
  "觀察中":   "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200/60 dark:border-amber-700/40",
  "忽略":     "bg-zinc-100 dark:bg-zinc-800/50 text-zinc-500 dark:text-zinc-400 border-zinc-200/60 dark:border-zinc-700/40",
};

const GRADE_LABEL: Record<string, string> = {
  "⭐⭐⭐": "text-emerald-600 dark:text-emerald-400",
  "⭐⭐":   "text-sky-600 dark:text-sky-400",
  "⭐":     "text-zinc-500 dark:text-zinc-400",
};

// ── 單支股票列 ──────────────────────────────────────────────────────────
function StockRow({ stock, rank }: { stock: RankedStock; rank: number }) {
  const changePct = stock.change_pct;
  const flag = stock.price_flag ?? "normal";

  return (
    <tr className="border-b border-zinc-100 dark:border-zinc-800 hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40 transition-colors">
      <td className="py-2 px-3 text-center text-xs text-zinc-400 font-mono w-8">{rank}</td>
      <td className="py-2 px-3">
        <div className="flex items-center gap-1.5">
          <span className="font-mono font-semibold text-sm text-zinc-900 dark:text-zinc-100">{stock.id}</span>
          {stock.name_zh && (
            <span className="text-xs text-zinc-500 dark:text-zinc-400 hidden sm:inline">{stock.name_zh}</span>
          )}
        </div>
      </td>
      <td className="py-2 px-3">
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${LEVEL_BADGE[stock.sectorLevel] ?? LEVEL_BADGE["忽略"]}`}>
          {stock.sectorName}
        </span>
      </td>
      <td className="py-2 px-3 text-center">
        <span className={`text-sm font-bold ${GRADE_LABEL[stock.grade] ?? ""}`}>
          {stock.grade || "—"}
        </span>
      </td>
      <td className="py-2 px-3 text-right font-semibold text-sm text-zinc-700 dark:text-zinc-300">
        {stock.score != null ? stock.score.toFixed(1) : "—"}
      </td>
      <td className="py-2 px-3 text-right text-sm font-bold">
        {flag === "halt" ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">停牌</span>
        ) : flag === "ex_div" ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">除權息</span>
        ) : (
          <span className={changePctColor(changePct)}>{formatChangePct(changePct)}</span>
        )}
      </td>
      <td className="py-2 px-3 hidden lg:table-cell">
        <div className="flex flex-wrap gap-1">
          {stock.triggered.slice(0, 3).map((t, i) => (
            <span key={i} className="text-[10px] px-1 py-0.5 rounded bg-zinc-100 dark:bg-zinc-700/50 text-zinc-500 dark:text-zinc-400">
              {t.length > 3 ? t.slice(0, 3) : t}
            </span>
          ))}
        </div>
      </td>
    </tr>
  );
}

// ── 股票表格（含 header）──────────────────────────────────────────────────
function StockTable({ stocks, showRank = true }: { stocks: RankedStock[]; showRank?: boolean }) {
  if (stocks.length === 0) return (
    <p className="text-center text-zinc-400 text-sm py-6">此主題目前無符合條件的股票</p>
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-zinc-400 dark:text-zinc-500 border-b border-zinc-200/40 dark:border-zinc-700/40 text-left">
            {showRank && <th className="py-1.5 px-3 text-center w-8">#</th>}
            <th className="py-1.5 px-3">股票</th>
            <th className="py-1.5 px-3">所屬板塊</th>
            <th className="py-1.5 px-3 text-center">評級</th>
            <th className="py-1.5 px-3 text-right">評分</th>
            <th className="py-1.5 px-3 text-right">漲跌</th>
            <th className="py-1.5 px-3 hidden lg:table-cell">觸發信號</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock, i) => (
            <StockRow key={`${stock.sectorId}-${stock.id}`} stock={stock} rank={i + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 主元件 ────────────────────────────────────────────────────────────────
export function ThemePanel({ sectors }: ThemePanelProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("theme");
  const [expandedTheme, setExpandedTheme] = useState<string | null>(null);

  // 建構每個主題的股票列表（去重：同一支股票只保留評分最高的那筆）
  const themeStocks = useMemo(() => {
    const result: Record<string, RankedStock[]> = {};

    for (const theme of THEMES) {
      const seen = new Map<string, RankedStock>(); // stockId → best ranked

      for (const sectorId of theme.sectorIds) {
        const sector = sectors[sectorId];
        if (!sector) continue;

        for (const stock of sector.stocks) {
          const existing = seen.get(stock.id);
          const score = stock.score ?? 0;
          if (!existing || score > (existing.score ?? 0)) {
            seen.set(stock.id, {
              ...stock,
              sectorId,
              sectorName: sector.name_zh,
              sectorLevel: sector.level,
              sectorTotal: sector.total,
            });
          }
        }
      }

      result[theme.id] = Array.from(seen.values())
        .sort((a, b) => {
          // 優先：板塊等級，其次：評分
          const levelOrder = { "強烈關注": 3, "觀察中": 2, "忽略": 1 };
          const la = levelOrder[a.sectorLevel] ?? 0;
          const lb = levelOrder[b.sectorLevel] ?? 0;
          if (lb !== la) return lb - la;
          return (b.score ?? 0) - (a.score ?? 0);
        });
    }

    return result;
  }, [sectors]);

  // 綜合排名：所有主題合併去重，按評分排序
  const overallRanking = useMemo(() => {
    const seen = new Map<string, RankedStock>();

    for (const theme of THEMES) {
      for (const stock of themeStocks[theme.id] ?? []) {
        const existing = seen.get(stock.id);
        if (!existing || (stock.score ?? 0) > (existing.score ?? 0)) {
          seen.set(stock.id, stock);
        }
      }
    }

    return Array.from(seen.values())
      .sort((a, b) => {
        const levelOrder = { "強烈關注": 3, "觀察中": 2, "忽略": 1 };
        const la = levelOrder[a.sectorLevel] ?? 0;
        const lb = levelOrder[b.sectorLevel] ?? 0;
        if (lb !== la) return lb - la;
        return (b.score ?? 0) - (a.score ?? 0);
      })
      .slice(0, 50); // 最多顯示 50 支
  }, [themeStocks]);

  const totalStocks = overallRanking.length;

  return (
    <div className="mt-6 space-y-6">
      {/* 標題 + 切換 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-white">風口選股 🎯</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            AI / 半導體 / 電動車 / 區塊鏈 跨板塊龍頭排名 · 共 {totalStocks} 支
          </p>
        </div>
        <div className="flex gap-1 p-1 bg-zinc-100 dark:bg-zinc-800/60 rounded-lg">
          <button
            onClick={() => setViewMode("theme")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              viewMode === "theme"
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            主題分組
          </button>
          <button
            onClick={() => setViewMode("overall")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              viewMode === "overall"
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            綜合排名
          </button>
        </div>
      </div>

      {/* ── 主題分組視圖 ────────────────────────────────────────────────── */}
      {viewMode === "theme" && (
        <div className="space-y-4">
          {THEMES.map((theme) => {
            const stocks = themeStocks[theme.id] ?? [];
            const isExpanded = expandedTheme === theme.id;
            const visibleStocks = isExpanded ? stocks : stocks.slice(0, 5);
            const hiddenCount = stocks.length - 5;
            const hotCount = stocks.filter((s) => s.sectorLevel === "強烈關注").length;
            const watchCount = stocks.filter((s) => s.sectorLevel === "觀察中").length;

            return (
              <div
                key={theme.id}
                className="border border-zinc-200/60 dark:border-zinc-700/40 rounded-xl overflow-hidden bg-white/50 dark:bg-zinc-900/40"
              >
                {/* 主題標頭 */}
                <div className="px-4 py-3 bg-zinc-50/80 dark:bg-zinc-800/40 border-b border-zinc-200/40 dark:border-zinc-700/30">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{theme.emoji}</span>
                      <div>
                        <h3 className="font-bold text-zinc-900 dark:text-white text-sm">{theme.label}</h3>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">{theme.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {hotCount > 0 && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200/60 font-medium">
                          🔥 強烈關注 {hotCount}支
                        </span>
                      )}
                      {watchCount > 0 && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200/60 font-medium">
                          ⚡ 觀察中 {watchCount}支
                        </span>
                      )}
                      <span className="text-[10px] text-zinc-400">共 {stocks.length} 支</span>
                    </div>
                  </div>

                  {/* 警示訊息 */}
                  {theme.warning && (
                    <div className="mt-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200/60 dark:border-amber-700/40">
                      <p className="text-xs text-amber-700 dark:text-amber-300">{theme.warning}</p>
                    </div>
                  )}
                </div>

                {/* 股票列表 */}
                <div>
                  <StockTable stocks={visibleStocks} />
                  {stocks.length > 5 && (
                    <button
                      onClick={() => setExpandedTheme(isExpanded ? null : theme.id)}
                      className="w-full py-2 text-xs text-zinc-400 hover:text-blue-500 dark:hover:text-blue-400
                                 border-t border-zinc-100 dark:border-zinc-800
                                 hover:bg-zinc-50/60 dark:hover:bg-zinc-800/30 transition-colors"
                    >
                      {isExpanded
                        ? "收起"
                        : `展開更多 (${hiddenCount} 支)`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── 綜合排名視圖 ────────────────────────────────────────────────── */}
      {viewMode === "overall" && (
        <div className="border border-zinc-200/60 dark:border-zinc-700/40 rounded-xl overflow-hidden bg-white/50 dark:bg-zinc-900/40">
          <div className="px-4 py-3 bg-zinc-50/80 dark:bg-zinc-800/40 border-b border-zinc-200/40 dark:border-zinc-700/30">
            <h3 className="font-bold text-zinc-900 dark:text-white text-sm">
              全風口族群 · 綜合排名 Top {overallRanking.length}
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              跨所有主題去重後，依「板塊等級 → 個股評分」排序。同一支股票只出現一次（取最高評分板塊）。
            </p>
          </div>
          <StockTable stocks={overallRanking} />
        </div>
      )}
    </div>
  );
}
