// fetcher.ts — GitHub Raw URL 資料取得 + Zod schema 驗證

import { z } from "zod";

const GITHUB_RAW_BASE =
  process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL || "";

// Zod schema：驗證 JSON 結構，防止 malformed data 崩潰
const OHLCBarSchema = z.object({
  date: z.string(),
  o: z.number(),
  h: z.number(),
  l: z.number(),
  c: z.number(),
  v: z.number(),
});

const MacroSchema = z.object({
  warning: z.boolean(),
  signal: z.boolean().optional().default(false),
  positive_count: z.number().optional().default(0),
  total_available: z.number().optional().default(0),
  details: z.record(z.string()).optional().default({}),
  us_bond_10y: z.number().optional(),
  bond_trend: z.enum(["up", "down", "unknown"]).optional(),
  ip_index: z.number().optional(),
  ip_trend: z.enum(["up", "down", "unknown"]).optional(),
  sox_price: z.number().optional(),
  sox_trend: z.enum(["up", "down", "unknown"]).optional(),
  usd_twd: z.number().optional(),
  twd_trend: z.enum(["up", "down", "unknown"]).optional(),
});

const StockSchema = z.object({
  id: z.string(),
  name_zh: z.string().optional().default(""),
  score: z.number().nullable().optional(),
  grade: z.string().optional().default(""),
  change_pct: z.number().nullable().optional(),
  triggered: z.array(z.string()).optional().default([]),
  breakdown: z
    .object({
      fundamental: z.number(),
      technical: z.number(),
      chipset: z.number(),
      bonus: z.number(),
    })
    .optional(),
  price_flag: z.enum(["normal", "ex_div", "halt"]).optional(),
  ohlcv_7d: z.array(OHLCBarSchema).optional(),
});

const ExitRiskSchema = z.object({
  score: z.number(),
  action: z.enum(["持有", "留意", "減碼", "出場"]),
  triggers: z.array(z.string()),
  rs_quadrant: z.string(),
});

const SectorSchema = z.object({
  name_zh: z.string(),
  total: z.number(),
  signals: z.array(z.number()).length(7),
  level: z.enum(["強烈關注", "觀察中", "忽略"]),
  cycle_stage: z.enum(["萌芽期", "確認期", "加速期", "過熱期"]).nullable().optional(),
  exit_risk: ExitRiskSchema.nullable().optional(),
  rs_momentum: z.number().nullable().optional(),
  constituent_count: z.number().optional(),
  source: z.enum(["custom", "auto"]).optional(),
  homogeneity: z.number().nullable().optional(),
  member_count: z.number().optional(),
  stocks: z.array(StockSchema).optional().default([]),
});

const MarketStateSchema = z.object({
  state: z.enum(["bull", "sideways", "bear", "unknown"]).default("unknown"),
  state_zh: z.string().optional().default(""),
  confidence: z.number().optional().default(0),
  taiex_vs_200ma_pct: z.number().nullable().optional(),
  momentum_20d_pct: z.number().nullable().optional(),
  details: z.string().optional().default(""),
});

const SnapshotSchema = z.object({
  schema_version: z.string().optional(),
  date: z.string(),
  run_at: z.string(),
  last_trading_date: z.string().optional(),
  macro: MacroSchema,
  macro_warning: z.boolean().optional(),
  market_state: MarketStateSchema.optional(),
  sectors: z.record(SectorSchema),
});

const HistoryIndexSchema = z.object({
  dates: z.array(z.string()),
  sectors: z.record(
    z.object({
      name_zh: z.string(),
      totals: z.array(z.number()),
      levels: z.array(z.string()),
    })
  ),
  macro: z
    .array(
      z.object({
        date: z.string(),
        warning: z.boolean(),
        signal: z.boolean().optional(),
        positive_count: z.number().optional(),
        us_bond_10y: z.number().optional(),
        sox_price: z.number().optional(),
      })
    )
    .optional()
    .default([]),
});

// ── 商品市場 Zod schema ───────────────────────────────────────────────────

const EconSignalSchema = z.object({
  key: z.string(),
  triggered: z.boolean(),
  severity: z.enum(["high", "medium", "low"]),
  commentary: z.string(),
  source: z.string(),
});

const CommodityAssetSchema = z.object({
  slug: z.string(),
  name_zh: z.string(),
  category: z.enum(["precious_metal", "energy", "industrial", "crypto", "index", "bonds"]),
  price: z.number().nullable(),
  change_1d_pct: z.number().nullable(),
  change_7d_pct: z.number().nullable(),
  signals: z.array(EconSignalSchema).optional().default([]),
  last_updated: z.string(),
});

const YieldPointSchema = z.object({
  tenor: z.string(),
  years: z.number(),
  yield_pct: z.number(),
});

const CommoditySnapshotSchema = z.object({
  updated_at: z.string(),
  assets: z.record(CommodityAssetSchema),
  yield_curve: z.array(YieldPointSchema).optional().default([]),
  yield_curve_analysis: z.object({
    spread_2_10:  z.number().nullable(),
    spread_2_30:  z.number().nullable(),
    spread_10_30: z.number().nullable(),
    is_inverted:  z.boolean(),
    slope_signal: z.enum(["inverted", "flat", "normal", "steep", "unknown"]),
    signals:      z.array(EconSignalSchema).optional().default([]),
  }).optional(),
  market_summary: z.object({
    total_triggered: z.number(),
    high_count:      z.number(),
    medium_count:    z.number(),
    overall:         z.enum(["risk_off", "caution", "neutral", "risk_on"]),
    headline:        z.string(),
    key_alerts:      z.array(z.string()).optional().default([]),
  }).optional(),
});

// ── fetch 工具 ────────────────────────────────────────────────────────────

async function fetchJSON<T>(url: string, revalidate = 1800): Promise<T> {
  const res = await fetch(url, { next: { revalidate } }); // ISR 30 分鐘
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${url}`);
  }
  // Python json.dumps 可能產出 NaN/Infinity（非合法 JSON），先替換再解析
  const text = await res.text();
  return JSON.parse(text.replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/-Infinity\b/g, "null"));
}

export async function fetchLatestSnapshot() {
  if (!GITHUB_RAW_BASE) {
    // build 時未設定 env var （第一次部署）
    return null;
  }
  const url = `${GITHUB_RAW_BASE}/output/signals_latest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = SnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.error("signals_latest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch (e) {
    console.error("fetchLatestSnapshot failed:", e);
    return null;
  }
}

export async function fetchHistoryIndex() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/history/history_index.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = HistoryIndexSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("history_index.json schema 驗證失敗");
      return null;
    }
    return parsed.data;
  } catch {
    // 首次部署時 history_index 可能不存在
    return null;
  }
}

export async function fetchCommodities() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/commodities/latest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = CommoditySnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("commodities/latest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch {
    return null;
  }
}

export async function fetchCommodityOHLCV(slug: string) {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/commodities/${slug}.json`;
  try {
    const raw = await fetch(url, { cache: "no-store" });
    if (!raw.ok) return null;
    const data = await raw.json();
    const parsed = z.array(OHLCBarSchema).safeParse(data);
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

// ── MAGA 投資組合追蹤 ─────────────────────────────────────────────────────

const MagaPolicySchema = z.object({
  key:         z.string(),
  label:       z.string(),
  active:      z.boolean(),
  description: z.string(),
});

const MagaStockSchema = z.object({
  ticker:              z.string(),
  id:                  z.string(),
  name_zh:             z.string(),
  sector_id:           z.string(),
  sector_name:         z.string(),
  category:            z.enum(["beneficiary", "victim"]),
  impact_score:        z.number(),
  policy_contributions: z.record(z.number()).optional().default({}),
  price:               z.number().nullable(),
  change_1d_pct:       z.number().nullable(),
  change_7d_pct:       z.number().nullable(),
  ohlcv_7d:            z.array(OHLCBarSchema).optional().default([]),
});

const MagaNewsItemSchema = z.object({
  date:      z.string(),
  headline:  z.string(),
  url:       z.string(),
  sentiment: z.enum(["positive", "negative", "neutral"]),
});

const MagaSnapshotSchema = z.object({
  updated_at:               z.string(),
  active_policies:          z.array(MagaPolicySchema).optional().default([]),
  stocks:                   z.array(MagaStockSchema).optional().default([]),
  policy_sensitivity_matrix: z.record(z.record(z.number())).optional().default({}),
  sector_names:             z.record(z.string()).optional().default({}),
  summary: z.object({
    total_beneficiary:     z.number(),
    total_victim:          z.number(),
    avg_beneficiary_score: z.number(),
  }).optional(),
  news: z.array(MagaNewsItemSchema).optional().default([]),
});

export async function fetchMagaData() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/maga/latest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = MagaSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("maga/latest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch {
    return null;
  }
}

// ── 三合一：複合訊號 / 組合 / 損益 / 回測 ────────────────────────────────

const SectorCompositeScoreSchema = z.object({
  composite: z.number(),
  nlp:       z.number(),
  tariff:    z.number(),
  signal:    z.enum(["強烈買入", "買入", "中性", "賣出", "強烈賣出"]),
});

const CompositeSnapshotSchema = z.object({
  updated_at:      z.string(),
  scenario:        z.enum(["10%", "25%", "60%"]),
  nlp_weight:      z.number(),
  tariff_weight:   z.number(),
  scores:          z.record(SectorCompositeScoreSchema),
  top_buy:         z.array(z.string()).optional().default([]),
  top_sell:        z.array(z.string()).optional().default([]),
  keyword_hits:    z.array(z.string()).optional().default([]),
  tariff_scenario: z.enum(["10%", "25%", "60%"]),
  signal_strength: z.number(),
  source_count:    z.number(),
});

const HoldingPositionSchema = z.object({
  name_zh:         z.string(),
  sector:          z.string(),
  category:        z.enum(["beneficiary", "victim", "neutral"]),
  composite_score: z.number(),
  entry_price:     z.number().nullable(),
  shares:          z.number().nullable(),
  weight:          z.number(),
  added_at:        z.string(),
  reason:          z.string(),
});

const HoldingsSnapshotSchema = z.object({
  updated_at:     z.string(),
  positions:      z.record(HoldingPositionSchema),
  total_weight:   z.number(),
  sector_weights: z.record(z.number()),
});

const PnlPositionSchema = z.object({
  name_zh:       z.string(),
  sector:        z.string(),
  entry_price:   z.number().nullable(),
  current_price: z.number().nullable(),
  pnl_pct:       z.number().nullable(),
  pnl_abs:       z.number().nullable(),
  shares:        z.number(),
  days_held:     z.number(),
});

const PnlSnapshotSchema = z.object({
  updated_at:        z.string(),
  positions:         z.record(PnlPositionSchema),
  portfolio_pnl_pct: z.number().nullable(),
  best_position:     z.string().nullable(),
  worst_position:    z.string().nullable(),
});

const BacktestTradeSchema = z.object({
  buy_date:   z.string(),
  buy_price:  z.number(),
  sell_date:  z.string(),
  sell_price: z.number(),
  pnl_pct:    z.number(),
  hold_days:  z.number(),
});

const BacktestTickerResultSchema = z.object({
  name_zh:          z.string(),
  sector:           z.string(),
  trades:           z.array(BacktestTradeSchema).optional().default([]),
  total_return_pct: z.number(),
  win_rate:         z.number(),
  trade_count:      z.number(),
  max_drawdown_pct: z.number(),
});

const BacktestSnapshotSchema = z.object({
  ran_at:        z.string(),
  strategy:      z.object({
    entry_threshold: z.number(),
    exit_threshold:  z.number(),
    lookback_days:   z.number(),
    initial_capital: z.number(),
  }),
  tickers_tested: z.number(),
  results:        z.record(BacktestTickerResultSchema),
  portfolio_summary: z.object({
    avg_return_pct: z.number(),
    avg_win_rate:   z.number(),
    best_ticker:    z.string(),
    worst_ticker:   z.string(),
  }).optional(),
});

export async function fetchComposite() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/composite/latest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = CompositeSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("composite/latest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

export async function fetchHoldings() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/portfolio/holdings.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = HoldingsSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("portfolio/holdings.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

// ── 用戶自選持倉 ────────────────────────────────────────────────────────────

const UserHoldingPositionSchema = z.object({
  name_zh:     z.string(),
  sector:      z.string(),
  entry_price: z.number().nullable(),
  entry_date:  z.string(),
  shares:      z.number().nullable(),
  note:        z.string().optional().default(""),
});

const UserHoldingsSnapshotSchema = z.object({
  updated_at:  z.string(),
  updated_by:  z.string(),
  positions:   z.record(UserHoldingPositionSchema),
});

export async function fetchUserHoldings() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/portfolio/user_holdings.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = UserHoldingsSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("portfolio/user_holdings.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

// ── 完整股票代碼→名稱+板塊對照 ──────────────────────────────────────────
const StockNameEntrySchema = z.object({
  name_zh: z.string(),
  sector:  z.string(),
  sector_name: z.string().optional().default(""),
});

const StockNamesMapSchema = z.record(StockNameEntrySchema);

export type StockNamesMap = z.infer<typeof StockNamesMapSchema>;

export async function fetchStockNames(): Promise<StockNamesMap | null> {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/stock_names.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = StockNamesMapSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("stock_names.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

export async function fetchPnl() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/portfolio/pnl.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = PnlSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("portfolio/pnl.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

// ── 隔日出場警報 ────────────────────────────────────────────────────────────

const ExitAlertPositionSchema = z.object({
  name_zh:            z.string(),
  sector:             z.string(),
  sector_name:        z.string(),
  score:              z.number(),
  action:             z.enum(["留意", "減碼", "出場"]),
  delta:              z.number().nullable(),
  prev_score:         z.number().nullable(),
  current_exit_risk:  z.number(),
  triggers:           z.array(z.string()),
  cycle_stage:        z.string(),
  composite_score:    z.number(),
  weight:             z.number(),
});

const SectorAlertSchema = z.object({
  score:              z.number(),
  action:             z.string(),
  delta:              z.number().nullable(),
  prev_score:         z.number().nullable(),
  current_exit_risk:  z.number(),
  triggers:           z.array(z.string()),
  cycle_stage:        z.string(),
  sector_name:        z.string(),
});

const ExitAlertsSnapshotSchema = z.object({
  updated_at:           z.string(),
  system_risk_level:    z.enum(["low", "moderate", "elevated"]),
  systemic_sector_count: z.number(),
  sector_alerts:        z.record(SectorAlertSchema),
  position_alerts:      z.record(ExitAlertPositionSchema),
  summary: z.object({
    exit_count:   z.number(),
    reduce_count: z.number(),
    watch_count:  z.number(),
    safe_count:   z.number(),
  }),
});

export async function fetchExitAlerts() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/portfolio/exit_alerts.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = ExitAlertsSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("portfolio/exit_alerts.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

export async function fetchBacktest() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/portfolio/backtest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = BacktestSnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("portfolio/backtest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}

// ── 敏感度分析 ────────────────────────────────────────────────────────────

const SensitivityPresetSchema = z.object({
  label:           z.string(),
  nlp_weight:      z.number(),
  tariff_weight:   z.number(),
  top_buy:         z.array(z.string()).optional().default([]),
  top_sell:        z.array(z.string()).optional().default([]),
  signal_strength: z.number(),
  scores: z.record(z.object({
    composite: z.number(),
    signal:    z.enum(["強烈買入", "買入", "中性", "賣出", "強烈賣出"]),
  })),
});

const SectorStabilitySchema = z.object({
  rank_std:    z.number(),
  always_buy:  z.boolean(),
  always_sell: z.boolean(),
});

const SensitivitySnapshotSchema = z.object({
  updated_at: z.string(),
  scenario:   z.enum(["10%", "25%", "60%"]),
  presets:    z.array(SensitivityPresetSchema),
  stability:  z.record(SectorStabilitySchema),
  note:       z.string().optional().default(""),
});

export async function fetchSensitivity() {
  if (!GITHUB_RAW_BASE) return null;
  const url = `${GITHUB_RAW_BASE}/output/composite/sensitivity.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = SensitivitySnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("composite/sensitivity.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch { return null; }
}