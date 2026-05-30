"""
rotation_backtest.py — 輪動策略 Walk-Forward 回測核心（可單元測試的純函式）

目的（使用者裁示「回測決勝」）：用本系統真實資料，決定
  ① 板塊級法人權重：外資×2/投信×1（中長期 P5/P6）vs 投信×2/外資×1（短線 P1/P2/P3）
  ② RSI / 籌碼門檻
而非照抄論文數字。

設計：
  - 中長期月頻輪動（對應「抱中長期板塊輪動」目標）
  - 每月底依 rotation_score 選前 N 強板塊，等權持有成分股（板塊內等權）至下月
  - 換倉扣交易成本（round-trip，預設 0.585% 賣稅+雙邊手續費近似）
  - Walk-Forward：滾動 train→test 視窗，比較各權重變體的 OOS 績效

純函式（不依賴 fetcher / 檔案 I/O），由 scripts/backtest_rotation.py 注入真實資料。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

# 交易成本（台股實務近似）：買 0.1425% + 賣 0.1425% + 證交稅 0.3% ≈ round-trip 0.585%
DEFAULT_ROUND_TRIP_COST = 0.00585


@dataclass(frozen=True)
class WeightVariant:
    """法人權重變體（待回測比較）。"""
    name: str
    foreign: float
    trust: float
    use_dealer_filter: bool = False


VARIANTS = [
    WeightVariant("foreign_led", 2.0, 1.0),              # 中長期假說（P5/P6）
    WeightVariant("trust_led", 1.0, 2.0),                # 短線假說（P1/P2/P3）
    WeightVariant("trust_led_dealer_filter", 1.0, 2.0, True),  # +自營雜訊濾網
]


def month_end_dates(index: pd.DatetimeIndex) -> List[pd.Timestamp]:
    """取每月最後一個交易日（rebalance 日）。"""
    s = pd.Series(index, index=index)
    return list(s.groupby([index.year, index.month]).last())


def sector_chip_score_at(
    foreign_net: pd.DataFrame,
    trust_net: pd.DataFrame,
    stocks: List[str],
    asof: pd.Timestamp,
    variant: WeightVariant,
    *,
    window: int = 20,
    dealer_net: Optional[pd.DataFrame] = None,
) -> float:
    """
    某板塊在 asof 日的法人合力近 window 日累積（依變體權重）。
    use_dealer_filter：若自營商同向大買（疑避險雜訊），扣減合力。
    """
    def _sum(df: Optional[pd.DataFrame], w: float) -> pd.Series:
        if df is None:
            return pd.Series(dtype=float)
        cols = [s for s in stocks if s in df.columns]
        if not cols:
            return pd.Series(dtype=float)
        sub = df.loc[df.index <= asof, cols]
        return sub.tail(window).sum(axis=1) * w

    parts = [_sum(foreign_net, variant.foreign), _sum(trust_net, variant.trust)]
    combined = None
    for p in parts:
        if p.empty:
            continue
        combined = p if combined is None else combined.add(p, fill_value=0)
    if combined is None or combined.empty:
        return 0.0
    score = float(combined.sum())

    if variant.use_dealer_filter and dealer_net is not None:
        d = _sum(dealer_net, 1.0)
        if not d.empty and float(d.sum()) > 0:
            # 自營同向買超視為避險雜訊 → 折減（P1/P6）
            score -= 0.5 * float(d.sum())
    return score


def rotation_rank(
    price_df: pd.DataFrame,
    foreign_net: pd.DataFrame,
    trust_net: pd.DataFrame,
    sector_stocks: Dict[str, List[str]],
    asof: pd.Timestamp,
    variant: WeightVariant,
    *,
    mom_lookback: int = 60,
    chip_window: int = 20,
    dealer_net: Optional[pd.DataFrame] = None,
) -> List[str]:
    """
    回傳 asof 日各板塊依綜合強度（z動能 + z籌碼）排序（強→弱）。
    （回測簡化版：用動能 + 籌碼兩維，與線上 rotation_score 一致精神）
    """
    mom: Dict[str, float] = {}
    chip: Dict[str, float] = {}
    for sid, stocks in sector_stocks.items():
        avail = [s for s in stocks if s in price_df.columns]
        if not avail:
            continue
        sub = price_df.loc[price_df.index <= asof, avail]
        if len(sub) < mom_lookback + 1:
            continue
        idx = (1 + sub.ffill().pct_change(fill_method=None).mean(axis=1).fillna(0)).cumprod()
        base = float(idx.iloc[-(mom_lookback + 1)])
        if base:
            mom[sid] = (float(idx.iloc[-1]) - base) / base
        chip[sid] = sector_chip_score_at(
            foreign_net, trust_net, stocks, asof, variant,
            window=chip_window, dealer_net=dealer_net,
        )

    def _z(d: Dict[str, float]) -> Dict[str, float]:
        if len(d) < 2:
            return {k: 0.0 for k in d}
        v = np.array(list(d.values()), dtype=float)
        sd = v.std()
        if sd == 0:
            return {k: 0.0 for k in d}
        mu = v.mean()
        return {k: (val - mu) / sd for k, val in d.items()}

    zm, zc = _z(mom), _z(chip)
    common = set(mom) & set(chip)
    strength = {sid: (zm.get(sid, 0) + zc.get(sid, 0)) / 2 for sid in common}
    return [sid for sid, _ in sorted(strength.items(), key=lambda x: -x[1])]


def _sector_forward_return(
    price_df: pd.DataFrame, stocks: List[str],
    start: pd.Timestamp, end: pd.Timestamp,
) -> Optional[float]:
    """板塊等權成分股在 (start, end] 的報酬。"""
    avail = [s for s in stocks if s in price_df.columns]
    if not avail:
        return None
    sub = price_df[avail]
    p0 = sub.loc[sub.index <= start].ffill().iloc[-1] if (sub.index <= start).any() else None
    p1 = sub.loc[sub.index <= end].ffill().iloc[-1] if (sub.index <= end).any() else None
    if p0 is None or p1 is None:
        return None
    rets = (p1 / p0 - 1).dropna()
    return float(rets.mean()) if not rets.empty else None


def simulate(
    price_df: pd.DataFrame,
    foreign_net: pd.DataFrame,
    trust_net: pd.DataFrame,
    sector_stocks: Dict[str, List[str]],
    variant: WeightVariant,
    *,
    top_n: int = 3,
    cost: float = DEFAULT_ROUND_TRIP_COST,
    start_idx: int = 0,
    end_idx: Optional[int] = None,
    dealer_net: Optional[pd.DataFrame] = None,
    **rank_kwargs,
) -> pd.Series:
    """
    月頻輪動回測 → 回傳淨值序列（index=rebalance 日）。
    每月選前 top_n 強板塊等權持有，扣換倉成本。
    """
    rebs = month_end_dates(price_df.index)  # type: ignore[arg-type]
    if end_idx is None:
        end_idx = len(rebs) - 1
    rebs = rebs[start_idx:end_idx + 1]
    if len(rebs) < 2:
        return pd.Series(dtype=float)

    equity = 1.0
    nav = {rebs[0]: equity}
    prev_set: set = set()

    for i in range(len(rebs) - 1):
        d0, d1 = rebs[i], rebs[i + 1]
        ranked = rotation_rank(
            price_df, foreign_net, trust_net, sector_stocks, d0, variant,
            dealer_net=dealer_net, **rank_kwargs,
        )
        picks = ranked[:top_n]
        # 期間報酬（等權）
        rets = [_sector_forward_return(price_df, sector_stocks[s], d0, d1) for s in picks]
        rets = [r for r in rets if r is not None]
        period_ret = float(np.mean(rets)) if rets else 0.0
        # 換倉成本：與上期持倉的差異比例 × cost
        new_set = set(picks)
        turnover = len(new_set ^ prev_set) / (2 * max(len(new_set), 1))
        equity *= (1 + period_ret) * (1 - cost * turnover)
        nav[d1] = equity
        prev_set = new_set

    return pd.Series(nav)


def metrics(nav: pd.Series, periods_per_year: int = 12) -> Dict[str, float]:
    """從月頻淨值算年化/夏普/卡瑪/最大回撤。"""
    if len(nav) < 2:
        return {"annual": 0.0, "sharpe": 0.0, "calmar": 0.0, "mdd": 0.0, "total": 0.0}
    rets = nav.pct_change().dropna()
    n = len(rets)
    total = float(nav.iloc[-1] / nav.iloc[0] - 1)
    annual = float((nav.iloc[-1] / nav.iloc[0]) ** (periods_per_year / max(n, 1)) - 1)
    vol = float(rets.std() * np.sqrt(periods_per_year))
    sharpe = annual / vol if vol > 0 else 0.0
    cummax = nav.cummax()
    mdd = float(((nav - cummax) / cummax).min())
    calmar = annual / abs(mdd) if mdd < 0 else 0.0
    return {
        "annual": round(annual, 4), "sharpe": round(sharpe, 3),
        "calmar": round(calmar, 3), "mdd": round(mdd, 4),
        "total": round(total, 4),
    }


def walk_forward(
    price_df: pd.DataFrame,
    foreign_net: pd.DataFrame,
    trust_net: pd.DataFrame,
    sector_stocks: Dict[str, List[str]],
    variant: WeightVariant,
    *,
    train_months: int = 12,
    test_months: int = 3,
    dealer_net: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Dict[str, float]:
    """
    Walk-Forward：滾動 (train→test) 視窗，串接所有 OOS 測試段淨值再算總指標。
    rotation_score 無擬合參數（除權重選擇），故 WF 的價值在驗證 OOS 穩健性。
    """
    rebs = month_end_dates(price_df.index)  # type: ignore[arg-type]
    seg_navs: List[pd.Series] = []
    i = train_months
    equity = 1.0
    while i + test_months <= len(rebs) - 1:
        seg = simulate(
            price_df, foreign_net, trust_net, sector_stocks, variant,
            start_idx=i, end_idx=i + test_months, dealer_net=dealer_net, **kwargs,
        )
        if not seg.empty:
            seg = seg / seg.iloc[0] * equity   # 串接（接續上一段淨值）
            equity = float(seg.iloc[-1])
            seg_navs.append(seg)
        i += test_months

    if not seg_navs:
        return {"annual": 0.0, "sharpe": 0.0, "calmar": 0.0, "mdd": 0.0, "total": 0.0, "oos_segments": 0}
    full = pd.concat(seg_navs)
    full = full[~full.index.duplicated(keep="first")].sort_index()
    m = metrics(full)
    m["oos_segments"] = len(seg_navs)
    return m


__all__ = [
    "WeightVariant", "VARIANTS", "DEFAULT_ROUND_TRIP_COST",
    "month_end_dates", "sector_chip_score_at", "rotation_rank",
    "simulate", "metrics", "walk_forward",
]
