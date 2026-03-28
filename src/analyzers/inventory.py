"""
燈3 — 庫存循環偵測

主指標（季頻）：存貨週轉率 QoQ 改善 → 個股亮燈
板塊閾值：≥50% 個股亮燈 → 板塊亮燈

注意：融資/借券已移至燈6（籌碼集中）計算，不再影響燈3。
"""
import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

_INVENTORY_TURNOVER_KEY = "fundamental_features:存貨週轉率"


def _turnover_improving(series: pd.Series) -> bool:
    """存貨週轉率：最新季 > 前一季（QoQ 改善）。"""
    clean = series.dropna()
    if len(clean) < 2:
        return False
    return float(clean.iloc[-1]) > float(clean.iloc[-2])


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    inv_df = fetcher.get(_INVENTORY_TURNOVER_KEY)

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        available = [s for s in stocks if inv_df is not None and s in inv_df.columns]

        if not available:
            results[sector_id] = _empty(0)
            continue

        lit: List[str] = []

        for stock in available:
            # 主判斷：存貨週轉率 QoQ 改善
            if _turnover_improving(inv_df[stock]):
                lit.append(stock)

        pct = len(lit) / len(available)
        signal = pct >= config.INVENTORY_SECTOR_THRESHOLD

        results[sector_id] = {
            "signal":        signal,
            "score":         round(pct, 3),
            "pct_lit":       round(pct * 100, 1),
            "lit_stocks":    lit,
            "total_stocks":  len(available),
            "inv_improving": lit,
            "details": (
                f"{len(lit)}/{len(available)} 檔週轉率改善"
            ),
        }

    return results


def _empty(total: int) -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "lit_stocks": [], "total_stocks": total,
        "inv_improving": [], "details": "無數據",
    }
