"use client";
// CommodityPanel.tsx — 商品市場儀表板主體（Client Component + 同排同步展開）
import { useState, useCallback } from "react";
import type { CommoditySnapshot } from "@/lib/types";
import { CommodityCard } from "@/components/CommodityCard";
import { YieldCurveChart } from "@/components/YieldCurveChart";

interface Props {
  data: CommoditySnapshot | null;
}

const CATEGORY_ORDER = [
  "precious_metal", "energy", "industrial", "index", "bonds", "crypto",
];
const CATEGORY_LABELS: Record<string, string> = {
  precious_metal: "貴金屬",
  energy:         "能源",
  industrial:     "工業金屬",
  index:          "指數 / 情緒",
  bonds:          "債券殖利率",
  crypto:         "加密貨幣",
};

const OVERALL_STYLE: Record<string, string> = {
  risk_off: "border-red-500/40 bg-red-500/10",
  caution:  "border-amber-500/40 bg-amber-500/10",
  neutral:  "border-blue-500/40 bg-blue-500/10",
  risk_on:  "border-emerald-500/40 bg-emerald-500/10",
};

/** 同排同步：以 cols=3 為基準計算 rowIndex，同一 row 的所有卡片一起展開/收合 */
function useRowSync() {
  // expandedRows[cat] = Set<rowIndex>
  const [expandedRows, setExpandedRows] = useState<Record<string, Set<number>>>({});

  const isExpanded = useCallback(
    (cat: string, idx: number) => expandedRows[cat]?.has(Math.floor(idx / 3)) ?? false,
    [expandedRows],
  );

  const toggle = useCallback((cat: string, idx: number, listLen: number) => {
    const rowIdx = Math.floor(idx / 3);
    setExpandedRows(prev => {
      const cur = new Set(prev[cat] ?? []);
      if (cur.has(rowIdx)) {
        cur.delete(rowIdx);
      } else {
        cur.add(rowIdx);
      }
      return { ...prev, [cat]: cur };
    });
  }, []);

  return { isExpanded, toggle };
}

export function CommodityPanel({ data }: Props) {
  const { isExpanded, toggle } = useRowSync();

  if (!data) {
    return (
      <div className="py-16 text-center text-zinc-400 dark:text-zinc-500">
        <p className="text-lg">商品市場資料尚未產生</p>
        <p className="text-sm mt-2">請先執行後端分析（選單 C）並推送資料</p>
      </div>
    );
  }

  const { assets, yield_curve, yield_curve_analysis, market_summary, updated_at } = data;

  // 依 CATEGORY_ORDER 分組
  const grouped: Record<string, typeof assets[string][]> = {};
  for (const cat of CATEGORY_ORDER) grouped[cat] = [];
  for (const asset of Object.values(assets)) {
    if (grouped[asset.category]) grouped[asset.category].push(asset);
    else grouped["index"]?.push(asset);
  }

  return (
    <div className="space-y-8 mt-6">

      {/* ── 市場總覽 Banner ─────────────────────────────────────────── */}
      {market_summary && (
        <section className={`rounded-xl border px-4 py-3.5 ${OVERALL_STYLE[market_summary.overall] ?? OVERALL_STYLE.neutral}`}>
          <p className="text-sm font-semibold text-zinc-900 dark:text-white">
            {market_summary.headline}
          </p>
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-zinc-600 dark:text-zinc-400">
            <span>觸發信號 <strong className="text-zinc-900 dark:text-white">{market_summary.total_triggered}</strong></span>
            <span>高危 <strong className="text-red-600 dark:text-red-400">{market_summary.high_count}</strong></span>
            <span>中危 <strong className="text-amber-600 dark:text-amber-400">{market_summary.medium_count}</strong></span>
          </div>
          {market_summary.key_alerts.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {market_summary.key_alerts.map((alert, i) => (
                <li key={i} className="text-[11px] text-red-700 dark:text-red-400 flex gap-1.5">
                  <span className="shrink-0">▲</span><span>{alert}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* ── 收益率曲線 ─────────────────────────────────────────────── */}
      {yield_curve && yield_curve.length > 0 && (
        <section>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
            📈 美債收益率曲線
          </h3>
          <YieldCurveChart
            data={yield_curve}
            updated_at={updated_at}
            analysis={yield_curve_analysis}
          />
        </section>
      )}

      {/* ── 各類別資產卡片 ─────────────────────────────────────────── */}
      {CATEGORY_ORDER.map(cat => {
        const list = grouped[cat] ?? [];
        if (list.length === 0) return null;
        return (
          <section key={cat}>
            <h3 className="text-base font-bold text-zinc-900 dark:text-white mb-3">
              {CATEGORY_LABELS[cat] ?? cat}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map((asset, idx) => (
                <CommodityCard
                  key={asset.slug}
                  asset={asset}
                  isExpanded={isExpanded(cat, idx)}
                  onToggle={() => toggle(cat, idx, list.length)}
                />
              ))}
            </div>
          </section>
        );
      })}

      {/* 資料時間戳記 */}
      {updated_at && (
        <p className="text-[10px] text-zinc-400 dark:text-zinc-600 text-right">
          資料更新：{new Date(updated_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}
        </p>
      )}
    </div>
  );
}
