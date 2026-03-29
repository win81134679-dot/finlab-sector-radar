"use client";
// StockSummary.tsx — 一句話評估個股綜合狀態
// 整合 RSI / MACD / K線型態 / 因子雷達 → 快速判讀
import type { OHLCBar } from "@/lib/types";

// ── 內部計算（複用 RsiGauge / MacdChart 邏輯） ──────────────────────────
function calcRSI(data: OHLCBar[]): number | null {
  if (data.length < 15) return null;
  const closes  = data.map((b) => b.c);
  const changes = closes.slice(1).map((c, i) => c - closes[i]);
  let avgGain = changes.slice(0, 14).filter((d) => d > 0).reduce((s, d) => s + d, 0) / 14;
  let avgLoss = changes.slice(0, 14).filter((d) => d < 0).reduce((s, d) => s + Math.abs(d), 0) / 14;
  for (let i = 14; i < changes.length; i++) {
    avgGain = (avgGain * 13 + (changes[i] > 0 ? changes[i] : 0)) / 14;
    avgLoss = (avgLoss * 13 + (changes[i] < 0 ? Math.abs(changes[i]) : 0)) / 14;
  }
  return avgLoss === 0 ? 100 : parseFloat((100 - 100 / (1 + avgGain / avgLoss)).toFixed(1));
}

type MACDSignal = "黃金交叉" | "死亡交叉" | "多頭" | "空頭" | "中性";
function calcMACDSignal(data: OHLCBar[]): MACDSignal {
  if (data.length < 35) return "中性";
  const k = (p: number) => 2 / (p + 1);
  const closes = data.map((b) => b.c);
  let e12 = closes[0], e26 = closes[0];
  const macdArr: number[] = [];
  for (const c of closes) {
    e12 = c * k(12) + e12 * (1 - k(12));
    e26 = c * k(26) + e26 * (1 - k(26));
    macdArr.push(e12 - e26);
  }
  const macd = macdArr.slice(25);
  let sig = macd[0];
  const sigArr: number[] = [sig];
  for (let i = 1; i < macd.length; i++) {
    sig = macd[i] * k(9) + sig * (1 - k(9));
    sigArr.push(sig);
  }
  const n = macd.length;
  const last = macd[n - 1], prev = macd[n - 2] ?? last;
  const lastS = sigArr[n - 1], prevS = sigArr[n - 2] ?? lastS;
  if (prev <= prevS && last > lastS) return "黃金交叉";
  if (prev >= prevS && last < lastS) return "死亡交叉";
  if (last > lastS && last > 0) return "多頭";
  if (last < lastS && last < 0) return "空頭";
  return "中性";
}

interface Breakdown {
  fundamental: number;
  technical:   number;
  chipset:     number;
  bonus:       number;
}

interface StockSummaryProps {
  data:       OHLCBar[];   // 完整歷史 K 棒
  grade:      string;
  breakdown?: Breakdown;
  loading:    boolean;
}

export function StockSummary({ data, grade, breakdown, loading }: StockSummaryProps) {
  if (loading || data.length < 2) {
    return (
      <div className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800/50">
        <div className="w-full h-3 rounded-full bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
      </div>
    );
  }

  const rsi  = calcRSI(data);
  const macd = calcMACDSignal(data);

  // ── RSI 評語 ──────────────────────────────────────────────────────────
  const rsiLabel = rsi === null ? null
    : rsi < 30 ? `RSI ${rsi}（超賣）`
    : rsi > 70 ? `RSI ${rsi}（超買）`
    : `RSI ${rsi}（中性）`;

  // ── MACD 評語 ─────────────────────────────────────────────────────────
  const macdLabel =
    macd === "黃金交叉" ? "MACD 黃金交叉↑"
    : macd === "死亡交叉" ? "MACD 死亡交叉↓"
    : macd === "多頭"   ? "MACD 多頭排列"
    : macd === "空頭"   ? "MACD 空頭排列"
    : "MACD 中性";

  // ── 基本面評語 ────────────────────────────────────────────────────────
  const fund = breakdown?.fundamental ?? 0;
  const fundLabel =
    fund >= 4   ? "基本面強"
    : fund >= 2 ? "基本面中"
    : fund > 0  ? "基本面弱"
    : null;

  // ── 綜合判斷 ──────────────────────────────────────────────────────────
  // 多頭點：grade好 + RSI不超買 + MACD偏多 + 基本面中以上
  let bullScore = 0;
  if (grade === "強烈關注" || grade === "A+" || grade === "A") bullScore += 2;
  if (grade === "觀察中" || grade === "B") bullScore += 1;
  if (rsi !== null && rsi < 70) bullScore += 1;
  if (rsi !== null && rsi < 30) bullScore += 1;  // 超賣 = 潛在反彈加分
  if (macd === "黃金交叉") bullScore += 2;
  if (macd === "多頭") bullScore += 1;
  if (macd === "死亡交叉") bullScore -= 2;
  if (macd === "空頭") bullScore -= 1;
  if (fund >= 4) bullScore += 1;
  if (rsi !== null && rsi > 70) bullScore -= 1;

  const verdict =
    bullScore >= 4 ? { text: "短線偏多，可積極關注",    color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50/80 dark:bg-emerald-900/20 border-emerald-200/60 dark:border-emerald-700/40" }
    : bullScore >= 2 ? { text: "中性偏多，謹慎擇機",    color: "text-blue-600 dark:text-blue-400",     bg: "bg-blue-50/80 dark:bg-blue-900/20 border-blue-200/60 dark:border-blue-700/40" }
    : bullScore >= 0 ? { text: "中性，等待方向明確",    color: "text-zinc-600 dark:text-zinc-400",     bg: "bg-zinc-50/80 dark:bg-zinc-800/40 border-zinc-200/60 dark:border-zinc-700/40" }
    : bullScore >= -2 ? { text: "偏空，宜觀望或防守",   color: "text-amber-600 dark:text-amber-400",   bg: "bg-amber-50/80 dark:bg-amber-900/20 border-amber-200/60 dark:border-amber-700/40" }
    : { text: "空頭訊號，注意風險控管",                color: "text-red-600 dark:text-red-400",       bg: "bg-red-50/80 dark:bg-red-900/20 border-red-200/60 dark:border-red-700/40" };

  // ── 組合句子 ──────────────────────────────────────────────────────────
  const parts = [
    fundLabel,
    rsiLabel,
    macdLabel,
  ].filter(Boolean).join("，");

  return (
    <div className={`mx-3 mt-2 mb-1 px-3 py-2 rounded-xl border text-[11px] ${verdict.bg}`}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-sm leading-none shrink-0">📋</span>
        <div className="flex-1 min-w-0">
          <span className="text-zinc-600 dark:text-zinc-400">
            {parts}。
          </span>
          <span className={`ml-1 font-bold ${verdict.color}`}>
            ▶ {verdict.text}
          </span>
        </div>
      </div>
    </div>
  );
}
