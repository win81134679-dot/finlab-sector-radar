"""
燈1 — 月營收 YoY 拐點偵測

主指標：個股連續 N 個月 YoY 由負轉正（預設 N=3）
輔助指標：MoM 連續加速（連續 2 個月 MoM% 遞增）
  → 代理庫存補貨訊號，與燈3 庫存循環互補，提供月頻前瞻

板塊閾值：≥50% 個股亮燈 → 板塊亮燈
"""
import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def _yoy_turnaround(series: pd.Series, n: int = 3) -> bool:
    """連續 n 個月：第 1 個月為負，後 n-1 個月全為正。"""
    clean = series.dropna()
    if len(clean) < n:
        return False
    recent = clean.iloc[-n:]
    return float(recent.iloc[0]) < 0 and all(float(v) > 0 for v in recent.iloc[1:])


def _mom_accelerating(series: pd.Series, n: int = 2) -> bool:
    """MoM% 連續 n 期遞增（加速成長）。"""
    clean = series.dropna()
    if len(clean) < n + 1:
        return False
    recent = clean.iloc[-(n + 1):]
    diffs = recent.diff().dropna()
    return all(float(v) > 0 for v in diffs)


def _sector_weighted_yoy_positive(yoy_df: pd.DataFrame, stocks: list, n: int = 3, min_yoy: float = 5.0) -> bool:
    """板塊等權重平均 YoY 連 n 個月正成長，且最近一月 > min_yoy%（捕捉整體板塊具實質動能的萌芽期）。"""
    avail = [s for s in stocks if s in yoy_df.columns]
    if not avail:
        return False
    sector_yoy = yoy_df[avail].mean(axis=1).dropna()
    if len(sector_yoy) < n:
        return False
    recent = sector_yoy.iloc[-n:]
    return all(float(v) > 0 for v in recent) and float(recent.iloc[-1]) > min_yoy


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    """
    回傳格式：
    {
        sector_id: {
            "signal": bool,
            "score": float,          # 0-1，亮燈個股比例
            "pct_lit": float,        # e.g. 62.5
            "lit_stocks": list,
            "total_stocks": int,
            "mom_accel_stocks": list,  # MoM 加速個股（輔助）
            "details": str,
        }
    }
    """
    results: Dict[str, Dict[str, Any]] = {}

    yoy_df: pd.DataFrame | None = fetcher.get("monthly_revenue:去年同月增減(%)")
    mom_df: pd.DataFrame | None = fetcher.get("monthly_revenue:上月比較增減(%)")

    if yoy_df is None:
        logger.warning("燈1: 無法取得月營收 YoY 數據")
        return results

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        available = [s for s in stocks if s in yoy_df.columns]
        if not available:
            results[sector_id] = _empty_result(sector_id, 0)
            continue

        # YoY 拐點掃描
        lit: List[str] = []
        for stock in available:
            if _yoy_turnaround(yoy_df[stock], config.REVENUE_CONSECUTIVE_MONTHS):
                lit.append(stock)

        pct = len(lit) / len(available)
        # OR 條件：個股拐點比例達標 OR 板塊加權 YoY 連 N 月正成長且最近月 > min%
        weighted_ok = _sector_weighted_yoy_positive(
            yoy_df, available,
            n=config.REVENUE_WEIGHTED_YOY_MONTHS,
            min_yoy=config.REVENUE_WEIGHTED_YOY_MIN_PCT,
        )
        signal = (pct >= config.REVENUE_SECTOR_THRESHOLD) or weighted_ok

        # MoM 加速掃描（輔助）
        mom_accel: List[str] = []
        if mom_df is not None:
            avail_mom = [s for s in stocks if s in mom_df.columns]
            for stock in avail_mom:
                if _mom_accelerating(mom_df[stock], config.REVENUE_MOM_ACCEL_MONTHS):
                    mom_accel.append(stock)

        trigger = "板塊加權YoY" if (weighted_ok and pct < config.REVENUE_SECTOR_THRESHOLD) else "個股拐點"
        results[sector_id] = {
            "signal":          signal,
            "score":           round(pct, 3),
            "pct_lit":         round(pct * 100, 1),
            "lit_stocks":      lit,
            "total_stocks":    len(available),
            "mom_accel_stocks": mom_accel,
            "weighted_signal": weighted_ok,
            "details": (
                f"{len(lit)}/{len(available)} 個股 YoY 拐點 | MoM 加速: {len(mom_accel)} 檔"
                + (f" | 加權YoY✅" if weighted_ok else "")
            ),
        }

    return results


def _empty_result(sector_id: str, total: int) -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "lit_stocks": [], "total_stocks": total,
        "mom_accel_stocks": [], "details": "無數據",
    }
