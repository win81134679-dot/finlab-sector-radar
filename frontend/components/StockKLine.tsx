"use client";
// StockKLine.tsx — K線圖（lightweight-charts v5），支援多時間框架
import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import type { Time } from "lightweight-charts";
import type { OHLCBar } from "@/lib/types";

// ── 時間框架 ──────────────────────────────────────────────────────────────
export type Timeframe = "D" | "W" | "Mo" | "Y";

// 日K 期間選項
export type DayPeriod = "週" | "月" | "年";
const DAY_PERIOD_BARS: Record<DayPeriod, number> = { "週": 5, "月": 22, "年": 252 };
const DAY_PERIODS: DayPeriod[] = ["週", "月", "年"];

const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  "D": "日K", "W": "週K", "Mo": "月K", "Y": "年K",
};
const TIMEFRAMES: Timeframe[] = ["D", "W", "Mo", "Y"];

// ── 資料聚合工具 ───────────────────────────────────────────────────────────
function toWeekly(data: OHLCBar[]): OHLCBar[] {
  const grouped = new Map<string, OHLCBar[]>();
  for (const bar of data) {
    const d = new Date(bar.date + "T00:00:00Z");
    const offset = d.getUTCDay() === 0 ? 6 : d.getUTCDay() - 1; // 0=Mon
    const ws = new Date(d);
    ws.setUTCDate(d.getUTCDate() - offset);
    const key = ws.toISOString().slice(0, 10);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(bar);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, bars]) => ({
    date: key, o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }));
}

function toMonthly(data: OHLCBar[]): OHLCBar[] {
  const grouped = new Map<string, OHLCBar[]>();
  for (const bar of data) {
    const key = bar.date.slice(0, 7);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(bar);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, bars]) => ({
    date: key + "-01", o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }));
}

function toYearly(data: OHLCBar[]): OHLCBar[] {
  const grouped = new Map<string, OHLCBar[]>();
  for (const bar of data) {
    const key = bar.date.slice(0, 4);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(bar);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, bars]) => ({
    date: key + "-01-01", o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }));
}

function applyTimeframe(data: OHLCBar[], tf: Timeframe, dayPeriod: DayPeriod): OHLCBar[] {
  switch (tf) {
    case "D":  return data.slice(-DAY_PERIOD_BARS[dayPeriod]);
    case "W":  return toWeekly(data);
    case "Mo": return toMonthly(data);
    case "Y":  return toYearly(data);
  }
}

// ── 時間軸格式化（修正 NaN/NaN：v5 傳入 BusinessDay 物件非 Unix 戳）──────
function fmtAxisTime(time: Time, tf: Timeframe, _period?: DayPeriod): string {
  let y = 0, mo = 0, d = 0;
  if (typeof time === "number") {
    const dt = new Date(time * 1000);
    y = dt.getUTCFullYear(); mo = dt.getUTCMonth() + 1; d = dt.getUTCDate();
  } else if (typeof time === "string") {
    const p = (time as string).split("-").map(Number);
    y = p[0]; mo = p[1]; d = p[2] ?? 1;
  } else {
    // BusinessDay { year, month, day }
    const bd = time as { year: number; month: number; day: number };
    y = bd.year; mo = bd.month; d = bd.day;
  }
  if (tf === "Y")  return `${y}`;
  if (tf === "Mo") return `${y}/${mo}`;
  return `${mo}/${d}`;
}

export interface KLineProps { data: OHLCBar[]; stockId: string; }

function isDark(): boolean {
  return typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");
}

function getChartColors(dark: boolean) {
  return {
    background: dark ? "#18181b" : "#ffffff",
    text:       dark ? "#a1a1aa" : "#52525b",
    grid:       dark ? "#27272a" : "#f4f4f5",
    border:     dark ? "#3f3f46" : "#e4e4e7",
    up:   "#16a34a",
    down: "#dc2626",
  };
}

const GITHUB_RAW_BASE = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

export function StockKLine({ data: initData, stockId }: KLineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tf, setTf] = useState<Timeframe>("D");
  const [dayPeriod, setDayPeriod] = useState<DayPeriod>("月");
  const [fullData, setFullData] = useState<OHLCBar[]>(initData);
  const [loading, setLoading] = useState(false);

  // 掛載時從 GitHub Raw 抓取完整 OHLCV（約 400 交易日）
  useEffect(() => {
    if (!GITHUB_RAW_BASE) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${GITHUB_RAW_BASE}/output/ohlcv/${stockId}.json`, { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then((d: OHLCBar[] | null) => {
        if (!cancelled && d && d.length > 0) setFullData(d);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [stockId]);

  // 資料或時間框架切換時重建圖表
  useEffect(() => {
    if (!containerRef.current) return;
    const bars = applyTimeframe(fullData, tf, dayPeriod);
    if (bars.length === 0) return;

    const dark = isDark();
    const c = getChartColors(dark);

    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: 200,
      layout: {
        background: { color: c.background },
        textColor: c.text,
        fontSize: 10,
      },
      grid: {
        vertLines: { color: c.grid },
        horzLines: { color: c.grid },
      },
      rightPriceScale: {
        borderColor: c.border,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: c.border,
        tickMarkFormatter: (time: Time) => fmtAxisTime(time, tf, dayPeriod),
      },
      crosshair: { mode: 1 },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: c.up, downColor: c.down,
      borderUpColor: c.up, borderDownColor: c.down,
      wickUpColor:   c.up, wickDownColor:   c.down,
    });

    series.setData(bars.map(bar => ({
      time:  bar.date as unknown as Time,
      open:  bar.o,
      high:  bar.h,
      low:   bar.l,
      close: bar.c,
    })));
    chart.timeScale().fitContent();

    // 監聽主題切換（dark class 變化）
    const observer = new MutationObserver(() => {
      const d = isDark();
      const nc = getChartColors(d);
      chart.applyOptions({
        layout: { background: { color: nc.background }, textColor: nc.text },
        grid: { vertLines: { color: nc.grid }, horzLines: { color: nc.grid } },
      });
    });
    observer.observe(document.documentElement, {
      attributes: true, attributeFilter: ["class"],
    });

    // 視窗 resize
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [fullData, tf, dayPeriod]);

  return (
    <div className="mt-1 rounded border border-zinc-200/50 dark:border-zinc-700/30 overflow-hidden">
      {/* 頂部：股票代號 + 時間框架按鈕 */}
      <div className="flex items-center justify-between px-2 pt-1.5 pb-1">
        <span className="text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">
          {stockId}{loading ? " · 載入…" : ""}
        </span>
        <div className="flex items-center gap-1">
          {/* 日K 期間切換（僅 D 模式顯示） */}
          {tf === "D" && (
            <div className="flex gap-0.5 border-r border-zinc-200/50 dark:border-zinc-700/40 pr-1 mr-0.5">
              {DAY_PERIODS.map(p => (
                <button
                  key={p}
                  onClick={() => setDayPeriod(p)}
                  className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${
                    dayPeriod === p
                      ? "bg-zinc-200/80 dark:bg-zinc-700/80 text-zinc-700 dark:text-zinc-200 font-medium"
                      : "text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
          {/* K線類型切換 */}
          {TIMEFRAMES.map(t => (
            <button
              key={t}
              onClick={() => setTf(t)}
              className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${
                tf === t
                  ? "bg-blue-500/20 text-blue-600 dark:text-blue-400 font-medium"
                  : "text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
              }`}
            >
              {TIMEFRAME_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
