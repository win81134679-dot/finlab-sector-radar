"use client";
// YieldCurveChart.tsx — 美債收益率曲線圖（Recharts）+ 學術信號面板

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
import type { YieldPoint, YieldCurveAnalysis } from "@/lib/types";

interface Props {
  data:        YieldPoint[];
  updated_at?: string;
  analysis?:   YieldCurveAnalysis;
}

const SEVERITY_STYLE: Record<string, string> = {
  high:   "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  low:    "bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border-zinc-500/20",
};

const SLOPE_LABEL: Record<string, string> = {
  inverted: "⚠ 倒掛",
  flat:     "⚡ 趨平",
  normal:   "✓ 正常",
  steep:    "↗ 陡峭",
  unknown:  "— 未知",
};
const SLOPE_STYLE: Record<string, string> = {
  inverted: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  flat:     "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  normal:   "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  steep:    "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  unknown:  "bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border-zinc-500/20",
};

function SpreadBadge({ label, value }: { label: string; value: number | null | undefined }) {
  if (value == null) return null;
  const positive = value >= 0;
  return (
    <div className="text-center">
      <div className={`text-xs font-mono font-semibold ${positive ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
        {value > 0 ? "+" : ""}{value.toFixed(2)}%
      </div>
      <div className="text-[9px] text-zinc-400 mt-0.5">{label}</div>
    </div>
  );
}

export function YieldCurveChart({ data, updated_at, analysis }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-zinc-400 text-sm">
        收益率曲線資料暫無
      </div>
    );
  }

  // 若無 analysis，從 data 自行計算基本指標
  const spread_2_10 = analysis?.spread_2_10
    ?? (() => {
      const y2 = data.find(d => d.tenor === "2Y");
      const y10 = data.find(d => d.tenor === "10Y");
      return y2 && y10 ? parseFloat((y10.yield_pct - y2.yield_pct).toFixed(3)) : null;
    })();

  const slopeSignal = analysis?.slope_signal ?? (
    spread_2_10 === null ? "unknown"
    : spread_2_10 < 0   ? "inverted"
    : spread_2_10 < 0.25 ? "flat"
    : spread_2_10 < 1.5  ? "normal"
    : "steep"
  );
  const isInverted = spread_2_10 !== null && spread_2_10 < 0;
  const triggeredSignals = (analysis?.signals ?? []).filter(s => s.triggered);

  return (
    <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-700/40 bg-white/60 dark:bg-zinc-800/40 backdrop-blur p-4 space-y-4">

      {/* ── 標題列 ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">美債殖利率曲線</h3>
          {updated_at && (
            <p className="text-[10px] text-zinc-400 mt-0.5">
              {new Date(updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
            </p>
          )}
        </div>
        <div className={`text-xs px-2.5 py-1 rounded-full font-medium border ${SLOPE_STYLE[slopeSignal] ?? SLOPE_STYLE.unknown}`}>
          {SLOPE_LABEL[slopeSignal]}
          {spread_2_10 !== null && <span className="ml-1 opacity-80">2-10Y={spread_2_10 > 0 ? "+" : ""}{spread_2_10}%</span>}
        </div>
      </div>

      {/* ── 利差摘要列 ─────────────────────────────────────────────── */}
      {analysis && (
        <div className="flex gap-6 justify-center py-2 border-y border-zinc-100/60 dark:border-zinc-700/40">
          <SpreadBadge label="2Y-10Y 利差" value={analysis.spread_2_10} />
          <SpreadBadge label="2Y-30Y 利差" value={analysis.spread_2_30} />
          <SpreadBadge label="10Y-30Y 利差" value={analysis.spread_10_30} />
        </div>
      )}

      {/* ── 收益率曲線圖 ────────────────────────────────────────────── */}
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

      {/* ── 學術信號面板 ─────────────────────────────────────────────── */}
      {analysis && analysis.signals.length > 0 && (
        <div className="space-y-2 pt-1">
          <div className="text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
            殖利率曲線學術信號
          </div>
          {analysis.signals.map(sig => (
            <div
              key={sig.key}
              className={`rounded-lg border px-3 py-2 text-[11px] ${SEVERITY_STYLE[sig.severity] ?? SEVERITY_STYLE.low}`}
            >
              <div className="flex items-start gap-2">
                <span className="shrink-0 mt-0.5">{sig.triggered ? "🔔" : "○"}</span>
                <div>
                  <p className="leading-relaxed">{sig.commentary}</p>
                  <p className="mt-1 opacity-60 text-[10px]">{sig.source}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 無 analysis 時的舊版倒掛說明 */}
      {!analysis && isInverted && (
        <p className="text-[10px] text-red-500/80 dark:text-red-400/70 leading-relaxed">
          ⚠ 殖利率曲線倒掛：2Y &gt; 10Y。根據 Campbell &amp; Shiller (1991)，此現象為歷史上最可靠的衰退領先指標之一，平均領先 12–18 個月。
        </p>
      )}
    </div>
  );
}
