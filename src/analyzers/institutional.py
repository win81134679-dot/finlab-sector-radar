"""
燈2 — 法人籌碼共振

外資（外陸資買賣超）+ 投信（投信買賣超）同步連續 ≥3 天買超 → 個股共振亮燈
板塊閾值：≥30% 個股共振 → 板塊亮燈

額外記錄：外資獨亮/投信獨亮個股數（供參考，不計入燈號）
"""
import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

_FOREIGN_KEY = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST_KEY = "institutional_investors_trading_summary:投信買賣超股數"


def _consecutive_buy(series: pd.Series, n: int) -> bool:
    """連續 n 個交易日均為正（買超）。"""
    clean = series.dropna()
    if len(clean) < n:
        return False
    return all(float(v) > 0 for v in clean.iloc[-n:])


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    foreign_df: pd.DataFrame | None = fetcher.get(_FOREIGN_KEY)
    trust_df: pd.DataFrame | None = fetcher.get(_TRUST_KEY)

    if foreign_df is None and trust_df is None:
        logger.warning("燈2: 無法取得法人買賣超數據")
        return results

    n = config.INSTITUTIONAL_CONSECUTIVE_DAYS

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        # 取交集：兩個 DF 均有的個股
        avail_f = set(s for s in stocks if foreign_df is not None and s in foreign_df.columns)
        avail_t = set(s for s in stocks if trust_df is not None and s in trust_df.columns)
        available = list(avail_f | avail_t)

        if not available:
            results[sector_id] = _empty(0)
            continue

        resonance: List[str] = []
        foreign_only: List[str] = []
        trust_only: List[str] = []

        for stock in available:
            f_buy = stock in avail_f and _consecutive_buy(foreign_df[stock], n)
            t_buy = stock in avail_t and _consecutive_buy(trust_df[stock], n)

            if f_buy and t_buy:
                resonance.append(stock)
            elif f_buy:
                foreign_only.append(stock)
            elif t_buy:
                trust_only.append(stock)

        pct = len(resonance) / len(available)
        signal = pct >= config.INSTITUTIONAL_SECTOR_THRESHOLD

        # 半亮：外資獨買 ≥2 檔 OR 投信獨買 ≥2 檔（法人早期境訊號）
        half_signal = (len(foreign_only) >= 2 or len(trust_only) >= 2) and not signal
        score_contrib = 1.0 if signal else (0.5 if half_signal else 0.0)

        results[sector_id] = {
            "signal":       signal,
            "score":        score_contrib,
            "score_contrib": score_contrib,
            "pct_lit":      round(pct * 100, 1),
            "lit_stocks":   resonance,
            "total_stocks": len(available),
            "foreign_only": foreign_only,
            "trust_only":   trust_only,
            "half_signal":  half_signal,
            "details": (
                f"共振: {len(resonance)}/{len(available)} 檔 | "
                f"外資獨買: {len(foreign_only)} | 投信獨買: {len(trust_only)}"
                + (" 🟡外資/投信早期跟蹤" if half_signal else "")
            ),
        }

    return results


def _empty(total: int) -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "lit_stocks": [], "total_stocks": total,
        "foreign_only": [], "trust_only": [], "details": "無數據",
    }
