"use client";
// CommodityKLine.tsx — 商品 K 線圖（3 Pane：K線 + 成交量 + MACD）

import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import type { Time } from "lightweight-charts";
import type { OHLCBar } from "@/lib/types";

// ── 時間框架（與 StockKLine 相同結構）────────────────────────────────────
export type CKLTimeframe = "D" | "W" | "Mo" | "Y";
type DayPeriod = "週" | "月" | "年";
const DAY_PERIOD_BARS: Record<DayPeriod, number> = { 週: 5, 月: 22, 年: 252 };
const DAY_PERIODS: DayPeriod[] = ["週", "月", "年"];
const TF_LABELS: Record<CKLTimeframe, string> = { D: "日K", W: "週K", Mo: "月K", Y: "年K" };
const TFS: CKLTimeframe[] = ["D", "W", "Mo", "Y"];

// ── 資料聚合 ─────────────────────────────────────────────────────────────
function agg(data: OHLCBar[], fn: (bars: OHLCBar[], key: string) => OHLCBar, keyFn: (bar: OHLCBar) => string) {
  const grouped = new Map<string, OHLCBar[]>();
  for (const bar of data) {
    const k = keyFn(bar);
    if (!grouped.has(k)) grouped.set(k, []);
    grouped.get(k)!.push(bar);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([k, bars]) => fn(bars, k));
}

function toWeekly(data: OHLCBar[]) {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  return agg(data, (bars, _k) => ({
    date: bars[0].date, o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }), bar => {
    const d = new Date(bar.date + "T00:00:00Z");
    const off = d.getUTCDay() === 0 ? 6 : d.getUTCDay() - 1;
    const ws = new Date(d); ws.setUTCDate(d.getUTCDate() - off);
    return ws.toISOString().slice(0, 10);
  });
}

function toMonthly(data: OHLCBar[]) {
  return agg(data, (bars, k) => ({
    date: k + "-01", o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }), bar => bar.date.slice(0, 7));
}

function toYearly(data: OHLCBar[]) {
  return agg(data, (bars, k) => ({
    date: k + "-01-01", o: bars[0].o,
    h: Math.max(...bars.map(b => b.h)), l: Math.min(...bars.map(b => b.l)),
    c: bars[bars.length - 1].c, v: bars.reduce((s, b) => s + b.v, 0),
  }), bar => bar.date.slice(0, 4));
}

function applyTF(data: OHLCBar[], tf: CKLTimeframe, dp: DayPeriod): OHLCBar[] {
  switch (tf) {
    case "D":  return data.slice(-DAY_PERIOD_BARS[dp]);
    case "W":  return toWeekly(data);
    case "Mo": return toMonthly(data);
    case "Y":  return toYearly(data);
  }
}

// ── 時間軸格式（修正 BusinessDay 物件）───────────────────────────────────
function fmtTime(time: Time, tf: CKLTimeframe): string {
  let y = 0, mo = 0, d = 0;
  if (typeof time === "number") {
    const dt = new Date(time * 1000);
    y = dt.getUTCFullYear(); mo = dt.getUTCMonth() + 1; d = dt.getUTCDate();
  } else if (typeof time === "string") {
    const p = (time as string).split("-").map(Number);
    y = p[0]; mo = p[1]; d = p[2] ?? 1;
  } else {
    const bd = time as { year: number; month: number; day: number };
    y = bd.year; mo = bd.month; d = bd.day;
  }
  if (tf === "Y")  return `${y}`;
  if (tf === "Mo") return `${y}/${mo}`;
  return `${mo}/${d}`;
}

// ── MACD 計算（前端純函式）────────────────────────────────────────────────
function ema(prices: number[], n: number): number[] {
  if (prices.length === 0) return [];
  const alpha = 2 / (n + 1);
  const result: number[] = [prices[0]];
  for (let i = 1; i < prices.length; i++) {
    result.push(alpha * prices[i] + (1 - alpha) * result[i - 1]);
  }
  return result;
}

interface MACDPoint { macd: number; signal: number; hist: number; }
function calcMACD(bars: OHLCBar[]): MACDPoint[] {
  const closes = bars.map(b => b.c);
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const macdLine = ema12.map((v, i) => v - ema26[i]);
  const signalLine = ema(macdLine, 9);
  return macdLine.map((m, i) => ({
    macd: m, signal: signalLine[i], hist: m - signalLine[i],
  }));
}

// ── 主題顏色 ─────────────────────────────────────────────────────────────
function isDark() {
  return typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");
}
function colors(dark: boolean) {
  return {
    bg:     dark ? "#18181b" : "#ffffff",
    text:   dark ? "#a1a1aa" : "#52525b",
    grid:   dark ? "#27272a" : "#f4f4f5",
    border: dark ? "#3f3f46" : "#e4e4e7",
    up:     "#16a34a",
    down:   "#dc2626",
    macd:   "#60a5fa",
    signal: "#f97316",
  };
}

// ── Props ─────────────────────────────────────────────────────────────────
export interface CommodityKLineProps {
  data: OHLCBar[];
  slug: string;
  nameZh: string;
}

const GITHUB_RAW_BASE = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

export function CommodityKLine({ data: initData, slug, nameZh }: CommodityKLineProps) {
  const pane1Ref = useRef<HTMLDivElement>(null); // K 線
  const pane2Ref = useRef<HTMLDivElement>(null); // 成交量
  const pane3Ref = useRef<HTMLDivElement>(null); // MACD
  const [tf, setTf] = useState<CKLTimeframe>("D");
  const [dp, setDp] = useState<DayPeriod>("月");
  const [fullData, setFullData] = useState<OHLCBar[]>(initData);
  const [loading, setLoading] = useState(false);

  // 從 GitHub Raw 懶載入完整 OHLCV
  useEffect(() => {
    if (!GITHUB_RAW_BASE) return;
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) setLoading(true); });
    fetch(`${GITHUB_RAW_BASE}/output/commodities/${slug}.json`, { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then((d: OHLCBar[] | null) => {
        if (!cancelled && d && d.length > 0) setFullData(d);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [slug]);

  // 建立 3 個 lightweight-charts 圖表，共享時間軸
  useEffect(() => {
    if (!pane1Ref.current || !pane2Ref.current || !pane3Ref.current) return;
    const bars = applyTF(fullData, tf, dp);
    if (bars.length === 0) return;

    const dark = isDark();
    const c = colors(dark);
    const width = pane1Ref.current.clientWidth;

    const baseOpts = {
      width,
      layout: { background: { color: c.bg }, textColor: c.text, fontSize: 10 },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      timeScale: {
        borderColor: c.border,
        tickMarkFormatter: (time: Time) => fmtTime(time, tf),
        visible: false, // 只在底部 pane 顯示
      },
      crosshair: { mode: 1 },
      handleScroll: true,
      handleScale: true,
    };

    // Pane 1: K 線（200px）
    const chart1 = createChart(pane1Ref.current, {
      ...baseOpts,
      height: 200,
      rightPriceScale: { borderColor: c.border, scaleMargins: { top: 0.1, bottom: 0.05 } },
      timeScale: { ...baseOpts.timeScale, visible: false },
    });
    const candleSeries = chart1.addSeries(CandlestickSeries, {
      upColor: c.up, downColor: c.down,
      borderUpColor: c.up, borderDownColor: c.down,
      wickUpColor: c.up, wickDownColor: c.down,
    });
    candleSeries.setData(bars.map(b => ({
      time: b.date as unknown as Time, open: b.o, high: b.h, low: b.l, close: b.c,
    })));

    // Pane 2: 成交量（60px）
    const chart2 = createChart(pane2Ref.current, {
      ...baseOpts,
      height: 60,
      rightPriceScale: { borderColor: c.border, scaleMargins: { top: 0.1, bottom: 0 } },
      timeScale: { ...baseOpts.timeScale, visible: false },
    });
    const volSeries = chart2.addSeries(HistogramSeries, {
      priceScaleId: "right",
    });
    volSeries.setData(bars.map(b => ({
      time: b.date as unknown as Time,
      value: b.v,
      color: b.c >= b.o ? c.up + "99" : c.down + "99",
    })));

    // Pane 3: MACD（80px）
    const macdData = calcMACD(bars);
    const chart3 = createChart(pane3Ref.current, {
      ...baseOpts,
      height: 80,
      rightPriceScale: { borderColor: c.border, scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { ...baseOpts.timeScale, visible: true, borderColor: c.border },
    });
    const macdLineSeries = chart3.addSeries(LineSeries, { color: c.macd, lineWidth: 1 });
    const signalLineSeries = chart3.addSeries(LineSeries, { color: c.signal, lineWidth: 1 });
    const histSeries = chart3.addSeries(HistogramSeries, { priceScaleId: "right" });

    macdLineSeries.setData(macdData.map((d, i) => ({
      time: bars[i].date as unknown as Time, value: d.macd,
    })));
    signalLineSeries.setData(macdData.map((d, i) => ({
      time: bars[i].date as unknown as Time, value: d.signal,
    })));
    histSeries.setData(macdData.map((d, i) => ({
      time: bars[i].date as unknown as Time,
      value: d.hist,
      color: d.hist >= 0 ? c.up + "99" : c.down + "99",
    })));

    // 時間軸同步
    const onRange1 = (range: { from: number; to: number } | null) => {
      if (range) {
        chart2.timeScale().setVisibleLogicalRange(range);
        chart3.timeScale().setVisibleLogicalRange(range);
      }
    };
    const onRange3 = (range: { from: number; to: number } | null) => {
      if (range) {
        chart1.timeScale().setVisibleLogicalRange(range);
        chart2.timeScale().setVisibleLogicalRange(range);
      }
    };
    chart1.timeScale().subscribeVisibleLogicalRangeChange(onRange1);
    chart3.timeScale().subscribeVisibleLogicalRangeChange(onRange3);

    chart1.timeScale().fitContent();

    // 主題觀察器
    const observer = new MutationObserver(() => {
      const d = isDark();
      const nc = colors(d);
      [chart1, chart2, chart3].forEach(ch => {
        ch.applyOptions({
          layout: { background: { color: nc.bg }, textColor: nc.text },
          grid: { vertLines: { color: nc.grid }, horzLines: { color: nc.grid } },
        });
      });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    // Resize
    const onResize = () => {
      const w = pane1Ref.current?.clientWidth ?? width;
      [chart1, chart2, chart3].forEach(ch => ch.applyOptions({ width: w }));
    };
    window.addEventListener("resize", onResize);

    return () => {
      chart1.timeScale().unsubscribeVisibleLogicalRangeChange(onRange1);
      chart3.timeScale().unsubscribeVisibleLogicalRangeChange(onRange3);
      observer.disconnect();
      window.removeEventListener("resize", onResize);
      chart1.remove(); chart2.remove(); chart3.remove();
    };
  }, [fullData, tf, dp]);

  return (
    <div className="rounded border border-zinc-200/50 dark:border-zinc-700/30 overflow-hidden">
      {/* 頂部控制列 */}
      <div className="flex items-center justify-between px-2 pt-1.5 pb-1">
        <span className="text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">
          {nameZh}{loading ? " · 載入…" : ""}
        </span>
        <div className="flex items-center gap-1">
          {tf === "D" && (
            <div className="flex gap-0.5 border-r border-zinc-200/50 dark:border-zinc-700/40 pr-1 mr-0.5">
              {DAY_PERIODS.map(p => (
                <button key={p} onClick={() => setDp(p)}
                  className={`px-1.5 py-0.5 text-[10px] rounded ${dp === p
                    ? "bg-zinc-200/80 dark:bg-zinc-700/80 text-zinc-700 dark:text-zinc-200 font-medium"
                    : "text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"}`}>
                  {p}
                </button>
              ))}
            </div>
          )}
          {TFS.map(t => (
            <button key={t} onClick={() => setTf(t)}
              className={`px-1.5 py-0.5 text-[10px] rounded ${tf === t
                ? "bg-blue-500/20 text-blue-600 dark:text-blue-400 font-medium"
                : "text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"}`}>
              {TF_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      {/* 3 Pane 容器 */}
      <div ref={pane1Ref} className="w-full" />
      <div ref={pane2Ref} className="w-full border-t border-zinc-200/30 dark:border-zinc-700/20" />
      <div ref={pane3Ref} className="w-full border-t border-zinc-200/30 dark:border-zinc-700/20" />
      {/* MACD 圖例 */}
      <div className="flex items-center gap-3 px-2 pb-1.5 pt-0.5">
        <span className="flex items-center gap-1 text-[9px] text-blue-400">
          <span className="inline-block w-3 h-0.5 bg-blue-400 rounded" />MACD
        </span>
        <span className="flex items-center gap-1 text-[9px] text-orange-400">
          <span className="inline-block w-3 h-0.5 bg-orange-400 rounded" />Signal
        </span>
      </div>
    </div>
  );
}
