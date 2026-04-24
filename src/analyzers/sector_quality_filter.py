"""
P3 — 垃圾股五大業障過濾（板塊品質篩選器）

對應股票老師「第16節：虛孤破偏散」
每個過濾項可透過 config 獨立開關，防止板塊因過濾過度而完全清空訊號。

五大業障：
  破(po)   — price < MA120 且 MA120 斜率下彎（技術上長期趨勢已破壞）
  孤(gu)   — 個股不在燈2任何法人集合（外資/投信/外資投信共振）內
  虛(xu)   — 近期營業現金流量為負（虛胖成長，不可持續）【預設關閉】
  偏(pian) — PE < 0 或 PE > 80（估值扭曲，不符合合理範圍）
  散(san)  — 近20日平均日成交量 < 50萬股（流動性不足，散戶主導）

輸出（per sector）：
  junk_ratio     — 板塊內垃圾股佔比（0.0–1.0），取五項聯集去重後計算
  junk_flags     — 各過濾項詳情 {po/gu/xu/pian/san: {label, count, ratio, stocks}}
  quality_warning — 是否觸發品質警示（junk_ratio ≥ config.JUNK_SECTOR_THRESHOLD）
  enabled_filters — 本次啟用的過濾項清單

注意：此分析器不修改板塊 level（強烈關注/觀察中/忽略），只是附加品質標籤。
      前端依 quality_warning 顯示提示，使用者自行判斷。
"""
import logging
from typing import Any, Dict, List, Optional, Set

import pandas as pd

logger = logging.getLogger(__name__)

_PRICE_KEY  = "price:收盤價"
_VOLUME_KEY = "price:成交股數"
_PE_KEY     = "price_earning_ratio:本益比"
_OCF_KEY    = "fundamental_features:營業現金流量"

# 散：平均日成交量低於此值（股數）視為流動性不足
_SAN_MIN_VOLUME = 500_000
# 破：MA 斜率判定回看天數（近N日MA有無下彎）
_PO_SLOPE_DAYS = 20
# 破：MA 週期
_PO_MA_PERIOD = 120


def analyze_sector(
    sector_id: str,
    stocks: List[str],
    raw_results: Dict[str, Any],
    fetcher: Any,
    config: Any,
    *,
    price_df: Optional[pd.DataFrame] = None,
    volume_df: Optional[pd.DataFrame] = None,
    pe_df: Optional[pd.DataFrame] = None,
    ocf_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    對指定板塊執行垃圾股五大業障過濾。

    可傳入預取的 DataFrame 以避免重複 API 呼叫（multi_signal.py 批次呼叫時使用）。

    Parameters
    ----------
    sector_id   : 板塊 ID
    stocks      : 板塊成員股票代號清單
    raw_results : multi_signal 各燈原始結果（用於取燈2法人集合）
    fetcher     : DataFetcher 實例（有磁碟快取，重複呼叫不影響性能）
    config      : AppConfig 實例
    price_df / volume_df / pe_df / ocf_df : 預取的 DataFrame（可選）

    Returns
    -------
    {
        "junk_ratio":       float,          # 垃圾股比例 0.0–1.0
        "junk_flags":       dict,           # 各過濾項明細
        "quality_warning":  bool,
        "enabled_filters":  list[str],
        "details":          str,
    }
    """
    if not stocks:
        return _empty()

    enabled   = _enabled_filters(config)
    threshold = float(getattr(config, "JUNK_SECTOR_THRESHOLD", 0.60))

    if not enabled:
        return {
            "junk_ratio": 0.0, "junk_flags": {},
            "quality_warning": False, "enabled_filters": [],
            "details": "所有過濾項已關閉",
        }

    # ── 讀取市場資料（使用傳入值或從快取取得）─────────────────────────────
    if price_df is None and ("po" in enabled):
        price_df = _safe_get(fetcher, _PRICE_KEY)
    if volume_df is None and ("san" in enabled):
        volume_df = _safe_get(fetcher, _VOLUME_KEY)
    if pe_df is None and ("pian" in enabled):
        pe_df = _safe_get(fetcher, _PE_KEY)
    if ocf_df is None and ("xu" in enabled):
        ocf_df = _safe_get(fetcher, _OCF_KEY)

    # ── 從 raw_results 取燈2法人集合 ─────────────────────────────────────
    lamp2 = raw_results.get("燈2 法人共振", {}).get(sector_id, {})
    inst_stocks: Set[str] = (
        set(lamp2.get("lit_stocks",   []))
        | set(lamp2.get("foreign_only", []))
        | set(lamp2.get("trust_only",   []))
    )

    # ── 逐股判斷 ──────────────────────────────────────────────────────────
    po_stocks:   List[str] = []
    gu_stocks:   List[str] = []
    xu_stocks:   List[str] = []
    pian_stocks: List[str] = []
    san_stocks:  List[str] = []

    for sid in stocks:
        # 破：price < MA120 且 MA120 在最近20日下彎
        if "po" in enabled and price_df is not None and sid in price_df.columns:
            s = price_df[sid].dropna().iloc[-(_PO_MA_PERIOD * 2):]
            if len(s) >= _PO_MA_PERIOD:
                ma = s.rolling(_PO_MA_PERIOD).mean().dropna()
                if len(ma) >= _PO_SLOPE_DAYS + 1:
                    below_ma   = float(s.iloc[-1]) < float(ma.iloc[-1])
                    ma_falling = float(ma.iloc[-1]) < float(ma.iloc[-(_PO_SLOPE_DAYS + 1)])
                    if below_ma and ma_falling:
                        po_stocks.append(sid)

        # 孤：不在任何法人集合中
        if "gu" in enabled and sid not in inst_stocks:
            gu_stocks.append(sid)

        # 虛：最近一期營業現金流量為負
        if "xu" in enabled and ocf_df is not None and sid in ocf_df.columns:
            ocf_s = ocf_df[sid].dropna()
            if not ocf_s.empty and float(ocf_s.iloc[-1]) < 0:
                xu_stocks.append(sid)

        # 偏：PE < 0 或 PE > 80
        if "pian" in enabled and pe_df is not None and sid in pe_df.columns:
            pe_s = pe_df[sid].ffill().dropna()
            if not pe_s.empty:
                pe_val = float(pe_s.iloc[-1])
                if pe_val < 0 or pe_val > 80:
                    pian_stocks.append(sid)

        # 散：近20日平均日成交量 < 50萬股
        if "san" in enabled and volume_df is not None and sid in volume_df.columns:
            vol_s = volume_df[sid].dropna().iloc[-20:]
            if not vol_s.empty and float(vol_s.mean()) < _SAN_MIN_VOLUME:
                san_stocks.append(sid)

    # ── 彙算板塊垃圾比例（聯集去重）──────────────────────────────────────
    all_junk = (
        set(po_stocks) | set(gu_stocks) | set(xu_stocks)
        | set(pian_stocks) | set(san_stocks)
    )
    n_total    = len(stocks)
    junk_ratio = round(len(all_junk) / n_total, 4) if n_total > 0 else 0.0
    quality_warning = junk_ratio >= threshold

    junk_flags: Dict[str, Any] = {}
    _all_flags = [
        ("po",   "破", po_stocks),
        ("gu",   "孤", gu_stocks),
        ("xu",   "虛", xu_stocks),
        ("pian", "偏", pian_stocks),
        ("san",  "散", san_stocks),
    ]
    for key, label, slist in _all_flags:
        if key in enabled:
            junk_flags[key] = {
                "label":  label,
                "count":  len(slist),
                "ratio":  round(len(slist) / n_total, 3) if n_total else 0.0,
                "stocks": slist,
            }

    active = [v["label"] for v in junk_flags.values() if v["count"] > 0]
    details = (
        f"垃圾股比例={junk_ratio*100:.1f}% ({len(all_junk)}/{n_total}股)"
        + (f" | 觸發: {'、'.join(active)}" if active else " | 品質良好")
        + (" ⚠️品質警示" if quality_warning else "")
    )

    return {
        "junk_ratio":      junk_ratio,
        "junk_flags":      junk_flags,
        "quality_warning": quality_warning,
        "enabled_filters": list(enabled),
        "details":         details,
    }


def _enabled_filters(config) -> List[str]:
    """依 config 開關回傳啟用的過濾項清單。"""
    if not getattr(config, "JUNK_FILTER_ENABLED", True):
        return []
    result: List[str] = []
    for cfg_key, label in [
        ("JUNK_FILTER_PO",   "po"),
        ("JUNK_FILTER_GU",   "gu"),
        ("JUNK_FILTER_XU",   "xu"),
        ("JUNK_FILTER_PIAN", "pian"),
        ("JUNK_FILTER_SAN",  "san"),
    ]:
        if getattr(config, cfg_key, True):
            result.append(label)
    return result


def _safe_get(fetcher, key: str) -> Optional[pd.DataFrame]:
    """安全取得 DataFrame，失敗回傳 None（不中斷流程）。"""
    try:
        df = fetcher.get(key)
        return df if isinstance(df, pd.DataFrame) else None
    except Exception as e:
        logger.debug("P3 品質過濾: 無法取得 %s — %s", key, e)
        return None


def _empty() -> Dict[str, Any]:
    return {
        "junk_ratio":      0.0,
        "junk_flags":      {},
        "quality_warning": False,
        "enabled_filters": [],
        "details":         "無成員股票",
    }
