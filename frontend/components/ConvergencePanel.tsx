// ConvergencePanel.tsx — 最強進場訊號面板（雙重確認算法）
// 短線非忽略（燈號比率）× 50% ＋ 長線複合評分（NLP+關稅）× 50%
// 參考：Asness, Moskowitz & Pedersen (2013) "Value and Momentum Everywhere"

"use client";

import { useState, useMemo } from "react";
import type { SignalSnapshot, CompositeSnapshot, HoldingsSnapshot, MagaSnapshot } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";

// 長線複合分需超過此閾值才進入交集
const COMPOSITE_THRESHOLD = 0.10;

interface Props {
  snapshot:  SignalSnapshot | null | undefined;
  composite: CompositeSnapshot | null;
  holdings:  HoldingsSnapshot | null;
  magaData:  MagaSnapshot | null;
}

interface ConvergenceSector {
  sectorId:   string;
  level:      string;
  lightRatio: number;
  composite:  number;
  combined:   number; // 0–100
  stockCount: number;
}

interface ConvergenceStock {
  id:       string;
  sectorId: string;
  score:    number | null;
  grade:    string;
  tags:     Array<"持倉" | "MAGA">;
  combined: number;
}

const LEVEL_COLOR: Record<string, string> = {
  "強烈關注": "text-emerald-600 dark:text-emerald-400",
  "觀察中":   "text-amber-600  dark:text-amber-400",
  "忽略":     "text-zinc-400",
};

const LEVEL_DOT: Record<string, string> = {
  "強烈關注": "bg-emerald-500",
  "觀察中":   "bg-amber-400",
  "忽略":     "bg-zinc-400",
};

const GRADE_COLOR: Record<string, string> = {
  "A+": "text-emerald-600 dark:text-emerald-400 font-bold",
  "A":  "text-emerald-500 dark:text-emerald-400",
  "B":  "text-blue-500   dark:text-blue-400",
  "C":  "text-zinc-400",
  "D":  "text-red-400",
};

export function ConvergencePanel({ snapshot, composite, holdings, magaData }: Props) {
  const [view, setView] = useState<"stocks" | "rank">("stocks");

  // ──── 計算交集板塊 ────────────────────────────────────────────────
  const convergenceSectors = useMemo<ConvergenceSector[]>(() => {
    if (!snapshot || !composite) return [];

    return Object.entries(snapshot.sectors)
      .filter(([sectorId, sector]) => {
        if (sector.level === "忽略") return false;
        const cd = composite.scores[sectorId];
        return cd != null && cd.composite > COMPOSITE_THRESHOLD;
      })
      .map(([sectorId, sector]) => {
        const cd         = composite.scores[sectorId];
        const lightCount = sector.signals.filter((s) => s > 0).length;
        const lightRatio = sector.signals.length > 0 ? lightCount / sector.signals.length : 0;
        const normComp   = Math.max(0, Math.min(1, (cd.composite + 2) / 4));
        const combined   = Math.round((lightRatio * 0.5 + normComp * 0.5) * 100);
        return {
          sectorId,
          level:      sector.level,
          lightRatio,
          composite:  cd.composite,
          combined,
          stockCount: sector.stocks.length,
        };
      })
      .sort((a, b) => b.combined - a.combined);
  }, [snapshot, composite]);

  // ──── 計算交集個股 ────────────────────────────────────────────────
  const convergenceStocks = useMemo<ConvergenceStock[]>(() => {
    if (!snapshot || convergenceSectors.length === 0) return [];

    const holdingIds  = new Set(Object.keys(holdings?.positions ?? {}));
    const magaBeneIds = new Set(
      (magaData?.stocks ?? [])
        .filter((s) => s.category === "beneficiary")
        .map((s) => s.id)
    );
    const intersectIds = new Set(convergenceSectors.map((s) => s.sectorId));
    const combinedMap  = Object.fromEntries(
      convergenceSectors.map((s) => [s.sectorId, s.combined])
    );

    const seen = new Set<string>();
    const result: ConvergenceStock[] = [];

    for (const [sectorId, sector] of Object.entries(snapshot.sectors)) {
      if (!intersectIds.has(sectorId)) continue;
      for (const stock of sector.stocks) {
        if (seen.has(stock.id)) continue;
        seen.add(stock.id);
        const tags: Array<"持倉" | "MAGA"> = [];
        if (holdingIds.has(stock.id))  tags.push("持倉");
        if (magaBeneIds.has(stock.id)) tags.push("MAGA");
        result.push({
          id:       stock.id,
          sectorId,
          score:    stock.score ?? null,
          grade:    stock.grade,
          tags,
          combined: combinedMap[sectorId] ?? 0,
        });
      }
    }

    // 排序：有標籤優先，再依板塊綜合分數
    return result.sort((a, b) => {
      const tagWeight = (s: ConvergenceStock) => s.tags.length * 10 + s.combined;
      return tagWeight(b) - tagWeight(a);
    });
  }, [snapshot, composite, holdings, magaData, convergenceSectors]);

  // ──── 空狀態 ──────────────────────────────────────────────────────
  if (!snapshot && !composite) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">⭐</span>
        <p className="text-sm">尚無資料</p>
        <p className="text-xs mt-1 opacity-60">請先執行 Python --auto 分析</p>
      </div>
    );
  }

  if (convergenceSectors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">🔍</span>
        <p className="text-sm font-medium">目前無雙重確認板塊</p>
        <p className="text-xs mt-1 opacity-60 text-center">
          {!snapshot  && "短線訊號尚未生成 · "}
          {!composite && "長線複合評分尚未生成"}
          {snapshot && composite && "短線非忽略且長線複合分 > 0.10 的板塊目前為零"}
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-6">

      {/* Header + 統計 */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">最強進場訊號</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            短線燈號比率 × 50%  ＋  長線複合評分（NLP＋關稅）× 50%
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs shrink-0">
          <span className="px-2.5 py-1 rounded-full bg-emerald-100/70 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 font-medium">
            {convergenceSectors.length} 板塊
          </span>
          <span className="px-2.5 py-1 rounded-full bg-blue-100/70 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium">
            {convergenceStocks.length} 個股
          </span>
        </div>
      </div>

      {/* View toggle */}
      <div className="flex gap-1 p-1 rounded-lg bg-zinc-100/70 dark:bg-zinc-800/70 w-fit">
        {(["stocks", "rank"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors font-medium ${
              view === v
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            {v === "stocks" ? "交集個股" : "板塊排行"}
          </button>
        ))}
      </div>

      {/* ── 板塊排行 ── */}
      {view === "rank" && (
        <div className="space-y-2">
          {convergenceSectors.map((sec) => (
            <div
              key={sec.sectorId}
              className="flex items-center gap-4 px-4 py-3 rounded-xl border border-zinc-200/50 dark:border-zinc-700/50 bg-white/60 dark:bg-zinc-900/40"
            >
              {/* 短線燈號 dot */}
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${LEVEL_DOT[sec.level] ?? "bg-zinc-400"}`} />

              {/* 板塊名稱 + 短線等級 */}
              <div className="w-28 shrink-0">
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                  {getSectorName(sec.sectorId)}
                </p>
                <p className={`text-xs ${LEVEL_COLOR[sec.level] ?? "text-zinc-400"}`}>{sec.level}</p>
              </div>

              {/* 綜合分數進度條 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <div className="flex-1 bg-zinc-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all duration-500"
                      style={{ width: `${sec.combined}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-zinc-600 dark:text-zinc-400 w-8 text-right">
                    {sec.combined}
                  </span>
                </div>
                <div className="flex gap-3 text-xs text-zinc-400">
                  <span>短線 {Math.round(sec.lightRatio * 100)}%</span>
                  <span>長線 {sec.composite >= 0 ? "+" : ""}{sec.composite.toFixed(2)}</span>
                </div>
              </div>

              {/* 個股數量 */}
              <span className="text-xs text-zinc-400 shrink-0">{sec.stockCount} 支</span>
            </div>
          ))}

          <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center pt-2">
            綜合分數 = 短線燈號比率 × 50% ＋ 正規化複合分 × 50%  ·  Asness, Moskowitz & Pedersen (2013)
          </p>
        </div>
      )}

      {/* ── 交集個股 ── */}
      {view === "stocks" && (
        <div className="space-y-2">
          {convergenceStocks.length === 0 ? (
            <p className="text-sm text-zinc-400 text-center py-8">
              交集板塊中暫無個股資料
            </p>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {convergenceStocks.map((stock) => (
                  <div
                    key={stock.id}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-zinc-200/50 dark:border-zinc-700/50 bg-white/60 dark:bg-zinc-900/40"
                  >
                    {/* 左側強度色條 */}
                    <div
                      className="w-1 self-stretch rounded-full shrink-0"
                      style={{
                        background:
                          stock.combined >= 70 ? "#10b981" :
                          stock.combined >= 50 ? "#3b82f6" : "#a1a1aa",
                      }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                          {stock.id}
                        </span>
                        <span className={`text-xs ${GRADE_COLOR[stock.grade] ?? "text-zinc-400"}`}>
                          {stock.grade}
                        </span>
                        {stock.tags.includes("持倉") && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
                            💼
                          </span>
                        )}
                        {stock.tags.includes("MAGA") && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100/80 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                            🇺🇸
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-zinc-400 mt-0.5 truncate">
                        {getSectorName(stock.sectorId)}
                      </p>
                    </div>
                    {stock.score != null && (
                      <span className="text-xs font-mono text-zinc-500 dark:text-zinc-400 shrink-0">
                        {stock.score.toFixed(1)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center pt-2">
                僅顯示短線非忽略且長線複合分 &gt; {COMPOSITE_THRESHOLD} 的板塊個股
                ·  💼 持倉  🇺🇸 MAGA受益
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
