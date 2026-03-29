"use client";
// MacdChart.tsx — MACD 動量指標（純 SVG）
// 學術基礎：Appel, G. (1979). The Moving Average Convergence-Divergence Method.
// MACD = EMA(12) − EMA(26)；Signal = EMA(9, MACD)；Histogram = MACD − Signal
import type { OHLCBar } from "@/lib/types";
import { InfoPopover } from "./InfoPopover";

// ── EMA 計算 ──────────────────────────────────────────────────────────────
function calcEMA(values: number[], period: number): number[] {
  const k = 2 / (period + 1);
  const result: number[] = [];
  let ema = values[0];
  result.push(ema);
  for (let i = 1; i < values.length; i++) {
    ema = values[i] * k + ema * (1 - k);
    result.push(ema);
  }
  return result;
}

interface MACDResult {
  macd:      number[];
  signal:    number[];
  histogram: number[];
}

function calcMACD(data: OHLCBar[]): MACDResult | null {
  // EMA26 需要 26 根；Signal EMA9 需要再 9 根 → 最少 34 根
  if (data.length < 35) return null;

  const closes  = data.map((b) => b.c);
  const ema12   = calcEMA(closes, 12);
  const ema26   = calcEMA(closes, 26);

  // MACD line：從 index 25 起 EMA26 才穩定
  const macdLine   = ema12.map((v, i) => v - ema26[i]).slice(25);
  const signalLine = calcEMA(macdLine, 9);
  const histogram  = macdLine.map((v, i) => v - signalLine[i]);

  // 顯示最後 60 根
  const N = 60;
  return {
    macd:      macdLine.slice(-N),
    signal:    signalLine.slice(-N),
    histogram: histogram.slice(-N),
  };
}

interface MacdChartProps {
  data:    OHLCBar[];
  loading: boolean;
}

export function MacdChart({ data, loading }: MacdChartProps) {
  const macdData = data.length >= 35 ? calcMACD(data) : null;

  if (loading || !macdData) {
    return (
      <div className="px-3 pt-2 pb-2 border-b border-zinc-100 dark:border-zinc-800/50">
        <div className="flex items-center justify-between mb-0.5">
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-wide">
              MACD 動量指標
            </span>
            <InfoPopover
              title="MACD 怎麼看"
              tips={[
                { label: "藍線 (MACD)",    desc: "EMA12 − EMA26，白色 0 線上方為多頭動能，下方為空頭" },
                { label: "橘處線 (Signal)", desc: "MACD 的 9 日 EMA，表達趨勢平滑度" },
                { label: "黃金交叉 ▲",   desc: "MACD 由下穿上 Signal 線：動能反轉向上，熱門进場訊號" },
                { label: "死亡交叉 ▼",   desc: "MACD 由上穿下 Signal 線：動能複弱，空頭規避訊號" },
                { label: "綠柱大 / 切短", desc: "Histogram 間距擴大為動能增強；收縮为初步衣空" },
              ]}
            />
          </div>
          <span className="text-[10px] text-zinc-400">Appel (1979)</span>
        </div>
        <div className="flex flex-col items-center gap-1 py-2">
          <div className="w-28 h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
          <span className="text-[11px] text-zinc-400">
            {loading ? "載入歷史資料…" : "資料不足（需 ≥35 根）"}
          </span>
        </div>
      </div>
    );
  }

  const W = 280, H = 88;
  const PAD_L = 4, PAD_R = 4, PAD_T = 6, PAD_B = 4;
  const chartW = W - PAD_L - PAD_R;

  // 上半：MACD + Signal 折線（55%）；下半：Histogram（45%）
  const lineH = Math.floor((H - PAD_T - PAD_B) * 0.55);
  const histH = H - PAD_T - PAD_B - lineH - 3;   // 3px gap

  const n    = macdData.macd.length;
  const step = chartW / Math.max(n - 1, 1);

  // ── 折線區 ──────────────────────────────────────────────────────────────
  const allLineVals = [...macdData.macd, ...macdData.signal];
  const lineMin  = Math.min(...allLineVals);
  const lineMax  = Math.max(...allLineVals);
  const lineRange = lineMax - lineMin || 0.001;

  const lx = (i: number) => PAD_L + i * step;
  const ly = (v: number) => PAD_T + lineH - ((v - lineMin) / lineRange) * lineH;

  const zeroY  = ly(0);
  const macdPts   = macdData.macd.map((v, i)   => `${lx(i).toFixed(1)},${ly(v).toFixed(1)}`).join(" ");
  const signalPts = macdData.signal.map((v, i) => `${lx(i).toFixed(1)},${ly(v).toFixed(1)}`).join(" ");

  // ── Histogram 區 ────────────────────────────────────────────────────────
  const histTop  = PAD_T + lineH + 3;
  const histMidY = histTop + histH / 2;
  const histMax  = Math.max(...macdData.histogram.map(Math.abs)) || 0.001;
  const barW     = Math.max(1, step * 0.65);

  // ── 交叉偵測 ────────────────────────────────────────────────────────────
  const lastMacd   = macdData.macd[n - 1];
  const lastSignal = macdData.signal[n - 1];
  const prevMacd   = macdData.macd[n - 2] ?? lastMacd;
  const prevSignal = macdData.signal[n - 2] ?? lastSignal;
  const goldCross  = prevMacd <= prevSignal && lastMacd > lastSignal;
  const deadCross  = prevMacd >= prevSignal && lastMacd < lastSignal;
  const crossLabel = goldCross ? "黃金交叉 ▲" : deadCross ? "死亡交叉 ▼" : null;
  const crossColor = goldCross ? "#10b981" : "#ef4444";

  // 最新 Histogram 趨勢（最近3根）
  const recentHist = macdData.histogram.slice(-3);
  const histTrend  =
    recentHist[2] > recentHist[1] && recentHist[1] > recentHist[0]   ? "↑ 動能擴張" :
    recentHist[2] < recentHist[1] && recentHist[1] < recentHist[0]   ? "↓ 動能收縮" : null;
  const histTrendColor = recentHist[2] >= 0 ? "#10b981" : "#ef4444";

  return (
    <div className="px-3 pt-2 pb-2 border-b border-zinc-100 dark:border-zinc-800/50">
      {/* 標題 */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-wide">
            MACD 動量指標
          </span>
          <InfoPopover
            title="MACD 怎麼看"
            tips={[
              { label: "藍線 (MACD)",    desc: "EMA12 − EMA26，白色 0 線上方為多頭動能，下方為空頭" },
              { label: "樘處線 (Signal)", desc: "MACD 的 9 日 EMA，表達趨勢平滑度" },
              { label: "黃金交叉 ▲",   desc: "MACD 由下穿上 Signal 線：動能反轉向上，熱門进場訊號" },
              { label: "死亡交叉 ▼",   desc: "MACD 由上穿下 Signal 線：動能複弱，空頭規避訊號" },
              { label: "綠柱大 / 切短", desc: "Histogram 間距擴大為動能增強；收縮為初步袓空" },
            ]}
          />
        </div>
        <div className="flex items-center gap-2">
          {histTrend && !crossLabel && (
            <span className="text-[10px] font-semibold" style={{ color: histTrendColor }}>
              {histTrend}
            </span>
          )}
          {crossLabel && (
            <span className="text-[10px] font-bold" style={{ color: crossColor }}>
              {crossLabel}
            </span>
          )}
          <span className="text-[10px] text-zinc-400">Appel (1979)</span>
        </div>
      </div>

      {/* SVG 圖表 */}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
        {/* 零線（折線區） */}
        {zeroY >= PAD_T && zeroY <= PAD_T + lineH && (
          <line
            x1={PAD_L} y1={zeroY.toFixed(1)}
            x2={W - PAD_R} y2={zeroY.toFixed(1)}
            stroke="rgba(161,161,170,0.35)" strokeWidth="0.5" strokeDasharray="3 2"
          />
        )}

        {/* Histogram bars */}
        {macdData.histogram.map((v, i) => {
          const bH  = Math.abs(v) / histMax * (histH / 2);
          const bX  = lx(i) - barW / 2;
          const bY  = v >= 0 ? histMidY - bH : histMidY;
          return (
            <rect
              key={i}
              x={bX.toFixed(1)} y={bY.toFixed(1)}
              width={barW.toFixed(1)} height={Math.max(0.5, bH).toFixed(1)}
              fill={v >= 0 ? "rgba(16,185,129,0.55)" : "rgba(239,68,68,0.55)"}
              rx="0.5"
            />
          );
        })}

        {/* Histogram 中線 */}
        <line
          x1={PAD_L} y1={histMidY.toFixed(1)}
          x2={W - PAD_R} y2={histMidY.toFixed(1)}
          stroke="rgba(161,161,170,0.25)" strokeWidth="0.5"
        />

        {/* MACD 折線（藍） */}
        <polyline
          points={macdPts}
          fill="none" stroke="#3b82f6" strokeWidth="1.5"
          strokeLinejoin="round" strokeLinecap="round"
        />

        {/* Signal 折線（橘，虛線） */}
        <polyline
          points={signalPts}
          fill="none" stroke="#f97316" strokeWidth="1"
          strokeLinejoin="round" strokeLinecap="round"
          strokeDasharray="3 1.5"
        />
      </svg>

      {/* 圖例 */}
      <div className="flex items-center gap-3 mt-0.5">
        <div className="flex items-center gap-1">
          <div className="w-5 h-0.5" style={{ background: "#3b82f6" }} />
          <span className="text-[10px] text-zinc-400">MACD</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-5 h-px border-t border-dashed border-orange-400" />
          <span className="text-[10px] text-zinc-400">Signal</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="flex gap-px items-end">
            <span className="w-1.5 h-2.5 bg-emerald-500/60 rounded-sm inline-block" />
            <span className="w-1.5 h-1.5 bg-red-500/60 rounded-sm inline-block" />
          </div>
          <span className="text-[10px] text-zinc-400">柱狀差距</span>
        </div>
      </div>
    </div>
  );
}
