"""
sector_rsi.py — 產業 RSI 輪動偵測（輪動層 L2）

照「TEJ 三層藍圖」第二層移植進板塊偵測網站。原始實作在
`台股主動式ETF換倉策略/src/signals/sector_rsi.py`，此處改用本專案的
`sector_map`（59 個策展板塊）+ `fetcher`（FinLab 價格），而非 ETF 專案的
sym2cat 字典。

藍圖核心：用 60 日 RSI 偵測哪個產業動能轉強；高檔產業（RSI≥分位上界）
可能領先落後產業數週上漲（接棒訊號的燃料）。

設計（與 ETF 專案一致，且修正 Wilder 邊界）：
  - 產業指數 = 板塊成分股「等權累積報酬指數」（從 1.0 起算）
  - RSI = Wilder 60 日；零跌損 → 100、零漲益 → 0、完全持平 → 50（非 NaN）
  - 動態分位：用過去 N 日該板塊 RSI 的 80/20 分位當超買/超賣界（自適應，
    避免固定 65/35 過度擬合不同景氣環境）

輸出（per sector，注入 signals_latest.json）：
  rsi_60 / rsi_percentile / rsi_state / rsi_slope_5d / sector_momentum_pct
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PRICE_KEY = "price:收盤價"

# 與 config 對齊的預設（缺 config 時 fallback）
_RSI_PERIOD = 60          # Wilder RSI 週期（藍圖用 60）
_PCTL_LOOKBACK = 252      # 動態分位回看（約一年）
_SLOPE_DAYS = 5           # RSI 斜率（近 N 日變化 = 轉強速度）
_MOM_LOOKBACK = 60        # 產業動能回看（近 N 日報酬）
_MIN_MEMBERS = 2          # 板塊至少成分股數（少於則資料意義弱，仍計算）


def _wilder_rsi(series: pd.Series, period: int) -> pd.Series:
    """
    Wilder RSI，含正確邊界處理：
      - avg_loss=0 且 avg_gain>0 → 100（全漲無跌）
      - avg_gain=0 且 avg_loss>0 → 0（全跌無漲，rs=0 自然得 0）
      - 兩者皆 0（完全持平）→ 50（中性，而非 NaN）
      - rolling 期數不足 → NaN
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    out = out.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    valid = avg_gain.notna() & avg_loss.notna()
    return out.where(valid)


def _sector_index(price_df: pd.DataFrame, stocks: list[str]) -> pd.Series:
    """板塊成分股等權累積報酬指數（從 1.0 起算）。"""
    avail = [s for s in stocks if s in price_df.columns]
    if len(avail) < 1:
        return pd.Series(dtype=float)
    ret = price_df[avail].ffill().pct_change(fill_method=None)
    eq_ret = ret.mean(axis=1)               # 等權日報酬
    return (1.0 + eq_ret.fillna(0)).cumprod()


def _rsi_state(rsi_val: float, pctl: float | None) -> str:
    """以動態分位（若有）或固定門檻判定 RSI 狀態。"""
    if rsi_val != rsi_val:  # NaN
        return "資料不足"
    if pctl is not None:
        if pctl >= 80:
            return "超買"
        if pctl >= 60:
            return "偏多"
        if pctl <= 20:
            return "超賣"
        if pctl <= 40:
            return "偏空"
        return "中性"
    # fallback 固定門檻
    if rsi_val >= 70:
        return "超買"
    if rsi_val >= 55:
        return "偏多"
    if rsi_val <= 30:
        return "超賣"
    if rsi_val <= 45:
        return "偏空"
    return "中性"


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    """
    回傳 {sector_id: {rsi_60, rsi_percentile, rsi_state, rsi_slope_5d,
                      sector_momentum_pct, signal, score, details}}。
    signal/score 不計入七燈總分（輪動層為附加維度）。
    """
    period      = int(getattr(config, "SECTOR_RSI_PERIOD", _RSI_PERIOD))
    pctl_look   = int(getattr(config, "SECTOR_RSI_PERCENTILE_LOOKBACK", _PCTL_LOOKBACK))
    slope_days  = int(getattr(config, "SECTOR_RSI_SLOPE_DAYS", _SLOPE_DAYS))
    mom_look    = int(getattr(config, "SECTOR_RSI_MOMENTUM_LOOKBACK", _MOM_LOOKBACK))

    results: Dict[str, Dict[str, Any]] = {}

    price_df = fetcher.get(_PRICE_KEY)
    if price_df is None or price_df.empty:
        logger.warning("產業RSI: 無法取得價格數據")
        return results

    for sid in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sid)
        idx = _sector_index(price_df, stocks)
        if len(idx) < period + 1:
            results[sid] = _empty()
            continue

        rsi_series = _wilder_rsi(idx, period).dropna()
        if rsi_series.empty:
            results[sid] = _empty()
            continue

        rsi_val = float(rsi_series.iloc[-1])

        # 動態分位（最新 RSI 在過去 pctl_look 日 RSI 分佈的位置）
        hist = rsi_series.tail(pctl_look)
        pctl: float | None = None
        if len(hist) >= 20:
            pctl = round(float((hist < rsi_val).sum()) / len(hist) * 100, 1)

        # RSI 斜率（近 slope_days 變化）
        slope = None
        if len(rsi_series) > slope_days:
            slope = round(rsi_val - float(rsi_series.iloc[-(slope_days + 1)]), 2)

        # 產業動能（近 mom_look 日報酬）
        mom_pct = None
        if len(idx) > mom_look:
            base = float(idx.iloc[-(mom_look + 1)])
            mom_pct = round((float(idx.iloc[-1]) - base) / base * 100, 2) if base else None

        state = _rsi_state(rsi_val, pctl)
        # 「轉入」訊號：RSI 高於 50 且近 N 日上升（藍圖：動量斜率上升 = 輪動開始）
        signal = bool(slope is not None and slope > 0 and rsi_val > 50)

        results[sid] = {
            "rsi_60":              round(rsi_val, 1),
            "rsi_percentile":      pctl,
            "rsi_state":           state,
            "rsi_slope_5d":        slope,
            "sector_momentum_pct": mom_pct,
            "signal":              signal,
            "score":               round(min(max((rsi_val - 50) / 30, 0.0), 1.0), 3),
            "member_count":        len([s for s in stocks if s in price_df.columns]),
            "details": (
                f"RSI={rsi_val:.1f}"
                + (f"（{pctl:.0f}分位）" if pctl is not None else "")
                + f" | {state}"
                + (f" | 斜率{slope:+.1f}" if slope is not None else "")
                + (f" | 動能{mom_pct:+.1f}%" if mom_pct is not None else "")
            ),
        }

    return results


def _empty() -> Dict[str, Any]:
    return {
        "rsi_60": None, "rsi_percentile": None, "rsi_state": "資料不足",
        "rsi_slope_5d": None, "sector_momentum_pct": None,
        "signal": False, "score": 0.0, "member_count": 0,
        "details": "數據不足",
    }


__all__ = ["analyze"]
