"""
chip_factor_bakeoff.py — 法人籌碼因子 bakeoff 核心（純函式，可單元測試）

目的：把 P1–P6 每個法人籌碼假說當**獨立選股因子**，point-in-time、持有1季、
贏 TAIEX 回測，**讓數據選贏家**（不靠直覺）。贏過 baseline(全股贏大盤率) 才算有 alpha。

因子（每個產出「個股 × 日期」的布林訊號矩陣，True=該日該股觸發）：
  F1 外資持股比率上升趨勢（P6）：持股比率 > N 日前（方向性上升）
  F2 外資連買 ≥10 日（P1）vs F2b 外資連買 ≥3 日（對照）
  F3 投信連買 ≥3 日（P2/P3）
  F4 自營商(自行買賣)淨買（P1：預期 ≤50%，反指標/雜訊驗證）

評估：每月底取訊號為 True 的股，算未來 HOLD 日報酬 > 同期 TAIEX 的比例。
與 baseline（全部有效股的同條件贏大盤率）比較 → 因子 alpha = 命中率 − baseline。

純函式，由 scripts/backtest_chip_factors.py 注入真資料。
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def consecutive_buy_signal(net_df: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    連續 n 日買超（>0）的布林矩陣（個股 × 日期）。
    用 rolling min > 0：近 n 日最小值 > 0 ⇔ n 日全買超。
    """
    return net_df.rolling(n).min() > 0


def holding_uptrend_signal(holding_df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    持股比率上升趨勢（P6）：今值 > lookback 日前值（方向性上升）。
    holding_df 為日頻持股比率（%），已無前視問題。
    """
    return holding_df > holding_df.shift(lookback)


def net_buy_signal(net_df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """近 window 日累積淨買超 > 0（自營雜訊驗證用）。"""
    return net_df.rolling(window).sum() > 0


def forward_beat_matrix(
    price_df: pd.DataFrame,
    benchmark: pd.Series,
    hold: int,
) -> pd.DataFrame:
    """
    個股未來 hold 日報酬 > 同期大盤 的布林矩陣（個股 × 日期，向量化）。
    未來不足 hold 日 → NaN（後續 .where 排除）。
    """
    pxf = price_df.ffill()
    fwd = pxf.shift(-hold) / pxf - 1
    b = benchmark.reindex(price_df.index, method="ffill")
    bench_fwd = b.shift(-hold) / b - 1
    beat = fwd.sub(bench_fwd, axis=0) > 0
    # 未來不足的位置設 NaN（fwd 為 NaN 處）
    return beat.where(fwd.notna())


def evaluate_factor(
    signal_me: pd.DataFrame,        # 月底 × 個股 布林訊號
    beat_me: pd.DataFrame,          # 月底 × 個股 贏大盤布林（NaN=資料不足）
) -> Dict[str, float]:
    """
    因子命中率 = 在訊號 True 的 (月,股) 格子中，贏大盤的比例。
    回傳 {hit_rate, n, base_rate, alpha}。base_rate=全部有效格子贏大盤率。
    """
    # 對齊
    common_cols = signal_me.columns.intersection(beat_me.columns)
    sig = signal_me[common_cols]
    beat = beat_me[common_cols]

    valid = beat.notna()
    # 因子格子：訊號 True 且 beat 非 NaN
    fac_mask = sig.fillna(False) & valid
    n = int(fac_mask.values.sum())
    hits = int((beat.where(fac_mask) == True).values.sum())  # noqa: E712
    hit_rate = hits / n if n else 0.0

    base_n = int(valid.values.sum())
    base_hits = int((beat.where(valid) == True).values.sum())  # noqa: E712
    base_rate = base_hits / base_n if base_n else 0.0

    return {
        "hit_rate": round(hit_rate, 4),
        "n": n,
        "base_rate": round(base_rate, 4),
        "alpha": round(hit_rate - base_rate, 4),
    }


def reindex_month_end(daily_bool: pd.DataFrame, month_ends: list) -> pd.DataFrame:
    """日頻布林 → 月底取樣（ffill）。"""
    return daily_bool.reindex(month_ends, method="ffill").fillna(False)


__all__ = [
    "consecutive_buy_signal", "holding_uptrend_signal", "net_buy_signal",
    "forward_beat_matrix", "evaluate_factor", "reindex_month_end",
]
