"""
rotation_validation.py — 輪動系統的歷史驗證（誠實版）

回答兩個關鍵問題（純函式，可單元測試；由 scripts/backtest_rotation_validate.py 注入真資料）：

  Q1 板塊層級：每月/每季用 rotation_score 選出的前 N 強板塊，
     未來一期報酬是否真的贏過「全板塊平均」？（命中率 + 超額報酬）

  Q2 個股層級：在選中的強勢板塊裡，用「輪動感知排名」挑出的前 K 檔個股，
     未來一期的命中率（報酬 > 0 的比例）與「贏過大盤」的比例如何？

⚠️ 個股排名為**輕量代理**（RS rank + 近月動能），非完整 stock_scorer
   （完整版需逐日基本面，回測成本過高）。報告會明確標註此限制。

復用 rotation_backtest 的 month_end_dates / rotation_rank / _sector_forward_return。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.analyzers.rotation_backtest import (
    WeightVariant, month_end_dates, rotation_rank, _sector_forward_return,
)


def _stock_forward_return(price_df: pd.DataFrame, sid: str,
                          start: pd.Timestamp, end: pd.Timestamp) -> Optional[float]:
    """單一個股 (start, end] 報酬。"""
    if sid not in price_df.columns:
        return None
    s = price_df[sid]
    a = s.loc[s.index <= start].ffill()
    b = s.loc[s.index <= end].ffill()
    if a.empty or b.empty:
        return None
    p0, p1 = float(a.iloc[-1]), float(b.iloc[-1])
    if not np.isfinite(p0) or not np.isfinite(p1) or p0 == 0:
        return None
    return p1 / p0 - 1


def rank_stocks_in_sector(
    price_df: pd.DataFrame,
    stocks: List[str],
    asof: pd.Timestamp,
    *,
    mom_lookback: int = 60,
) -> List[str]:
    """
    板塊內個股「輪動感知」排名（強→弱）的輕量代理：
    用近 mom_lookback 日報酬（動能）排序。與 stock_scorer 的技術/RS 維度同精神。
    """
    avail = [s for s in stocks if s in price_df.columns]
    scored: Dict[str, float] = {}
    for s in avail:
        ser = price_df[s].loc[price_df[s].index <= asof].ffill().dropna()
        if len(ser) < mom_lookback + 1:
            continue
        base = float(ser.iloc[-(mom_lookback + 1)])
        if base:
            scored[s] = float(ser.iloc[-1]) / base - 1
    return [s for s, _ in sorted(scored.items(), key=lambda x: -x[1])]


def validate(
    price_df: pd.DataFrame,
    foreign_net: pd.DataFrame,
    trust_net: pd.DataFrame,
    sector_stocks: Dict[str, List[str]],
    variant: WeightVariant,
    *,
    top_n_sectors: int = 3,
    top_k_stocks: int = 3,
    hold_months: int = 1,
    benchmark: Optional[pd.Series] = None,
    dealer_net: Optional[pd.DataFrame] = None,
    **rank_kwargs,
) -> Dict[str, object]:
    """
    走歷史每個 rebalance 點，回傳 Q1/Q2 統計。

    Returns dict:
      rebalances:            有效再平衡次數
      sector_hit_rate:       選中板塊報酬 > 全板塊平均 的比例（Q1）
      sector_avg_excess:     選中板塊相對全板塊平均的平均超額報酬
      sector_avg_return:     選中板塊平均報酬
      universe_avg_return:   全板塊平均報酬（基準）
      stock_hit_rate:        選中個股報酬 > 0 的比例（Q2）
      stock_beat_bench_rate: 選中個股報酬 > 同期大盤 的比例
      stock_avg_return:      選中個股平均報酬
      n_stock_samples:       個股樣本數
    """
    rebs = month_end_dates(price_df.index)  # type: ignore[arg-type]
    rebs = rebs[::hold_months]  # 每 hold_months 個月一次
    if len(rebs) < 2:
        return {"rebalances": 0}

    sector_excess: List[float] = []
    sector_picks_ret: List[float] = []
    universe_ret: List[float] = []
    sector_wins = 0

    stock_rets: List[float] = []
    stock_pos = 0
    stock_beat = 0

    for i in range(len(rebs) - 1):
        d0, d1 = rebs[i], rebs[i + 1]
        ranked = rotation_rank(
            price_df, foreign_net, trust_net, sector_stocks, d0, variant,
            dealer_net=dealer_net, **rank_kwargs,
        )
        if not ranked:
            continue
        picks = ranked[:top_n_sectors]

        # ── Q1 板塊層級 ──
        pick_rets = [_sector_forward_return(price_df, sector_stocks[s], d0, d1) for s in picks]
        pick_rets = [r for r in pick_rets if r is not None]
        all_rets = [_sector_forward_return(price_df, sector_stocks[s], d0, d1) for s in ranked]
        all_rets = [r for r in all_rets if r is not None]
        if pick_rets and all_rets:
            pr, ur = float(np.mean(pick_rets)), float(np.mean(all_rets))
            sector_picks_ret.append(pr)
            universe_ret.append(ur)
            sector_excess.append(pr - ur)
            if pr > ur:
                sector_wins += 1

        # ── Q2 個股層級（選中板塊內，動能前 K）──
        bench_ret = None
        if benchmark is not None:
            b0 = benchmark.loc[benchmark.index <= d0].ffill()
            b1 = benchmark.loc[benchmark.index <= d1].ffill()
            if not b0.empty and not b1.empty and float(b0.iloc[-1]):
                bench_ret = float(b1.iloc[-1]) / float(b0.iloc[-1]) - 1
        for s in picks:
            top_stocks = rank_stocks_in_sector(price_df, sector_stocks[s], d0,
                                               **{k: v for k, v in rank_kwargs.items()
                                                  if k == "mom_lookback"})[:top_k_stocks]
            for st in top_stocks:
                r = _stock_forward_return(price_df, st, d0, d1)
                if r is None:
                    continue
                stock_rets.append(r)
                if r > 0:
                    stock_pos += 1
                if bench_ret is not None and r > bench_ret:
                    stock_beat += 1

    n_reb = len(sector_picks_ret)
    n_stk = len(stock_rets)
    return {
        "rebalances": n_reb,
        "sector_hit_rate": round(sector_wins / n_reb, 4) if n_reb else 0.0,
        "sector_avg_excess": round(float(np.mean(sector_excess)), 4) if sector_excess else 0.0,
        "sector_avg_return": round(float(np.mean(sector_picks_ret)), 4) if sector_picks_ret else 0.0,
        "universe_avg_return": round(float(np.mean(universe_ret)), 4) if universe_ret else 0.0,
        "stock_hit_rate": round(stock_pos / n_stk, 4) if n_stk else 0.0,
        "stock_beat_bench_rate": round(stock_beat / n_stk, 4) if n_stk else 0.0,
        "stock_avg_return": round(float(np.mean(stock_rets)), 4) if stock_rets else 0.0,
        "n_stock_samples": n_stk,
    }


__all__ = ["validate", "rank_stocks_in_sector"]
