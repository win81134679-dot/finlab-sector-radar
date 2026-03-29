// CompositePanel.tsx — 三合一複合訊號面板（Tab #4）
// 顯示：NLP 關鍵詞命中、關稅矩陣情境、板塊複合評分排行

"use client";

import type { CompositeSnapshot } from "@/lib/types";

interface Props {
  data: CompositeSnapshot | null;
}

const SIGNAL_COLOR: Record<string, string> = {
  "強烈買入": "text-emerald-600 dark:text-emerald-400 font-bold",
  "買入":     "text-emerald-500 dark:text-emerald-400",
  "中性":     "text-zinc-400 dark:text-zinc-500",
  "賣出":     "text-red-500 dark:text-red-400",
  "強烈賣出": "text-red-600 dark:text-red-400 font-bold",
};

const SIGNAL_BG: Record<string, string> = {
  "強烈買入": "bg-emerald-50/80 dark:bg-emerald-900/20 border-emerald-200/60 dark:border-emerald-800/50",
  "買入":     "bg-emerald-50/50 dark:bg-emerald-900/10 border-emerald-200/40 dark:border-emerald-800/30",
  "中性":     "bg-zinc-50/60 dark:bg-zinc-900/20 border-zinc-200/40 dark:border-zinc-700/30",
  "賣出":     "bg-red-50/50 dark:bg-red-900/10 border-red-200/40 dark:border-red-800/30",
  "強烈賣出": "bg-red-50/80 dark:bg-red-900/20 border-red-200/60 dark:border-red-800/50",
};

const SCENARIO_LABELS: Record<string, string> = {
  "10%": "🟡 溫和 10%",
  "25%": "🟠 標準 25%",
  "60%": "🔴 極端 60%",
};

function ScoreBar({ value }: { value: number }) {
  // value: -2 ~ +2，轉成 0~100% 的寬度條
  const pct = Math.round(((value + 2) / 4) * 100);
  const isPositive = value >= 0;
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="w-full bg-zinc-200/60 dark:bg-zinc-700/60 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isPositive ? "bg-emerald-500" : "bg-red-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-12 text-right ${isPositive ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
        {value >= 0 ? "+" : ""}{value.toFixed(2)}
      </span>
    </div>
  );
}

function SectorRow({ sectorId, score }: { sectorId: string; score: CompositeSnapshot["scores"][string] }) {
  const bgClass = SIGNAL_BG[score.signal] ?? SIGNAL_BG["中性"];
  const textClass = SIGNAL_COLOR[score.signal] ?? "text-zinc-500";
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${bgClass}`}>
      <div className="w-24 shrink-0">
        <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate">{sectorId}</span>
      </div>
      <ScoreBar value={score.composite} />
      <span className={`text-xs shrink-0 w-[5.5rem] text-right ${textClass}`}>{score.signal}</span>
    </div>
  );
}

export function CompositePanel({ data }: Props) {
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">🔄</span>
        <p className="text-sm">複合訊號資料尚未生成</p>
        <p className="text-xs mt-1 opacity-60">請先執行一次 Python --auto 分析</p>
      </div>
    );
  }

  const sortedScores = Object.entries(data.scores)
    .sort((a, b) => b[1].composite - a[1].composite);

  const buyScores  = sortedScores.filter(([, v]) => v.composite > 0.05);
  const sellScores = sortedScores.filter(([, v]) => v.composite < -0.05).reverse();

  const strengthPct = Math.round(data.signal_strength * 100);
  const strengthColor =
    data.signal_strength >= 0.7 ? "text-emerald-500" :
    data.signal_strength >= 0.4 ? "text-amber-500" :
    "text-zinc-400";

  return (
    <div className="space-y-6">
      {/* ── 頂部摘要卡片 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">關稅情境</p>
          <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
            {SCENARIO_LABELS[data.scenario] ?? data.scenario}
          </p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">訊號強度</p>
          <p className={`text-2xl font-bold ${strengthColor}`}>{strengthPct}%</p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">分析貼文</p>
          <p className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">{data.source_count}</p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">命中關鍵詞</p>
          <p className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">{data.keyword_hits.length}</p>
        </div>
      </div>

      {/* ── 關鍵詞標籤 ── */}
      {data.keyword_hits.length > 0 && (
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-2">本次命中關鍵詞</p>
          <div className="flex flex-wrap gap-1.5">
            {data.keyword_hits.map((kw, i) => (
              <span
                key={i}
                className="text-xs px-2 py-0.5 rounded-full bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200/50 dark:border-amber-800/50"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── 受益板塊 + 受害板塊雙欄 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 受益 */}
        <div>
          <h3 className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mb-3 flex items-center gap-1.5">
            <span>📈 受益板塊</span>
            <span className="text-xs font-normal text-zinc-400">（composite &gt; 0）</span>
          </h3>
          <div className="space-y-1.5">
            {buyScores.length > 0
              ? buyScores.map(([sid, score]) => (
                  <SectorRow key={sid} sectorId={sid} score={score} />
                ))
              : <p className="text-xs text-zinc-400 py-4 text-center">無明顯受益板塊</p>
            }
          </div>
        </div>

        {/* 受害 */}
        <div>
          <h3 className="text-sm font-semibold text-red-500 dark:text-red-400 mb-3 flex items-center gap-1.5">
            <span>📉 受害板塊</span>
            <span className="text-xs font-normal text-zinc-400">（composite &lt; 0）</span>
          </h3>
          <div className="space-y-1.5">
            {sellScores.length > 0
              ? sellScores.map(([sid, score]) => (
                  <SectorRow key={sid} sectorId={sid} score={score} />
                ))
              : <p className="text-xs text-zinc-400 py-4 text-center">無明顯受害板塊</p>
            }
          </div>
        </div>
      </div>

      {/* ── NLP / 關稅 權重說明 ── */}
      <div className="flex flex-wrap gap-3 text-xs text-zinc-400 dark:text-zinc-500">
        <span>NLP 權重：{Math.round(data.nlp_weight * 100)}%</span>
        <span>·</span>
        <span>關稅矩陣權重：{Math.round(data.tariff_weight * 100)}%</span>
        <span>·</span>
        <span>更新：{new Date(data.updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}</span>
      </div>
    </div>
  );
}
