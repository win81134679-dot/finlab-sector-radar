"""
rotation_pairs.py — 板塊領先落後 / 接棒訊號（輪動層）

照「TEJ 三層藍圖」：某些板塊有固定輪動順序（如航運轉強領先半導體）。
本模組做兩件事：

  1. lead_lag_correlation()：純 numpy 滯後互相關（無 statsmodels 依賴，
     保持每日管道輕量）。離線探勘腳本 scripts/discover_rotation_pairs.py
     會跑全板塊兩兩關係 + 可選 Granger，產出 output/rotation/pairs.json
     供**人工審核固化**（避免過度擬合）。

  2. detect_handoffs()：線上接棒訊號。對固化的領先→落後對 (A→B)，
     當 A 的 RSI 分位 ≥ 80（領先板塊過熱）且 B 仍在萌芽/確認期（尚未發動）
     → 標記 B 的 rotation_handoff。

學術依據：Granger (1969) 因果；Hong, Torous & Valkanov (2007, JFE) 產業領先大盤；
Menzly & Ozbas (2010, J. Finance) 供應鏈產業間可預測的報酬領先落後。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_MAX_LAG = 20          # 最大滯後天數（約一個月交易日）
_LEADING_RSI_PCTL = 80.0       # 領先板塊 RSI 分位門檻（過熱→可能接棒給落後者）
_HANDOFF_STAGES = ("萌芽期", "確認期")   # 落後板塊須在這些階段（尚未發動）


def lead_lag_correlation(
    a: np.ndarray,
    b: np.ndarray,
    max_lag: int = _DEFAULT_MAX_LAG,
) -> Tuple[int, float]:
    """
    A 領先 B 的最佳滯後與相關係數（純 numpy）。
    對 lag = 1..max_lag，計算 corr(a[:-lag], b[lag:])，取絕對值最大者。
    回傳 (best_lag, corr)；best_lag>0 表示 A 領先 B 約 best_lag 期。
    資料不足或無變異 → (0, 0.0)。
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n < max_lag + 5:
        return 0, 0.0
    a, b = a[-n:], b[-n:]

    best_lag, best_corr = 0, 0.0
    for lag in range(1, max_lag + 1):
        x, y = a[:-lag], b[lag:]
        if len(x) < 5 or np.std(x) == 0 or np.std(y) == 0:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        if abs(c) > abs(best_corr):
            best_lag, best_corr = lag, c
    return best_lag, round(best_corr, 4)


def detect_handoffs(
    sectors_rotation: Dict[str, Dict[str, Any]],
    sector_levels: Dict[str, str],
    pairs: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    線上接棒偵測。

    Parameters
    ----------
    sectors_rotation : {sid: rotation dict}（含 rsi_percentile）
    sector_levels    : {sid: level}（強烈關注/觀察中/忽略；用 cycle_stage 更精準，見下）
    pairs            : 固化的領先→落後對
        [{"leader": sid_a, "laggard": sid_b, "lag_days": n, "corr": c}, ...]

    Returns
    -------
    {laggard_sid: {"from": leader, "from_name": ..., "lag_days": n,
                   "corr": c, "signal": "接棒候選"}}
    僅在 leader RSI 分位 ≥ 80 且 laggard 仍在萌芽/確認期時觸發。
    """
    handoffs: Dict[str, Dict[str, Any]] = {}
    for pair in pairs:
        leader = pair.get("leader")
        laggard = pair.get("laggard")
        if not leader or not laggard:
            continue
        lead_rot = sectors_rotation.get(leader, {})
        lead_pctl = lead_rot.get("rsi_percentile")
        if lead_pctl is None or float(lead_pctl) < _LEADING_RSI_PCTL:
            continue
        # 落後板塊須尚未發動（萌芽/確認期）
        lag_stage = sector_levels.get(laggard)
        if lag_stage not in _HANDOFF_STAGES:
            continue
        handoffs[laggard] = {
            "from": leader,
            "lag_days": pair.get("lag_days"),
            "corr": pair.get("corr"),
            "signal": "接棒候選",
        }
    return handoffs


def load_pairs(config) -> List[Dict[str, Any]]:
    """讀 output/rotation/pairs.json（人工審核固化的對）。無則回空 list。"""
    import json
    from pathlib import Path
    path = Path(getattr(config, "OUTPUT_DIR", Path("output"))) / "rotation" / "pairs.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("pairs", []) if isinstance(data, dict) else (data or [])
    except Exception as e:
        logger.warning("讀取 rotation/pairs.json 失敗: %s", e)
        return []


__all__ = ["lead_lag_correlation", "detect_handoffs", "load_pairs"]
