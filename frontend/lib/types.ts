// types.ts — FinLab 板塊偵測系統前端型別定義

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
