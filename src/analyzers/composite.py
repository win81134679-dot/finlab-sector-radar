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


# ══════════════════════════════════════════════════════════════════════════
# 敏感度分析 / 格線搜尋
# ══════════════════════════════════════════════════════════════════════════

# 預設權重組合（涵蓋「NLP 主導」到「關稅主導」）
WEIGHT_PRESETS: list[tuple[str, float, float]] = [
    ("NLP 主導 (9:1)",  0.9, 0.1),
    ("NLP 偏重 (7:3)",  0.7, 0.3),
    ("均衡 (5:5)",      0.5, 0.5),
    ("關稅偏重 (3:7)",  0.3, 0.7),
    ("關稅主導 (1:9)",  0.1, 0.9),
]


def run_sensitivity_analysis(
    posts: list[dict],
    scenario: TariffScenario = "25%",
    write_output: bool = True,
) -> dict[str, Any]:
    """
    以 5 組預設權重各跑一次 composite，輸出:
    {
      "updated_at": str,
      "scenario":   str,
      "presets": [
        {
          "label":         "均衡 (5:5)",
          "nlp_weight":    0.5,
          "tariff_weight": 0.5,
          "top_buy":       [...],
          "top_sell":      [...],
          "signal_strength": float,
          "scores":        {sector: composite_float},  # 只保留 composite 值，縮減體積
        }, ...
      ],
      "stability": {          # 各板塊在不同權重下的排名穩定度
        sector_id: {
          "rank_std":      float,   # 排名標準差（越小越穩定）
          "always_buy":    bool,
          "always_sell":   bool,
        }
      },
      "note": str,            # 說明此分析的學術侷限性
    }
    """
    # 先算一次 NLP 信號（所有 preset 共用）
    analyses = analyze_batch(posts)
    nlp_signals = aggregate_impacts([a["nlp"] for a in analyses])
    tariff_signals = get_tariff_impact(scenario)

    all_sectors = sorted(set(nlp_signals) | set(tariff_signals))
    preset_results = []

    # 各 preset 的板塊排名（用於穩定度計算）
    rank_matrix: dict[str, list[int]] = {s: [] for s in all_sectors}

    for label, nw, tw in WEIGHT_PRESETS:
        scores_this: dict[str, float] = {}
        for sector in all_sectors:
            nlp_v = nlp_signals.get(sector, 0.0)
            tar_v = tariff_signals.get(sector, 0.0)
            scores_this[sector] = round(nw * nlp_v + tw * tar_v, 4)

        ranked = sorted(scores_this.items(), key=lambda x: -x[1])
        for rank, (sid, _) in enumerate(ranked):
            rank_matrix[sid].append(rank + 1)

        # 前五
        top_b = [s for s, v in ranked if v > 0][:5]
        top_s = [s for s, v in ranked[::-1] if v < 0][:5]

        # 評分詳細（供前端切換用）
        full_scores = {
            s: {
                "composite": v,
                "signal": _signal_label(v),
            }
            for s, v in scores_this.items()
        }

        strength_vals = [abs(v) for v in scores_this.values()]
        preset_results.append({
            "label":         label,
            "nlp_weight":    nw,
            "tariff_weight": tw,
            "top_buy":       top_b,
            "top_sell":      top_s,
            "signal_strength": round(min(1.0, sum(strength_vals) / len(strength_vals) / 2.0), 3) if strength_vals else 0.0,
            "scores":        full_scores,
        })

    # ── 穩定度計算 ─────────────────────────────────────────────────────────
    import statistics as _stats

    n_presets = len(WEIGHT_PRESETS)
    stability: dict[str, dict] = {}
    for sid in all_sectors:
        ranks = rank_matrix[sid]
        std = round(_stats.stdev(ranks), 2) if len(ranks) > 1 else 0.0
        # 在所有 preset 下都在前 1/3 → always_buy
        threshold = len(all_sectors) // 3
        stability[sid] = {
            "rank_std":   std,
            "always_buy":  all(r <= threshold for r in ranks),
            "always_sell": all(r > len(all_sectors) - threshold for r in ranks),
        }

    result: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "scenario":   scenario,
        "presets":    preset_results,
        "stability":  stability,
        "note": (
            "此敏感度分析以 5 組 NLP:關稅 權重比例各跑一次複合評分，"
            "觀察板塊排名的穩定性。rank_std 越低代表此板塊不論權重如何設定，"
            "排名都穩定（結論可信度較高）。always_buy/always_sell 代表在所有"
            "5 種權重假設下均被列為受益/受害板塊。"
            "注意：目前 NLP 訊號來自靜態關鍵詞規則（非訓練模型），"
            "50:50 預設為工程設計值，非從歷史資料最佳化得出。"
        ),
    }

    if write_output:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_OUTPUT_DIR / "sensitivity.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result
