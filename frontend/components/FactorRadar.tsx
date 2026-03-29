"use client";
// FactorRadar.tsx — 四因子雷達圖（Recharts RadarChart）
// 學術基礎：
//   基本面 → Piotroski F-Score (2000, Journal of Accounting Research)
//   技術面 → Jegadeesh & Titman 動量 (1993, Journal of Finance)
//   籌碼面 → 三大法人共振（台股市場獨特因子）
//   加分   → Graham 安全邊際估值（PE＋ROE）

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Breakdown {
  fundamental: number;
  technical:   number;
  chipset:     number;
  bonus:       number;
}

const AXES = [
  { key: "fundamental" as const, label: "基本面", max: 5.5 },
  { key: "technical"   as const, label: "技術面", max: 3.5 },
  { key: "chipset"     as const, label: "籌碼面", max: 4.0 },
  { key: "bonus"       as const, label: "加分",   max: 2.0 },
];

export function FactorRadar({
  breakdown,
  grade,
}: {
  breakdown: Breakdown;
  grade:     string;
}) {
  const data = AXES.map(({ key, label, max }) => ({
    axis:  label,
    // 歸一化成百分比（方便雷達圖各軸等長）
    value: parseFloat(((breakdown[key] / max) * 100).toFixed(1)),
    raw:   breakdown[key],
    max,
  }));

  // 顏色對應成績
  const color =
    grade === "A+" || grade === "A" ? "#10b981" :
    grade === "B"                   ? "#3b82f6" : "#a1a1aa";

  return (
    <div className="px-3 pt-2 pb-2 border-b border-zinc-100 dark:border-zinc-800/50">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-wide">
          因子強度分析
        </span>
        <span className="text-[10px] text-zinc-400">
          面積越大 = 三面越均衡強勢
        </span>
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <RadarChart data={data} margin={{ top: 10, right: 24, bottom: 10, left: 24 }}>
          <PolarGrid stroke="rgba(113,113,122,0.25)" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fontSize: 10, fill: "#a1a1aa" }}
          />
          <Radar
            dataKey="value"
            stroke={color}
            fill={color}
            fillOpacity={0.20}
            strokeWidth={1.5}
          />
          <Tooltip
            formatter={(value: number) => [`${value}%`, "填充度"]}
            contentStyle={{
              fontSize: 11,
              borderRadius: 8,
              border: "1px solid rgba(113,113,122,0.25)",
              padding: "4px 8px",
            }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* 原始得分/滿分明細 */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-zinc-400 mt-0.5">
        {AXES.map(({ key, label, max }) => (
          <span key={key}>
            <span className="text-zinc-500 dark:text-zinc-300 font-medium">{label}</span>{" "}
            <span className="font-mono">{breakdown[key].toFixed(1)}/{max}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
