// ConvergencePanel.tsx — 最強進場訊號面板（雙重確認算法）
// 短線非忽略（燈號比率）× 50% ＋ 長線複合評分（NLP+關稅）× 50%
// 參考：Asness, Moskowitz & Pedersen (2013) "Value and Momentum Everywhere"

"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { SignalSnapshot, CompositeSnapshot, HoldingsSnapshot, MagaSnapshot, OHLCBar } from "@/lib/types";
import { getSectorName } from "@/lib/sectors";
import { changePctColor, formatChangePct, SIGNAL_NAMES } from "@/lib/signals";

const COMPOSITE_THRESHOLD = 0.10;

/** 回傳目前 grid 欄數（對應 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3） */
function useColumns() {
  const [cols, setCols] = useState(1);
  useEffect(() => {
    const update = () => {
      const w = window.innerWidth;
      setCols(w >= 1280 ? 3 : w >= 640 ? 2 : 1);
    };
    update();
    window.addEventListener("resize", update, { passive: true });
    return () => window.removeEventListener("resize", update);
  }, []);
  return cols;
}

import { MiniSparkline } from "./MiniSparkline";
import { FactorRadar } from "./FactorRadar";
import { RsiGauge } from "./RsiGauge";
import { MacdChart } from "./MacdChart";
import { CandlePatternBadges } from "./CandlePatternBadges";

const GITHUB_RAW_BASE_CP = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

/** 展開後 lazy-load 完整 ohlcv，只 fetch 一次 */
function useOHLCV(stockId: string, enabled: boolean) {
  const [fullData, setFullData] = useState<OHLCBar[]>([]);
  const [loading, setLoading]   = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!enabled || fetchedRef.current || !GITHUB_RAW_BASE_CP) return;
    fetchedRef.current = true;
    let cancelled = false;
    setLoading(true);
    fetch(`${GITHUB_RAW_BASE_CP}/output/ohlcv/${stockId}.json`, { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then((d: OHLCBar[] | null) => { if (!cancelled && d && d.length > 0) setFullData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [stockId, enabled]);

  return { fullData, loading };
}

const StockKLine = dynamic<{ data: OHLCBar[]; stockId: string; fullData?: OHLCBar[] }>(
  () => import("./StockKLine").then((m) => m.StockKLine),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] flex items-center justify-center text-zinc-400 text-xs">載入中...</div>
    ),
  }
);

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
  lightCount: number;
  composite:  number;
  combined:   number;
  stockCount: number;
}

interface ConvergenceStock {
  id:          string;
  name_zh?:    string;
  sectorId:    string;
  sectorLevel: string;
  score:       number | null;
  grade:       string;
  change_pct:  number | null;
  price_flag:  string;
  triggered:   string[];
  ohlcv_7d?:   OHLCBar[];
  breakdown?:  { fundamental: number; technical: number; chipset: number; bonus: number };
  tags:        Array<"持倉" | "MAGA">;
  combined:    number;
  lightRatio:  number;
  composite:   number;  nlpBearish:  boolean;
  nlpSeverity: "high" | "medium" | null;}

const LEVEL_BADGE: Record<string, string> = {
  "強烈關注": "bg-red-100/80 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800/50",
  "觀察中":   "bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/50",
};

const GRADE_BADGE: Record<string, string> = {
  "A+": "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300",
  "A":  "bg-emerald-50  dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400",
  "B":  "bg-blue-50     dark:bg-blue-900/20    text-blue-600   dark:text-blue-400",
  "C":  "bg-zinc-100    dark:bg-zinc-800/50     text-zinc-500",
  "D":  "bg-red-50      dark:bg-red-900/20      text-red-500   dark:text-red-400",
};

function CombinedBar({ combined, lightRatio, composite }: {
  combined: number; lightRatio: number; composite: number;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-zinc-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all"
            style={{ width: `${combined}%` }}
          />
        </div>
        <span className="text-xs font-mono text-zinc-600 dark:text-zinc-400 w-7 text-right font-semibold">
          {combined}
        </span>
      </div>
      <div className="flex gap-3 text-[11px] text-zinc-400">
        <span>短線 <span className="text-zinc-600 dark:text-zinc-300 font-medium">{Math.round(lightRatio * 100)}%</span></span>
        <span>長線 <span className={`font-medium ${composite >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}>
          {composite >= 0 ? "+" : ""}{composite.toFixed(2)}
        </span></span>
      </div>
    </div>
  );
}

function StockCard({ stock, isExpanded, onToggle }: {
  stock: ConvergenceStock;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const { fullData, loading: loadingFull } = useOHLCV(stock.id, isExpanded);
  const displayBars = fullData.length >= 2 ? fullData : (stock.ohlcv_7d ?? []);

  const hasKLine     = (stock.ohlcv_7d?.length ?? 0) >= 2;
  const hasBreakdown  = !!(stock.breakdown && (
    stock.breakdown.fundamental > 0 || stock.breakdown.technical > 0 ||
    stock.breakdown.chipset > 0     || stock.breakdown.bonus > 0
  ));
  const hasExpandable = hasKLine || hasBreakdown;
  const signalLabels = (stock.triggered ?? [])
    .slice(0, 4)
    .map((key) => {
      const name = SIGNAL_NAMES[key] ?? key;
      return name.length > 2 ? name.slice(0, 2) : name;
    });

  const isFeatured = stock.sectorLevel === "強烈關注";
  const isWatch    = stock.sectorLevel === "觀察中";

  // 左色條：板塊等級優先，其次才是綜合分
  const barColor = isFeatured ? "#ef4444" : isWatch ? "#f59e0b" :
    stock.combined >= 70 ? "#10b981" :
    stock.combined >= 50 ? "#3b82f6" : "#a1a1aa";

  // 卡片邊框：強烈關注用紅色微營光
  const cardBorder = isFeatured
    ? "border-red-300/70 dark:border-red-700/50 shadow-[0_0_0_1px_rgba(239,68,68,0.15)]"
    : "border-zinc-200/60 dark:border-zinc-700/50";

  return (
    <div className={`rounded-xl border bg-white/70 dark:bg-zinc-900/50 overflow-hidden ${cardBorder}`}>
      {/* NLP 空方衝擊警示條 */}
      {stock.nlpBearish && stock.nlpSeverity && (
        <div className={`flex items-center gap-1.5 px-3.5 py-1.5 text-[11px] font-medium border-b ${
          stock.nlpSeverity === "high"
            ? "bg-red-50/90 dark:bg-red-950/40 border-red-200/50 dark:border-red-800/50 text-red-700 dark:text-red-300"
            : "bg-amber-50/90 dark:bg-amber-950/40 border-amber-200/50 dark:border-amber-800/50 text-amber-700 dark:text-amber-300"
        }`}>
          <span>{stock.nlpSeverity === "high" ? "🚨" : "⚠️"}</span>
          <span>
            <strong>{getSectorName(stock.sectorId)}</strong>
            {stock.nlpSeverity === "high"
              ? " 承受強空方訊號衝擊，建議降低曝險或設停損"
              : " 承受NLP空方壓力，持倉需提高警覺"}
          </span>
        </div>
      )}
      <div className="px-3.5 pt-3 pb-2.5 space-y-2.5">
        {/* Row 1: ID + 名稱 + 漲跌 + 標籤 */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-1 h-8 rounded-full shrink-0" style={{ background: barColor }} />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[15px] font-bold text-zinc-900 dark:text-zinc-100">{stock.id}</span>
                {stock.name_zh && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-[5rem]">{stock.name_zh}</span>
                )}
                <span className={`text-[11px] px-1.5 py-0.5 rounded-md font-medium ${GRADE_BADGE[stock.grade] ?? GRADE_BADGE["C"]}`}>
                  {stock.grade}
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 mt-0.5 truncate flex items-center gap-1">
                {getSectorName(stock.sectorId)}
                {isFeatured && (
                  <span className="inline-flex items-center gap-0.5 text-[10px] px-1 py-0.5 rounded font-bold bg-red-100/80 dark:bg-red-900/30 text-red-700 dark:text-red-300 leading-none">
                    🔴 強烈關注
                  </span>
                )}
                {isWatch && (
                  <span className="inline-flex items-center gap-0.5 text-[10px] px-1 py-0.5 rounded font-medium bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 leading-none">
                    🟡 觀察中
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {hasKLine && <MiniSparkline bars={stock.ohlcv_7d!} />}
            {stock.price_flag === "halt" ? (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-700/40">停牌</span>
            ) : stock.price_flag === "ex_div" ? (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-700/40">除權息</span>
            ) : (
              <span className={`text-sm font-bold ${changePctColor(stock.change_pct)}`}>{formatChangePct(stock.change_pct)}</span>
            )}
            <div className="flex gap-1">
              {stock.tags.includes("持倉") && (
                <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-amber-100/80 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700/40">💼持倉</span>
              )}
              {stock.tags.includes("MAGA") && (
                <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-blue-100/80 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700/40">🇺🇸政策</span>
              )}
            </div>
          </div>
        </div>
        {/* Row 2: 觸發訊號 */}
        {signalLabels.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {signalLabels.map((label, i) => (
              <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">{label}</span>
            ))}
            {(stock.triggered?.length ?? 0) > 4 && (
              <span className="text-[11px] text-zinc-400">+{stock.triggered.length - 4}</span>
            )}
          </div>
        )}
        {/* Row 3: 雙線分數條 */}
        <CombinedBar combined={stock.combined} lightRatio={stock.lightRatio} composite={stock.composite} />
      </div>
      {/* 分析展開按鈕（因子雷達 + K 線） */}
      {hasExpandable && (
        <button
          onClick={onToggle}
          className={`w-full flex items-center justify-center gap-1.5 py-1.5 text-[11px] transition-colors border-t ${
            isExpanded
              ? "border-blue-200/60 dark:border-blue-800/40 bg-blue-50/60 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
              : "border-zinc-100 dark:border-zinc-800/50 text-zinc-400 hover:text-blue-500 dark:hover:text-blue-400 hover:bg-blue-50/40 dark:hover:bg-blue-900/10"
          }`}
        >
          <span>📊</span>
          <span className="font-medium">{isExpanded ? "收起分析" : "展開分析"}</span>
        </button>
      )}
      {isExpanded && hasExpandable && (
        <div className="border-t border-zinc-100 dark:border-zinc-800/50">
          {hasBreakdown && stock.breakdown && (
            <FactorRadar breakdown={stock.breakdown} grade={stock.grade} />
          )}
          <CandlePatternBadges bars={displayBars} />
          <RsiGauge data={fullData} loading={loadingFull} />
          <MacdChart data={fullData} loading={loadingFull} />
          {hasKLine && (
            <div className="px-1 py-1">
              <StockKLine data={stock.ohlcv_7d!} stockId={stock.id} fullData={fullData.length > 0 ? fullData : undefined} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StockMiniRow({
  stock,
  nameMap,
}: {
  stock: { id: string; score?: number | null; grade: string; change_pct?: number | null };
  nameMap: Record<string, string>;
}) {
  const gradeColor =
    stock.grade === "A+" ? "text-emerald-600 dark:text-emerald-400" :
    stock.grade === "A"  ? "text-emerald-500 dark:text-emerald-500" :
    stock.grade === "B"  ? "text-blue-500 dark:text-blue-400" : "text-zinc-400";
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
      <span className="font-mono text-[11px] text-zinc-400 w-10 shrink-0">{stock.id}</span>
      <span className="text-xs text-zinc-700 dark:text-zinc-300 flex-1 truncate">
        {nameMap[stock.id] ?? "—"}
      </span>
      <span className={`text-xs font-bold ${gradeColor} w-6 text-center`}>{stock.grade}</span>
      <span className={`text-xs font-medium ${changePctColor(stock.change_pct ?? null)} w-14 text-right`}>
        {formatChangePct(stock.change_pct ?? null)}
      </span>
    </div>
  );
}

export function ConvergencePanel({ snapshot, composite, holdings, magaData }: Props) {
  const [view, setView] = useState<"stocks" | "rank">("stocks");
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [sectorExpandSet, setSectorExpandSet] = useState<Set<string>>(new Set());
  const cols = useColumns();

  // 切換 view 時收合所有 K 線
  const handleViewChange = (v: "stocks" | "rank") => {
    setView(v);
    setExpandedRows(new Set());
  };

  const toggleSector = (id: string) =>
    setSectorExpandSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

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
          lightCount,
          composite:  cd.composite,
          combined,
          stockCount: sector.stocks.length,
        };
      })
      .sort((a, b) => b.combined - a.combined);
  }, [snapshot, composite]);

  const nameMap = useMemo<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const [id, pos] of Object.entries(holdings?.positions ?? {})) {
      if (pos.name_zh) map[id] = pos.name_zh;
    }
    for (const s of magaData?.stocks ?? []) {
      if (s.name_zh) map[s.id] = s.name_zh;
    }
    return map;
  }, [holdings, magaData]);

  // 計算交集個股
  const convergenceStocks = useMemo<ConvergenceStock[]>(() => {
    if (!snapshot || convergenceSectors.length === 0) return [];

    const holdingIds   = new Set(Object.keys(holdings?.positions ?? {}));
    const magaBeneIds  = new Set(
      (magaData?.stocks ?? []).filter((s) => s.category === "beneficiary").map((s) => s.id)
    );
    const intersectIds = new Set(convergenceSectors.map((s) => s.sectorId));
    const secMetaMap   = Object.fromEntries(convergenceSectors.map((s) => [s.sectorId, s]));

    const seen = new Set<string>();
    const result: ConvergenceStock[] = [];

    for (const [sectorId, sector] of Object.entries(snapshot.sectors)) {
      if (!intersectIds.has(sectorId)) continue;
      const secMeta = secMetaMap[sectorId];
      for (const stock of sector.stocks) {
        if (seen.has(stock.id)) continue;
        seen.add(stock.id);
        const tags: Array<"持倉" | "MAGA"> = [];
        if (holdingIds.has(stock.id))  tags.push("持倉");
        if (magaBeneIds.has(stock.id)) tags.push("MAGA");
        result.push({
          id:         stock.id,
          name_zh:    nameMap[stock.id],
          sectorId,
          sectorLevel: sector.level,
          score:      stock.score ?? null,
          grade:      stock.grade,
          change_pct: stock.change_pct ?? null,
          price_flag: stock.price_flag ?? "normal",
          triggered:  stock.triggered ?? [],
          ohlcv_7d:   stock.ohlcv_7d,
          breakdown:  stock.breakdown,
          tags,
          combined:   secMeta.combined,
          lightRatio: secMeta.lightRatio,
          composite:  secMeta.composite,
          nlpBearish:  (composite?.scores?.[sectorId] as { nlp?: number } | undefined)?.nlp !== undefined
            ? ((composite!.scores[sectorId] as unknown as { nlp: number }).nlp < -0.1)
            : false,
          nlpSeverity: (() => {
            const nlp = (composite?.scores?.[sectorId] as { nlp?: number } | undefined)?.nlp ?? 0;
            return nlp < -0.35 ? "high" : nlp < -0.1 ? "medium" : null;
          })(),
        });
      }
    }

    return result.sort((a, b) => {
      const w = (s: ConvergenceStock) => s.tags.length * 20 + s.combined;
      return w(b) - w(a);
    });
  }, [snapshot, composite, holdings, magaData, convergenceSectors, nameMap]);

  // ─ 空狀態：兩者皆無
  if (!snapshot && !composite) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400 dark:text-zinc-600">
        <span className="text-4xl mb-3">🎯</span>
        <p className="text-sm">尚無資料，請先執行 Python --auto 分析</p>
      </div>
    );
  }

  const hasShort = snapshot != null;
  const hasLong  = composite != null;

  if (!hasShort || !hasLong) {
    return (
      <div className="mt-6 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">雙線共振進場清單</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">短線板塊燈號 × 長線複合評分，雙重確認才納入</p>
        </div>
        <div className="flex flex-col gap-3 max-w-sm">
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${hasShort ? "border-emerald-300/60 dark:border-emerald-700/40 bg-emerald-50/60 dark:bg-emerald-900/20" : "border-zinc-200/40 dark:border-zinc-700/40 bg-zinc-50/60 dark:bg-zinc-900/30"}`}>
            <span className="text-xl">{hasShort ? "✅" : "⬜"}</span>
            <div>
              <p className={`text-sm font-semibold ${hasShort ? "text-emerald-700 dark:text-emerald-300" : "text-zinc-500"}`}>短線訊號（板塊燈號）</p>
              <p className="text-xs text-zinc-400">{hasShort ? "已就緒" : "尚未生成"}</p>
            </div>
          </div>
          <div className="text-zinc-300 dark:text-zinc-600 text-center">↓</div>
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${hasLong ? "border-emerald-300/60 dark:border-emerald-700/40 bg-emerald-50/60 dark:bg-emerald-900/20" : "border-zinc-200/40 dark:border-zinc-700/40 bg-zinc-50/60 dark:bg-zinc-900/30"}`}>
            <span className="text-xl">{hasLong ? "✅" : "⬜"}</span>
            <div>
              <p className={`text-sm font-semibold ${hasLong ? "text-emerald-700 dark:text-emerald-300" : "text-zinc-500"}`}>長線複合評分（NLP＋關稅）</p>
              <p className="text-xs text-zinc-400">{hasLong ? "已就緒" : "尚未生成"}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (convergenceSectors.length === 0) {
    return (
      <div className="mt-6">
        <div className="mb-5">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">雙線共振進場清單</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">短線板塊燈號 × 長線複合評分，雙重確認才納入</p>
        </div>
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-600">
          <span className="text-4xl mb-3">🔍</span>
          <p className="text-sm font-medium">目前無雙重確認板塊</p>
          <p className="text-xs mt-1 opacity-60">短線非忽略且長線複合分 &gt; {COMPOSITE_THRESHOLD} 的板塊目前為零</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-5">

      {/* Header + 統計 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-white">雙線共振進場清單</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            短線板塊燈號比率 × 50%  ＋  長線複合評分（NLP＋關稅）× 50%  ·  composite &gt; {COMPOSITE_THRESHOLD}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs shrink-0">
          <span className="px-2.5 py-1 rounded-full bg-emerald-100/70 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 font-medium border border-emerald-200/60 dark:border-emerald-800/40">
            {convergenceSectors.length} 板塊
          </span>
          <span className="px-2.5 py-1 rounded-full bg-blue-100/70 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200/60 dark:border-blue-800/40">
            {convergenceStocks.length} 個股
          </span>
        </div>
      </div>

      {/* View toggle */}
      <div className="flex gap-1 p-1 rounded-lg bg-zinc-100/70 dark:bg-zinc-800/70 w-fit">
        {(["stocks", "rank"] as const).map((v) => (
          <button
            key={v}
            onClick={() => handleViewChange(v)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors font-medium ${
              view === v
                ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            {v === "stocks" ? "進場個股" : "板塊排行"}
          </button>
        ))}
      </div>

      {/* ── 板塊排行 ── */}
      {view === "rank" && (
        <div className="space-y-2">
          {convergenceSectors.map((sec) => {
            const isExpanded = sectorExpandSet.has(sec.sectorId);
            const sectorStocks = (snapshot?.sectors[sec.sectorId]?.stocks ?? [])
              .slice()
              .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
              .slice(0, 8);
            return (
              <div
                key={sec.sectorId}
                className="rounded-xl border border-zinc-200/50 dark:border-zinc-700/50 bg-white/60 dark:bg-zinc-900/40 overflow-hidden"
              >
                {/* 可點擊摘要列 */}
                <button
                  className="w-full flex items-center gap-3 px-4 py-3 text-left"
                  onClick={() => toggleSector(sec.sectorId)}
                  aria-expanded={isExpanded}
                >
                  <div className="w-32 shrink-0">
                    <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                      {getSectorName(sec.sectorId)}
                    </p>
                    <span className={`inline-block mt-0.5 text-xs px-1.5 py-0.5 rounded-full font-medium ${LEVEL_BADGE[sec.level] ?? "bg-zinc-100 dark:bg-zinc-800 text-zinc-500"}`}>
                      {sec.level}
                    </span>
                  </div>
                  <div className="flex flex-col items-center shrink-0 w-14 text-center">
                    <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 leading-none">
                      {sec.lightCount}
                    </span>
                    <span className="text-[10px] text-zinc-400 leading-tight">/ 7 燈</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <CombinedBar combined={sec.combined} lightRatio={sec.lightRatio} composite={sec.composite} />
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-xs text-zinc-400">{sec.stockCount} 支</span>
                    {sectorStocks.length > 0 && (
                      <svg
                        width="14" height="14" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2.5"
                        className={`text-zinc-400 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                      >
                        <path d="M6 9l6 6 6-6" />
                      </svg>
                    )}
                  </div>
                </button>
                {/* 展開個股 */}
                {isExpanded && sectorStocks.length > 0 && (
                  <div className="border-t border-zinc-100/70 dark:border-zinc-800/60 px-3 pb-3 pt-2 space-y-0.5">
                    <p className="text-[10px] text-zinc-400 px-2 pb-1">板塊個股排名（依綜合評分）</p>
                    {sectorStocks.map((stock) => (
                      <StockMiniRow key={stock.id} stock={stock} nameMap={nameMap} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center pt-2">
            綜合分 = 短線燈號比率 × 50% ＋ 正規化複合分 × 50%  ·  Asness, Moskowitz & Pedersen (2013)
          </p>
        </div>
      )}

      {/* 進場個股 */}
      {view === "stocks" && (
        <div className="space-y-3">
          {convergenceStocks.length === 0 ? (
            <p className="text-sm text-zinc-400 text-center py-8">交集板塊中暫無個股資料</p>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {convergenceStocks.map((stock, i) => {
                  const rowKey = Math.floor(i / cols);
                  return (
                    <StockCard
                      key={stock.id}
                      stock={stock}
                      isExpanded={expandedRows.has(rowKey)}
                      onToggle={() =>
                        setExpandedRows((prev) => {
                          const next = new Set(prev);
                          if (next.has(rowKey)) next.delete(rowKey);
                          else next.add(rowKey);
                          return next;
                        })
                      }
                    />
                  );
                })}
              </div>
              <p className="text-[11px] text-zinc-400 dark:text-zinc-500 text-center pt-1">
                以所屬板塊「雙線共振綜合分數」排序  ·  💼 持倉  🇺🇸 MAGA政策受益  ·  點擊「展開 K 線」查看走勢
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
