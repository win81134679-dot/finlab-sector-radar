// regime.ts — 盤性辨識核心計算邏輯（純函式，無副作用）
// 對應老師心法：法人盤 / 大戶盤 / 散戶情緒盤 三分類 + 七項量化訊號
//
// 資料來源：signals_latest.json（ohlcv_7d 實際含最多20棒）
// ③ 499張現象：保留接口 ticker499，未來接入即時 tick 後填入

import type { OHLCBar, SectorData, StockData } from "@/lib/types";

// ────────────────────────────────────────────────────────────────────────────
// 型別定義
// ────────────────────────────────────────────────────────────────────────────

export type RegimeType = "法人盤" | "大戶盤" | "散戶情緒盤" | "混合盤" | "不明";
export type PhaseType  = "建倉期" | "拉升期" | "派發期" | "整理期" | "不明";
export type ActionType =
  | "可跟進 · 追蹤法人動向"
  | "短線機動（嚴設停損）"
  | "⚠️ 不建議 · 等回調確認"
  | "⚠️ 出場或空手"
  | "觀望";

/** 單一訊號結果（七項各一個） */
export interface SignalResult {
  label: string;       // 訊號名稱
  value: string;       // 結論文字
  detail: string;      // 詳細說明
  score: number;       // 貢獻分數（-2 ~ +4，供加總判斷盤性）
  bullish: boolean | null; // true=正向 false=負向 null=中性/不支援
  supported: boolean;  // false = 此訊號因資料不足無法計算
  futureExpansion?: boolean; // 保留接口標記
}

/** 個股盤性結果 */
export interface StockRegimeResult {
  stockId:    string;
  stockName?: string;
  regime:     RegimeType;
  phase:      PhaseType;
  action:     ActionType;
  confidence: number;   // 0–100
  signals:    SignalResult[];  // 七項訊號明細
  regimeScores: { institutional: number; whale: number; retail: number };
}

/** 板塊盤性結果 */
export interface SectorRegimeResult {
  sectorId:    string;
  sectorName:  string;
  sectorLevel: SectorData["level"];
  regime:      RegimeType;
  phase:       PhaseType;
  confidence:  number;
  institutionalStrength: string; // "強" | "中" | "弱" | "無"
  stockCount:  number;
  topStocks:   StockRegimeResult[];
}

/** 大盤盤性結果 */
export interface MarketRegimeResult {
  regime:      RegimeType;
  phase:       PhaseType;
  confidence:  number;
  description: string;
  signals:     string[];   // 大盤層面的具體訊號列表
}

// ────────────────────────────────────────────────────────────────────────────
// 1. K棒規律性分析
// ────────────────────────────────────────────────────────────────────────────

interface KBarAnalysis {
  avgDailyRange:   number;   // 日均振幅 %（ATR%代理）
  consecutiveLimitUp: number; // 連續漲停天數（收漲幅>=9.5%視為漲停）
  longUpperShadows: number;  // 長上影線次數（影線 > 實體1.5倍且在高位）
  isRegular:       boolean;  // 規律性（振幅 < 4% 且無連續漲停）
  label:           string;
  score:           number;   // 正=利好法人盤，負=利好大戶/散戶
}

export function analyzeKBar(bars: OHLCBar[]): KBarAnalysis {
  if (bars.length < 3) {
    return { avgDailyRange: 0, consecutiveLimitUp: 0, longUpperShadows: 0, isRegular: false, label: "資料不足", score: 0 };
  }

  const recent = bars.slice(-Math.min(bars.length, 14));

  // 日均振幅（High-Low / Open）%
  const ranges = recent.map(b => b.o > 0 ? ((b.h - b.l) / b.o) * 100 : 0);
  const avgDailyRange = ranges.reduce((a, b) => a + b, 0) / ranges.length;

  // 連續漲停（台股漲停10% → 用 9.5% 作門檻，包含零股/ETF）
  let consecutive = 0;
  for (let i = recent.length - 1; i >= 0; i--) {
    const bar = recent[i];
    if (bar.o > 0 && ((bar.c - bar.o) / bar.o) >= 0.095) consecutive++;
    else break;
  }

  // 長上影線（上影線 > 實體1.5倍）
  const longUpper = recent.filter(b => {
    const body = Math.abs(b.c - b.o);
    const upper = b.h - Math.max(b.c, b.o);
    return body > 0 && upper > body * 1.5;
  }).length;

  const isRegular = avgDailyRange < 4 && consecutive === 0;

  let label: string;
  let score: number;
  if (consecutive >= 2) {
    label = `連 ${consecutive} 漲停 · 大戶攻勢`;
    score = -2; // 偏向大戶盤
  } else if (longUpper >= 2) {
    label = `${longUpper} 次長上影線 · 疑似派發`;
    score = -3; // 偏向散戶盤（主力派發）
  } else if (isRegular) {
    label = `K棒規律 · 振幅 ${avgDailyRange.toFixed(1)}%`;
    score = 2; // 利好法人盤
  } else {
    label = `振幅偏大 ${avgDailyRange.toFixed(1)}% · 盤整`;
    score = 0;
  }

  return { avgDailyRange, consecutiveLimitUp: consecutive, longUpperShadows: longUpper, isRegular, label, score };
}

// ────────────────────────────────────────────────────────────────────────────
// 2. 成交量位階分析
// ────────────────────────────────────────────────────────────────────────────

interface VolumeAnalysis {
  recentVolRatio:  number;    // 近3日 vs 全期均量比
  trend:           "爆量" | "溫和放量" | "窒息量" | "量增不漲" | "量減價漲" | "正常";
  label:           string;
  score:           number;    // 正=法人佈局 負=派發/散戶
}

export function analyzeVolume(bars: OHLCBar[]): VolumeAnalysis {
  if (bars.length < 5) {
    return { recentVolRatio: 1, trend: "正常", label: "資料不足", score: 0 };
  }

  const avgVol   = bars.slice(0, -3).reduce((s, b) => s + b.v, 0) / Math.max(bars.length - 3, 1);
  const recent3  = bars.slice(-3);
  const recentVol = recent3.reduce((s, b) => s + b.v, 0) / 3;
  const ratio    = avgVol > 0 ? recentVol / avgVol : 1;

  // 近3日價格方向
  const priceChange = bars.length >= 4
    ? (bars[bars.length - 1].c - bars[bars.length - 4].c) / bars[bars.length - 4].c * 100
    : 0;

  let trend: VolumeAnalysis["trend"];
  let score: number;
  let label: string;

  if (ratio >= 2.5) {
    if (priceChange < 1) {
      trend = "量增不漲"; score = -3; label = `爆量滯漲（${ratio.toFixed(1)}x）· 派發警示`;
    } else {
      trend = "爆量"; score = -1; label = `爆量 ${ratio.toFixed(1)}x · 可能主力拉抬或追高`;
    }
  } else if (ratio >= 1.3) {
    trend = "溫和放量"; score = 2; label = `溫和放量 ${ratio.toFixed(1)}x · 主力佈局特徵`;
  } else if (ratio < 0.5) {
    if (priceChange > 2) {
      // 量縮價漲：可能是主力控盤，也可能是無量虛漲，中性觀察
      trend = "量減價漲"; score = 0; label = `量縮價漲 ${ratio.toFixed(1)}x · 需確認籌碼支撐`;
    } else {
      trend = "窒息量"; score = -1; label = `窒息量 ${ratio.toFixed(1)}x · 觀望盤`;
    }
  } else {
    trend = "正常"; score = 0; label = `量能正常 ${ratio.toFixed(1)}x`;
  }

  return { recentVolRatio: ratio, trend, label, score };
}

// ────────────────────────────────────────────────────────────────────────────
// 3. 499張現象（保留接口，未來擴充）
// ────────────────────────────────────────────────────────────────────────────

export interface Ticker499Data {
  hasData: false;  // 未來實作後改為 true | false
  // 未來欄位：count499: number; ratio499: number; verdict: string;
}

export function analyze499(): SignalResult {
  // 保留接口：未來接入券商即時委託 tick 資料後，在此實作連續499張偵測邏輯
  // 偵測方法：成交明細連續出現 490~499 張 = 大戶規避500張申報門檻
  return {
    label:    "③ 499張委託現象",
    value:    "❌ 不支援",
    detail:   "需券商即時撮合 tick 資料（FinLab 不提供）· 未來擴充接口已保留",
    score:    0,
    bullish:  null,
    supported: false,
    futureExpansion: true,
  };
}

// ────────────────────────────────────────────────────────────────────────────
// 4. KDJ 指標計算（Stochastic %K/%D/%J）
// ────────────────────────────────────────────────────────────────────────────

interface KDJResult {
  K: number;
  D: number;
  J: number;
  crossover: "金叉" | "死叉" | "高位鈍化" | "低位" | "中性";
  label: string;
  score: number;
  isPrecise:    boolean; // bars >= 30：殘差 0.02%，標準精確
  isAcceptable: boolean; // bars >= 20：殘差 0.77%，可接受
}

export function calcKDJ(bars: OHLCBar[]): KDJResult {
  const N = 9;
  if (bars.length < N) {
    return { K: 50, D: 50, J: 50, crossover: "中性", label: "資料不足（需≥9棒）", score: 0, isPrecise: false, isAcceptable: false };
  }

  const isPrecise = bars.length >= 30;  // 30棒 = 22次迭代，殘差 0.02%，精確
  const isAcceptable = bars.length >= 20; // 20棒 = 12次迭代，殘差 0.77%，良好

  // 計算 RSV（Raw Stochastic Value）
  let K = 50, D = 50;
  for (let i = N - 1; i < bars.length; i++) {
    const window = bars.slice(i - N + 1, i + 1);
    const high = Math.max(...window.map(b => b.h));
    const low  = Math.min(...window.map(b => b.l));
    const rsv  = high === low ? 50 : ((bars[i].c - low) / (high - low)) * 100;
    K = (2 / 3) * K + (1 / 3) * rsv;
    D = (2 / 3) * D + (1 / 3) * K;
  }
  const J = 3 * K - 2 * D;

  let crossover: KDJResult["crossover"];
  let score: number;
  let label: string;

  if (K > D && K < 30) {
    crossover = "金叉"; score = 2; label = `低位金叉 K${K.toFixed(0)} D${D.toFixed(0)} · 主力啟動特徵`;
  } else if (K > D && K > 80) {
    crossover = "高位鈍化"; score = -1; label = `高位 K${K.toFixed(0)} · 注意鈍化風險`;
  } else if (K < D && K > 70) {
    crossover = "死叉"; score = -2; label = `高位死叉 K${K.toFixed(0)} D${D.toFixed(0)} · 轉弱訊號`;
  } else if (K > D && K >= 30 && K <= 80) {
    // 中位金叉：方向向上但非極端區，給小正分
    crossover = "金叉"; score = 1; label = `中位金叉 K${K.toFixed(0)} D${D.toFixed(0)} · 偏多格局`;
  } else if (K < D && K <= 70) {
    crossover = "死叉"; score = -1; label = `中位死叉 K${K.toFixed(0)} D${D.toFixed(0)} · 偏弱`;
  } else if (K < 30) {
    crossover = "低位"; score = 1; label = `低位盤整 K${K.toFixed(0)} · 等待金叉`;
  } else {
    crossover = "中性"; score = 0; label = `中位 K${K.toFixed(0)} D${D.toFixed(0)} · 無明確訊號`;
  }

  return { K, D, J, crossover, label, score, isPrecise, isAcceptable };
}

// ────────────────────────────────────────────────────────────────────────────
// 5. 法人籌碼分析（從 triggered / breakdown）
// ────────────────────────────────────────────────────────────────────────────

interface InstitutionalAnalysis {
  hasForeign:    boolean;
  hasTrust:      boolean;
  hasChipset:    boolean;   // 燈6：融資+借券雙降
  hasShortCover: boolean;
  hasShortAdd:   boolean;   // 警示
  hasFundamental: boolean;  // EPS
  label:   string;
  score:   number;
}

export function analyzeInstitutional(stock: StockData): InstitutionalAnalysis {
  const t = stock.triggered ?? [];
  const hasForeign    = t.some(x => x.includes("燈2") || x.includes("外資"));
  const hasTrust      = t.some(x => x.includes("投信"));
  const hasChipset    = t.some(x => x.includes("燈6"));
  const hasShortCover = t.includes("借券回補↑");
  const hasShortAdd   = t.includes("空頭加碼⚠");
  const hasFundamental = t.some(x => x.includes("EPS") || x.includes("燈1") || x.includes("ROE"));

  let score = 0;
  const parts: string[] = [];

  if (hasForeign && hasTrust) { score += 3; parts.push("外資+投信共振"); }
  else if (hasForeign)        { score += 1.5; parts.push("外資獨買"); }
  else if (hasTrust)          { score += 1.5; parts.push("投信獨買"); }
  if (hasChipset)  { score += 2; parts.push("融資借券雙降"); }
  if (hasShortCover) { score += 0.5; parts.push("空頭回補"); }
  if (hasShortAdd)   { score -= 1; parts.push("空頭加碼⚠"); }
  if (hasFundamental) { score += 0.5; }

  const label = parts.length > 0 ? parts.join(" · ") : "無明確法人訊號";
  return { hasForeign, hasTrust, hasChipset, hasShortCover, hasShortAdd, hasFundamental, label, score };
}

// ────────────────────────────────────────────────────────────────────────────
// 6. 領頭股分析（板塊排名）
// ────────────────────────────────────────────────────────────────────────────

interface LeaderAnalysis {
  rankInSector: number;     // 1-based
  totalInSector: number;
  rankPct: number;          // 0=第一 100=最後
  isLeader: boolean;        // Top 1/3
  label: string;
  score: number;
}

export function analyzeLeader(stock: StockData, sectorStocks: StockData[]): LeaderAnalysis {
  if (sectorStocks.length === 0) {
    return { rankInSector: 1, totalInSector: 1, rankPct: 0, isLeader: true, label: "唯一成員", score: 1 };
  }

  const sorted = [...sectorStocks].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const rank   = sorted.findIndex(s => s.id === stock.id) + 1;
  const rankPct = sectorStocks.length > 1 ? ((rank - 1) / (sectorStocks.length - 1)) * 100 : 0;
  const isLeader = rankPct <= 33;

  let score: number;
  let label: string;
  if (rank === 1) {
    score = 2; label = `板塊第1名 · 明確領頭`;
  } else if (isLeader) {
    score = 1; label = `板塊第${rank}名（前33%）`;
  } else {
    score = -1; label = `板塊第${rank}名（後${100 - Math.round(rankPct)}%）`;
  }

  return { rankInSector: rank, totalInSector: sorted.length, rankPct, isLeader, label, score };
}

// ────────────────────────────────────────────────────────────────────────────
// 7. 媒體熱度分析（Proxy）
// ────────────────────────────────────────────────────────────────────────────

interface MediaHeatAnalysis {
  heatLevel: "冷門" | "正常" | "偏熱" | "過熱";
  label: string;
  score: number;  // 正=冷門（好事） 負=過熱（壞事）
}

export function analyzeMediaHeat(stock: StockData): MediaHeatAnalysis {
  const change  = Math.abs(stock.change_pct ?? 0);
  const triggeredCount = (stock.triggered ?? []).length;
  const score_  = stock.score ?? 0;
  const grade   = stock.grade ?? "";

  // 高漲幅但低訊號數 = 消息面/散戶追高
  let heatLevel: MediaHeatAnalysis["heatLevel"];
  let label: string;
  let score: number;

  if (change >= 7 && triggeredCount <= 3) {
    heatLevel = "過熱"; score = -3; label = `漲幅${change.toFixed(1)}% · 訊號少(${triggeredCount}) → 散戶情緒追高`;
  } else if (change >= 5 && score_ < 6) {
    heatLevel = "偏熱"; score = -2; label = `漲幅${change.toFixed(1)}% · 評分${score_.toFixed(1)} · 注意追高風險`;
  } else if (change <= 1 && (grade === "⭐⭐⭐" || score_ >= 9)) {
    heatLevel = "冷門"; score = 2; label = `無人關注但燈強 · 主力佈局初期特徵`;
  } else {
    heatLevel = "正常"; score = 0; label = `漲跌${stock.change_pct != null ? (stock.change_pct > 0 ? "+" : "") + stock.change_pct.toFixed(2) + "%" : "N/A"} · 無異常熱度`;
  }

  return { heatLevel, label, score };
}

// ────────────────────────────────────────────────────────────────────────────
// 主分類器：個股盤性
// ────────────────────────────────────────────────────────────────────────────

export function classifyStockRegime(
  stock: StockData,
  sector: SectorData,
  sectorStocks: StockData[],
): StockRegimeResult {
  const bars = stock.ohlcv_7d ?? [];

  // 七訊號計算
  const kbar       = analyzeKBar(bars);
  const vol        = analyzeVolume(bars);
  const sig499     = analyze499();                        // 接口保留
  const kdj        = calcKDJ(bars);
  const inst       = analyzeInstitutional(stock);
  const leader     = analyzeLeader(stock, sectorStocks);
  const media      = analyzeMediaHeat(stock);

  // ─── 盤性原始評分 ───────────────────────────────────────────────────────
  // ① 法人分：法人籌碼 + 領頭地位 + 量能（溫和放量是法人特徵）
  const institutional = inst.score + (leader.score * 0.5) + (vol.trend === "溫和放量" ? 1 : 0);
  // ② 大戶分：連漲停爆發力 + 暴量
  const whale         = (kbar.consecutiveLimitUp >= 2 ? 4 : 0) + (vol.trend === "爆量" ? 2 : 0);
  // ③ 散戶分：量增不漲（派發）+ 熱度過高 + 長上影線（派發特徵）
  const retail        = (media.score * -1) + (vol.trend === "量增不漲" ? 3 : 0) + (kbar.longUpperShadows >= 2 ? 2 : 0);

  // ─── 正規化（各維度量綱不同，對齊後比較才有意義）──────────────────────────
  // INST_MAX=8：inst最高6(外資+投信+籌碼+加分) + leader×0.5最高1 + vol加成最高1
  // WHALE_MAX=6：連漲停4 + 爆量2
  // RETAIL_MAX=8：媒體過熱3 + 量增不漲3 + 長上影線2
  const INST_MAX   = 8.0;
  const WHALE_MAX  = 6.0;
  const RETAIL_MAX = 8.0;
  // 防呗：未來新增訊號忘記更新常數時，開發期間立刻發現
  if (process.env.NODE_ENV !== "production") {
    console.assert(institutional <= INST_MAX, `inst.score ${institutional.toFixed(2)} 超過 INST_MAX ${INST_MAX}`);
    console.assert(whale <= WHALE_MAX,         `whale.score ${whale} 超過 WHALE_MAX ${WHALE_MAX}`);
    console.assert(retail <= RETAIL_MAX,       `retail.score ${retail.toFixed(2)} 超過 RETAIL_MAX ${RETAIL_MAX}`);
  }
  const instNorm   = Math.max(0, institutional) / INST_MAX;
  const whaleNorm  = Math.max(0, whale)         / WHALE_MAX;
  const retailNorm = Math.max(0, retail)        / RETAIL_MAX;

  // ─── 盤性判定（正規化後比較，差距 ≥ 0.25 才判明確盤性）──────────────────
  const maxNorm = Math.max(instNorm, whaleNorm, retailNorm);
  let regime: RegimeType;
  if (maxNorm < 0.25) {
    regime = "不明";
  } else if (instNorm >= whaleNorm && instNorm >= retailNorm && instNorm - Math.max(whaleNorm, retailNorm) >= 0.25) {
    regime = "法人盤";
  } else if (whaleNorm >= instNorm && whaleNorm >= retailNorm && whaleNorm - Math.max(instNorm, retailNorm) >= 0.25) {
    regime = "大戶盤";
  } else if (retailNorm >= instNorm && retailNorm >= whaleNorm && retailNorm - Math.max(instNorm, whaleNorm) >= 0.25) {
    regime = "散戶情緒盤";
  } else {
    regime = "混合盤";
  }

  // 階段判定（用 ohlcv 近期走勢）
  let phase: PhaseType = "不明";
  if (bars.length >= 5) {
    const oldest  = bars[bars.length - 5].c;
    const latest  = bars[bars.length - 1].c;
    const pctChange = oldest > 0 ? ((latest - oldest) / oldest) * 100 : 0;

    // 從期間最高點到現在的回撤（抓高檔震盪派發）
    const maxHigh  = Math.max(...bars.map(b => b.h));
    const fromPeak = maxHigh > 0 ? (latest - maxHigh) / maxHigh : 0; // 負値 = 回撤

    // 派發判定：量增不漲，或長上影線 + （近期漲幅>5% OR 從高點回撤>3%）
    const isDistributionPhase =
      vol.trend === "量增不漲" ||
      (kbar.longUpperShadows >= 2 && (pctChange > 5 || fromPeak < -0.03));

    if (kbar.consecutiveLimitUp >= 2 || pctChange > 15) {
      // 強勢上漲：需>=2根長上影線才判派發（1根可能只是單日震盪）
      phase = kbar.longUpperShadows >= 2 ? "派發期" : "拉升期";
    } else if (isDistributionPhase) {
      phase = "派發期";
    } else if (pctChange > 5 && vol.trend !== "量增不漲") {
      phase = "拉升期";
    } else if (vol.trend === "溫和放量" && pctChange < 5 && inst.hasForeign) {
      phase = "建倉期";
    } else {
      phase = "整理期";
    }
  }

  // ─── 第零層：排除條件（兩條進場路徑共用，最先判定）─────────────────────
  const isDistribution = phase === "派發期";
  const isRetailDriven = regime === "散戶情緒盤";

  // ─── 建議動作 ────────────────────────────────────────────────────────────
  let action: ActionType;
  if (isDistribution || isRetailDriven) {
    // 排除條件：派發期或散戶情緒主導，兩條進場路徑均不適用
    action = "⚠️ 出場或空手";
  } else if (regime === "法人盤" && (phase === "建倉期" || phase === "拉升期")) {
    action = "可跟進 · 追蹤法人動向";
  } else if (regime === "大戶盤") {
    // 到達此處時 isDistribution 已確認為 false（派發期已在最外層排除）
    action = "短線機動（嚴設停損）";
  } else if (regime === "混合盤" || regime === "不明") {
    action = "觀望";
  } else {
    action = "⚠️ 不建議 · 等回調確認";
  }

  // 信心度（0~100）：使用正規化差距計算，差距越大信心越高
  const normSecond = maxNorm === instNorm ? Math.max(whaleNorm, retailNorm)
                   : maxNorm === whaleNorm ? Math.max(instNorm, retailNorm)
                   : Math.max(instNorm, whaleNorm);
  // 上限 95：避免顯示 100%（不確定性永遠存在）
  const confidence = Math.min(95, Math.round(40 + (maxNorm - normSecond) * 80));

  // 七訊號明細清單
  const signals: SignalResult[] = [
    {
      label: "① K棒規律性",
      value: kbar.label,
      detail: `振幅${kbar.avgDailyRange.toFixed(1)}% · 連漲停${kbar.consecutiveLimitUp}次 · 長上影線${kbar.longUpperShadows}次`,
      score: kbar.score,
      bullish: kbar.score > 0 ? true : kbar.score < 0 ? false : null,
      supported: bars.length >= 3,
    },
    {
      label: "② 成交量位階",
      value: vol.label,
      detail: `近3日均量 vs 基期均量 = ${vol.recentVolRatio.toFixed(2)}x`,
      score: vol.score,
      bullish: vol.score > 0 ? true : vol.score < 0 ? false : null,
      supported: bars.length >= 5,
    },
    sig499,
    {
      label: "④ 法人+融資+借券",
      value: inst.label,
      detail: `外資${inst.hasForeign ? "✓" : "✗"} 投信${inst.hasTrust ? "✓" : "✗"} 籌碼集中${inst.hasChipset ? "✓" : "✗"} 空頭加碼${inst.hasShortAdd ? "⚠️" : "無"}`,
      score: inst.score,
      bullish: inst.score > 1 ? true : inst.score < 0 ? false : null,
      supported: true,
    },
    {
      label: "⑤ 領頭股明確性",
      value: leader.label,
      detail: `板塊第${leader.rankInSector}/${leader.totalInSector}名（前${100 - Math.round(leader.rankPct)}%）`,
      score: leader.score,
      bullish: leader.isLeader,
      supported: true,
    },
    {
      label: "⑥ KDJ 指標",
      value: kdj.label,
      detail: `K=${kdj.K.toFixed(1)} D=${kdj.D.toFixed(1)} J=${kdj.J.toFixed(1)}${
        kdj.isPrecise    ? " · 精准度：標準" :
        kdj.isAcceptable ? " · 精准度：良好" :
        ` · ⚠️ 僅${bars.length}棒（需≥20棒），參考用`
      }`,
      score: kdj.score,
      bullish: kdj.score > 0 ? true : kdj.score < 0 ? false : null,
      supported: bars.length >= 9,
    },
    {
      label: "⑦ 媒體/散戶熱度",
      value: media.label,
      detail: `漲跌${stock.change_pct != null ? (stock.change_pct > 0 ? "+" : "") + stock.change_pct.toFixed(2) + "%" : "N/A"} · 訊號數${(stock.triggered ?? []).length} · 評分${(stock.score ?? 0).toFixed(1)}（Proxy指標）`,
      // score 用 media.score 本身：冷門=+2=綠燈，過熱=-3=紅燈（原 *-1 為 regime 公式用，顯示應為正向=好）
      score: media.score,
      bullish: media.heatLevel === "冷門" ? true : media.heatLevel === "過熱" ? false : null,
      supported: true,
    },
  ];

  return {
    stockId:    stock.id,
    stockName:  stock.name_zh,
    regime,
    phase,
    action,
    confidence,
    signals,
    regimeScores: { institutional, whale, retail },
  };
}

// ────────────────────────────────────────────────────────────────────────────
// 板塊盤性
// ────────────────────────────────────────────────────────────────────────────

export function classifySectorRegime(
  sector: SectorData,
  sectorId: string,
): SectorRegimeResult {
  const stocks      = sector.stocks ?? [];
  const signals     = sector.signals ?? [];      // [燈1,燈2,燈3,燈4,燈5,燈6,燈7]
  const lamp2       = signals[1] ?? 0;           // 燈2 法人
  const lamp6       = signals[5] ?? 0;           // 燈6 籌碼
  const rsMomentum  = sector.rs_momentum ?? 0;
  const cycleStage  = sector.cycle_stage;
  const homogeneity = sector.homogeneity ?? 0;

  // 法人強度
  let institutionalStrength: SectorRegimeResult["institutionalStrength"];
  if (lamp2 >= 1 && lamp6 >= 1) institutionalStrength = "強";
  else if (lamp2 >= 0.5 || lamp6 >= 1) institutionalStrength = "中";
  else if (lamp2 > 0) institutionalStrength = "弱";
  else institutionalStrength = "無";

  // 板塊盤性
  let regime: RegimeType;
  let confidence: number;
  if (lamp2 >= 1 && lamp6 >= 1 && rsMomentum > 0) {
    regime = "法人盤"; confidence = 80;
  } else if (lamp2 >= 0.5 || lamp6 >= 0.5) {
    regime = "法人盤"; confidence = 55;
  } else if (homogeneity > 0.7 && sector.level === "強烈關注") {
    // 高同質性 + 強烈關注 但無法人 = 大戶/主題炒作
    regime = "大戶盤"; confidence = 60;
  } else if (sector.level === "忽略" && stocks.length > 0) {
    regime = "散戶情緒盤"; confidence = 40;
  } else {
    regime = "混合盤"; confidence = 35;
  }

  // 板塊週期 → 階段
  let phase: PhaseType;
  switch (cycleStage) {
    case "萌芽期": phase = "建倉期"; break;
    case "確認期": phase = "拉升期"; break;
    case "加速期": phase = "拉升期"; break;
    case "過熱期": phase = "派發期"; break;
    default:       phase = "整理期"; break;
  }

  // 計算板塊內 Top 3 個股盤性
  const topStocks = stocks.slice(0, 3).map(s => classifyStockRegime(s, sector, stocks));

  return {
    sectorId,
    sectorName: sector.name_zh,
    sectorLevel: sector.level,
    regime,
    phase,
    confidence,
    institutionalStrength,
    stockCount: stocks.length,
    topStocks,
  };
}

// ────────────────────────────────────────────────────────────────────────────
// 大盤盤性
// ────────────────────────────────────────────────────────────────────────────

export function classifyMarketRegime(
  marketState: { state: string; taiex_vs_200ma_pct?: number; momentum_20d_pct?: number } | null | undefined,
  macro: { warning?: boolean; sox_trend?: string; bond_trend?: string } | null | undefined,
  hotSectorCount: number,
): MarketRegimeResult {
  const state      = marketState?.state ?? "unknown";
  const momentum   = marketState?.momentum_20d_pct ?? 0;
  const macroOk    = !macro?.warning;
  const soxBull    = macro?.sox_trend === "up";

  const signals: string[] = [];
  let regimeScore = 0;

  if (state === "bull")        { signals.push("📈 TAIEX 牛市（200MA上方）"); regimeScore += 3; }
  else if (state === "bear")   { signals.push("📉 TAIEX 熊市（200MA下方）"); regimeScore -= 3; }
  else                         { signals.push("📊 TAIEX 震盪盤整"); }

  if (momentum > 3)  { signals.push(`🚀 近20日強勢 +${momentum.toFixed(1)}%`); regimeScore += 1; }
  else if (momentum < -3) { signals.push(`⚠️ 近20日疲弱 ${momentum.toFixed(1)}%`); regimeScore -= 1; }

  if (macroOk)  { signals.push("✅ 宏觀正向（FRED+SOXX）"); regimeScore += 1; }
  else           { signals.push("⚠️ 宏觀警示"); regimeScore -= 1; }

  if (soxBull)  { signals.push("💻 SOXX 半導體上漲"); regimeScore += 1; }

  if (hotSectorCount >= 5)  { signals.push(`🔥 ${hotSectorCount}個板塊強烈關注`); regimeScore += 1; }
  else if (hotSectorCount === 0) { signals.push("❄️ 無板塊強烈關注"); regimeScore -= 1; }

  let regime: RegimeType;
  let phase: PhaseType;
  let description: string;
  let confidence: number;

  if (regimeScore >= 4) {
    regime = "法人盤"; phase = hotSectorCount >= 5 ? "拉升期" : "建倉期";
    description = "大盤處於多頭格局，法人資金主導，板塊輪動明確";
    confidence = Math.min(90, 60 + regimeScore * 5);
  } else if (regimeScore >= 1) {
    regime = "法人盤"; phase = "整理期";
    description = "大盤偏多但動能不強，法人選股而非全面佈局";
    confidence = Math.min(75, 50 + regimeScore * 5);
  } else if (regimeScore <= -3) {
    regime = "散戶情緒盤"; phase = "派發期";
    description = "大盤走弱，主力撤退，散戶情緒主導，高風險";
    confidence = 70;
  } else {
    regime = "混合盤"; phase = "整理期";
    description = "大盤方向不明，法人觀望，等待明確觸發因子";
    confidence = 40;
  }

  return { regime, phase, confidence, description, signals };
}
