"""
trump_nlp.py — Trump 貼文 / 新聞 NLP 情感分析引擎

輸入：任意純文字（貼文、新聞標題、全文）
輸出：{
    "sentiment":  {"compound": float, "label": str},   # VADER 複合分數 + 標籤
    "keywords":   list[str],                            # 命中的關鍵詞
    "impacts":    {sector_id: float},                   # -1.0 ~ +1.0 板塊衝擊係數
    "confidence": float,                                # 0.0-1.0 可信度
    "summary":    str,                                  # 人類可讀摘要
}

依賴：
  - vaderSentiment（pip install vaderSentiment）
  若未安裝則退化為僅關鍵詞模式，sentiment.compound = 0.0

NLP vs tariff.py 語義差異：
  NLP  捕捉「短期市場恐慌 / 即時情緒反應」（tariff→foundry 短期賣壓 -0.7）
  tariff.py 捕捉「長期結構受益」（台積電替代效應 +0.60）
  兩者方向相反是刻意設計，composite.py 50:50 加權後反映真實複雜性
"""

from __future__ import annotations

from typing import NamedTuple

from src.analyzers.keywords import (
    KEYWORD_MATRIX,
    PHRASE_MATRIX,
    NOISE_WORDS,
    TRUMP_VADER_LEXICON,
)

# ── 可選：VADER 情感分析 ─────────────────────────────────────────────────────
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
    _vader = SentimentIntensityAnalyzer()
    # 注入川普語境自訂詞彙（覆蓋預設情緒分數）
    _vader.lexicon.update(TRUMP_VADER_LEXICON)
    VADER_AVAILABLE = True
except ImportError:
    _vader = None
    VADER_AVAILABLE = False


# ── 標籤對應 ─────────────────────────────────────────────────────────────────
def _sentiment_label(compound: float) -> str:
    if compound >= 0.5:
        return "強烈利多"
    if compound >= 0.1:
        return "偏多"
    if compound <= -0.5:
        return "強烈利空"
    if compound <= -0.1:
        return "偏空"
    return "中性"


# ══════════════════════════════════════════════════════════════════════════════
# 主函式
# ══════════════════════════════════════════════════════════════════════════════

def analyze_post(text: str) -> dict:
    """
    分析單篇貼文或新聞文字。

    Returns
    -------
    {
      "sentiment":  {"compound": float, "label": str},
      "keywords":   list[str],
      "impacts":    {sector_id: int},
      "confidence": float,
      "summary":    str,
    }
    """
    if not text or not text.strip():
        return _empty_result()

    lower = text.lower()

    # ── 1. VADER 情感分數 ────────────────────────────────────────────────────
    if VADER_AVAILABLE and _vader is not None:
        scores = _vader.polarity_scores(text)
        compound: float = scores["compound"]
    else:
        compound = 0.0

    # ── 2. 關鍵詞匹配（PHRASE_MATRIX 優先，再處理 KEYWORD_MATRIX）─────────────
    matched_keywords: list[str] = []
    impact_accumulator: dict[str, float] = {}

    # 2a. 多詞組（較長的短語先匹配）
    for phrase, sector_impacts in PHRASE_MATRIX.items():
        if phrase in lower and sector_impacts:
            matched_keywords.append(phrase)
            for sector, signal in sector_impacts.items():
                impact_accumulator[sector] = impact_accumulator.get(sector, 0.0) + signal

    # 2b. 單詞關鍵詞（排除雜訊詞）
    for keyword, sector_impacts in KEYWORD_MATRIX.items():
        if keyword in NOISE_WORDS or not sector_impacts:
            continue
        if keyword in lower:
            matched_keywords.append(keyword)
            for sector, signal in sector_impacts.items():
                impact_accumulator[sector] = impact_accumulator.get(sector, 0.0) + signal

    # 去重（同一關鍵詞多次出現只計一次）
    matched_keywords = list(dict.fromkeys(matched_keywords))

    # clamp to ±1.0
    impacts: dict[str, float] = {
        s: round(max(-1.0, min(1.0, v)), 3)
        for s, v in impact_accumulator.items()
        if abs(v) >= 0.05
    }

    # ── 3. 可信度 = 有關鍵詞命中時才有意義 ─────────────────────────────────
    hit_count = len(matched_keywords)
    if hit_count == 0:
        confidence = 0.1
    elif hit_count <= 2:
        confidence = 0.5
    elif hit_count <= 5:
        confidence = 0.75
    else:
        confidence = 0.90

    # 若 VADER 分數強烈（|compound| > 0.5），上調可信度
    if abs(compound) >= 0.5 and hit_count > 0:
        confidence = min(1.0, confidence + 0.1)

    # ── 4. 人類可讀摘要 ──────────────────────────────────────────────────────
    label = _sentiment_label(compound)
    top_impact = sorted(impacts.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
    impact_str = ", ".join(f"{s}({'+' if v>0 else ''}{v:.2f})" for s, v in top_impact)
    summary = f"[{label}] 命中 {hit_count} 個關鍵詞；主要衝擊板塊：{impact_str or '無'}"

    return {
        "sentiment":  {"compound": round(compound, 4), "label": label},
        "keywords":   matched_keywords,
        "impacts":    impacts,
        "confidence": round(confidence, 2),
        "summary":    summary,
    }


def analyze_batch(posts: list[dict]) -> list[dict]:
    """
    批次分析一組貼文。
    每個 post 需含 "text" 欄位，其餘欄位原樣保留。
    """
    results = []
    for post in posts:
        text = post.get("text", "")
        analysis = analyze_post(text)
        results.append({**post, "nlp": analysis})
    return results


def aggregate_impacts(analyses: list[dict], decay: float = 0.8) -> dict[str, float]:
    """
    將多篇分析結果聚合成板塊加權分數。
    較新的貼文以 decay 因子衰減舊貼文的影響力。

    Parameters
    ----------
    analyses : list of analyze_post() 結果，依時間由新到舊排列
    decay    : 每篇遞減係數（default 0.8）

    Returns
    -------
    {sector_id: weighted_score}  score 範圍 -2.0 ~ 2.0
    """
    accumulator: dict[str, float] = {}
    weight = 1.0
    for a in analyses:
        for sector, signal in a.get("impacts", {}).items():
            accumulator[sector] = accumulator.get(sector, 0.0) + signal * weight
        weight *= decay

    # normalize to ±2
    if accumulator:
        max_abs = max(abs(v) for v in accumulator.values())
        if max_abs > 2.0:
            factor = 2.0 / max_abs
            accumulator = {s: round(v * factor, 3) for s, v in accumulator.items()}

    return {s: round(v, 3) for s, v in accumulator.items()}


def _empty_result() -> dict:
    return {
        "sentiment":  {"compound": 0.0, "label": "中性"},
        "keywords":   [],
        "impacts":    {},
        "confidence": 0.0,
        "summary":    "無內容",
    }
