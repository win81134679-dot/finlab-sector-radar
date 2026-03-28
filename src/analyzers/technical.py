"""
燈4 — 技術突破偵測

板塊等權重平均股價突破 60MA，且當日成交量 > 20MA × 1.5 倍
→ 帶量突破，板塊亮燈

額外輸出：距 60MA 距離百分比，用於標示「即將突破」的板塊
"""
import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PRICE_KEY = "price:收盤價"
_VOLUME_KEY = "price:成交股數"


def _sector_avg(df: pd.DataFrame, stocks: list, n_days: int = 100) -> pd.Series:
    """取板塊內可用個股等權重均價，最近 n_days 天。"""
    avail = [s for s in stocks if s in df.columns]
    if not avail:
        return pd.Series(dtype=float)
    sub = df[avail].iloc[-n_days:]
    # 每日只取有成交的個股均值
    return sub.mean(axis=1)


def _above_ma(series: pd.Series, period: int) -> bool:
    if len(series) < period:
        return False
    ma = series.rolling(period).mean()
    return float(series.iloc[-1]) > float(ma.iloc[-1])


def _ma_distance_pct(series: pd.Series, period: int) -> float:
    """最新價距 MA 的百分比（正 = 上方，負 = 下方）。"""
    if len(series) < period:
        return float("nan")
    ma = series.rolling(period).mean().iloc[-1]
    price = series.iloc[-1]
    if ma == 0:
        return float("nan")
    return round((float(price) - float(ma)) / float(ma) * 100, 2)


def _volume_surge(series: pd.Series, short: int, multiplier: float) -> bool:
    """當日成交量 > 20MA × multiplier。"""
    if len(series) < short:
        return False
    ma20 = series.rolling(short).mean().iloc[-1]
    return float(series.iloc[-1]) > float(ma20) * multiplier


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    price_df = fetcher.get(_PRICE_KEY)
    vol_df = fetcher.get(_VOLUME_KEY)

    if price_df is None:
        logger.warning("燈4: 無法取得收盤價數據")
        return results

    long_ma = config.TECHNICAL_MA_LONG
    short_ma = config.TECHNICAL_MA_SHORT
    vol_mult = config.TECHNICAL_VOLUME_MULTIPLIER
    lookback = max(long_ma * 2, 150)

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        price_avg = _sector_avg(price_df, stocks, lookback)
        if price_avg.empty or len(price_avg) < long_ma:
            results[sector_id] = _empty()
            continue

        above_60 = _above_ma(price_avg, long_ma)
        dist_pct = _ma_distance_pct(price_avg, long_ma)

        # 成交量判斷（板塊總量）
        vol_ok = False
        if vol_df is not None:
            vol_avg = _sector_avg(vol_df, stocks, lookback)
            if not vol_avg.empty and len(vol_avg) >= short_ma:
                vol_ok = _volume_surge(vol_avg, short_ma, vol_mult)

        signal = above_60 and vol_ok

        # 半亮：60MA 上方超過 10% 但成交量不足（圖形強勢但等量择日）
        half_bright = (
            above_60
            and not vol_ok
            and not np.isnan(dist_pct)
            and dist_pct > 10.0
        )

        # 「即將突破」：在 60MA 下方但距離 < 3%
        approaching = (not above_60) and (not np.isnan(dist_pct)) and (dist_pct > -3.0)

        score_contrib = 1.0 if signal else (0.5 if (half_bright or approaching) else 0.0)

        results[sector_id] = {
            "signal":        signal,
            "score":         score_contrib,
            "score_contrib": score_contrib,
            "pct_lit":       100.0 if signal else (50.0 if score_contrib == 0.5 else 0.0),
            "above_60ma":    above_60,
            "vol_surge":     vol_ok,
            "dist_60ma_pct": dist_pct,
            "approaching":   approaching,
            "half_bright":   half_bright,
            "total_stocks":  len([s for s in stocks if s in price_df.columns]),
            "details": (
                "60MA " + ("上方" if above_60 else "下方")
                + f" ({dist_pct:+.1f}%) | "
                + "成交量" + ("放大" if vol_ok else "不足")
                + (" ⚠️接近突破" if approaching else "")
                + (" 🟡超MA10%但不帶量" if half_bright else "")
            ),
        }

    return results


def _empty() -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "above_60ma": False, "vol_surge": False,
        "dist_60ma_pct": float("nan"), "approaching": False,
        "total_stocks": 0, "stock_signals": {}, "details": "無數據",
    }
