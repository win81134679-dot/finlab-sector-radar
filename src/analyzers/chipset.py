"""
燈6 — 籌碼集中偵測

條件：
  ① 融資今日餘額（散戶）5 日連續下降
  ② 借券賣出餘額（空頭）5 日連續下降
  → 雙降：散戶撤 + 空頭回補，籌碼往強手集中

雙向借券偵測（Hu, Huang & Liao 2009）：
  · 借券↓ + 融資↓ → 亮燈（籌碼集中）
  · 借券↓（空頭回補）→ 個股 triggered 加入 "借券回補↑"（樂觀信號）
  · 借券↑（空頭加碼）→ 個股 triggered 加入 "空頭加碼⚠"（警示信號）

板塊閾值：≥30% 個股亮燈
"""
import logging
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

_MARGIN_KEY = "margin_transactions:融資今日餘額"
_SHORT_KEY = "security_lending_sell:借券賣出餘額"


def _declining_trend(series: pd.Series, n: int) -> bool:
    """近 n 日整體下降（最後值 < 第一值）。"""
    clean = series.dropna()
    if len(clean) < n:
        return False
    window = clean.iloc[-n:]
    return float(window.iloc[-1]) < float(window.iloc[0])


def _increasing_trend(series: pd.Series, n: int) -> bool:
    """近 n 日整體上升（最後值 > 第一值）。"""
    clean = series.dropna()
    if len(clean) < n:
        return False
    window = clean.iloc[-n:]
    return float(window.iloc[-1]) > float(window.iloc[0])


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    margin_df = fetcher.get(_MARGIN_KEY)
    short_df = fetcher.get(_SHORT_KEY)

    if margin_df is None and short_df is None:
        logger.warning("燈6: 無法取得籌碼數據")
        return results

    n = config.INVENTORY_LOOKBACK_DAYS  # 複用同一 5 日參數
    lend_n = getattr(config, "CHIPSET_LENDING_WINDOW", n)

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        avail_m = [s for s in stocks if margin_df is not None and s in margin_df.columns]
        avail_s = [s for s in stocks if short_df is not None and s in short_df.columns]
        available = list(set(avail_m + avail_s))

        if not available:
            results[sector_id] = _empty(0)
            continue

        lit: List[str] = []
        margin_down: List[str] = []
        short_down: List[str] = []
        short_cover: List[str] = []   # 借券↓（空頭回補）
        short_add: List[str] = []     # 借券↑（空頭加碼）

        for stock in available:
            m_ok = stock in avail_m and _declining_trend(margin_df[stock], n)
            s_down = stock in avail_s and _declining_trend(short_df[stock], lend_n)
            s_up   = stock in avail_s and _increasing_trend(short_df[stock], lend_n)

            if m_ok:
                margin_down.append(stock)
            if s_down:
                short_down.append(stock)
                short_cover.append(stock)   # 借券減少 = 空頭回補
            elif s_up:
                short_add.append(stock)     # 借券增加 = 空頭加碼

            if m_ok and s_down:  # 融資+借券同時下降才算籌碼集中
                lit.append(stock)

        pct = len(lit) / len(available)
        signal = pct >= config.CHIPSET_SECTOR_THRESHOLD

        results[sector_id] = {
            "signal":       signal,
            "score":        round(pct, 3),
            "pct_lit":      round(pct * 100, 1),
            "lit_stocks":   lit,
            "total_stocks": len(available),
            "margin_down":  margin_down,
            "short_down":   short_down,
            "short_cover":  short_cover,
            "short_add":    short_add,
            "details": (
                f"{len(lit)}/{len(available)} 籌碼集中 | "
                f"融資↓: {len(margin_down)} | 借券↓: {len(short_down)}"
                + (f" | 借券回補: {len(short_cover)}" if short_cover else "")
                + (f" | 空頭加碼⚠: {len(short_add)}" if short_add else "")
            ),
        }

    return results


def _empty(total: int) -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "lit_stocks": [], "total_stocks": total,
        "margin_down": [], "short_down": [],
        "short_cover": [], "short_add": [], "details": "無數據",
    }
