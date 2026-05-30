"""
燈2 — 法人籌碼共振

外資（外陸資買賣超）+ 投信（投信買賣超）同步連續 N 天買超 → 個股共振亮燈
板塊閾值：≥30% 個股共振 → 板塊亮燈

市場狀態自適應門檻（Chiang et al. 2012; Huang & Shiu 2009）：
  · 牛市（加權指數 > 260MA）：連續 3 日 → "外資牛市共振"
  · 熊市（加權指數 ≤ 260MA）：需連續 5 日 → "外資熊市防守"
  兩種情境的觸發標籤不同，標記到個股 triggered 列表供前端顯示

額外記錄：外資獨亮/投信獨亮個股數（供參考，不計入燈號）
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_FOREIGN_KEY = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST_KEY = "institutional_investors_trading_summary:投信買賣超股數"
_TWII_SYMBOL = "^TWII"


def _consecutive_buy(series: pd.Series, n: int) -> bool:
    """連續 n 個交易日均為正（買超）。"""
    clean = series.dropna()
    if len(clean) < n:
        return False
    return all(float(v) > 0 for v in clean.iloc[-n:])


def _is_quarter_end_window(trust_df: pd.DataFrame | None, last_n_days: int = 10) -> bool:
    """
    最新交易日是否落在「季末作帳期」= 3/6/9/12 月的最後 last_n_days 個交易日。
    依據 bakeoff 實證（claude.md §9.4.2）：排除此期間的投信訊號可把 alpha
    從 +3.7pp 提到 +4.3pp（持有1季）/ +5.4pp（持有1月）。P2 herding/作帳。
    """
    if trust_df is None or trust_df.empty:
        return False
    try:
        idx = trust_df.dropna(how="all").index
        if len(idx) == 0:
            return False
        latest = pd.Timestamp(idx[-1])
        if latest.month not in (3, 6, 9, 12):
            return False
        # 用該月「日曆上的營業日」判斷 latest 是否在最後 last_n_days 個之內
        # （以營業日日曆為準，不受 DataFrame 起點稀疏影響）
        month_end = latest + pd.offsets.MonthEnd(0)
        month_bdays = pd.bdate_range(latest.replace(day=1), month_end)
        if len(month_bdays) == 0:
            return False
        return latest >= month_bdays[-last_n_days]
    except Exception:
        return False


def _get_market_state(config) -> str:
    """
    判斷市場狀態（牛 / 熊）：加權指數收盤是否站上 260MA。
    失敗時回傳 "bull"（保守偏向多頭門檻，不阻止原有邏輯）。
    """
    try:
        from src.csv_cache import fetch_with_cache

        ma_period = getattr(config, "INSTITUTIONAL_MARKET_MA", 260)

        def _fetch_twii(start: Optional[pd.Timestamp]) -> pd.Series:
            import src.ssl_fix  # noqa: F401
            import yfinance as yf
            kwargs = {"period": "3y"} if start is None else {
                "start": start.strftime("%Y-%m-%d")
            }
            hist = yf.Ticker(_TWII_SYMBOL).history(**kwargs)
            if hist.empty:
                return pd.Series(dtype=float)
            s = hist["Close"].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            return s

        cache_key = f"YF_{_TWII_SYMBOL.replace('^', 'IDX_')}"
        twii = fetch_with_cache(cache_key, _fetch_twii)
        if twii is None or len(twii) < ma_period:
            return "bull"
        ma_val = twii.rolling(ma_period).mean().iloc[-1]
        return "bull" if float(twii.iloc[-1]) > float(ma_val) else "bear"
    except Exception as e:
        logger.debug("市場狀態判斷失敗（用牛市門檻）: %s", e)
        return "bull"


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    foreign_df: pd.DataFrame | None = fetcher.get(_FOREIGN_KEY)
    trust_df: pd.DataFrame | None = fetcher.get(_TRUST_KEY)

    if foreign_df is None and trust_df is None:
        logger.warning("燈2: 無法取得法人買賣超數據")
        return results

    # 市場狀態自適應門檻
    market_state = _get_market_state(config)
    if market_state == "bull":
        n = getattr(config, "INSTITUTIONAL_BULL_DAYS", config.INSTITUTIONAL_CONSECUTIVE_DAYS)
        resonance_label = "外資牛市共振"
    else:
        n = getattr(config, "INSTITUTIONAL_BEAR_DAYS", config.INSTITUTIONAL_CONSECUTIVE_DAYS + 2)
        resonance_label = "外資熊市防守"

    logger.info("燈2: 市場狀態=%s，法人連買門檻=%d 日（%s）", market_state, n, resonance_label)

    # 季末作帳期偵測（bakeoff §9.4.2：此期間投信訊號低信度，個股評分不獎勵投信獨買）
    in_window_dressing = _is_quarter_end_window(trust_df)
    if in_window_dressing:
        logger.info("燈2: 目前為季末作帳期，投信獨買訊號將降級（不計入個股評分加分）")

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

        # 半亮：外資獨買 ≥2 檔 OR 投信獨買 ≥2 檔（法人早期跟蹤訊號）
        half_signal = (len(foreign_only) >= 2 or len(trust_only) >= 2) and not signal
        score_contrib = 1.0 if signal else (0.5 if half_signal else 0.0)

        results[sector_id] = {
            "signal":          signal,
            "score":           score_contrib,
            "score_contrib":   score_contrib,
            "pct_lit":         round(pct * 100, 1),
            "lit_stocks":      resonance,
            "total_stocks":    len(available),
            "foreign_only":    foreign_only,
            "trust_only":      trust_only,
            "half_signal":     half_signal,
            "market_state":    market_state,
            "in_window_dressing": in_window_dressing,
            "resonance_label": resonance_label,
            "details": (
                f"共振: {len(resonance)}/{len(available)} 檔 ({resonance_label}) | "
                f"外資獨買: {len(foreign_only)} | 投信獨買: {len(trust_only)}"
                + (" 🟡外資/投信早期跟蹤" if half_signal else "")
            ),
        }

    return results


def _empty(total: int) -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "lit_stocks": [], "total_stocks": total,
        "foreign_only": [], "trust_only": [], "market_state": "bull",
        "resonance_label": "外資牛市共振", "details": "無數據",
    }
