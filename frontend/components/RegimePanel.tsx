"use client";
// RegimePanel.tsx — 盤性診斷面板（法人盤/大戶盤/散戶情緒盤辨識）
// 對應老師心法七項訊號框架

import { useState, useMemo } from "react";
import type { SectorData } from "@/lib/types";
import { fetchLatestSnapshot } from "@/lib/fetcher";
import {
  classifyMarketRegime,
  classifySectorRegime,
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

function StockSignalDetail({ result }: { result: StockRegimeResult }) {
  return (
    <div className="bg-zinc-50/80 dark:bg-zinc-800/40 rounded-lg p-3 space-y-1.5">
      {/* 個股標頭 */}
      <div className="flex items-center gap-2 pb-1.5 border-b border-zinc-200/40 dark:border-zinc-700/30 flex-wrap">
        <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">{result.stockId}</span>
        {result.stockName && <span className="text-xs text-zinc-500">{result.stockName}</span>}
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
  const [filter, setFilter] = useState<FilterOption>("全部");

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

  // 篩選板塊
  const filtered = useMemo(() => {
    if (filter === "全部") return sectorResults;
    return sectorResults.filter(r => r.regime === filter);
  }, [sectorResults, filter]);

  const counts = useMemo(() => {
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
          依老師心法辨識每個板塊屬於法人盤 / 大戶盤 / 散戶情緒盤，點板塊展開七項訊號明細
        </p>
      </div>

      {/* 大盤盤性 */}
      {marketResult && (
        <div>
          <h3 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 mb-2 uppercase tracking-wider">今日大盤盤性</h3>
          <MarketRegimeBanner result={marketResult} />
        </div>
      )}

      {/* 板塊篩選 */}
      <div>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h3 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">板塊盤性掃描</h3>
          <div className="flex gap-1 p-1 bg-zinc-100 dark:bg-zinc-800/60 rounded-lg flex-wrap">
            {SECTOR_FILTER_OPTIONS.map(opt => (
              <button
                key={opt}
                onClick={() => setFilter(opt)}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
                  filter === opt
                    ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                    : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                }`}
              >
                {opt === "全部" ? `全部 (${counts["全部"] ?? 0})` : (
                  `${REGIME_ICON[opt as RegimeType]} ${opt} (${counts[opt] ?? 0})`
                )}
              </button>
            ))}
          </div>
        </div>

        {/* 板塊列表 */}
        <div className="space-y-2">
          {filtered.length === 0 ? (
            <p className="text-zinc-400 text-sm text-center py-8">此盤性分類無板塊</p>
          ) : (
            filtered.map(r => <SectorRow key={r.sectorId} result={r} />)
          )}
        </div>
      </div>

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
