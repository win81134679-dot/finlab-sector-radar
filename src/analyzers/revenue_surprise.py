"""
學術燈9 — 月營收連續加速超預期

研究支撐：
  Lu & Xin (2024) Int'l J. Accounting:
    「月營收資訊內容比盈利公告更強」— 連續 3 個月 YoY 加速且每月均超過
    自身過去 12 個月平均 YoY → 正異常報酬更顯著（相較燈1 的由負轉正拐點）

觸發邏輯：
  · 連續 REVENUE_ACCEL_LOOKBACK（3）個月：每月 YoY > 過去 REVENUE_ACCEL_AVG_MONTHS（12）月 YoY 均值
  · 且最近月 YoY 遞增（加速方向確認）

新信號作為 breakdown.bonus，不計入七燈總分。
觸發值加入個股 triggered 列表：
  "營收加速↑✓" — 連續 3 月 YoY 加速且超過自身 12 月均值
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _revenue_accelerating_surprise(
    series: pd.Series,
    lookback: int = 3,
    avg_months: int = 12,
) -> bool:
    """
    判斷個股月營收是否「持續加速超預期」。
    條件：
      1. 有足夠歷史資料（avg_months + lookback 個月）
      2. 最近 lookback 個月的 YoY 均 > 過去 avg_months 月 YoY 的均值
      3. 最近 lookback 個月 YoY 遞增（加速方向確認）
    """
    clean = series.dropna()
    if len(clean) < avg_months + lookback:
        return False

    recent = clean.iloc[-lookback:]
    baseline = clean.iloc[-(avg_months + lookback):-lookback]

    if baseline.empty:
        return False

    baseline_avg = float(baseline.mean())
    # 條件 2：近期每月均高於基準
    all_above = all(float(v) > baseline_avg for v in recent)
    if not all_above:
        return False

    # 條件 3：遞增趨勢（近期 YoY 加速）
    diffs = recent.diff().dropna()
    accelerating = all(float(v) > 0 for v in diffs)
    return accelerating


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    """
    回傳格式：
    {
        sector_id: {
            "signal": bool,
            "accel_stocks": list,
            "pct_accel": float,
            "details": str,
        }
    }
    """
    results: Dict[str, Dict[str, Any]] = {}

    yoy_df: Optional[pd.DataFrame] = fetcher.get("monthly_revenue:去年同月增減(%)")
    if yoy_df is None:
        logger.warning("學術燈9: 無法取得月營收 YoY 數據")
        return results

    lookback   = getattr(config, "REVENUE_ACCEL_LOOKBACK",   3)
    avg_months = getattr(config, "REVENUE_ACCEL_AVG_MONTHS", 12)

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        available = [s for s in stocks if s in yoy_df.columns]
        if not available:
            results[sector_id] = _empty(0)
            continue

        accel_stocks: List[str] = []
        for stock in available:
            if _revenue_accelerating_surprise(yoy_df[stock], lookback, avg_months):
                accel_stocks.append(stock)

        pct = len(accel_stocks) / len(available)
        # 板塊 ≥30% 個股加速，視為板塊動能確認（信號非必要，主要供個股標記用）
        signal = pct >= 0.30

        results[sector_id] = {
            "signal":       signal,
            "accel_stocks": accel_stocks,
            "pct_accel":    round(pct * 100, 1),
            "total_stocks": len(available),
            "details": (
                f"{len(accel_stocks)}/{len(available)} 營收連加速超預期"
                + (" ✅板塊確認" if signal else "")
            ),
        }

    return results


def _empty(total: int) -> Dict[str, Any]:
    return {
        "signal": False, "accel_stocks": [], "pct_accel": 0.0,
        "total_stocks": total, "details": "無數據",
    }
