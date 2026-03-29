// types.ts — FinLab 板塊偵測系統前端型別定義

export interface OHLCBar {
  date: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface StockData {
  id: string;
  score?: number | null;
  grade: string;
  change_pct?: number | null;
  triggered: string[];
  breakdown?: {
    fundamental: number;
    technical: number;
    chipset: number;
    bonus: number;
  };
  price_flag?: "normal" | "ex_div" | "halt";
  ohlcv_7d?: OHLCBar[];
}

export interface SectorData {
  name_zh: string;
  total: number;
  signals: number[];   // 0.0 / 0.5 / 1.0，7個元素
  level: "強烈關注" | "觀察中" | "忽略";
  stocks: StockData[];
}

export interface MacroData {
  warning: boolean;
  signal: boolean;
  positive_count: number;
  total_available: number;
  details: Record<string, string>;
  us_bond_10y?: number;
  bond_trend?: "up" | "down";
  ip_index?: number;
  ip_trend?: "up" | "down";
  sox_price?: number;
  sox_trend?: "up" | "down";
}

export interface SignalSnapshot {
  schema_version?: string;
  date: string;
  run_at: string;
  last_trading_date?: string;
  macro: MacroData;
  macro_warning?: boolean;  // 向下相容
  sectors: Record<string, SectorData>;
}

// history_index.json 的型別
export interface HistoryIndex {
  dates: string[];
  sectors: Record<string, {
    name_zh: string;
    totals: number[];
    levels: string[];
  }>;
  macro: Array<{
    date: string;
    warning: boolean;
    signal?: boolean;
    positive_count?: number;
    us_bond_10y?: number;
    sox_price?: number;
  }>;
}

// 前端用的歷史週期選項
export type HistoryRange = "7d" | "14d" | "30d" | "90d";

export const HISTORY_RANGE_LABELS: Record<HistoryRange, string> = {
  "7d":  "7 日",
  "14d": "14 日",
  "30d": "1 個月",
  "90d": "3 個月",
};

// ────────────────────────────────────────────────────────────────────────
// 商品市場（Commodities Dashboard）型別
// ────────────────────────────────────────────────────────────────────────

export type CommodityCategory =
  | "precious_metal"
  | "energy"
  | "industrial"
  | "crypto"
  | "index"
  | "bonds";

export interface EconSignal {
  key: string;
  triggered: boolean;
  severity: "high" | "medium" | "low";
  commentary: string;
  source: string;
}

export interface CommodityAsset {
  slug: string;
  name_zh: string;
  category: CommodityCategory;
  price: number | null;
  change_1d_pct: number | null;
  change_7d_pct: number | null;
  signals: EconSignal[];
  last_updated: string;
}

export interface YieldPoint {
  tenor: string;    // "2Y" | "5Y" | "10Y" | "30Y"
  years: number;
  yield_pct: number;
}

export interface YieldCurveAnalysis {
  spread_2_10:  number | null;
  spread_2_30:  number | null;
  spread_10_30: number | null;
  is_inverted:  boolean;
  slope_signal: "inverted" | "flat" | "normal" | "steep" | "unknown";
  signals:      EconSignal[];
}

export interface MarketSummary {
  total_triggered: number;
  high_count:      number;
  medium_count:    number;
  overall:         "risk_off" | "caution" | "neutral" | "risk_on";
  headline:        string;
  key_alerts:      string[];
}

export interface CommoditySnapshot {
  updated_at:            string;
  assets:                Record<string, CommodityAsset>;
  yield_curve:           YieldPoint[];
  yield_curve_analysis?: YieldCurveAnalysis;
  market_summary?:       MarketSummary;
}

// ────────────────────────────────────────────────────────────────────────
// MAGA 投資組合追蹤型別
// ────────────────────────────────────────────────────────────────────────

export interface MagaPolicy {
  key:         string;
  label:       string;
  active:      boolean;
  description: string;
}

export interface MagaStock {
  ticker:              string;   // e.g. "2330.TW"
  id:                  string;   // e.g. "2330"
  name_zh:             string;
  sector_id:           string;
  sector_name:         string;
  category:            "beneficiary" | "victim";
  impact_score:        number;   // -100 ~ +100
  policy_contributions: Record<string, number>;
  price:               number | null;
  change_1d_pct:       number | null;
  change_7d_pct:       number | null;
  ohlcv_7d?:           OHLCBar[];
}

export interface MagaNewsItem {
  date:      string;
  headline:  string;
  url:       string;
  sentiment: "positive" | "negative" | "neutral";
}

export interface MagaSnapshot {
  updated_at:               string;
  active_policies:          MagaPolicy[];
  stocks:                   MagaStock[];
  policy_sensitivity_matrix: Record<string, Record<string, number>>;
  sector_names:             Record<string, string>;
  summary?: {
    total_beneficiary:    number;
    total_victim:         number;
    avg_beneficiary_score: number;
  };
  news: MagaNewsItem[];
}
