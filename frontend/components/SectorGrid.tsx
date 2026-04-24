// SectorGrid.tsx — Bento Grid 板塊容器（含行動版收折）
"use client";

import type { SignalSnapshot, CompositeSnapshot } from "@/lib/types";
import { sortedSectors } from "@/lib/signals";
import { SectorCard } from "./SectorCard";
import { SkeletonCard } from "./SkeletonCard";

interface SectorGridProps {
  data: SignalSnapshot | null;
  isLoading?: boolean;
  composite?: CompositeSnapshot | null;
}

const SKELETON_COUNT = 8;

export function SectorGrid({ data, isLoading = false, composite }: SectorGridProps) {

  if (isLoading) {
    return (
      <section aria-label="板塊載入中" className="mt-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="mt-6 p-8 text-center rounded-2xl bg-zinc-100 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
        <p className="text-zinc-500 dark:text-zinc-400">無法載入板塊資料</p>
      </section>
    );
  }

  const sectors = sortedSectors(data.sectors);
  const featuredIds = new Set(
    sectors
      .filter((s) => s.level === "強烈關注")
      .map((s) => s.id)
  );

  return (
    <section aria-label="板塊概覽" className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-white">
          板塊偵測
        </h2>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {sectors.length} 個板塊
        </span>
      </div>

      {/* Desktop: Bento Grid */}
      <div className="hidden md:grid grid-cols-3 lg:grid-cols-4 gap-3">
        {sectors.map((s, i) => (
          <div
            key={s.id}
            className={featuredIds.has(s.id) ? "col-span-2" : ""}
          >
            <SectorCard
              sectorId={s.id}
              sector={s}
              featured={featuredIds.has(s.id)}
              defaultExpanded={false}
              composite={composite}
              macroWarning={data?.macro?.warning}
              animIndex={i}
            />
          </div>
        ))}
      </div>

      {/* Mobile: Accordion list */}
      <div className="flex flex-col gap-3 md:hidden">
        {sectors.map((s, i) => (
          <SectorCard
            key={s.id}
            sectorId={s.id}
            sector={s}
            featured={false}
            defaultExpanded={false}
            composite={composite}
            macroWarning={data?.macro?.warning}
            animIndex={i}
          />
        ))}
      </div>
    </section>
  );
}
