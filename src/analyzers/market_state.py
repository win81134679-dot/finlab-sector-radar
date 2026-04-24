"""
P1 — 大盤三態分類器（軟版）

讀取 TAIEX 收盤指數，計算：
  - TAIEX vs 200MA 相對位置（正=上方%，負=下方%）
  - 近20日動能（報酬率%）

輸出三態：bull（牛市多頭）| sideways（震盪整理）| bear（熊市空頭）

設計原則（討論點 A 軟版）：
  - 不修改七燈亮燈閾值
  - 僅注入 signals_latest.json 的 market_state 欄位
  - 前端依狀態顯示警示 banner 和置信度標籤
  - 所有異常情況下退化為 unknown，不中斷主流程
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TAIEX_KEY = "taiex_total_index:收盤指數"
_TAIEX_COL = "發行量加權股價指數"


def analyze(fetcher, config) -> Dict[str, Any]:
    """
    Returns:
      {
        "state":               "bull" | "sideways" | "bear" | "unknown",
        "state_zh":            "牛市多頭" | "震盪整理" | "熊市空頭" | "數據不足",
        "confidence":          float  0.0–1.0,
        "taiex_vs_200ma_pct":  float | None,   # 正=MA上方%，負=MA下方%
        "momentum_20d_pct":    float | None,   # 近20日報酬率%
        "details":             str,
      }
    """
    bull_ma       = int(getattr(config, "MARKET_STATE_BULL_MA", 200))
    momentum_days = int(getattr(config, "MARKET_STATE_MOMENTUM_DAYS", 20))

    try:
        taiex_df = fetcher.get(_TAIEX_KEY)
        if taiex_df is None or taiex_df.empty:
            logger.warning("P1 大盤三態: 無法取得 TAIEX 數據")
            return _unknown()

        taiex: pd.Series = (
            taiex_df[_TAIEX_COL].dropna()
            if _TAIEX_COL in taiex_df.columns
            else taiex_df.iloc[:, 0].dropna()
        )

        if len(taiex) < bull_ma:
            logger.warning("P1 大盤三態: TAIEX 資料不足 %d 日", bull_ma)
            return _unknown()

        current   = float(taiex.iloc[-1])
        ma_val    = float(taiex.rolling(bull_ma).mean().iloc[-1])
        vs_ma_pct = round((current - ma_val) / ma_val * 100, 2) if ma_val else 0.0

        if len(taiex) > momentum_days:
            prev         = float(taiex.iloc[-(momentum_days + 1)])
            momentum_pct = round((current - prev) / prev * 100, 2) if prev else 0.0
        else:
            momentum_pct = 0.0

        # ── 三態判斷 ────────────────────────────────────────────────────
        # 牛市：TAIEX > 200MA 且近20日動能正
        # 熊市：TAIEX 低於200MA -5% 且動能 < -2%（避免橫盤初跌誤判）
        # 震盪：介於兩者之間
        if vs_ma_pct > 0 and momentum_pct > 0:
            state, state_zh = "bull", "牛市多頭"
            _pos = min(1.0, vs_ma_pct / 10.0) * 0.6 + min(1.0, momentum_pct / 5.0) * 0.4
            confidence = round(min(1.0, _pos), 3)
        elif vs_ma_pct < -5 and momentum_pct < -2:
            state, state_zh = "bear", "熊市空頭"
            _neg = min(1.0, abs(vs_ma_pct) / 10.0) * 0.6 + min(1.0, abs(momentum_pct) / 5.0) * 0.4
            confidence = round(min(1.0, _neg), 3)
        else:
            state, state_zh = "sideways", "震盪整理"
            confidence = 0.5

        return {
            "state":              state,
            "state_zh":           state_zh,
            "confidence":         confidence,
            "taiex_vs_200ma_pct": vs_ma_pct,
            "momentum_20d_pct":   momentum_pct,
            "details": (
                f"TAIEX={current:,.0f} vs {bull_ma}MA={ma_val:,.0f} ({vs_ma_pct:+.1f}%)"
                f" | 20日動能={momentum_pct:+.1f}%"
            ),
        }

    except Exception as e:
        logger.warning("P1 大盤三態: 計算失敗 — %s", e)
        return _unknown()


def _unknown() -> Dict[str, Any]:
    return {
        "state":              "unknown",
        "state_zh":           "數據不足",
        "confidence":         0.0,
        "taiex_vs_200ma_pct": None,
        "momentum_20d_pct":   None,
        "details":            "TAIEX 數據不足，無法判斷市場狀態",
    }
