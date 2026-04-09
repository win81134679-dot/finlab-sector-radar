"""
correlation_gate.py — 報酬率相關性品質閘門

基於 Bhojraj, Lee & Oler (JAR 2003) 的 intra-industry return comovement 指標：
計算每檔個股 vs 板塊等權重均報酬率的 rolling Pearson 相關性。

用途：
  - 燈4/5（等權均價聚合）：corr ≥ 0.40 才納入計算
  - 燈1/2/3/6（百分比門檻）：corr ≥ 0.25 較寬門檻
  - 過濾異質股，提升板塊信號準確率
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── 預設參數 ─────────────────────────────────────────────
ROLLING_WINDOW = 120        # 交易日（≈半年）
THRESHOLD_STRICT = 0.40     # 燈4/5 等權均價聚合門檻
THRESHOLD_LOOSE = 0.25      # 燈1/2/3/6 百分比門檻
MIN_OBSERVATIONS = 60       # 最少需要的有效觀察天數


def compute_sector_correlations(
    price_df: pd.DataFrame,
    sector_stocks: Dict[str, List[str]],
    window: int = ROLLING_WINDOW,
) -> Dict[str, Dict[str, float]]:
    """
    計算每個板塊中每檔個股與板塊等權均報酬率的相關性。

    Parameters
    ----------
    price_df : pd.DataFrame
        收盤價 DataFrame（行=日期, 列=股票代碼）
    sector_stocks : dict
        {sector_id: [stock_id, ...]}
    window : int
        Rolling 相關性窗口天數

    Returns
    -------
    dict
        {sector_id: {stock_id: correlation_score, ...}, ...}
    """
    # 計算日報酬率
    returns = price_df.pct_change().iloc[1:]

    result: Dict[str, Dict[str, float]] = {}

    for sector_id, stocks in sector_stocks.items():
        avail = [s for s in stocks if s in returns.columns]
        if len(avail) < 3:
            # 成員太少，無統計意義，全部給 NaN
            result[sector_id] = {s: float("nan") for s in stocks}
            continue

        sector_returns = returns[avail]

        # 取最近 window 天
        if len(sector_returns) > window:
            sector_returns = sector_returns.iloc[-window:]

        # 板塊等權重均報酬率（排除自身的 leave-one-out 太慢，用全體近似）
        sector_avg = sector_returns.mean(axis=1)

        corr_scores: Dict[str, float] = {}
        for stock_id in avail:
            stock_ret = sector_returns[stock_id]
            # 只取兩邊都有值的日期
            valid = stock_ret.notna() & sector_avg.notna()
            n_valid = valid.sum()
            if n_valid < MIN_OBSERVATIONS:
                corr_scores[stock_id] = float("nan")
                continue
            corr = stock_ret[valid].corr(sector_avg[valid])
            corr_scores[stock_id] = round(float(corr), 4) if not np.isnan(corr) else float("nan")

        # 不在 columns 中的股票標記為 NaN
        for stock_id in stocks:
            if stock_id not in corr_scores:
                corr_scores[stock_id] = float("nan")

        result[sector_id] = corr_scores

    return result


def filter_stocks_by_correlation(
    sector_stocks: Dict[str, List[str]],
    correlations: Dict[str, Dict[str, float]],
    threshold: float = THRESHOLD_STRICT,
) -> Dict[str, List[str]]:
    """
    根據相關性門檻過濾板塊成員。

    Parameters
    ----------
    sector_stocks : dict
        原始 {sector_id: [stock_id, ...]}
    correlations : dict
        compute_sector_correlations() 的輸出
    threshold : float
        相關性門檻

    Returns
    -------
    dict
        過濾後的 {sector_id: [stock_id, ...]}
    """
    filtered: Dict[str, List[str]] = {}

    for sector_id, stocks in sector_stocks.items():
        corr_map = correlations.get(sector_id, {})
        passed = []
        for s in stocks:
            c = corr_map.get(s, float("nan"))
            # NaN 視為通過（資料不足時保守保留）
            if np.isnan(c) or c >= threshold:
                passed.append(s)
        # 至少保留 3 檔，否則退化到全部
        if len(passed) < 3:
            filtered[sector_id] = stocks
        else:
            filtered[sector_id] = passed

    return filtered


def compute_sector_homogeneity(
    correlations: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """
    計算每個板塊的同質性指數（平均 intra-sector correlation）。

    Returns
    -------
    dict
        {sector_id: homogeneity_score}
    """
    result: Dict[str, float] = {}
    for sector_id, corr_map in correlations.items():
        values = [v for v in corr_map.values() if not np.isnan(v)]
        if values:
            result[sector_id] = round(float(np.mean(values)), 4)
        else:
            result[sector_id] = float("nan")
    return result


def save_correlation_scores(
    correlations: Dict[str, Dict[str, float]],
    homogeneity: Dict[str, float],
    output_dir: Optional[Path] = None,
) -> None:
    """將相關性分數寫入 output/correlation_scores.json。"""
    from src import config
    output_dir = output_dir or config.OUTPUT_DIR

    payload = {
        "homogeneity": {k: v if not np.isnan(v) else None for k, v in homogeneity.items()},
        "stock_correlations": {
            sector_id: {
                stock_id: (score if not np.isnan(score) else None)
                for stock_id, score in scores.items()
            }
            for sector_id, scores in correlations.items()
        },
    }

    out_path = output_dir / "correlation_scores.json"
    tmp_path = output_dir / "correlation_scores.tmp.json"
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(out_path))
    logger.info("correlation_scores.json 已更新（%d 個板塊）", len(correlations))
