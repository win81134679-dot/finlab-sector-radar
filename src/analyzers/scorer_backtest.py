"""
scorer_backtest.py — 完整評分卡的 point-in-time 歷史回測核心（無前視偏誤）

回答：「七燈+基本面+技術+輪動加分」選出的個股，持有 1 季是否贏過大盤？
      且輪動加分能否把命中率從動能代理的 ~44% 拉高？

⚠️ 這是回測**專用複製品**，非正式 stock_scorer（正式版需逐燈 raw_results，
   逐月重跑 7 燈成本過高）。本複製品涵蓋評分卡主要可向量化維度：
     基本面：EPS YoY ≥25%(+2) / ROE ≥15%(+1) / PE < 板塊中位(+1)
     技術面：價 > MA60(+1) / 0<dist_MA60≤10%(+0.5)
     相對強度：板塊內 60 日報酬 rank > 70%(+1)
     輪動加分：板塊動能轉強(+0.5) / 板塊法人合力進駐(+0.5)（上限 +1）

**避免前視偏誤的關鍵**：所有 fundamental_features 必須先 `.index_str_to_date()`
（FinLab 把財報季 index 轉成「真實揭露日」），再 `.loc[:asof]`。
財報季 index（2020-Q1）若直接對齊日期會用到 5 月才公布的資料 = look-ahead。

純函式（接收已對齊的 DataFrame），由 scripts/backtest_full_scorer.py 注入真資料。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

_EPS_YOY_T = 25.0
_ROE_MIN = 15.0
_DIST_MAX = 10.0
_RS_RANK_MIN = 70.0
_MA_LONG = 60
_MOM_LOOKBACK = 60
_CHIP_WINDOW = 20


def _asof_latest(df: Optional[pd.DataFrame], sid: str, asof: pd.Timestamp) -> Optional[float]:
    """取個股在 asof 日（含）之前最後一筆非 NaN 值。df 須已是日期 index（揭露日對齊）。"""
    if df is None or sid not in df.columns:
        return None
    s = df[sid]
    s = s.loc[s.index <= asof].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def score_stock_asof(
    sid: str,
    sector_stocks: List[str],
    asof: pd.Timestamp,
    *,
    price_df: pd.DataFrame,
    eps_df: Optional[pd.DataFrame],
    roe_df: Optional[pd.DataFrame],
    pe_df: Optional[pd.DataFrame],
    sector_mom: Optional[float],
    sector_chip_z: Optional[float],
    sector_pe_median: Optional[float],
    with_rotation: bool = True,
) -> Optional[float]:
    """
    對單一個股在 asof 日做 point-in-time 評分。回傳分數或 None（資料不足）。
    所有 *_df 須為「揭露日對齊」的日期 index DataFrame。
    """
    px = price_df[sid].loc[price_df[sid].index <= asof].ffill().dropna() if sid in price_df.columns else pd.Series(dtype=float)
    if len(px) < _MA_LONG + 1:
        return None

    score = 0.0
    # 基本面
    eps = _asof_latest(eps_df, sid, asof)
    if eps is not None and eps >= _EPS_YOY_T:
        score += 2.0
    roe = _asof_latest(roe_df, sid, asof)
    if roe is not None and roe >= _ROE_MIN:
        score += 1.0
    pe = _asof_latest(pe_df, sid, asof)
    if pe is not None and sector_pe_median is not None and 0 < pe < sector_pe_median:
        score += 1.0

    # 技術
    ma60 = float(px.tail(_MA_LONG).mean())
    last = float(px.iloc[-1])
    if last > ma60:
        score += 1.0
    if ma60 > 0:
        dist = (last - ma60) / ma60 * 100
        if 0 < dist <= _DIST_MAX:
            score += 0.5

    # 相對強度（板塊內 60 日報酬 rank）
    rets = {}
    for s in sector_stocks:
        if s not in price_df.columns:
            continue
        ps = price_df[s].loc[price_df[s].index <= asof].ffill().dropna()
        if len(ps) >= _MOM_LOOKBACK + 1:
            base = float(ps.iloc[-(_MOM_LOOKBACK + 1)])
            if base:
                rets[s] = float(ps.iloc[-1]) / base - 1
    if len(rets) > 1 and sid in rets:
        rank_pct = (sorted(rets.values()).index(rets[sid])) / (len(rets) - 1) * 100
        if rank_pct > _RS_RANK_MIN:
            score += 1.0

    # 輪動加分（板塊級）
    if with_rotation:
        if sector_mom is not None and sector_mom > 0:
            score += 0.5
        if sector_chip_z is not None and sector_chip_z > 1.0:
            score += 0.5

    return round(score, 2)


def _zscore_map(d: Dict[str, float]) -> Dict[str, float]:
    if len(d) < 2:
        return {k: 0.0 for k in d}
    v = np.array(list(d.values()), dtype=float)
    sd = v.std()
    if sd == 0:
        return {k: 0.0 for k in d}
    mu = v.mean()
    return {k: (val - mu) / sd for k, val in d.items()}


def forward_beat(
    price_df: pd.DataFrame, sid: str, asof: pd.Timestamp,
    benchmark: pd.Series, hold_days: int,
) -> Optional[bool]:
    """個股未來 hold_days 報酬是否 > 同期大盤。資料不足回 None。"""
    if sid not in price_df.columns:
        return None
    px = price_df[sid].ffill()
    fut = px.loc[px.index > asof]
    cur = px.loc[px.index <= asof]
    if cur.empty or len(fut) < hold_days:
        return None
    p0 = float(cur.iloc[-1]); p1 = float(fut.iloc[hold_days - 1])
    if not np.isfinite(p0) or not np.isfinite(p1) or p0 == 0:
        return None
    stock_ret = p1 / p0 - 1
    # 大盤同期
    bcur = benchmark.loc[benchmark.index <= asof]
    bfut = benchmark.loc[benchmark.index > asof]
    if bcur.empty or len(bfut) < hold_days:
        return None
    b0 = float(bcur.iloc[-1]); b1 = float(bfut.iloc[hold_days - 1])
    bench_ret = b1 / b0 - 1 if b0 else 0.0
    return bool(stock_ret > bench_ret)


__all__ = ["score_stock_asof", "forward_beat", "_zscore_map", "_asof_latest"]
