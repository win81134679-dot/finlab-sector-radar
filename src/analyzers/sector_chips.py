"""
sector_chips.py — 板塊級法人籌碼聚合 + 主力進駐偵測（輪動層 L3）

照「TEJ 三層藍圖」第三層移植進板塊偵測網站。原始實作在
`台股主動式ETF換倉策略/src/signals/sector_chips.py`，此處改用本專案的
`sector_map`（59 策展板塊）+ `fetcher`，而非 ETF 專案的 sym2cat 字典。

⚠️ 權重說明（先不動，待回測決定）：
  目前沿用藍圖「外資×2 + 投信×1」（一般性「研究資源差異」直覺）。
  使用者目標為**中長期**持有 → P5/P6 台股實證支持外資為主角
  （外資持股比例方向性 + 月營收領先）。故中長期下此權重合理；
  最終值由 backtest 決定（INST_FLOW_WEIGHT_* 為 config 候選常數）。
  自營商現貨多為權證避險帳（P1: 4–90× 自營；反指標）→ 權重 0，不納入。

主力進駐五條件（藍圖原樣）：連續買超≥5日 / 累積淨正 / 近期加速 /
Z-Score>1.5 / 突破近 60 日 85 分位。

資料：fetcher.get(法人買賣超)（與燈2 同來源，已快取）。
輸出（per sector，注入 signals_latest.json）：
  chip_flow: { score, level, consec_buy, cum_chip, accel, z_score, breakout }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_FOREIGN_KEY = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST_KEY = "institutional_investors_trading_summary:投信買賣超股數"

_WINDOW = 20              # 主力進駐判定窗口
_ACCEL_MIN_BASE = 1e3     # 加速度最小分母（股數），避免近 0 均值假性放大


@dataclass(frozen=True)
class MainForceSignal:
    score: int
    level: str
    consec_buy: int
    cum_chip: float
    accel: float
    z_score: float
    breakout: bool


_LEVEL = {5: "★★★ 強力進駐", 4: "★★ 明顯布局", 3: "★ 初步觀察",
          2: "中性", 1: "觀望", 0: "無訊號"}


def _sector_flow_series(
    foreign_df: pd.DataFrame | None,
    trust_df: pd.DataFrame | None,
    stocks: list[str],
    foreign_weight: float,
    trust_weight: float,
) -> pd.Series:
    """板塊合力流入時序 = Σ(外資×w_f + 投信×w_t)（成分股加總）。"""
    parts = []
    if foreign_df is not None:
        cols = [s for s in stocks if s in foreign_df.columns]
        if cols:
            parts.append(foreign_df[cols].fillna(0).sum(axis=1) * foreign_weight)
    if trust_df is not None:
        cols = [s for s in stocks if s in trust_df.columns]
        if cols:
            parts.append(trust_df[cols].fillna(0).sum(axis=1) * trust_weight)
    if not parts:
        return pd.Series(dtype=float)
    # 對齊 index 後相加
    combined = parts[0]
    for p in parts[1:]:
        combined = combined.add(p, fill_value=0)
    return combined.dropna()


def detect_main_force(series: pd.Series, *, window: int = _WINDOW) -> MainForceSignal:
    """主力進駐五條件判定（藍圖原樣，含小分母防護）。"""
    series = series.dropna()
    if len(series) < window:
        return MainForceSignal(0, _LEVEL[0], 0, 0.0, 0.0, 0.0, False)

    recent = series.tail(window)

    # ① 連續買超天數（從最近往回數）
    pos = (recent > 0).astype(int).values[::-1]
    consec = 0
    for v in pos:
        if v:
            consec += 1
        else:
            break

    # ② 累積淨流入
    cum = float(recent.sum())

    # ③ 加速度（近5日均 / 近window均）；小分母防護（避免正負交錯近 0 時爆大）
    base = recent.mean()
    accel = float(recent.tail(5).mean() / base) if abs(base) >= _ACCEL_MIN_BASE else 0.0

    # ④ Z-Score（近 60 日）
    tail60 = series.tail(60)
    mu, sigma = tail60.mean(), tail60.std()
    z = float((recent.mean() - mu) / sigma) if sigma and not np.isnan(sigma) else 0.0

    # ⑤ 突破近 60 日 85 分位
    breakout = bool(recent.tail(5).max() > series.tail(60).quantile(0.85))

    score = int(sum([consec >= 5, cum > 0, accel > 1.5, z > 1.5, breakout]))
    return MainForceSignal(
        score, _LEVEL[score], consec, round(cum, 0), round(accel, 2),
        round(z, 2), breakout,
    )


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    """
    回傳 {sector_id: {chip_flow..., signal, score, details}}。
    signal/score 不計入七燈總分（輪動層為附加維度）。
    """
    fw = float(getattr(config, "INST_FLOW_WEIGHT_FOREIGN", 2.0))
    tw = float(getattr(config, "INST_FLOW_WEIGHT_TRUST", 1.0))
    window = int(getattr(config, "INST_FLOW_WINDOW", _WINDOW))

    results: Dict[str, Dict[str, Any]] = {}

    foreign_df = fetcher.get(_FOREIGN_KEY)
    trust_df = fetcher.get(_TRUST_KEY)
    if foreign_df is None and trust_df is None:
        logger.warning("板塊籌碼: 無法取得法人買賣超數據")
        return results

    for sid in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sid)
        flow = _sector_flow_series(foreign_df, trust_df, stocks, fw, tw)
        sig = detect_main_force(flow, window=window)

        results[sid] = {
            "chip_flow":  asdict(sig),
            "signal":     sig.score >= 3,          # ★ 以上視為布局訊號
            "score":      round(sig.score / 5.0, 3),
            "details": (
                f"{sig.level} | 連買{sig.consec_buy}日 | "
                f"累積{sig.cum_chip:,.0f} | 加速{sig.accel:.2f}x"
                + (" | 突破✓" if sig.breakout else "")
            ),
        }

    return results


__all__ = ["analyze", "detect_main_force", "MainForceSignal"]
