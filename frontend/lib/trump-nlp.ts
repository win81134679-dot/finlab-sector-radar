/**
 * trump-nlp.ts — 川普貼文 NLP 情感分析引擎（TypeScript 版）
 *
 * 架構：
 *   1. PHRASE_MATRIX 優先匹配（多詞組）
 *   2. KEYWORD_MATRIX 匹配（單詞 / 短語）
 *   3. TRUMP_CUSTOM_LEXICON 計算情緒複合分數（簡化 VADER 演算法）
 *
 * 輸出格式與 Python 版 trump_nlp.analyze_post() 保持相容
 */

import { PHRASE_MATRIX, KEYWORD_MATRIX, NOISE_WORDS, TRUMP_CUSTOM_LEXICON } from "@/lib/keywords";

// ── 情緒標籤 ─────────────────────────────────────────────────────────────────
function sentimentLabel(compound: number): string {
  if (compound >= 0.5)  return "強烈利多";
  if (compound >= 0.1)  return "偏多";
  if (compound <= -0.5) return "強烈利空";
  if (compound <= -0.1) return "偏空";
  return "中性";
}

/**
 * 簡化版 VADER 計算器
 * 使用 TRUMP_CUSTOM_LEXICON 為主詞彙，對文字中每個已知詞的情緒分數求和後正規化
 * 採用 VADER 的 sqrt(N) 正規化公式（Hutto & Gilbert, 2014）
 */
function calcCompound(text: string): number {
  const lower = text.toLowerCase();
  const tokens = lower.split(/\s+/);
  let sum = 0;

  for (const token of tokens) {
    const clean = token.replace(/[^a-z]/g, "");
    if (clean in TRUMP_CUSTOM_LEXICON) {
      sum += TRUMP_CUSTOM_LEXICON[clean];
    }
  }

  // 也掃多詞組（如 "witch hunt"）
  for (const [phrase, score] of Object.entries(TRUMP_CUSTOM_LEXICON)) {
    if (phrase.includes(" ") && lower.includes(phrase)) {
      sum += score;
    }
  }

  if (sum === 0) return 0;

  // VADER 正規化公式：compound = sum / sqrt(sum^2 + alpha)，alpha = 15
  const alpha = 15;
  const compound = sum / Math.sqrt(sum * sum + alpha);
  return Math.max(-1.0, Math.min(1.0, Math.round(compound * 10000) / 10000));
}


// ── 主分析函式 ────────────────────────────────────────────────────────────────

export interface TrumpNlpResult {
  sentiment:  { compound: number; label: string };
  keywords:   string[];
  impacts:    Record<string, number>;
  confidence: number;
  summary:    string;
}

export function analyzePost(text: string): TrumpNlpResult {
  if (!text.trim()) {
    return {
      sentiment:  { compound: 0, label: "中性" },
      keywords:   [],
      impacts:    {},
      confidence: 0,
      summary:    "無內容",
    };
  }

  const lower = text.toLowerCase();
  const compound = calcCompound(text);

  const matchedKeywords: string[] = [];
  const impactAcc: Record<string, number> = {};

  // 1. PHRASE_MATRIX 優先
  for (const [phrase, sectorImpacts] of Object.entries(PHRASE_MATRIX)) {
    if (lower.includes(phrase) && Object.keys(sectorImpacts).length > 0) {
      matchedKeywords.push(phrase);
      for (const [sector, signal] of Object.entries(sectorImpacts)) {
        impactAcc[sector] = (impactAcc[sector] ?? 0) + signal;
      }
    }
  }

  // 2. KEYWORD_MATRIX
  for (const [keyword, sectorImpacts] of Object.entries(KEYWORD_MATRIX)) {
    if (NOISE_WORDS.has(keyword) || Object.keys(sectorImpacts).length === 0) continue;
    if (lower.includes(keyword)) {
      matchedKeywords.push(keyword);
      for (const [sector, signal] of Object.entries(sectorImpacts)) {
        impactAcc[sector] = (impactAcc[sector] ?? 0) + signal;
      }
    }
  }

  // 去重 + clamp ±1.0
  const uniqueKeywords = [...new Set(matchedKeywords)];
  const impacts: Record<string, number> = {};
  for (const [sector, v] of Object.entries(impactAcc)) {
    const clamped = Math.max(-1.0, Math.min(1.0, v));
    if (Math.abs(clamped) >= 0.05) {
      impacts[sector] = Math.round(clamped * 1000) / 1000;
    }
  }

  // 可信度
  const hitCount = uniqueKeywords.length;
  let confidence =
    hitCount === 0 ? 0.1 :
    hitCount <= 2  ? 0.5 :
    hitCount <= 5  ? 0.75 : 0.90;
  if (Math.abs(compound) >= 0.5 && hitCount > 0) {
    confidence = Math.min(1.0, confidence + 0.1);
  }

  const label = sentimentLabel(compound);
  const topImpacts = Object.entries(impacts)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 3);
  const impactStr = topImpacts.length > 0
    ? topImpacts.map(([s, v]) => `${s}(${v > 0 ? "+" : ""}${v.toFixed(2)})`).join("、")
    : "無";
  const summary = `[${label}] 命中 ${hitCount} 個關鍵詞；主要衝擊板塊：${impactStr}`;

  return {
    sentiment:  { compound: Math.round(compound * 10000) / 10000, label },
    keywords:   uniqueKeywords,
    impacts,
    confidence: Math.round(confidence * 100) / 100,
    summary,
  };
}


/**
 * 批次分析並聚合多篇貼文的板塊影響
 * 較新貼文以 decay 因子衰減舊的（預設 0.85）
 */
export function aggregateImpacts(
  results: TrumpNlpResult[],
  decay = 0.85,
): Record<string, number> {
  const acc: Record<string, number> = {};
  let weight = 1.0;

  for (const result of results) {
    for (const [sector, signal] of Object.entries(result.impacts)) {
      acc[sector] = (acc[sector] ?? 0) + signal * weight;
    }
    weight *= decay;
  }

  // normalize to ±1.0
  const maxAbs = Math.max(0, ...Object.values(acc).map(Math.abs));
  if (maxAbs > 1.0) {
    const factor = 1.0 / maxAbs;
    for (const sector in acc) {
      acc[sector] = Math.round(acc[sector] * factor * 1000) / 1000;
    }
  }

  return acc;
}
