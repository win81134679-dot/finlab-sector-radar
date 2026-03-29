"use client";
// YieldCurveChart.tsx — 美債收益率曲線圖（Recharts）

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { YieldPoint } from "@/lib/types";

interface Props {
  data: YieldPoint[];
  updated_at?: string;
}

// 2-10Y 利差
function calc_spread(data: YieldPoint[]): number | null {
  const y2 = data.find(d => d.tenor === "2Y");
  const y10 = data.find(d => d.tenor === "10Y");
  if (!y2 || !y10) return null;
  return parseFloat((y10.yield_pct - y2.yield_pct).toFixed(3));
}

export function YieldCurveChart({ data, updated_at }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-zinc-400 text-sm">
        收益率曲線資料暫無
      </div>
    );
  }

  const spread = calc_spread(data);
  const isInverted = spread !== null && spread < 0;

  return (
    <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-700/40 bg-white/60 dark:bg-zinc-800/40 backdrop-blur p-4">
      {/* 標題列 */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">
            美債殖利率曲線
          </h3>
          {updated_at && (
            <p className="text-[10px] text-zinc-400 mt-0.5">
              {new Date(updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
            </p>
          )}
        </div>
        <div className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
          isInverted
            ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
        }`}>
          {spread !== null ? (
            <>{isInverted ? "⚠ 倒掛" : "✓ 正常"} 2-10Y = {spread > 0 ? "+" : ""}{spread}%</>
          ) : "—"}
        </div>
      </div>

      {/* 收益率曲線圖 */}
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="yieldGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#60a5fa" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#60a5fa" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="yieldGradRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#f87171" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f87171" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--tw-border, #27272a)" opacity={0.3} />
          <XAxis
            dataKey="tenor"
            tick={{ fontSize: 11, fill: "#a1a1aa" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#a1a1aa" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
              color: "#e4e4e7",
            }}
            formatter={(value: number) => [`${value.toFixed(3)}%`, "殖利率"]}
          />
          {isInverted && (
            <ReferenceLine y={0} stroke="#f87171" strokeDasharray="4 4" strokeWidth={1} />
          )}
          <Area
            type="monotone"
            dataKey="yield_pct"
            stroke={isInverted ? "#f87171" : "#60a5fa"}
            strokeWidth={2}
            fill={isInverted ? "url(#yieldGradRed)" : "url(#yieldGrad)"}
            dot={{ r: 3, fill: isInverted ? "#f87171" : "#60a5fa", strokeWidth: 0 }}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* 底部：倒掛說明 */}
      {isInverted && (
        <p className="mt-2 text-[10px] text-red-500/80 dark:text-red-400/70 leading-relaxed">
          ⚠ 殖利率曲線倒掛：2Y &gt; 10Y。根據 Campbell &amp; Shiller (1991)，此現象為歷史上最可靠的衰退領先指標之一，平均領先 12–18 個月。
        </p>
      )}
    </div>
  );
}
