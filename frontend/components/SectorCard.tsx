// SectorCard.tsx — 單一板塊 Bento 卡片（含7燈 + 個股展開）
"use client";

import { useState } from "react";
import type { SectorData, CompositeSnapshot } from "@/lib/types";
import { SignalDots } from "./SignalDots";
import { StockTable } from "./StockTable";
import { LEVEL_CONFIG, CYCLE_STAGE_CONFIG, type CycleStageKey } from "@/lib/signals";

interface SectorCardProps {
  sectorId: string;
  sector: SectorData;
  featured?: boolean;
  defaultExpanded?: boolean;
  composite?: CompositeSnapshot | null;
  macroWarning?: boolean;
}

export function SectorCard({ sectorId, sector, featured = false, defaultExpanded = false, composite, macroWarning }: SectorCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const levelCfg = LEVEL_CONFIG[sector.level] ?? LEVEL_CONFIG["忽略"];
  const stocks = sector.stocks ?? [];
  const hasStocks = stocks.length > 0;
  const cdScore = composite?.scores?.[sectorId];
  const isLongTermBull = !!cdScore &&
    (cdScore.signal === "強烈買入" || cdScore.signal === "買入");

  return (
    <article
      className={`
        group rounded-2xl border backdrop-blur-sm
        transition-all duration-300
        ${levelCfg.bgClass}
        ${expanded ? "shadow-lg" : "hover:shadow-md"}
        overflow-hidden
      `}
      aria-label={`${sector.name_zh} 板塊（${sector.level}）`}
    >
      {/* 卡片頭部 */}
      <button
        className="w-full p-3 flex items-start justify-between text-left"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={`sector-detail-${sectorId}`}
      >
        <div className="flex flex-col gap-1.5 min-w-0">
          {/* 板塊名稱 + 等級 badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`font-bold ${featured ? "text-lg" : "text-base"} text-zinc-900 dark:text-white truncate`}>
              {sector.name_zh}
            </h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${levelCfg.badgeClass}`}>
              {levelCfg.emoji} {sector.level}
            </span>
            {isLongTermBull && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-purple-100/80 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-200/60 dark:border-purple-800/40">
                🎯 長線共振
              </span>
            )}
            {sector.source === "auto" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-blue-100/80 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200/60 dark:border-blue-800/40"
                title={sector.homogeneity != null ? `同質性: ${(sector.homogeneity * 100).toFixed(0)}%` : "自動分類板塊"}
              >
                ✨ 自動
              </span>
            )}
            {sector.cycle_stage && (() => {
              const cfg = CYCLE_STAGE_CONFIG[sector.cycle_stage as CycleStageKey];
              return cfg ? (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${cfg.chipCls}`}
                  title={cfg.tooltip}
                >
                  {cfg.emoji} {cfg.label}
                </span>
              ) : null;
            })()}
          </div>

          {/* 總分 + 7燈 */}
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold ${levelCfg.textClass}`}>
              {sector.total.toFixed(1)}
            </span>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">/ 7 燈</span>
            <span className="ml-1"><SignalDots signals={sector.signals} size={featured ? "lg" : "sm"} /></span>
          </div>
        </div>

        {/* 展開箭頭 */}
        <div className={`
          ml-2 mt-1 shrink-0 w-6 h-6 flex items-center justify-center
          rounded-full text-zinc-400 dark:text-zinc-500
          transition-transform duration-200
          ${expanded ? "rotate-180" : ""}
          ${hasStocks ? "visible" : "invisible"}
        `}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>

      {/* 展開的個股列表 */}
      {hasStocks && (
        <div
          id={`sector-detail-${sectorId}`}
          className={`grid transition-[grid-template-rows,opacity] duration-500 ${expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
        >
          <div className="overflow-hidden min-h-0">
            <div className="px-3 pb-3 border-t border-zinc-200/30 dark:border-zinc-700/30 pt-2">
              <StockTable stocks={stocks} sectorLevel={sector.level} macroWarning={macroWarning} cycleStage={sector.cycle_stage ?? undefined} />
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
