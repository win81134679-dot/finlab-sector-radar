"use client";
// StockKLine.tsx — 7日日K線圖（lightweight-charts v5，僅客戶端）
import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import type { Time } from "lightweight-charts";
import type { OHLCBar } from "@/lib/types";

interface StockKLineProps {
  data: OHLCBar[];
  stockId: string;
}

function isDark(): boolean {
  return typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");
}

function getChartColors(dark: boolean) {
  return {
    background:   dark ? "#18181b" : "#ffffff",
    text:         dark ? "#a1a1aa" : "#52525b",
    grid:         dark ? "#27272a" : "#f4f4f5",
    border:       dark ? "#3f3f46" : "#e4e4e7",
    upColor:      "#16a34a",
    downColor:    "#dc2626",
    wickUpColor:  "#16a34a",
    wickDownColor:"#dc2626",
  };
}

export function StockKLine({ data, stockId }: StockKLineProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const dark = isDark();
    const c = getChartColors(dark);

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 160,
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
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number) => {
          const d = new Date(time * 1000);
          return `${d.getMonth() + 1}/${d.getDate()}`;
        },
      },
      crosshair: {
        mode: 1, // CrosshairMode.Magnet
      },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor:         c.upColor,
      downColor:       c.downColor,
      borderUpColor:   c.upColor,
      borderDownColor: c.downColor,
      wickUpColor:     c.wickUpColor,
      wickDownColor:   c.wickDownColor,
    });

    // 轉換資料格式：OHLCBar → lightweight-charts CandlestickData
    const lwData = data.map((bar) => ({
      time: bar.date as unknown as Time,
      open:  bar.o,
      high:  bar.h,
      low:   bar.l,
      close: bar.c,
    }));

    series.setData(lwData);
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
  }, [data, stockId]);

  return (
    <div className="mt-1 rounded border border-zinc-200/50 dark:border-zinc-700/30 overflow-hidden">
      <div className="px-2 pt-1 text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">
        {stockId} · 近 {data.length} 日K線
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
