// holdings-utils.ts — 持倉合併、行動等級解析、排序（獨立頁籤資料層）
// 五級行動：出場 → 減碼 → 留意 → 加碼 → 持有
// 學術依據：de Kempenaer (2014) RRG · Grinblatt et al. (1995) · Da et al. (2014)

import type {
  SignalSnapshot,
  HoldingsSnapshot,
  UserHoldingsSnapshot,
  PnlSnapshot,
  ExitAlertsSnapshot,
  ExitAlertPosition,
  SectorData,
  StockData,
  OHLCBar,
} from "./types";
import type { StockNamesMap } from "./fetcher";
import { getSectorName } from "./sectors";

// ── 五級行動定義 ────────────────────────────────────────────────────────

export type HoldingAction = "出場" | "減碼" | "留意" | "加碼" | "持有";

export const ACTION_CONFIG: Record<HoldingAction, {
  emoji: string;
  label: string;
  chipCls: string;
  sortWeight: number;
}> = {
  "出場": {
    emoji: "🔴",
    label: "出場",
    chipCls: "bg-red-100/80 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-300 dark:border-red-700/40",
    sortWeight: 0,
  },
  "減碼": {
    emoji: "🟠",
    label: "減碼",
    chipCls: "bg-orange-100/80 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-700/40",
    sortWeight: 1,
  },
  "留意": {
    emoji: "🟡",
    label: "留意",
    chipCls: "bg-yellow-100/80 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border border-yellow-200 dark:border-yellow-700/40",
    sortWeight: 2,
  },
  "加碼": {
    emoji: "🟢",
    label: "加碼",
    chipCls: "bg-emerald-100/80 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/40",
    sortWeight: 3,
  },
  "持有": {
    emoji: "🔵",
    label: "持有",
    chipCls: "bg-blue-100/80 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700/40",
    sortWeight: 4,
  },
};

// ── 合併持倉型別 ────────────────────────────────────────────────────────

export interface MergedHolding {
  stockId: string;
  nameZh: string;
  source: "user" | "algo" | "both";
  // 用戶持倉欄位
  entryPrice: number | null;
  entryDate: string | null;
  shares: number | null;
  note: string | null;
  // 演算法建議欄位
  compositeScore: number | null;
  weight: number | null;
  reason: string | null;
  // 市場資料（從 snapshot 填入）
  sectorId: string | null;
  sectorName: string | null;
  sectorLevel: string | null;
  cycleStage: string | null;
  signals: number[];
  grade: string;
  changePct: number | null;
  triggered: string[];
  ohlcv7d: OHLCBar[];
  breakdown: { fundamental: number; technical: number; chipset: number; bonus: number } | null;
  score: number | null;
  // PnL
  currentPrice: number | null;
  pnlPct: number | null;
  pnlAbs: number | null;
  daysHeld: number | null;
  // 行動等級
  action: HoldingAction;
  exitAlertScore: number | null;
  exitAlertTriggers: string[];
}

// ── 合併持倉 ────────────────────────────────────────────────────────────

export function mergeHoldings(
  snapshot: SignalSnapshot | null | undefined,
  holdings: HoldingsSnapshot | null,
  userHoldings: UserHoldingsSnapshot | null,
  pnl: PnlSnapshot | null,
  exitAlerts: ExitAlertsSnapshot | null,
  stockNames: StockNamesMap | null,
): MergedHolding[] {
  const merged = new Map<string, MergedHolding>();

  // 建立 stockId → StockData + sectorId 索引
  const stockIndex = new Map<string, { stock: StockData; sectorId: string; sector: SectorData }>();
  if (snapshot?.sectors) {
    for (const [sectorId, sector] of Object.entries(snapshot.sectors)) {
      for (const stock of sector.stocks) {
        stockIndex.set(stock.id, { stock, sectorId, sector });
      }
    }
  }

  const positionAlerts = exitAlerts?.position_alerts ?? {};
  const pnlPositions = pnl?.positions ?? {};

  // helper: 從各資料源填入共用欄位
  function fillMarketData(h: MergedHolding) {
    const si = stockIndex.get(h.stockId);
    if (si) {
      h.sectorId = si.sectorId;
      h.sectorName = si.sector.name_zh || getSectorName(si.sectorId);
      h.sectorLevel = si.sector.level;
      h.cycleStage = si.sector.cycle_stage ?? null;
      h.signals = si.sector.signals;
      h.grade = si.stock.grade;
      h.changePct = si.stock.change_pct ?? null;
      h.triggered = si.stock.triggered ?? [];
      h.ohlcv7d = si.stock.ohlcv_7d ?? [];
      h.breakdown = si.stock.breakdown ?? null;
      h.score = si.stock.score ?? null;
    } else {
      // Sector-level fallback：個股未達門檻不在 stocks[] 中，但仍屬於該板塊
      const sectorId = h.sectorId
        ?? pnlPositions[h.stockId]?.sector
        ?? (holdings?.positions[h.stockId] as { sector?: string } | undefined)?.sector
        ?? stockNames?.[h.stockId]?.sector
        ?? null;
      if (sectorId && snapshot?.sectors?.[sectorId]) {
        const sec = snapshot.sectors[sectorId];
        h.sectorId = sectorId;
        h.sectorName = sec.name_zh || getSectorName(sectorId);
        h.sectorLevel = sec.level;
        h.cycleStage = sec.cycle_stage ?? null;
        h.signals = sec.signals;
      }
    }

    // stockNames fallback（名稱 + 板塊）
    const sn = stockNames?.[h.stockId];
    if (sn) {
      if (!h.sectorName) {
        h.sectorName = sn.sector_name || getSectorName(sn.sector);
        h.sectorId = h.sectorId ?? sn.sector;
      }
      if (h.nameZh === h.stockId) {
        h.nameZh = sn.name_zh;
      }
    }

    // PnL
    const pp = pnlPositions[h.stockId];
    if (pp) {
      h.currentPrice = pp.current_price;
      h.pnlPct = pp.pnl_pct;
      h.pnlAbs = pp.pnl_abs;
      h.daysHeld = pp.days_held;
    }

    // daysHeld 前端補算：當 Python 回傳 0 但有 entryDate 時
    if ((h.daysHeld == null || h.daysHeld === 0) && h.entryDate) {
      const ms = Date.now() - new Date(h.entryDate).getTime();
      if (ms > 0) h.daysHeld = Math.floor(ms / 86_400_000);
    }

    // 行動等級
    const sectorForAction = si?.sector ?? (h.sectorId && snapshot?.sectors?.[h.sectorId]) ?? null;
    h.action = resolveAction(h.stockId, positionAlerts, sectorForAction as SectorData | null);
    const alert = positionAlerts[h.stockId];
    if (alert) {
      h.exitAlertScore = alert.score;
      h.exitAlertTriggers = alert.triggers;
    }
  }

  function emptyHolding(stockId: string, nameZh: string): MergedHolding {
    return {
      stockId,
      nameZh,
      source: "user",
      entryPrice: null,
      entryDate: null,
      shares: null,
      note: null,
      compositeScore: null,
      weight: null,
      reason: null,
      sectorId: null,
      sectorName: null,
      sectorLevel: null,
      cycleStage: null,
      signals: [],
      grade: "—",
      changePct: null,
      triggered: [],
      ohlcv7d: [],
      breakdown: null,
      score: null,
      currentPrice: null,
      pnlPct: null,
      pnlAbs: null,
      daysHeld: null,
      action: "持有",
      exitAlertScore: null,
      exitAlertTriggers: [],
    };
  }

  // 1. User holdings
  if (userHoldings?.positions) {
    for (const [id, pos] of Object.entries(userHoldings.positions)) {
      const h = emptyHolding(id, pos.name_zh || id);
      h.source = "user";
      h.entryPrice = pos.entry_price;
      h.entryDate = pos.entry_date;
      h.shares = pos.shares;
      h.note = pos.note;
      merged.set(id, h);
    }
  }

  // 2. Algo holdings
  if (holdings?.positions) {
    for (const [id, pos] of Object.entries(holdings.positions)) {
      const algoDate = pos.added_at ? pos.added_at.slice(0, 10) : null;
      const existing = merged.get(id);
      if (existing) {
        existing.source = "both";
        existing.compositeScore = pos.composite_score;
        existing.weight = pos.weight;
        existing.reason = pos.reason;
        // 保留 user entry_date 優先，fallback algo added_at
        if (!existing.entryDate && algoDate) existing.entryDate = algoDate;
        if (existing.entryPrice == null && pos.entry_price != null) existing.entryPrice = pos.entry_price;
        if (existing.shares == null && pos.shares != null) existing.shares = pos.shares;
      } else {
        const h = emptyHolding(id, pos.name_zh || id);
        h.source = "algo";
        h.compositeScore = pos.composite_score;
        h.weight = pos.weight;
        h.reason = pos.reason;
        h.entryDate = algoDate;
        h.entryPrice = pos.entry_price ?? null;
        h.shares = pos.shares ?? null;
        h.sectorId = pos.sector || null;
        merged.set(id, h);
      }
    }
  }

  // 3. Fill market data for all
  for (const h of merged.values()) {
    fillMarketData(h);
  }

  return Array.from(merged.values());
}

// ── 行動等級解析 ────────────────────────────────────────────────────────
// 🔴 出場 — ExitAlert action="出場"
// 🟠 減碼 — ExitAlert action="減碼"
// 🟡 留意 — ExitAlert action="留意"
// 🟢 加碼 — No ExitAlert + sector "強烈關注" + cycle 萌芽期/確認期
// 🔵 持有 — Default

function resolveAction(
  stockId: string,
  positionAlerts: Record<string, ExitAlertPosition>,
  sector: SectorData | null,
): HoldingAction {
  const alert = positionAlerts[stockId];
  if (alert) {
    if (alert.action === "出場") return "出場";
    if (alert.action === "減碼") return "減碼";
    if (alert.action === "留意") return "留意";
  }
  // 加碼：無出場警報 + 板塊強烈關注 + 萌芽期/確認期
  if (
    !alert &&
    sector &&
    sector.level === "強烈關注" &&
    (sector.cycle_stage === "萌芽期" || sector.cycle_stage === "確認期")
  ) {
    return "加碼";
  }
  return "持有";
}

// ── 排序 ────────────────────────────────────────────────────────────────
// 出場最上 → 行動嚴重度 → 出場風險分↓ → PnL%（虧損優先）

export function sortHoldings(items: MergedHolding[]): MergedHolding[] {
  return [...items].sort((a, b) => {
    // 1. 行動嚴重度
    const wa = ACTION_CONFIG[a.action].sortWeight;
    const wb = ACTION_CONFIG[b.action].sortWeight;
    if (wa !== wb) return wa - wb;

    // 2. 出場風險分數↓
    const sa = a.exitAlertScore ?? 0;
    const sb = b.exitAlertScore ?? 0;
    if (sa !== sb) return sb - sa;

    // 3. PnL%（虧損優先用於風險等級，獲利優先用於加碼等級）
    const pa = a.pnlPct ?? 0;
    const pb = b.pnlPct ?? 0;
    if (wa <= 2) return pa - pb; // 出場/減碼/留意：虧損在上
    return pb - pa; // 加碼/持有：獲利在上
  });
}
