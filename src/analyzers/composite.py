"""
composite.py — Trump 訊號複合評分引擎

公式：
  composite_score(sector) =
      NLP_weight  * nlp_aggregated_signal(sector)   # 來自 trump_nlp.py
    + tariff_weight * tariff_impact(sector, scenario) # 來自 tariff.py

輸出（寫入 output/composite/latest.json）：
{
  "updated_at":    "ISO datetime",
  "scenario":      "25%",          # 關稅情境
  "nlp_weight":    0.5,
  "tariff_weight": 0.5,
  "scores": {
      sector_id: {
          "composite": float,      # -2.0 ~ +2.0
          "nlp":       float,
          "tariff":    float,
          "signal":    str,        # "強烈買入"|"買入"|"中性"|"賣出"|"強烈賣出"
      }
  },
  "top_buy":  [sector_id, ...],    # 前 5 受益板塊
  "top_sell": [sector_id, ...],    # 前 5 受害板塊
  "keyword_hits": [str, ...],      # 本次命中的關鍵詞
  "tariff_scenario": str,
  "signal_strength": float,        # 整體訊號強度 0.0-1.0
  "source_count": int,             # 分析的貼文數
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.analyzers.trump_nlp import analyze_batch, aggregate_impacts
from src.analyzers.tariff import get_tariff_impact, TariffScenario

# 輸出目錄
_OUTPUT_DIR = Path(__file__).parents[2] / "output" / "composite"

# 預設權重
DEFAULT_NLP_WEIGHT: float = 0.5
DEFAULT_TARIFF_WEIGHT: float = 0.5


def _signal_label(score: float) -> str:
    if score >= 1.2:
        return "強烈買入"
    if score >= 0.4:
        return "買入"
    if score <= -1.2:
        return "強烈賣出"
    if score <= -0.4:
        return "賣出"
    return "中性"


def _signal_strength(scores: dict[str, dict]) -> float:
    """整體訊號強度 = 所有板塊複合分的 abs 平均值，歸一化到 0-1。"""
    vals = [abs(v["composite"]) for v in scores.values()]
    if not vals:
        return 0.0
    return round(min(1.0, sum(vals) / len(vals) / 2.0), 3)


def run_composite_analysis(
    posts: list[dict],
    scenario: TariffScenario = "25%",
    nlp_weight: float = DEFAULT_NLP_WEIGHT,
    tariff_weight: float = DEFAULT_TARIFF_WEIGHT,
    write_output: bool = True,
) -> dict[str, Any]:
    """
    Parameters
    ----------
    posts       : 貼文列表，每個 dict 至少含 "text" 欄位
    scenario    : 關稅情境 "10%" / "25%" / "60%"
    nlp_weight  : NLP 信號權重（0-1）
    tariff_weight: 關稅矩陣權重（0-1）
    write_output: 是否寫入 output/composite/latest.json

    Returns
    -------
    composite result dict（同 latest.json 格式）
    """
    # ── 1. NLP 批次分析 ──────────────────────────────────────────────────────
    analyses = analyze_batch(posts)
    nlp_signals = aggregate_impacts([a["nlp"] for a in analyses])

    # 收集關鍵詞 (去重保序)
    all_keywords: list[str] = []
    seen: set[str] = set()
    for a in analyses:
        for kw in a["nlp"].get("keywords", []):
            if kw not in seen:
                all_keywords.append(kw)
                seen.add(kw)

    # ── 2. 關稅矩陣 ──────────────────────────────────────────────────────────
    tariff_signals = get_tariff_impact(scenario)

    # ── 3. 複合評分：取全部板塊的聯集 ───────────────────────────────────────
    all_sectors = set(nlp_signals) | set(tariff_signals)
    scores: dict[str, dict] = {}

    for sector in sorted(all_sectors):
        nlp_v = nlp_signals.get(sector, 0.0)
        tar_v = tariff_signals.get(sector, 0.0)
        composite = round(nlp_weight * nlp_v + tariff_weight * tar_v, 4)
        scores[sector] = {
            "composite": composite,
            "nlp":       round(nlp_v, 4),
            "tariff":    round(tar_v, 4),
            "signal":    _signal_label(composite),
        }

    # ── 4. 排行榜 ────────────────────────────────────────────────────────────
    ranked = sorted(scores.items(), key=lambda x: x[1]["composite"], reverse=True)
    top_buy  = [s for s, v in ranked if v["composite"] > 0][:5]
    top_sell = [s for s, v in ranked[::-1] if v["composite"] < 0][:5]

    result: dict[str, Any] = {
        "updated_at":     datetime.now(timezone.utc).isoformat(),
        "scenario":       scenario,
        "nlp_weight":     nlp_weight,
        "tariff_weight":  tariff_weight,
        "scores":         scores,
        "top_buy":        top_buy,
        "top_sell":       top_sell,
        "keyword_hits":   all_keywords,
        "tariff_scenario": scenario,
        "signal_strength": _signal_strength(scores),
        "source_count":   len(posts),
    }

    # ── 5. 寫入 JSON ─────────────────────────────────────────────────────────
    if write_output:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _OUTPUT_DIR / "latest.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def load_latest() -> dict[str, Any] | None:
    """讀取上次寫入的 composite/latest.json，若不存在回傳 None。"""
    path = _OUTPUT_DIR / "latest.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
