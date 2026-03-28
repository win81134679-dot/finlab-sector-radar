"use client";
// StockTable.tsx — 板塊內個股排名表格（含 K 線展開）
import { useState } from "react";
import dynamic from "next/dynamic";
import type { StockData } from "@/lib/types";
import { changePctColor, formatChangePct, SIGNAL_NAMES } from "@/lib/signals";

// 動態載入 K 線圖，避免 SSR 問題
const StockKLine = dynamic(() => import("./StockKLine").then((m) => m.StockKLine), {
  ssr: false,
  loading: () => (
    <div className="h-[160px] flex items-center justify-center text-zinc-400 text-xs">
      載入中...
    </div>
  ),
});

interface StockTableProps {
  stocks: StockData[];
}

const GRADE_STARS: Record<string, string> = {
  "強烈關注": "⭐⭐⭐",
  "觀察中": "⭐⭐",
  "忽略": "⭐",
};

export function StockTable({ stocks }: StockTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!stocks || stocks.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400 text-center py-2">
        無個股資料
      </p>
    );
  }

  // 依評分由高到低排序
  const sorted = [...stocks].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-xs min-w-[340px]">
        <thead>
          <tr className="text-zinc-500 dark:text-zinc-400 border-b border-zinc-200/30 dark:border-zinc-700/30">
            <th className="py-1.5 px-2 text-left font-medium">股票</th>
            <th className="py-1.5 px-2 text-center font-medium">評級</th>
            <th className="py-1.5 px-2 text-right font-medium">評分</th>
            <th className="py-1.5 px-2 text-right font-medium">漲跌幅</th>
            <th className="py-1.5 px-2 text-left font-medium hidden sm:table-cell">觸發信號</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((stock) => (
            <StockRow
              key={stock.id}
              stock={stock}
              isExpanded={expandedId === stock.id}
              onToggle={() =>
                setExpandedId(expandedId === stock.id ? null : stock.id)
              }
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface StockRowProps {
  stock: StockData;
  isExpanded: boolean;
  onToggle: () => void;
}

function StockRow({ stock, isExpanded, onToggle }: StockRowProps) {
  const stars = GRADE_STARS[stock.grade] ?? "⭐";
  const changePct = stock.change_pct;
  const flag = stock.price_flag ?? "normal";
  const hasKLine = (stock.ohlcv_7d?.length ?? 0) >= 2;

  // 觸發信號縮寫（最多3個）
  const triggeredSignals = stock.triggered ?? [];
  const signalLabels = triggeredSignals
    .slice(0, 3)
    .map((key) => {
      const name = SIGNAL_NAMES[key] ?? key;
      return name.length > 2 ? name.slice(0, 2) : name;
    });

  return (
    <>
      <tr className="border-b border-zinc-200/20 dark:border-zinc-700/20 last:border-0
                     hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
        <td className="py-1.5 px-2">
          <div className="flex items-center gap-1">
            <span className="font-mono font-medium text-zinc-900 dark:text-zinc-100">
              {stock.id}
            </span>
            {hasKLine && (
              <button
                onClick={onToggle}
                title={isExpanded ? "收起K線" : "展開7日K線"}
                className={`text-[11px] leading-none transition-colors ${
                  isExpanded
                    ? "text-blue-500 dark:text-blue-400"
                    : "text-zinc-400 hover:text-blue-500 dark:hover:text-blue-400"
                }`}
              >
                📈
              </button>
            )}
          </div>
        </td>
        <td className="py-1.5 px-2 text-center">
          <span title={stock.grade}>{stars}</span>
        </td>
        <td className="py-1.5 px-2 text-right font-medium text-zinc-700 dark:text-zinc-300">
          {(stock.score ?? 0).toFixed(1)}
        </td>
        <td className="py-1.5 px-2 text-right font-bold">
          {flag === "halt" ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium
                             bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400
                             border border-red-200 dark:border-red-700/40">
              停牌
            </span>
          ) : flag === "ex_div" ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium
                             bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400
                             border border-amber-200 dark:border-amber-700/40">
              除權息
            </span>
          ) : (
            <span className={changePctColor(changePct)}>
              {formatChangePct(changePct)}
            </span>
          )}
        </td>
        <td className="py-1.5 px-2 hidden sm:table-cell">
          <div className="flex flex-wrap gap-1">
            {signalLabels.map((label, i) => (
              <span
                key={i}
                className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-700/50
                           text-zinc-600 dark:text-zinc-400 text-[10px]"
              >
                {label}
              </span>
            ))}
            {triggeredSignals.length > 3 && (
              <span className="text-zinc-400 text-[10px]">+{triggeredSignals.length - 3}</span>
            )}
          </div>
        </td>
      </tr>
      {isExpanded && hasKLine && (
        <tr className="border-b border-zinc-200/20 dark:border-zinc-700/20">
          <td colSpan={5} className="px-2 pb-2">
            <StockKLine data={stock.ohlcv_7d!} stockId={stock.id} />
          </td>
        </tr>
      )}
    </>
  );
}
