"""
trump_nlp.py — Trump 貼文 / 新聞 NLP 情感分析引擎

輸入：任意純文字（貼文、新聞標題、全文）
輸出：{
    "sentiment":  {"compound": float, "label": str},   # VADER 複合分數 + 標籤
    "keywords":   list[str],                            # 命中的關鍵詞
    "impacts":    {sector_id: int},                     # +2/+1/0/-1/-2 多空信號
    "confidence": float,                                # 0.0-1.0 可信度
    "summary":    str,                                  # 人類可讀摘要
}

依賴：
  - vaderSentiment（pip install vaderSentiment）
  若未安裝則退化為僅關鍵詞模式，sentiment.compound = 0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

# ── 可選：VADER 情感分析 ─────────────────────────────────────────────────────
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
    _vader = SentimentIntensityAnalyzer()
    VADER_AVAILABLE = True
except ImportError:
    _vader = None
    VADER_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# 關鍵詞 → 板塊衝擊表
# key: 關鍵詞（小寫，regex 支援）
# val: {sector_id: signal}  signal: +2=強買, +1=買, -1=賣, -2=強賣
# ══════════════════════════════════════════════════════════════════════════════
_KEYWORD_IMPACTS: dict[str, dict[str, int]] = {
    # AI / 半導體 扶植
    r"\bai\b":                       {"ai_server": +2, "foundry": +1, "ic_design": +1},
    r"artificial intelligence":      {"ai_server": +2, "foundry": +1},
    r"semiconductor":                {"foundry": +2, "packaging": +1, "ic_design": -1},
    r"chip(s)?":                     {"foundry": +2, "packaging": +1},
    r"nvidia":                       {"ai_server": +2, "foundry": +1},
    r"tsmc":                         {"foundry": +2, "packaging": +1},

    # 防衛 / 軍事
    r"defense|military|pentagon":    {"defense": +2, "foundry": +1},
    r"missile|weapon":               {"defense": +2},

    # 貿易戰 / 關稅
    r"tariff(s)?":                   {
        "foundry": +1, "ic_design": -2, "shipping": -2,
        "display": -2, "ev_supply": -1, "textile": -1,
    },
    r"trade war":                    {
        "ic_design": -2, "shipping": -2, "display": -1, "ev_supply": -1,
    },
    r"import tax":                   {"shipping": -2, "ic_design": -1},
    r"sanction(s)?":                 {"ic_design": -2, "foundry": +1},

    # 中國相關（負面）
    r"china|chinese":                {
        "ic_design": -1, "shipping": -1, "display": -1, "ev_supply": -1,
    },
    r"ban(ned)? china":              {"ic_design": -2, "shipping": -2},
    r"decouple":                     {
        "ic_design": -2, "foundry": +1, "shipping": -1,
    },

    # 貿易協定（正面）
    r"deal|agreement|bilateral":     {"shipping": +1, "ic_design": +1},
    r"trade deal":                   {"shipping": +2, "ic_design": +1, "display": +1},

    # 能源
    r"oil|petroleum|lng":            {"petrochemical": +1, "shipping": +1},
    r"drill|energy independent":     {"petrochemical": +2},
    r"solar|clean energy|renewable": {"solar": +1, "wind_energy": +1},
    r"electric vehicle|ev":          {"ev_supply": +1, "power_semi": +1},

    # 基建 / 製造回流
    r"manufactur(e|ing) (in )?america": {
        "foundry": +1, "semiconductor_equip": +1, "robotics": +1,
    },
    r"reshoring|onshoring":          {
        "foundry": +1, "packaging": +1, "robotics": +1,
    },
    r"infrastructure":               {
        "power_infra": +2, "construction": +1, "steel": +1,
    },

    # 科技反托拉斯 / 管制（負面）
    r"antitrust|break up (big )?tech": {"software_saas": -1, "ecommerce": -1},
    r"regulate tech":                {"software_saas": -1},

    # 美元 / 金融
    r"dollar|usd":                   {"banking": 0, "financial_holding": 0},
    r"interest rate|fed":            {
        "banking": -1, "financial_holding": -1, "power_semi": +1,
    },
    r"inflation":                    {
        "banking": -1, "petrochemical": +1,
    },

    # 航運
    r"port|shipping|maritime|freight": {"shipping": -1},
    r"panama|taiwan strait|south china sea": {"shipping": -2, "foundry": +2},

    # 加密貨幣
    r"bitcoin|btc|crypto":           {"gaming": +1},
    r"blockchain":                   {"software_saas": +1},
}


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

    # ── 2. 關鍵詞匹配 ────────────────────────────────────────────────────────
    matched_keywords: list[str] = []
    impact_accumulator: dict[str, int] = {}

    for pattern, sector_impacts in _KEYWORD_IMPACTS.items():
        if re.search(pattern, lower):
            matched_keywords.append(pattern.replace("\\b", "").replace("(s)?", "s").replace("(ed)?", "ed"))
            for sector, signal in sector_impacts.items():
                impact_accumulator[sector] = impact_accumulator.get(sector, 0) + signal

    # clamp to ±2
    impacts = {s: max(-2, min(2, v)) for s, v in impact_accumulator.items() if v != 0}

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
    impact_str = ", ".join(f"{s}({'+' if v>0 else ''}{v})" for s, v in top_impact)
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
