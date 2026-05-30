"""
regime_factor_bakeoff.py — 盤性診斷 regime.ts 手訂權重的回測驗證核心（純函式）

把 regime.ts 各「型態判斷」當獨立選股因子，point-in-time、持有1季、贏 TAIEX，
與 baseline 比 alpha → 校準手訂分數（讓數據說話，非拍腦袋）。

涵蓋 regime.ts 可向量化的型態：
  連續漲停（K棒判「大戶攻勢」score −2）
  長上影線（K棒判「派發」score −3，高位時）
  KDJ 低位金叉（判「主力啟動」score +2）
  KDJ 高位死叉（判「轉弱」score −2）

媒體熱度/499張/領頭股需 triggered/排名（依賴當期評分），不易歷史重建 → 不在此驗。
向量化（whole-frame），由 scripts/backtest_regime_factors.py 注入 OHLCV。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def consecutive_limit_up(open_df: pd.DataFrame, close_df: pd.DataFrame,
                         n: int = 2, thr: float = 0.095) -> pd.DataFrame:
    """連續 n 日收漲幅 ≥ thr（漲停代理）。regime.ts: 連2漲停判大戶盤 score −2。"""
    up = ((close_df - open_df) / open_df.replace(0, np.nan)) >= thr
    return up.rolling(n).min().astype(bool) if n == 1 else (up.rolling(n).sum() >= n)


def long_upper_shadow_highpos(
    open_df: pd.DataFrame, high_df: pd.DataFrame, low_df: pd.DataFrame,
    close_df: pd.DataFrame, *, count_days: int = 7, min_count: int = 2,
    rise_thr: float = 5.0,
) -> pd.DataFrame:
    """
    高位長上影線（regime.ts 判「高位派發」score −3）：
    近 count_days 內 ≥min_count 根長上影線（上影 > 實體1.5倍）且近5日漲幅 > rise_thr%。
    """
    body = (close_df - open_df).abs()
    body_top = close_df.where(close_df > open_df, open_df)  # element-wise max(close, open)
    upper = high_df - body_top
    is_long = (body > 0) & (upper > body * 1.5)
    cnt = is_long.rolling(count_days).sum()
    px = close_df.ffill()
    rise5 = (px / px.shift(5) - 1) * 100
    return (cnt >= min_count) & (rise5 > rise_thr)


def _kdj_kd(close_df: pd.DataFrame, high_df: pd.DataFrame, low_df: pd.DataFrame,
            n: int = 9):
    """向量化 KDJ 的 K、D（對全 frame）。回傳 (K_df, D_df)。"""
    ll = low_df.rolling(n).min()
    hh = high_df.rolling(n).max()
    rsv = (close_df - ll) / (hh - ll).replace(0, np.nan) * 100
    rsv = rsv.fillna(50)
    # Wilder 平滑：K = 2/3 K_prev + 1/3 RSV；用 ewm(alpha=1/3) 近似
    K = rsv.ewm(alpha=1/3, adjust=False).mean()
    D = K.ewm(alpha=1/3, adjust=False).mean()
    return K, D


def kdj_low_golden_cross(close_df, high_df, low_df, n: int = 9, k_max: float = 30) -> pd.DataFrame:
    """低位金叉（K>D 且 K<k_max）。regime.ts 判「主力啟動」score +2。"""
    K, D = _kdj_kd(close_df, high_df, low_df, n)
    return (K > D) & (K < k_max)


def kdj_high_death_cross(close_df, high_df, low_df, n: int = 9, k_min: float = 70) -> pd.DataFrame:
    """高位死叉（K<D 且 K>k_min）。regime.ts 判「轉弱」score −2。"""
    K, D = _kdj_kd(close_df, high_df, low_df, n)
    return (K < D) & (K > k_min)


__all__ = [
    "consecutive_limit_up", "long_upper_shadow_highpos",
    "kdj_low_golden_cross", "kdj_high_death_cross",
]
