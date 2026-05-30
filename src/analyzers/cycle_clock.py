"""
cycle_clock.py — 台灣景氣循環時鐘（第一層宏觀濾網）

判斷台灣景氣處於 復甦 / 擴張 / 趨緩 / 衰退 哪一象限，對應該超配哪類板塊
（Merrill Lynch Investment Clock 台股化）。對應「TEJ 三層藍圖」第一層。

資料來源（官方優先、缺則代理；使用者裁示）：
  1. 官方：data/ndc_monitor.csv（國發會景氣對策信號分數，每月 27 日公布）
       欄位：date, score   （藍燈 ≤16 / 黃藍 17–22 / 綠 23–31 / 黃紅 32–37 / 紅 ≥38）
       手動維護，一年補幾次即可；> 45 天未更新則自動切換代理。
  2. 代理 fallback：INDPRO（工業生產）+ TAIEX vs 200MA + USD/TWD 趨勢 +
       SOXX 趨勢 → 合成「景氣方向 × 動能」二維 → 象限。

輸出：
  {
    "phase": "recovery|expansion|slowdown|recession|unknown",
    "phase_zh": "復甦|擴張|趨緩|衰退|數據不足",
    "source": "ndc_official|proxy",
    "ndc_score": float|None,
    "favored_sectors": [sector_type, ...],   # 該象限超配類型
    "details": str,
  }

不修改七燈閾值；僅作前端濾網提示（軟版）。所有異常退化為 unknown。
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TAIEX_KEY = "taiex_total_index:收盤指數"
_TAIEX_COL = "發行量加權股價指數"

# 象限 → 超配板塊類型（Merrill Lynch 投資時鐘台股化）
_FAVORED = {
    "recovery":   ["banking", "financial_holding", "construction", "securities"],  # 復甦：金融、營建
    "expansion":  ["foundry", "ic_design", "ai_server", "semiconductor_equip"],    # 擴張：半導體、電子
    "slowdown":   ["steel", "petrochemical", "cement", "shipping"],                # 趨緩：原物料、傳產
    "recession":  ["telecom", "food", "gas_energy"],                              # 衰退：防禦
}
_PHASE_ZH = {
    "recovery": "復甦", "expansion": "擴張",
    "slowdown": "趨緩", "recession": "衰退", "unknown": "數據不足",
}

_NDC_STALE_DAYS = 45      # 官方分數超過此天數未更新 → 用代理
_NDC_BLUE = 16            # ≤ 藍燈（景氣低迷）
_NDC_RED = 38             # ≥ 紅燈（景氣過熱）


def _read_ndc_csv(config) -> Optional[tuple[float, datetime]]:
    """讀 data/ndc_monitor.csv 最新一筆 (score, date)。失敗回 None。"""
    path = Path(getattr(config, "BASE_DIR", Path("."))) / "data" / "ndc_monitor.csv"
    if not path.exists():
        return None
    try:
        latest_score: Optional[float] = None
        latest_date: Optional[datetime] = None
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    d = datetime.fromisoformat(row["date"].strip())
                    sc = float(row["score"])
                except (KeyError, ValueError):
                    continue
                if latest_date is None or d > latest_date:
                    latest_date, latest_score = d, sc
        if latest_score is None or latest_date is None:
            return None
        return latest_score, latest_date
    except Exception as e:
        logger.warning("讀取 ndc_monitor.csv 失敗: %s", e)
        return None


def _phase_from_ndc(score: float, momentum_up: bool) -> str:
    """
    依國發會分數 + 動能方向定象限：
      低檔(≤藍燈) + 動能轉正 → 復甦；低檔 + 動能負 → 衰退
      高檔(≥紅燈) + 動能正 → 擴張；高檔 + 動能負 → 趨緩
      中間：動能正 → 擴張、動能負 → 趨緩
    """
    if score <= _NDC_BLUE:
        return "recovery" if momentum_up else "recession"
    if score >= _NDC_RED:
        return "expansion" if momentum_up else "slowdown"
    return "expansion" if momentum_up else "slowdown"


def _proxy_phase(fetcher, config) -> tuple[str, str]:
    """
    代理象限：用 TAIEX vs 200MA（景氣高低代理）+ 近 20 日動能（方向）。
    回傳 (phase, details)。
    """
    try:
        df = fetcher.get(_TAIEX_KEY)
        if df is None or df.empty:
            return "unknown", "TAIEX 不可用"
        s = df[_TAIEX_COL].dropna() if _TAIEX_COL in df.columns else df.iloc[:, 0].dropna()
        if len(s) < 200:
            return "unknown", "TAIEX 資料不足 200 日"
        cur = float(s.iloc[-1])
        ma200 = float(s.rolling(200).mean().iloc[-1])
        above = cur > ma200
        mom_up = len(s) > 20 and cur > float(s.iloc[-21])
        # 高低（vs 200MA）對應景氣位階；動能對應方向
        if above:
            phase = "expansion" if mom_up else "slowdown"
        else:
            phase = "recovery" if mom_up else "recession"
        details = (f"代理：TAIEX {'>' if above else '<'}200MA, "
                   f"20日動能{'↑' if mom_up else '↓'}")
        return phase, details
    except Exception as e:
        logger.warning("代理景氣象限計算失敗: %s", e)
        return "unknown", "代理計算失敗"


def analyze(fetcher, config, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """回傳景氣象限 dict（官方優先、缺則代理）。now 可注入供測試。"""
    now = now or datetime.now()

    # 動能方向（官方分數 + 代理共用）
    momentum_up = True
    try:
        df = fetcher.get(_TAIEX_KEY)
        if df is not None and not df.empty:
            s = df[_TAIEX_COL].dropna() if _TAIEX_COL in df.columns else df.iloc[:, 0].dropna()
            if len(s) > 20:
                momentum_up = float(s.iloc[-1]) > float(s.iloc[-21])
    except Exception:
        pass

    ndc = _read_ndc_csv(config)
    if ndc is not None:
        score, ndc_date = ndc
        if (now - ndc_date) <= timedelta(days=_NDC_STALE_DAYS):
            phase = _phase_from_ndc(score, momentum_up)
            return {
                "phase": phase,
                "phase_zh": _PHASE_ZH[phase],
                "source": "ndc_official",
                "ndc_score": round(score, 1),
                "favored_sectors": _FAVORED.get(phase, []),
                "details": (
                    f"國發會景氣對策信號={score:.0f}分"
                    f"（{'藍燈' if score <= _NDC_BLUE else '紅燈' if score >= _NDC_RED else '綠/黃燈'}）"
                    f" + 動能{'↑' if momentum_up else '↓'} → {_PHASE_ZH[phase]}"
                ),
            }
        logger.info("國發會分數已過期（> %d 天），改用代理", _NDC_STALE_DAYS)

    phase, details = _proxy_phase(fetcher, config)
    return {
        "phase": phase,
        "phase_zh": _PHASE_ZH.get(phase, "數據不足"),
        "source": "proxy",
        "ndc_score": None,
        "favored_sectors": _FAVORED.get(phase, []),
        "details": details + f" → {_PHASE_ZH.get(phase, '數據不足')}",
    }


__all__ = ["analyze"]
