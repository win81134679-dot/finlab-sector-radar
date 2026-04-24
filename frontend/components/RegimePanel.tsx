"use client";
// RegimePanel.tsx — 盤性診斷面板（法人盤/大戶盤/散戶情緒盤辨識）
// 對應老師心法七項訊號框架

import { useState, useMemo } from "react";
import type { SectorData } from "@/lib/types";
import { fetchLatestSnapshot } from "@/lib/fetcher";
import {
  classifyMarketRegime,
  classifySectorRegime,
  classifyStockRegime,
  type RegimeType,
  type PhaseType,
  type ActionType,
  type StockRegimeResult,
  type SectorRegimeResult,
  type MarketRegimeResult,
} from "@/lib/regime";

type SnapshotType = Awaited<ReturnType<typeof fetchLatestSnapshot>>;

// ── 常數 ──────────────────────────────────────────────────────────────────────

const REGIME_COLOR: Record<RegimeType, string> = {
  "法人盤":     "bg-emerald-100/90 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 border-emerald-300/60 dark:border-emerald-700/50",
  "大戶盤":     "bg-sky-100/90 dark:bg-sky-900/40 text-sky-800 dark:text-sky-200 border-sky-300/60 dark:border-sky-700/50",
  "散戶情緒盤": "bg-red-100/90 dark:bg-red-900/40 text-red-800 dark:text-red-200 border-red-300/60 dark:border-red-700/50",
  "混合盤":     "bg-amber-100/90 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border-amber-300/60 dark:border-amber-700/50",
  "不明":       "bg-zinc-100 dark:bg-zinc-800/50 text-zinc-500 dark:text-zinc-400 border-zinc-200/60 dark:border-zinc-700/40",
};

const REGIME_ICON: Record<RegimeType, string> = {
  "法人盤":     "🏦",
  "大戶盤":     "🐋",
  "散戶情緒盤": "🐑",
  "混合盤":     "🔀",
  "不明":       "❓",
};

const PHASE_COLOR: Record<PhaseType, string> = {
  "建倉期": "text-sky-600 dark:text-sky-400",
  "拉升期": "text-emerald-600 dark:text-emerald-400",
  "派發期": "text-red-600 dark:text-red-400",
  "整理期": "text-amber-600 dark:text-amber-400",
  "不明":   "text-zinc-400",
};

const ACTION_COLOR: Record<ActionType, string> = {
  "可跟進 · 追蹤法人動向":   "bg-emerald-600 text-white",
  "短線機動（嚴設停損）":    "bg-sky-600 text-white",
  "⚠️ 不建議 · 等回調確認": "bg-amber-500 text-white",
  "⚠️ 出場或空手":          "bg-red-600 text-white",
  "觀望":                   "bg-zinc-500 text-white",
};

const SECTOR_FILTER_OPTIONS = ["全部", "法人盤", "大戶盤", "散戶情緒盤", "混合盤"] as const;
type FilterOption = typeof SECTOR_FILTER_OPTIONS[number];

// ── 篩選維度定義 ──────────────────────────────────────────────────────────────

type ActionGroup = "entry" | "watch" | "exit";

const ACTION_GROUPS: Record<ActionGroup, ActionType[]> = {
  entry: ["可跟進 · 追蹤法人動向", "短線機動（嚴設停損）"],
  watch: ["觀望"],
  exit:  ["⚠️ 出場或空手", "⚠️ 不建議 · 等回調確認"],
};

const ACTION_GROUP_LABELS: Record<ActionGroup, string> = {
  entry: "🟢 可進場",
  watch: "👁 觀望",
  exit:  "🔴 出場訊號",
};

// 訊號篩選選項（跳過③499張，不支援）
const SIGNAL_FILTER_OPTIONS = [
  { idx: 0, label: "①K棒",  desc: "K棒規律" },
  { idx: 1, label: "②量能", desc: "溫和放量" },
  { idx: 3, label: "④法人", desc: "法人籌碼觸發" },
  { idx: 4, label: "⑤領頭", desc: "板塊前1/3" },
  { idx: 5, label: "⑥KDJ", desc: "KDJ向上" },
  { idx: 6, label: "⑦冷門", desc: "無散戶追高" },
] as const;

interface FilterState {
  actionGroups:  Set<ActionGroup>;
  signalIndices: Set<number>;
}

// ── 大盤盤性 Banner ──────────────────────────────────────────────────────────

function MarketRegimeBanner({ result }: { result: MarketRegimeResult }) {
  return (
    <div className={`rounded-xl border p-4 ${REGIME_COLOR[result.regime]}`}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{REGIME_ICON[result.regime]}</span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-lg">{result.regime}</h3>
              <span className={`text-sm font-semibold ${PHASE_COLOR[result.phase]}`}>· {result.phase}</span>
              <span className="text-xs opacity-60">信心 {result.confidence}%</span>
            </div>
            <p className="text-sm opacity-80 mt-0.5">{result.description}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {result.signals.map((s, i) => (
            <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-white/30 dark:bg-black/20 font-medium">{s}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 訊號燈 ──────────────────────────────────────────────────────────────────

function SignalLight({ score, supported }: { score: number; supported: boolean }) {
  if (!supported) return <span className="text-zinc-300 dark:text-zinc-600">⊘</span>;
  if (score >= 2)  return <span className="text-emerald-500">●</span>;
  if (score >= 1)  return <span className="text-sky-400">●</span>;
  if (score === 0) return <span className="text-zinc-300 dark:text-zinc-600">●</span>;
  if (score >= -1) return <span className="text-amber-500">●</span>;
  return <span className="text-red-500">●</span>;
}

// ── 個股七訊號展開 ──────────────────────────────────────────────────────────

function StockSignalDetail({ result, sectorBadges }: { result: StockRegimeResult; sectorBadges?: string[] }) {
  return (
    <div className="bg-zinc-50/80 dark:bg-zinc-800/40 rounded-lg p-3 space-y-1.5">
      {/* 個股標頭 */}
      <div className="flex items-center gap-2 pb-1.5 border-b border-zinc-200/40 dark:border-zinc-700/30 flex-wrap">
        <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">{result.stockId}</span>
        {result.stockName && <span className="text-xs text-zinc-500">{result.stockName}</span>}
        {sectorBadges && sectorBadges.map(name => (
          <span key={name} className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700 text-zinc-500 font-medium">{name}</span>
        ))}
        <span className={`text-[11px] px-2 py-0.5 rounded-full border font-bold ${REGIME_COLOR[result.regime]}`}>
          {REGIME_ICON[result.regime]} {result.regime}
        </span>
        <span className={`text-xs font-semibold ${PHASE_COLOR[result.phase]}`}>{result.phase}</span>
        <span className={`ml-auto text-[10px] px-2 py-0.5 rounded font-bold ${ACTION_COLOR[result.action]}`}>
          {result.action}
        </span>
      </div>

      {/* 七訊號列表 */}
      {result.signals.map((sig, i) => (
        <div key={i} className="flex items-start gap-2">
          <SignalLight score={sig.score} supported={sig.supported} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 shrink-0">{sig.label}</span>
              {sig.futureExpansion && (
                <span className="text-[9px] px-1 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700 text-zinc-400 font-medium">未來擴充</span>
              )}
              <span className={`text-xs ${sig.supported ? "" : "text-zinc-400"}`}>{sig.value}</span>
            </div>
            {sig.detail && <p className="text-[10px] text-zinc-400 mt-0.5">{sig.detail}</p>}
          </div>
        </div>
      ))}

      {/* 盤性分數對比 */}
      <div className="flex gap-3 pt-1.5 text-[10px] text-zinc-400 border-t border-zinc-200/30 dark:border-zinc-700/20">
        <span>🏦 法人 {result.regimeScores.institutional.toFixed(1)}</span>
        <span>🐋 大戶 {result.regimeScores.whale.toFixed(1)}</span>
        <span>🐑 散戶 {result.regimeScores.retail.toFixed(1)}</span>
        <span className="ml-auto">信心 {result.confidence}%</span>
      </div>
    </div>
  );
}

// ── 篩選工具列 ────────────────────────────────────────────────────────────────

interface FilterToolbarProps {
  state:       FilterState;
  onChange:    (next: FilterState) => void;
  resultCount: number;
  hasActive:   boolean;
}

function FilterToolbar({ state, onChange, resultCount, hasActive }: FilterToolbarProps) {
  function toggleAction(group: ActionGroup) {
    const next = new Set(state.actionGroups);
    if (next.has(group)) next.delete(group); else next.add(group);
    onChange({ ...state, actionGroups: next });
  }

  function toggleSignal(idx: number) {
    const next = new Set(state.signalIndices);
    if (next.has(idx)) next.delete(idx); else next.add(idx);
    onChange({ ...state, signalIndices: next });
  }

  function clearAll() {
    onChange({ actionGroups: new Set<ActionGroup>(), signalIndices: new Set<number>() });
  }

  function applyPreset(preset: "entry" | "entry_strong") {
    if (preset === "entry") {
      onChange({ actionGroups: new Set<ActionGroup>(["entry"]), signalIndices: new Set<number>() });
    } else {
      onChange({ actionGroups: new Set<ActionGroup>(["entry"]), signalIndices: new Set<number>([3, 4]) });
    }
  }

  return (
    <div className="border border-zinc-200/50 dark:border-zinc-700/30 rounded-xl p-3 space-y-2.5 bg-white/50 dark:bg-zinc-900/30">
      {/* 第一排：動作狀態篩選 */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider shrink-0 w-10">動作</span>
        {(["entry", "watch", "exit"] as ActionGroup[]).map(group => (
          <button
            key={group}
            onClick={() => toggleAction(group)}
            className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
              state.actionGroups.has(group)
                ? group === "entry"
                  ? "bg-emerald-600 text-white border-emerald-600"
                  : group === "watch"
                  ? "bg-zinc-600 text-white border-zinc-600"
                  : "bg-red-600 text-white border-red-600"
                : "bg-transparent text-zinc-500 border-zinc-300 dark:border-zinc-600 hover:border-zinc-400"
            }`}
          >
            {ACTION_GROUP_LABELS[group]}
          </button>
        ))}
        <div className="w-px h-4 bg-zinc-200 dark:bg-zinc-700 shrink-0 mx-1" />
        <span className="text-[10px] text-zinc-400 shrink-0">快速：</span>
        <button
          onClick={() => applyPreset("entry")}
          className="px-2 py-0.5 text-[11px] font-medium rounded border border-emerald-300 dark:border-emerald-700 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
        >
          可進場
        </button>
        <button
          onClick={() => applyPreset("entry_strong")}
          className="px-2 py-0.5 text-[11px] font-medium rounded border border-emerald-300 dark:border-emerald-700 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
        >
          可進場＋法人④⑤
        </button>
      </div>

      {/* 第二排：訊號篩選（AND 邏輯） */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider shrink-0 w-10">訊號</span>
        {SIGNAL_FILTER_OPTIONS.map(({ idx, label, desc }) => (
          <button
            key={idx}
            onClick={() => toggleSignal(idx)}
            title={desc}
            className={`px-2.5 py-1 text-xs font-mono font-medium rounded-full border transition-colors ${
              state.signalIndices.has(idx)
                ? "bg-sky-600 text-white border-sky-600"
                : "bg-transparent text-zinc-500 border-zinc-300 dark:border-zinc-600 hover:border-zinc-400"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-[10px] text-zinc-400 ml-1 hidden sm:inline">AND 邏輯 · 全部亮才顯示</span>
      </div>

      {/* 第三排：結果統計 */}
      {hasActive && (
        <div className="flex items-center justify-between pt-1 border-t border-zinc-100 dark:border-zinc-800">
          <span className="text-xs text-zinc-500">
            找到 <strong className="text-zinc-900 dark:text-white">{resultCount}</strong> 支符合標的
          </span>
          <button
            onClick={clearAll}
            className="text-[11px] text-zinc-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          >
            ✕ 清除篩選
          </button>
        </div>
      )}
    </div>
  );
}

// ── 篩選結果：個股平鋪列表 ───────────────────────────────────────────────────

interface FilteredStock extends StockRegimeResult {
  sectorNames: string[];  // 可能跞多個板塊
  sectorLevel: string;
}

function FilteredStockList({ stocks }: { stocks: FilteredStock[] }) {
  if (stocks.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-400">
        <div className="text-2xl mb-2">🔍</div>
        <p className="text-sm">無符合條件的標的</p>
        <p className="text-xs mt-1">試著調整篩選條件，或清除部分選項</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {stocks.map(s => (
        <StockSignalDetail
          key={s.stockId}
          result={s}
          sectorBadges={s.sectorNames}
        />
      ))}
    </div>
  );
}

// ── 板塊行 ──────────────────────────────────────────────────────────────────

function SectorRow({ result }: { result: SectorRegimeResult }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-zinc-200/50 dark:border-zinc-700/30 rounded-lg overflow-hidden">
      {/* 板塊摘要列 */}
      <button
        onClick={() => setExpanded(p => !p)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-zinc-50/60 dark:hover:bg-zinc-800/30 transition-colors text-left"
      >
        {/* 盤性 badge */}
        <span className={`text-[11px] px-2 py-0.5 rounded-full border font-bold shrink-0 ${REGIME_COLOR[result.regime]}`}>
          {REGIME_ICON[result.regime]} {result.regime}
        </span>

        {/* 板塊名 */}
        <span className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{result.sectorName}</span>

        {/* 板塊等級 */}
        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium shrink-0 ${
          result.sectorLevel === "強烈關注"
            ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200/60"
            : result.sectorLevel === "觀察中"
            ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200/60"
            : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border-zinc-200/60"
        }`}>
          {result.sectorLevel}
        </span>

        {/* 週期階段 */}
        <span className={`text-xs font-semibold ${PHASE_COLOR[result.phase]} hidden sm:block`}>{result.phase}</span>

        {/* 法人強度 */}
        <span className="text-xs text-zinc-400 ml-auto shrink-0">
          法人 {result.institutionalStrength} · {result.stockCount}支
        </span>

        {/* 展開箭頭 */}
        <span className="text-zinc-400 text-xs shrink-0">{expanded ? "▲" : "▼"}</span>
      </button>

      {/* 展開：個股七訊號明細 */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-zinc-100 dark:border-zinc-800 pt-3">
          {result.topStocks.length === 0 ? (
            <p className="text-xs text-zinc-400">此板塊暫無個股資料</p>
          ) : (
            result.topStocks.map(s => <StockSignalDetail key={s.stockId} result={s} />)
          )}
        </div>
      )}
    </div>
  );
}

// ── 主元件 ──────────────────────────────────────────────────────────────────

interface RegimePanelProps {
  snapshot: SnapshotType | null | undefined;
}

export function RegimePanel({ snapshot }: RegimePanelProps) {
  const [sectorFilter, setSectorFilter] = useState<FilterOption>("全部");
  const [filterState, setFilterState] = useState<FilterState>({
    actionGroups:  new Set<ActionGroup>(),
    signalIndices: new Set<number>(),
  });

  const hasActiveFilter = filterState.actionGroups.size > 0 || filterState.signalIndices.size > 0;

  const { marketResult, sectorResults } = useMemo(() => {
    if (!snapshot?.sectors) {
      return { marketResult: null, sectorResults: [] };
    }

    const hotCount = Object.values(snapshot.sectors).filter(s => (s as SectorData).level === "強烈關注").length;

    const marketResult = classifyMarketRegime(
      snapshot.market_state as { state: string; taiex_vs_200ma_pct?: number; momentum_20d_pct?: number } | null,
      snapshot.macro as { warning?: boolean; sox_trend?: string; bond_trend?: string } | null,
      hotCount,
    );

    // 計算所有板塊盤性，按熱度排序
    const levelOrder: Record<string, number> = { "強烈關注": 3, "觀察中": 2, "忽略": 1 };
    const sectorResults: SectorRegimeResult[] = Object.entries(snapshot.sectors)
      .map(([id, sector]) => classifySectorRegime(sector as SectorData, id))
      .sort((a, b) => {
        const la = levelOrder[a.sectorLevel] ?? 0;
        const lb = levelOrder[b.sectorLevel] ?? 0;
        if (lb !== la) return lb - la;
        return b.confidence - a.confidence;
      });

    return { marketResult, sectorResults };
  }, [snapshot]);

  // ── 篩選結果計算（有篩選條件才跑全量個股掃描）
  const filteredStocks = useMemo<FilteredStock[]>(() => {
    if (!hasActiveFilter || !snapshot?.sectors) return [];

    // 以 stockId 為 key 去重：保留信心度最高那筆，並合並板塊名稱
    const seen = new Map<string, FilteredStock>();

    for (const [, sectorRaw] of Object.entries(snapshot.sectors)) {
      const sector = sectorRaw as SectorData;
      const stocks = sector.stocks ?? [];
      if (stocks.length === 0) continue;

      for (const stock of stocks) {
        const regimeResult = classifyStockRegime(stock, sector, stocks);

        // 動作狀態篩選（OR：符合任一 group 即通過）
        if (filterState.actionGroups.size > 0) {
          const actionMatch = [...filterState.actionGroups].some(group =>
            ACTION_GROUPS[group].includes(regimeResult.action)
          );
          if (!actionMatch) continue;
        }

        // 訊號篩選（AND：選中的訊號必須全部 bullish=true）
        if (filterState.signalIndices.size > 0) {
          const signalMatch = [...filterState.signalIndices].every(idx => {
            const sig = regimeResult.signals[idx];
            return sig && sig.supported && sig.bullish === true;
          });
          if (!signalMatch) continue;
        }

        const existing = seen.get(regimeResult.stockId);
        if (existing) {
          // 已存在：合並板塊名稱，保留信心度較高的
          if (!existing.sectorNames.includes(sector.name_zh)) {
            existing.sectorNames.push(sector.name_zh);
          }
          if (regimeResult.confidence > existing.confidence) {
            seen.set(regimeResult.stockId, {
              ...regimeResult,
              sectorNames: existing.sectorNames,
              sectorLevel: sector.level,
            });
          }
        } else {
          seen.set(regimeResult.stockId, {
            ...regimeResult,
            sectorNames: [sector.name_zh],
            sectorLevel: sector.level,
          });
        }
      }
    }

    // 可進場優先，再按信心度降序
    return [...seen.values()].sort((a, b) => {
      const aEntry = ACTION_GROUPS.entry.includes(a.action);
      const bEntry = ACTION_GROUPS.entry.includes(b.action);
      if (aEntry !== bEntry) return aEntry ? -1 : 1;
      return b.confidence - a.confidence;
    });
  }, [hasActiveFilter, snapshot, filterState]);

  // 板塊盤性篩選（無進階篩選時才用）
  const filteredSectors = useMemo(() => {
    if (sectorFilter === "全部") return sectorResults;
    return sectorResults.filter(r => r.regime === sectorFilter);
  }, [sectorResults, sectorFilter]);

  const sectorCounts = useMemo(() => {
    const c: Record<string, number> = { 全部: sectorResults.length };
    for (const r of sectorResults) {
      c[r.regime] = (c[r.regime] ?? 0) + 1;
    }
    return c;
  }, [sectorResults]);

  if (!snapshot) {
    return <p className="text-zinc-400 text-sm py-12 text-center">載入資料中…</p>;
  }

  return (
    <div className="mt-6 space-y-6">
      {/* 頁首說明 */}
      <div>
        <h2 className="text-xl font-bold text-zinc-900 dark:text-white">盤性診斷 🔍</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
          辨識每個板塊屬於法人盤 / 大戶盤 / 散戶情緒盤，使用篩選器找出可進場標的
        </p>
      </div>

      {/* 大盤盤性 */}
      {marketResult && (
        <div>
          <h3 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 mb-2 uppercase tracking-wider">今日大盤盤性</h3>
          <MarketRegimeBanner result={marketResult} />
        </div>
      )}

      {/* ━━ 篩選工具列 ━━ */}
      <div>
        <h3 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 mb-2 uppercase tracking-wider">篩選標的</h3>
        <FilterToolbar
          state={filterState}
          onChange={setFilterState}
          resultCount={filteredStocks.length}
          hasActive={hasActiveFilter}
        />
      </div>

      {/* ━━ 有篩選：個股平鋪列表  ||  無篩選：板塊盤性掃描 ━━ */}
      {hasActiveFilter ? (
        <FilteredStockList stocks={filteredStocks} />
      ) : (
        <div>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h3 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">板塊盤性掃描</h3>
            <div className="flex gap-1 p-1 bg-zinc-100 dark:bg-zinc-800/60 rounded-lg flex-wrap">
              {SECTOR_FILTER_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => setSectorFilter(opt)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
                    sectorFilter === opt
                      ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                      : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                  }`}
                >
                  {opt === "全部" ? `全部 (${sectorCounts["全部"] ?? 0})` : (
                    `${REGIME_ICON[opt as RegimeType]} ${opt} (${sectorCounts[opt] ?? 0})`
                  )}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            {filteredSectors.length === 0 ? (
              <p className="text-zinc-400 text-sm text-center py-8">此盤性分類無板塊</p>
            ) : (
              filteredSectors.map(r => <SectorRow key={r.sectorId} result={r} />)
            )}
          </div>
        </div>
      )}

      {/* 方法說明 */}
      <details className="text-xs text-zinc-400 border border-zinc-200/40 dark:border-zinc-700/30 rounded-lg">
        <summary className="px-4 py-2 cursor-pointer hover:text-zinc-600 dark:hover:text-zinc-300 font-medium">
          📖 盤性辨識方法說明
        </summary>
        <div className="px-4 pb-4 pt-2 space-y-2 leading-relaxed">
          <p><strong className="text-zinc-600 dark:text-zinc-300">🏦 法人盤</strong>：外資+投信共振、K棒規律收斂、低位溫和放量、籌碼集中→對應235的5（價值核心）＋3（中線波段）</p>
          <p><strong className="text-zinc-600 dark:text-zinc-300">🐋 大戶盤</strong>：連續漲停、不按K棒規律、資金暴力、千張大戶持股↑→對應235的2（短線機動）</p>
          <p><strong className="text-zinc-600 dark:text-zinc-300">🐑 散戶情緒盤</strong>：放量不漲、融資暴增、題材堆疊、高漲幅低燈號→不做，等回檔</p>
          <p><strong className="text-zinc-600 dark:text-zinc-300">③ 499張現象</strong>：需券商即時委託 tick 資料（FinLab 不提供），接口已保留，未來可擴充</p>
          <p><strong className="text-zinc-600 dark:text-zinc-300">⑥ KDJ精準度</strong>：ohlcv_7d 欄位含最多20棒，不足14棒時精準度有限，僅供參考</p>
          <p><strong className="text-zinc-600 dark:text-zinc-300">⑦ 媒體熱度</strong>：為 Proxy 指標（漲幅高但燈號少 = 消息面/散戶追高），非直接媒體 NLP</p>
        </div>
      </details>
    </div>
  );
}
