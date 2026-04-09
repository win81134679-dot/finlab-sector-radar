// CompositePanel.tsx — 三合一複合訊號面板（Tab #4）
// 顯示：NLP 關鍵詞命中、關稅矩陣情境、板塊複合評分排行
// 含權重敏感度分析（5 種 NLP:關稅 預設）

"use client";

import { useState } from "react";
import type { CompositeSnapshot, SensitivitySnapshot, SectorStability } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";

interface Props {
  data:        CompositeSnapshot | null;
  sensitivity: SensitivitySnapshot | null;
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

function StabilityBadge({ stab }: { stab?: SectorStability }) {
  if (!stab) return null;
  if (stab.always_buy)  return <span title="所有權重預設下皆為買入（高穩健性）" className="text-xs select-none">🔒</span>;
  if (stab.always_sell) return <span title="所有權重預設下皆為賣出（高穩健性）" className="text-xs select-none">🔒</span>;
  if (stab.rank_std > 3) return <span title={`排名標準差 ${stab.rank_std.toFixed(1)}（對權重敏感）`} className="text-xs select-none opacity-60">⚠️</span>;
  return null;
}

interface SectorRowProps {
  sectorId: string;
  score:    { composite: number; signal: string };
  stab?:    SectorStability;
}
function SectorRow({ sectorId, score, stab }: SectorRowProps) {
  const bgClass   = SIGNAL_BG[score.signal]   ?? SIGNAL_BG["中性"];
  const textClass = SIGNAL_COLOR[score.signal] ?? "text-zinc-500";
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${bgClass}`}>
      <div className="w-28 shrink-0 flex items-center gap-1">
        <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate">{getSectorName(sectorId)}</span>
        <StabilityBadge stab={stab} />
      </div>
      <ScoreBar value={score.composite} />
      <span className={`text-xs shrink-0 w-22 text-right ${textClass}`}>{score.signal}</span>
    </div>
  );
}

export function CompositePanel({ data, sensitivity }: Props) {
  // 預設選"均衡 (5:5)" = index 2；若 sensitivity 不存在就只顯示 composite
  const [presetIdx, setPresetIdx] = useState<number>(2);

  if (!data && !sensitivity) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">🔄</span>
        <p className="text-sm">複合訊號資料尚未生成</p>
        <p className="text-xs mt-1 opacity-60">請先執行一次 Python --auto 分析</p>
      </div>
    );
  }

  // 決定目前顯示的分數來源
  const activePreset = sensitivity?.presets[presetIdx];
  const activeScores: Record<string, { composite: number; signal: string }> =
    activePreset?.scores ?? data?.scores ?? {};
  const activeStrength  = activePreset?.signal_strength ?? data?.signal_strength ?? 0;

  const sortedScores = Object.entries(activeScores)
    .sort((a, b) => b[1].composite - a[1].composite);
  const buyScores  = sortedScores.filter(([, v]) => v.composite > 0.05);
  const sellScores = sortedScores.filter(([, v]) => v.composite < -0.05).reverse();

  const strengthPct = Math.round(activeStrength * 100);
  const strengthColor =
    activeStrength >= 0.7 ? "text-emerald-500" :
    activeStrength >= 0.4 ? "text-amber-500" :
    "text-zinc-400";

  const displayScenario = sensitivity?.scenario ?? data?.scenario;
  const displayNlpW     = activePreset?.nlp_weight    ?? data?.nlp_weight    ?? 0.5;
  const displayTariffW  = activePreset?.tariff_weight ?? data?.tariff_weight ?? 0.5;

  return (
    <div className="space-y-5">
      {/* ── 學術誠實聲明橫幅 ── */}
      {sensitivity && (
        <div className="rounded-lg border border-amber-300/60 dark:border-amber-700/40 bg-amber-50/80 dark:bg-amber-900/20 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
          <span className="font-semibold">⚠ 工程預設聲明：</span>
          NLP : 關稅 權重比例為工程預設值（非論文最佳化）。
          下方可切換 5 種預設以檢驗穩健性。
          排名在所有預設下均穩定的板塊（🔒）可信度較高；帶有 ⚠️ 的板塊對權重選擇敏感。
        </div>
      )}

      {/* ── 頂部摘要卡片 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">關稅情境</p>
          <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
            {SCENARIO_LABELS[displayScenario ?? ""] ?? displayScenario}
          </p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">訊號強度</p>
          <p className={`text-2xl font-bold ${strengthColor}`}>{strengthPct}%</p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">分析貼文</p>
          <p className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">{data?.source_count ?? 0}</p>
        </div>
        <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 p-4">
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase tracking-wide mb-1">命中關鍵詞</p>
          <p className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">{data?.keyword_hits.length ?? 0}</p>
        </div>
      </div>

      {/* ── 權重預設切換分頁 ── */}
      {sensitivity && (
        <div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">
            NLP : 關稅 權重預設
            <span className="ml-2 opacity-70 font-mono">（🔒 = 所有預設一致，⚠️ = 對權重敏感）</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {sensitivity.presets.map((preset, i) => (
              <button
                key={i}
                onClick={() => setPresetIdx(i)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  i === presetIdx
                    ? "bg-blue-500 text-white border-blue-500"
                    : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 border-zinc-200/60 dark:border-zinc-700/60 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── 關鍵詞標籤 ── */}
      {data?.keyword_hits && data.keyword_hits.length > 0 && (
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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mb-3 flex items-center gap-1.5">
            <span>📈 受益板塊</span>
            <span className="text-xs font-normal text-zinc-400">（composite &gt; 0）</span>
          </h3>
          <div className="space-y-1.5">
            {buyScores.length > 0
              ? buyScores.map(([sid, score]) => (
                  <SectorRow
                    key={sid}
                    sectorId={sid}
                    score={score}
                    stab={sensitivity?.stability[sid]}
                  />
                ))
              : <p className="text-xs text-zinc-400 py-4 text-center">無明顯受益板塊</p>
            }
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-red-500 dark:text-red-400 mb-3 flex items-center gap-1.5">
            <span>📉 受害板塊</span>
            <span className="text-xs font-normal text-zinc-400">（composite &lt; 0）</span>
          </h3>
          <div className="space-y-1.5">
            {sellScores.length > 0
              ? sellScores.map(([sid, score]) => (
                  <SectorRow
                    key={sid}
                    sectorId={sid}
                    score={score}
                    stab={sensitivity?.stability[sid]}
                  />
                ))
              : <p className="text-xs text-zinc-400 py-4 text-center">無明顯受害板塊</p>
            }
          </div>
        </div>
      </div>

      {/* ── 穩健性摘要（僅在有 sensitivity 時顯示）── */}
      {sensitivity && (() => {
        const alwaysBuy  = Object.entries(sensitivity.stability).filter(([, v]) => v.always_buy).map(([k]) => k);
        const alwaysSell = Object.entries(sensitivity.stability).filter(([, v]) => v.always_sell).map(([k]) => k);
        if (alwaysBuy.length === 0 && alwaysSell.length === 0) return null;
        return (
          <div className="rounded-xl border border-zinc-200/40 dark:border-zinc-800/40 bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-3 space-y-2">
            <p className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">🔒 跨權重穩健板塊（所有5種預設下結論一致）</p>
            {alwaysBuy.length > 0 && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                <span className="font-medium text-emerald-600 dark:text-emerald-400">穩健買入：</span>
                {alwaysBuy.map(getSectorName).join("、")}
              </p>
            )}
            {alwaysSell.length > 0 && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                <span className="font-medium text-red-500 dark:text-red-400">穩健賣出：</span>
                {alwaysSell.map(getSectorName).join("、")}
              </p>
            )}
          </div>
        );
      })()}

      {/* ── 頁尾資訊 ── */}
      <div className="flex flex-wrap gap-3 text-xs text-zinc-400 dark:text-zinc-500">
        <span>NLP 權重：{Math.round(displayNlpW * 100)}%</span>
        <span>·</span>
        <span>關稅矩陣權重：{Math.round(displayTariffW * 100)}%</span>
        {activePreset && sensitivity && (
          <>
            <span>·</span>
            <span>預設：{activePreset.label}</span>
          </>
        )}
        <span>·</span>
        <span>
          更新：{new Date((sensitivity?.updated_at ?? data?.updated_at) as string)
            .toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
        </span>
      </div>
    </div>
  );
}
