"""
燈7 — 宏觀環境濾網（全局燈，非板塊個別）

四個子指標（≥3 項正面 → 宏觀燈亮；可用不足 3 時按比例降門檻）：
  A. FRED DGS10  ：美 10 年公債殖利率 3 個月均線下彎（降息預期/資金寬鬆）
  B. FRED INDPRO ：美工業生產指數站上 12 個月均線（擴張期代理）
  C. yfinance SOXX：費半 ETF 站上 20MA（科技週期上行）
  D. yfinance USDTWD=X：美元/台幣 7日均線下彎（台幣升值，熱錢流入）
     → Singh, Mehta & Varsha (2011) JEB：USD/TWD 為台股最強宏觀領先指標之一

快取策略：
  - 所有時序資料透過 csv_cache 做 CSV 增量快取（.cache/csv/）
  - 每次只拉最後快取日之後的新資料，不重複打 API
  - 任一指標失效不影響其他燈，自動降為可用指標計分
"""
import logging
from typing import Any, Dict, Optional

import src.ssl_fix  # noqa: F401 — 修正 curl_cffi 中文路徑 SSL 錯誤；必須在 yfinance 之前 import

import pandas as pd

logger = logging.getLogger(__name__)

_FRED_BOND   = "DGS10"
_FRED_INDPRO = "INDPRO"
_BOND_MA_PERIOD   = 63   # ~3 個月交易日
_INDPRO_MA_PERIOD = 12   # 12 個月均線


# ── FRED（帶 CSV 增量快取）──────────────────────────────────────────────

def _make_fred_fetcher(series_id: str, fred_api_key: str):
    """工廠函數：回傳符合 csv_cache.fetch_with_cache 簽名的 fetch_fn。"""
    def _fn(start: Optional[pd.Timestamp]) -> pd.Series:
        from fredapi import Fred
        fred = Fred(api_key=fred_api_key)
        kwargs = {}
        if start is not None:
            kwargs["observation_start"] = start.strftime("%Y-%m-%d")
        s = fred.get_series(series_id, **kwargs)
        if s is None or s.empty:
            return pd.Series(dtype=float)
        s = s.dropna()
        s.index = pd.to_datetime(s.index)
        return s
    return _fn


def _get_fred(series_id: str, config) -> Optional[pd.Series]:
    """取 FRED 時序，帶 CSV 增量快取；失敗回傳 None。"""
    if not config.is_fred_key_set():
        logger.debug(f"FRED Key 未設定，跳過 {series_id}")
        return None
    from src.csv_cache import fetch_with_cache
    try:
        s = fetch_with_cache(series_id, _make_fred_fetcher(series_id, config.FRED_API_KEY))
        return s if not s.empty else None
    except Exception as e:
        logger.error(f"FRED {series_id} 取得失敗: {e}")
        return None


def _bond_signal(dgs10: pd.Series) -> bool:
    """10 年債最新值 < 63日MA → 利率下行趨勢 → 正面。"""
    if len(dgs10) < _BOND_MA_PERIOD:
        return False
    ma = dgs10.rolling(_BOND_MA_PERIOD).mean()
    return float(dgs10.iloc[-1]) < float(ma.iloc[-1])


def _indpro_signal(indpro: pd.Series) -> bool:
    """INDPRO 最新值 ≥ 12 個月均線 → 工業擴張期 → 正面（替代 NAPM PMI > 50）。"""
    if len(indpro) < _INDPRO_MA_PERIOD:
        return False
    ma = indpro.rolling(_INDPRO_MA_PERIOD).mean()
    return float(indpro.iloc[-1]) >= float(ma.iloc[-1])


# ── yfinance（帶 CSV 增量快取）──────────────────────────────────────────────

def _make_yf_fetcher(symbol: str):
    """工廠函數：回傳 yfinance 增量 fetch_fn。"""
    def _fn(start: Optional[pd.Timestamp]) -> pd.Series:
        import yfinance as yf
        kwargs = {"period": "1y"} if start is None else {
            "start": start.strftime("%Y-%m-%d")
        }
        hist = yf.Ticker(symbol).history(**kwargs)
        if hist.empty:
            return pd.Series(dtype=float)
        s = hist["Close"].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s
    return _fn


def _get_yf_series(symbol: str, cache_key: str) -> Optional[pd.Series]:
    """取 yfinance 時序，帶 CSV 增量快取；失敗回傳 None。"""
    from src.csv_cache import fetch_with_cache
    try:
        s = fetch_with_cache(cache_key, _make_yf_fetcher(symbol))
        return s if not s.empty else None
    except Exception as e:
        logger.warning(f"燈7: {symbol} 取得失敗: {e}")
        return None


def _get_sox(config) -> Optional[pd.Series]:
    """取 SOXX 日線，帶 CSV 增量快取；失敗回傳 None。"""
    cache_key = f"YF_{config.MACRO_SOX_SYMBOL}"
    return _get_yf_series(config.MACRO_SOX_SYMBOL, cache_key)


def _get_usd_twd(config) -> Optional[pd.Series]:
    """取 USD/TWD 日線，帶 CSV 增量快取；失敗回傳 None。"""
    symbol = getattr(config, "MACRO_USD_TWD_SYMBOL", "USDTWD=X")
    cache_key = f"YF_{symbol.replace('=', '_').replace('^', 'IDX_')}"
    return _get_yf_series(symbol, cache_key)


def _sox_signal(series: pd.Series, ma: int) -> bool:
    """SOXX 收盤站上 MA → 正面。"""
    if series is None or len(series) < ma:
        return False
    ma_val = series.rolling(ma).mean().iloc[-1]
    return float(series.iloc[-1]) > float(ma_val)


def _usd_twd_signal(series: pd.Series, ma: int) -> bool:
    """USD/TWD 收盤 < MA → 台幣升值趨勢 → 正面（外資淨流入）。"""
    if series is None or len(series) < ma:
        return False
    ma_val = series.rolling(ma).mean().iloc[-1]
    return float(series.iloc[-1]) < float(ma_val)


# ── 主函數 ───────────────────────────────────────────────────────────────

def analyze(fetcher, config) -> Dict[str, Any]:
    """全局燈號，回傳單一 dict（非板塊巡迴）。"""
    sub_signals: Dict[str, Optional[bool]] = {
        "bond_down":        None,
        "indpro_above_ma":  None,
        "sox_above_ma":     None,
        "twd_appreciating": None,
    }
    details: Dict[str, str] = {}

    # A. FRED 10 年債（CSV 增量快取）
    dgs10 = _get_fred(_FRED_BOND, config)
    if dgs10 is not None:
        sub_signals["bond_down"] = _bond_signal(dgs10)
        val = float(dgs10.iloc[-1])
        details["bond"] = f"US10Y={val:.2f}% ({'↓均線✅' if sub_signals['bond_down'] else '↑均線❌'})"
    else:
        details["bond"] = "DGS10 取得失敗"

    # B. FRED INDPRO 工業生產指數（替代已下架的 NAPM，CSV 增量快取）
    indpro = _get_fred(_FRED_INDPRO, config)
    if indpro is not None:
        sub_signals["indpro_above_ma"] = _indpro_signal(indpro)
        val  = float(indpro.iloc[-1])
        trend = "擴張✅" if sub_signals["indpro_above_ma"] else "收縮❌"
        details["pmi"] = f"INDPRO={val:.1f} ({trend})"
    else:
        details["pmi"] = "INDPRO 取得失敗"

    # C. yfinance SOXX（免費，無配額限制；CSV 增量快取）
    sox_series = _get_sox(config)
    if sox_series is not None:
        sub_signals["sox_above_ma"] = _sox_signal(sox_series, config.MACRO_SOX_MA)
        val = float(sox_series.iloc[-1])
        details["sox"] = f"SOXX={val:.2f} ({'站上20MA✅' if sub_signals['sox_above_ma'] else '20MA下方❌'})"
    else:
        details["sox"] = "SOXX 不可用"

    # D. yfinance USD/TWD（台幣升值 → 正面；Singh et al. 2011）
    usd_twd_series = _get_usd_twd(config)
    usd_twd_val: Optional[float] = None
    twd_trend: str = "unknown"
    if usd_twd_series is not None:
        ma_period = getattr(config, "MACRO_USD_TWD_MA", 7)
        sub_signals["twd_appreciating"] = _usd_twd_signal(usd_twd_series, ma_period)
        usd_twd_val = float(usd_twd_series.iloc[-1])
        twd_trend = "down" if sub_signals["twd_appreciating"] else "up"
        details["twd"] = (
            f"USD/TWD={usd_twd_val:.3f} "
            f"({'台幣升值✅' if sub_signals['twd_appreciating'] else '台幣貶值❌'})"
        )
    else:
        details["twd"] = "USD/TWD 取得失敗"

    # 計分：≥60% 正面（比例制閾值，防止單指標失效時連鎖崩潰）
    import math
    available = {k: v for k, v in sub_signals.items() if v is not None}
    positive_count   = sum(1 for v in available.values() if v)
    total_available  = len(available)

    if total_available >= 2:
        signal = positive_count >= math.ceil(total_available * 0.6)
    else:
        signal = (total_available >= 1) and (positive_count >= 1)

    return {
        "signal":          signal,
        "score":           round(positive_count / max(total_available, 1), 3),
        "positive_count":  positive_count,
        "total_available": total_available,
        "sub_signals":     sub_signals,
        "usd_twd":         usd_twd_val,
        "twd_trend":       twd_trend,
        "details_dict":    details,
        "details": (
            f"宏觀 {positive_count}/{total_available} 正面 | "
            + " | ".join(details.values())
        ),
    }
