"""
學術燈8 — 月份季節動能過濾器

研究支撐：
  Fu & Hsieh (2024) JAFB《Taiwan stock return seasonality after lunar new year correction》
  台灣市場的季節性規律（農曆修正後仍顯著）：
    · 1-2 月（年後效應）：均值回歸，前 60 日強勢的板塊容易拉回 → 逆勢反轉
    · 3-12 月：12 個月動量策略有正超額報酬 → 近 20 日動能持續

新信號作為 breakdown.bonus，不計入七燈總分。
觸發值加入個股 triggered 列表：
  "季節動能✓"   — 3-12 月且板塊近 20 日報酬 > 0
  "節後反轉⭐"  — 1-2 月且板塊近 60 日報酬 > 0（強勢後可能反轉，謹慎）
"""
import datetime
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TWII_SYMBOL = "^TWII"
_MOMENTUM_WINDOW   = 20   # 短期動量（3-12 月）
_REVERSAL_WINDOW   = 60   # 中期追蹤（1-2 月反轉期）


def _get_twii_series() -> Optional[pd.Series]:
    """取台灣加權指數日線（增量快取）。"""
    try:
        from src.csv_cache import fetch_with_cache
        import src.ssl_fix  # noqa: F401

        def _fetch(start: Optional[pd.Timestamp]) -> pd.Series:
            import yfinance as yf
            kwargs = {"period": "2y"} if start is None else {
                "start": start.strftime("%Y-%m-%d")
            }
            hist = yf.Ticker(_TWII_SYMBOL).history(**kwargs)
            if hist.empty:
                return pd.Series(dtype=float)
            s = hist["Close"].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            return s

        cache_key = f"YF_IDX_TWII"
        return fetch_with_cache(cache_key, _fetch)
    except Exception as e:
        logger.debug("TWII 取得失敗（momentum_season）: %s", e)
        return None


def _sector_momentum(yoy_df: pd.DataFrame, stocks: List[str], window: int) -> Optional[float]:
    """
    以月營收 YoY 的板塊等權均線作為板塊強弱代理，計算近 window 期變化。
    正值 → 動能持續；負值 → 動能弱化。
    """
    avail = [s for s in stocks if s in yoy_df.columns]
    if not avail:
        return None
    sector_avg = yoy_df[avail].mean(axis=1).dropna()
    if len(sector_avg) < window:
        return None
    delta = float(sector_avg.iloc[-1]) - float(sector_avg.iloc[-window])
    return delta


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    """
    回傳格式：
    {
        sector_id: {
            "season_label": "momentum" | "reversal",
            "season_signal": bool,
            "season_bonus_label": "季節動能✓" | "節後反轉⭐" | None,
            "momentum_delta": float | None,
            "details": str,
        }
    }
    """
    results: Dict[str, Dict[str, Any]] = {}

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Taipei")
        month = datetime.datetime.now(tz).month
    except Exception:
        month = datetime.datetime.now().month

    is_reversal_season = month in (1, 2)
    season_label = "reversal" if is_reversal_season else "momentum"
    window = _REVERSAL_WINDOW if is_reversal_season else _MOMENTUM_WINDOW

    # 取 TWII 供市場整體動能檢驗（可選）
    twii = _get_twii_series()
    twii_trend: Optional[str] = None
    if twii is not None and len(twii) >= window:
        twii_delta = float(twii.iloc[-1]) - float(twii.iloc[-window])
        twii_trend = "up" if twii_delta > 0 else "down"

    # 取月營收 YoY 作板塊動能代理
    yoy_df: Optional[pd.DataFrame] = fetcher.get("monthly_revenue:去年同月增減(%)")

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        if not stocks:
            continue

        momentum_delta: Optional[float] = None
        if yoy_df is not None:
            momentum_delta = _sector_momentum(yoy_df, stocks, window)

        # 信號邏輯（不計入七燈總分，僅作 bonus trigger）
        if is_reversal_season:
            # 1-2 月：若過去 60 日板塊動能「正」→ 提示「可能反轉」（謹慎）
            season_signal = (momentum_delta is not None and momentum_delta > 0)
            bonus_label: Optional[str] = "節後反轉⭐" if season_signal else None
        else:
            # 3-12 月：近 20 日動能正 → 動量延續
            season_signal = (momentum_delta is not None and momentum_delta > 0)
            bonus_label = "季節動能✓" if season_signal else None

        month_zh = f"{month} 月"
        trend_desc = ""
        if momentum_delta is not None:
            trend_desc = f"板塊動能Δ={momentum_delta:+.1f}"
        if twii_trend:
            trend_desc += f" | 大盤={'上行' if twii_trend == 'up' else '下行'}"

        results[sector_id] = {
            "season_label":      season_label,
            "season_signal":     season_signal,
            "season_bonus_label": bonus_label,
            "momentum_delta":    momentum_delta,
            "month":             month,
            "details": (
                f"{month_zh} {'反轉期' if is_reversal_season else '動能期'}"
                + (f" | {trend_desc}" if trend_desc else "")
                + (f" → {bonus_label}" if bonus_label else " → 無信號")
            ),
        }

    return results
