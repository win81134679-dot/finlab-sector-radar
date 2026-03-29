"use client";
// StockSummary.tsx — 多維度個股快速判讀
// 整合板塊等級 / 七燈觸發數 / RSI / MACD / 籌碼 / 宏觀逆風 → 動態一句話評估
import type { OHLCBar } from "@/lib/types";

// ── 內部計算 ──────────────────────────────────────────────────────────────
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
  data:          OHLCBar[];        // 完整歷史 K 棒
  grade:         string;
  breakdown?:    Breakdown;
  loading:       boolean;
  triggered?:    string[];         // 已觸發的七燈名稱列表
  score?:        number | null;    // 綜合評分（預留）
  sectorLevel?:  string;           // "強烈關注" | "觀察中" | "忽略"
  macroWarning?: boolean;          // 宏觀環境逆風警示
}

export function StockSummary({
  data, grade, breakdown, loading,
  triggered, sectorLevel, macroWarning,
}: StockSummaryProps) {
  if (loading) {
    return (
      <div className="px-3 py-2.5 border-b border-zinc-100 dark:border-zinc-800/50">
        <div className="w-full h-3 rounded-full bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
      </div>
    );
  }
  if (data.length < 2) return null;

  const rsi       = calcRSI(data);
  const macd      = calcMACDSignal(data);
  const fund      = breakdown?.fundamental ?? 0;
  const chip      = breakdown?.chipset     ?? 0;
  const tech      = breakdown?.technical   ?? 0;
  const trigCount = triggered?.length      ?? 0;

  // ── 多頭評分（各維度加減分）────────────────────────────────────────────
  let bullScore = 0;

  // ① 個股等級
  if      (grade === "強烈關注" || grade === "A+" || grade === "A") bullScore += 2;
  else if (grade === "觀察中"   || grade === "B")                   bullScore += 1;

  // ② 七燈觸發覆蓋率
  if      (trigCount >= 5) bullScore += 2;
  else if (trigCount >= 3) bullScore += 1;

  // ③ 板塊等級（情緒共振）
  if      (sectorLevel === "強烈關注") bullScore += 2;
  else if (sectorLevel === "觀察中")   bullScore += 1;
  else if (sectorLevel === "忽略")     bullScore -= 1;

  // ④ MACD 動能
  if      (macd === "黃金交叉") bullScore += 2;
  else if (macd === "多頭")     bullScore += 1;
  else if (macd === "死亡交叉") bullScore -= 2;
  else if (macd === "空頭")     bullScore -= 1;

  // ⑤ RSI 位置
  if (rsi !== null) {
    if      (rsi < 30) bullScore += 1;   // 超賣反彈潛力
    else if (rsi > 75) bullScore -= 1;   // 過熱風險
  }

  // ⑥ 籌碼 / 技術 / 基本面
  if (chip >= 3) bullScore += 1;
  if (tech >= 2) bullScore += 1;
  if (fund >= 4) bullScore += 1;

  // ⑦ 宏觀逆風重懲罰
  if (macroWarning) bullScore -= 2;

  // ── 信號芯片 ──────────────────────────────────────────────────────────
  const chips: Array<{ text: string; cls: string }> = [];

  if (trigCount > 0) {
    chips.push({
      text: `燈 ${trigCount}/7`,
      cls:  trigCount >= 5
        ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300"
        : trigCount >= 3
        ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
        : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400",
    });
  }

  if      (sectorLevel === "強烈關注") chips.push({ text: "🔴 板塊強勢", cls: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300" });
  else if (sectorLevel === "觀察中")   chips.push({ text: "🟡 板塊觀察", cls: "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300" });

  if (macroWarning) chips.push({ text: "⚠ 宏觀逆風", cls: "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400" });

  if (chip >= 3) chips.push({ text: "籌碼集中", cls: "bg-purple-100/80 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300" });

  // ── 指標摘要文字 ──────────────────────────────────────────────────────
  const fundText = fund >= 4 ? "基本面強" : fund >= 2 ? "基本面中" : fund > 0 ? "基本面弱" : null;
  const rsiText  = rsi === null ? null
    : rsi < 30 ? `RSI ${rsi}（超賣）`
    : rsi > 70 ? `RSI ${rsi}（超買）`
    : `RSI ${rsi}（中性）`;
  const macdText =
      macd === "黃金交叉" ? "MACD 黃金交叉↑"
    : macd === "死亡交叉" ? "MACD 死亡交叉↓"
    : macd === "多頭"     ? "MACD 多頭排列"
    : macd === "空頭"     ? "MACD 空頭排列"
    : null;

  const infoStr = [fundText, rsiText, macdText].filter(Boolean).join("，");

  // ── 動態情境判詞 ──────────────────────────────────────────────────────
  const isSectorHot   = sectorLevel === "強烈關注";
  const hasMacroRisk  = !!macroWarning;
  const isGoldenCross = macd === "黃金交叉";
  const isDeathCross  = macd === "死亡交叉";

  type VStyle = { text: string; color: string; bg: string };
  let verdict: VStyle;

  if (bullScore >= 6) {
    const text = isGoldenCross && isSectorHot
      ? "板塊情緒高漲，多頭力道充沛，積極布局"
      : isGoldenCross
      ? "動能全面轉強，短線上攻訊號明確"
      : isSectorHot
      ? "板塊＋個股多維共振，強勢格局確立"
      : "多指標高度共振，強烈多頭訊號";
    verdict = { text, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50/80 dark:bg-emerald-900/20 border-emerald-200/60 dark:border-emerald-700/40" };

  } else if (bullScore >= 4) {
    const text = hasMacroRisk
      ? "宏觀有雜音，但個股偏多，輕倉伺機"
      : isGoldenCross
      ? "黃金交叉確認，量能放大即可進場"
      : isSectorHot
      ? "板塊領漲族群，謹慎擇低進場"
      : "短線偏多，可積極關注";
    verdict = { text, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50/80 dark:bg-emerald-900/20 border-emerald-200/60 dark:border-emerald-700/40" };

  } else if (bullScore >= 2) {
    const text = hasMacroRisk
      ? "總經逆風下偏中性，先觀望再伺機"
      : isGoldenCross
      ? "MACD 剛轉多，中性偏多，謹慎尋找低點"
      : isSectorHot
      ? "板塊偏強，個股仍需確認，注意追高風險"
      : "中性偏多，謹慎擇機，等訊號明確再進";
    verdict = { text, color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50/80 dark:bg-blue-900/20 border-blue-200/60 dark:border-blue-700/40" };

  } else if (bullScore >= -1) {
    const text = hasMacroRisk
      ? "宏觀逆風，多空膠著，持倉輕，待突破確認"
      : isSectorHot
      ? "板塊偏強但個股訊號待確認，耐心等待"
      : "多空拉鋸，短線方向不明，先觀望為宜";
    verdict = { text, color: "text-zinc-600 dark:text-zinc-400", bg: "bg-zinc-50/80 dark:bg-zinc-800/40 border-zinc-200/60 dark:border-zinc-700/40" };

  } else if (bullScore >= -3) {
    const text = hasMacroRisk
      ? "宏觀環境偏空，個股亦弱，建議觀望防守"
      : isDeathCross
      ? "MACD 死叉，動能轉弱，謹慎多頭操作"
      : "偏空格局，宜輕倉觀望，等待底部訊號";
    verdict = { text, color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50/80 dark:bg-amber-900/20 border-amber-200/60 dark:border-amber-700/40" };

  } else {
    const text = hasMacroRisk
      ? "宏觀＋技術雙重壓力，嚴控風險為先"
      : isDeathCross
      ? "死叉確認空頭格局，注意設置停損"
      : "空頭格局，風險控管優先，等待反轉訊號";
    verdict = { text, color: "text-red-600 dark:text-red-400", bg: "bg-red-50/80 dark:bg-red-900/20 border-red-200/60 dark:border-red-700/40" };
  }

  return (
    <div className={`mx-3 mt-2.5 mb-1.5 rounded-xl border text-[11px] overflow-hidden ${verdict.bg}`}>
      {/* 信號芯片列 */}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1 px-3 pt-2 pb-1.5 border-b border-black/5 dark:border-white/5">
          {chips.map((c, i) => (
            <span key={i} className={`inline-flex items-center px-1.5 py-0.5 rounded-full font-medium text-[10px] ${c.cls}`}>
              {c.text}
            </span>
          ))}
        </div>
      )}
      {/* 摘要指標 + 情境判詞 */}
      <div className="flex items-start gap-2 px-3 py-2">
        <span className="mt-0.5 text-sm leading-none shrink-0">📋</span>
        <div className="flex-1 min-w-0 leading-relaxed">
          {infoStr && (
            <span className="text-zinc-600 dark:text-zinc-400">{infoStr}。</span>
          )}
          <span className={`${infoStr ? "ml-1 " : ""}font-bold ${verdict.color}`}>
            ▶ {verdict.text}
          </span>
        </div>
      </div>
    </div>
  );
}
