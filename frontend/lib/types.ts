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
  name_zh?: string;
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

export type CycleStage = "萌芽期" | "確認期" | "加速期" | "過熱期";
export type ExitAction = "持有" | "留意" | "減碼" | "出場";

export interface ExitRisk {
  score: number;          // 0–100
  action: ExitAction;
  triggers: string[];
  rs_quadrant: string;
}

export interface SectorData {
  name_zh: string;
  total: number;
  signals: number[];   // 0.0 / 0.5 / 1.0，7個元素
  level: "強烈關注" | "觀察中" | "忽略";
  cycle_stage?: CycleStage | null;
  exit_risk?: ExitRisk | null;
  rs_momentum?: number | null;
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
  usd_twd?: number;
  twd_trend?: "up" | "down";
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

// ────────────────────────────────────────────────────────────────────────
// 三合一：複合訊號 / 組合 / 回測型別
// ────────────────────────────────────────────────────────────────────────

export type TariffScenario = "10%" | "25%" | "60%";
export type SignalLabel = "強烈買入" | "買入" | "中性" | "賣出" | "強烈賣出";

export interface SectorCompositeScore {
  composite: number;   // -2.0 ~ +2.0
  nlp:       number;
  tariff:    number;
  signal:    SignalLabel;
}

export interface CompositeSnapshot {
  updated_at:      string;
  scenario:        TariffScenario;
  nlp_weight:      number;
  tariff_weight:   number;
  scores:          Record<string, SectorCompositeScore>;
  top_buy:         string[];
  top_sell:        string[];
  keyword_hits:    string[];
  tariff_scenario: TariffScenario;
  signal_strength: number;       // 0.0 ~ 1.0
  source_count:    number;
}

// 持倉
export interface HoldingPosition {
  name_zh:         string;
  sector:          string;
  category:        "beneficiary" | "victim" | "neutral";
  composite_score: number;
  entry_price:     number | null;
  shares:          number | null;
  weight:          number;
  added_at:        string;
  reason:          string;
}

export interface HoldingsSnapshot {
  updated_at:     string;
  positions:      Record<string, HoldingPosition>;
  total_weight:   number;
  sector_weights: Record<string, number>;
}

// 損益
export interface PnlPosition {
  name_zh:       string;
  sector:        string;
  entry_price:   number | null;
  current_price: number | null;
  pnl_pct:       number | null;
  pnl_abs:       number | null;
  shares:        number;
  days_held:     number;
}

export interface PnlSnapshot {
  updated_at:        string;
  positions:         Record<string, PnlPosition>;
  portfolio_pnl_pct: number | null;
  best_position:     string | null;
  worst_position:    string | null;
}

// 回測
export interface BacktestTrade {
  buy_date:   string;
  buy_price:  number;
  sell_date:  string;
  sell_price: number;
  pnl_pct:    number;
  hold_days:  number;
}

export interface BacktestTickerResult {
  name_zh:          string;
  sector:           string;
  trades:           BacktestTrade[];
  total_return_pct: number;
  win_rate:         number;
  trade_count:      number;
  max_drawdown_pct: number;
}

export interface BacktestSnapshot {
  ran_at:        string;
  strategy:      {
    entry_threshold: number;
    exit_threshold:  number;
    lookback_days:   number;
    initial_capital: number;
  };
  tickers_tested: number;
  results:        Record<string, BacktestTickerResult>;
  portfolio_summary?: {
    avg_return_pct: number;
    avg_win_rate:   number;
    best_ticker:    string;
    worst_ticker:   string;
  };
}

// ────────────────────────────────────────────────────────────────────────
// 敏感度分析（Sensitivity Analysis）型別
// ────────────────────────────────────────────────────────────────────────

export interface SensitivityPreset {
  label:           string;                  // e.g. "均衡 (5:5)"
  nlp_weight:      number;                  // 0.0 ~ 1.0
  tariff_weight:   number;                  // 0.0 ~ 1.0
  top_buy:         string[];
  top_sell:        string[];
  signal_strength: number;
  scores:          Record<string, { composite: number; signal: SignalLabel }>;
}

export interface SectorStability {
  rank_std:    number;   // 0 = 完全穩定，越大越敏感
  always_buy:  boolean;  // 在所有 5 種權重下皆為買入
  always_sell: boolean;  // 在所有 5 種權重下皆為賣出
}

export interface SensitivitySnapshot {
  updated_at: string;
  scenario:   TariffScenario;
  presets:    SensitivityPreset[];
  stability:  Record<string, SectorStability>;
  note:       string;   // 學術誠實聲明
}

// ────────────────────────────────────────────────────────────────────────
// Trump 貼文即時訊號型別（Vercel KV 存儲）
// ────────────────────────────────────────────────────────────────────────

/** 每個板塊的即時狀態（存於 Vercel KV） */
export interface SectorState {
  score:        number;    // composite score，-2.0 ~ +2.0
  lastUpdated:  string;    // ISO datetime
  deltaHistory: number[];  // 最近 10 筆 delta，由舊到新
}

/** 單篇貼文的板塊衝擊計算結果 */
export interface TrumpPost {
  text:      string;
  timestamp: string | null;
  url:       string | null;
  keywords:  string[];
  impacts:   Record<string, number>;  // sector → -1.0 ~ +1.0
  sentiment: { compound: number; label: string };
}

/** 一個板塊從上次更新到本次的變化 */
export type MomentumLabel =
  | "↑ 訊號強化"
  | "↑ 壓力緩解"
  | "↓ 訊號弱化"
  | "↓ 壓力加深"
  | "→ 無顯著變化";

export interface SectorDelta {
  sector:       string;
  sectorName:   string;           // 中文名稱
  prev:         number;
  current:      number;
  delta:        number;
  momentum:     MomentumLabel;
  accelerating: boolean;          // |delta| > |上一筆 delta| → 🔥
}

/** /api/trump-feed 回傳的完整資料 */
export interface TrumpEventLog {
  updatedAt:      string;
  posts:          TrumpPost[];
  deltas:         SectorDelta[];  // 所有有變動的板塊
  topDeltas:      SectorDelta[];  // 前 5 大絕對值 delta
  totalAnalyzed:  number;
  sources:        string[];       // 來源標示，例如 ["Truth Social", "Google News"]
  /** 儲存於 output/trump_signals.json，供下次 update-trump 計算 delta 用 */
  sectorState?:   Record<string, SectorState>;
}

// ────────────────────────────────────────────────────────────────────────
// 隔日出場警報（Exit Alert）型別
// ────────────────────────────────────────────────────────────────────────

export type ExitAlertAction = "留意" | "減碼" | "出場";

export interface ExitAlertPosition {
  name_zh:            string;
  sector:             string;
  sector_name:        string;
  score:              number;   // 0–100
  action:             ExitAlertAction;
  delta:              number | null;
  prev_score:         number | null;
  current_exit_risk:  number;
  triggers:           string[];
  cycle_stage:        string;
  composite_score:    number;
  weight:             number;
}

export interface ExitAlertSummary {
  exit_count:   number;
  reduce_count: number;
  watch_count:  number;
  safe_count:   number;
}

export interface ExitAlertsSnapshot {
  updated_at:           string;
  system_risk_level:    "low" | "moderate" | "elevated";
  systemic_sector_count: number;
  sector_alerts:        Record<string, {
    score:              number;
    action:             string;
    delta:              number | null;
    prev_score:         number | null;
    current_exit_risk:  number;
    triggers:           string[];
    cycle_stage:        string;
    sector_name:        string;
  }>;
  position_alerts:      Record<string, ExitAlertPosition>;
  summary:              ExitAlertSummary;
}
