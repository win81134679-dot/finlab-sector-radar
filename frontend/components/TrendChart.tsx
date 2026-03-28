// TrendChart.tsx — Recharts 歷史趨勢折線圖 (必須 dynamic import, ssr:false)
"use client";

import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, CartesianGrid
} from "recharts";
import type { HistoryIndex } from "@/lib/types";
import { HISTORY_RANGE_DAYS } from "@/lib/signals";
import { format, parseISO } from "date-fns";
import { zhTW } from "date-fns/locale";

// 預定義折線顏色（依板塊主題，循環使用）
const LINE_COLORS = [
  "#FF4D4F", "#FAAD14", "#52c41a", "#1677ff", "#722ed1",
  "#eb2f96", "#fa8c16", "#13c2c2", "#2f54eb", "#a0d911",
];

interface TrendChartProps {
  historyIndex: HistoryIndex | null;
  range: number;           // 天數: 7 | 14 | 30 | 90
  topSectors?: string[];   // 只繪製前 N 個板塊（預設前5）
}

interface ChartDataPoint {
  date: string;
  displayDate: string;
  [sector: string]: number | string;
}

export function TrendChart({ historyIndex, range, topSectors }: TrendChartProps) {
  if (!historyIndex || !historyIndex.dates || historyIndex.dates.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-zinc-500 dark:text-zinc-400 text-sm">
        無歷史資料
      </div>
    );
  }

  // 依 range 截取最近 N 天
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - range);
  const cutoffStr = cutoff.toISOString().slice(0, 10);

  const filteredDates = historyIndex.dates.filter((d) => d >= cutoffStr);

  // 取出需要展示的板塊（前5個出現在 sectors 資料中的）
  const allSectors = historyIndex.sectors && historyIndex.sectors.totals
    ? Object.keys(historyIndex.sectors.totals)
    : [];

  const displaySectors = topSectors && topSectors.length > 0
    ? topSectors.slice(0, 5)
    : allSectors.slice(0, 5);

  // 組裝 Recharts 資料陣列
  const chartData: ChartDataPoint[] = filteredDates.map((date) => {
    const idx = historyIndex.dates.indexOf(date);
    const point: ChartDataPoint = {
      date,
      displayDate: format(parseISO(date), "M/d", { locale: zhTW }),
    };
    for (const sectorId of displaySectors) {
      const totals = historyIndex.sectors?.[sectorId]?.totals;
      if (totals && Array.isArray(totals)) {
        point[sectorId] = totals[idx] ?? 0;
      }
    }
    return point;
  });

  if (chartData.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-zinc-500 dark:text-zinc-400 text-sm">
        此區間無資料
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
        <XAxis
          dataKey="displayDate"
          tick={{ fontSize: 11, fill: "#a1a1aa" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={[0, 7]}
          ticks={[0, 1, 2, 3, 4, 5, 6, 7]}
          tick={{ fontSize: 11, fill: "#a1a1aa" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1c1c1e",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 12,
            color: "#e4e4e7",
            fontSize: 12,
          }}
          labelStyle={{ color: "#a1a1aa", marginBottom: 4 }}
          formatter={(value: number, name: string) => [
            `${Number(value).toFixed(1)} 燈`,
            name,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(value) => (
            <span style={{ color: "#a1a1aa" }}>{value}</span>
          )}
        />
        {displaySectors.map((sectorId, i) => (
          <Line
            key={sectorId}
            type="monotone"
            dataKey={sectorId}
            name={historyIndex.sectors?.[sectorId]?.name_zh ?? sectorId}
            stroke={LINE_COLORS[i % LINE_COLORS.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
