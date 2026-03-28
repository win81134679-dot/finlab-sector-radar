// StockTable.tsx — 板塊內個股排名表格
import type { StockData } from "@/lib/types";
import { changePctColor, formatChangePct, SIGNAL_NAMES } from "@/lib/signals";

interface StockTableProps {
  stocks: StockData[];
}

const GRADE_STARS: Record<string, string> = {
  "強烈關注": "⭐⭐⭐",
  "觀察中": "⭐⭐",
  "忽略": "⭐",
};

export function StockTable({ stocks }: StockTableProps) {
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
            <StockRow key={stock.id} stock={stock} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StockRow({ stock }: { stock: StockData }) {
  const stars = GRADE_STARS[stock.grade] ?? "⭐";
  const changePct = stock.change_pct;
  const changeCls = changePctColor(changePct);

  // 觸發信號縮寫（最多3個）
  const triggeredSignals = stock.triggered ?? [];
  const signalLabels = triggeredSignals
    .slice(0, 3)
    .map((key) => {
      const name = SIGNAL_NAMES[key] ?? key;
      // 取前2個字
      return name.length > 2 ? name.slice(0, 2) : name;
    });

  return (
    <tr className="border-b border-zinc-200/20 dark:border-zinc-700/20 last:border-0
                   hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
      <td className="py-1.5 px-2">
        <span className="font-mono font-medium text-zinc-900 dark:text-zinc-100">
          {stock.id}
        </span>
      </td>
      <td className="py-1.5 px-2 text-center">
        <span title={stock.grade}>{stars}</span>
      </td>
      <td className="py-1.5 px-2 text-right font-medium text-zinc-700 dark:text-zinc-300">
        {(stock.score ?? 0).toFixed(1)}
      </td>
      <td className={`py-1.5 px-2 text-right font-bold ${changeCls}`}>
        {formatChangePct(changePct)}
      </td>
      <td className="py-1.5 px-2 hidden sm:table-cell">
        <div className="flex flex-wrap gap-1">
          {signalLabels.map((label, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 rounded bg-zinc-200/50 dark:bg-zinc-700/50
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
  );
}
