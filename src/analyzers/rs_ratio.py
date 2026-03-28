"""
燈5 — 板塊相對強度 RRG（Relative Rotation Graph 簡化版）

RS-Ratio  = 板塊均價相對 TWII 的超額報酬（14日 EMA 平滑）
RS-Moment = RS-Ratio 的 10日 EMA 斜率（動能方向）

象限判斷：
  Right-Upper (領先): RS-Ratio > 1 且 RS-Momentum > 0 → 亮燈 ✅
  Right-Lower (轉弱): RS-Ratio > 1 且 RS-Momentum < 0 → 警戒
  Left-Upper  (改善): RS-Ratio < 1 且 RS-Momentum > 0 → 觀察
  Left-Lower  (落後): RS-Ratio < 1 且 RS-Momentum < 0 → 忽略
"""
import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PRICE_KEY = "price:收盤價"
_TAIEX_KEY = "taiex_total_index:收盤指數"
_TAIEX_COL = "發行量加權股價指數"   # TWII 的欄名（fallback 到第一欄）

_EMA_RS = 14      # RS-Ratio EMA 週期
_EMA_MOM = 10     # RS-Momentum EMA 週期


def _safe_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _compute_rr(sector_prices: pd.DataFrame, benchmark: pd.Series,
                lookback: int) -> tuple[float, float, str]:
    """
    計算板塊的 RS-Ratio 和 RS-Momentum。
    回傳 (rs_ratio, rs_momentum, quadrant)
    """
    # 等權重板塊均價
    avg = sector_prices.mean(axis=1).dropna()
    bm = benchmark.reindex(avg.index).dropna()
    common = avg.index.intersection(bm.index)

    if len(common) < lookback:
        return float("nan"), float("nan"), "insufficient_data"

    p = avg.loc[common].iloc[-lookback:]
    b = bm.loc[common].iloc[-lookback:]

    # 以第一個共同點為基準，計算累積相對表現
    p_norm = p / float(p.iloc[0])
    b_norm = b / float(b.iloc[0])
    rs = p_norm / b_norm  # 相對強度比率原始值

    rs_ema = _safe_ema(rs, _EMA_RS)
    rs_ratio = float(rs_ema.iloc[-1])

    # RS-Momentum = RS-Ratio 的 EMA 化斜率
    rs_mom_raw = rs_ema.pct_change()
    rs_mom_ema = _safe_ema(rs_mom_raw.dropna(), _EMA_MOM)
    rs_momentum = float(rs_mom_ema.iloc[-1]) if not rs_mom_ema.empty else 0.0

    # 象限判斷（以 1.0 為中心線）
    if rs_ratio >= 1.0 and rs_momentum >= 0:
        quadrant = "領先(Right-Upper)"
    elif rs_ratio >= 1.0 and rs_momentum < 0:
        quadrant = "轉弱(Right-Lower)"
    elif rs_ratio < 1.0 and rs_momentum >= 0:
        quadrant = "改善(Left-Upper)"
    else:
        quadrant = "落後(Left-Lower)"

    return rs_ratio, rs_momentum, quadrant


def analyze(fetcher, sector_map, config) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    price_df = fetcher.get(_PRICE_KEY)
    taiex_df = fetcher.get(_TAIEX_KEY)

    if price_df is None or taiex_df is None:
        logger.warning("燈5: 無法取得價格或 TAIEX 數據")
        return results

    # 取 TAIEX 序列
    if _TAIEX_COL in taiex_df.columns:
        benchmark = taiex_df[_TAIEX_COL].dropna()
    else:
        benchmark = taiex_df.iloc[:, 0].dropna()

    lookback = config.RS_LOOKBACK_DAYS

    for sector_id in sector_map.all_sector_ids():
        stocks = sector_map.get_stocks(sector_id)
        avail = [s for s in stocks if s in price_df.columns]
        if not avail:
            results[sector_id] = _empty()
            continue

        sector_p = price_df[avail].iloc[-(lookback * 2):]

        rs_ratio, rs_moment, quadrant = _compute_rr(sector_p, benchmark, lookback)

        signal = (
            not np.isnan(rs_ratio)
            and rs_ratio >= 1.0
            and rs_moment >= 0
        )

        # ── 逐股 RS 計算（供 stock_scorer 個股評分用）──────────────────
        stock_rs: Dict[str, Any] = {}
        for stock_id in avail:
            s_p = price_df[[stock_id]].iloc[-(lookback * 2):]
            s_rs, s_mom, _ = _compute_rr(s_p, benchmark, lookback)
            stock_rs[stock_id] = {
                "rs_ratio":    round(s_rs, 4)  if not np.isnan(s_rs)  else None,
                "rs_momentum": round(s_mom, 6) if not np.isnan(s_mom) else None,
            }

        # 板塊內 rank_pct（0=最弱，100=最強）
        valid = {sid: v["rs_ratio"] for sid, v in stock_rs.items() if v["rs_ratio"] is not None}
        if len(valid) > 1:
            sorted_ids = sorted(valid, key=lambda x: valid[x])
            for i, sid in enumerate(sorted_ids):
                pct = round(i / (len(sorted_ids) - 1) * 100, 1)
                stock_rs[sid]["rank_pct"] = pct
        else:
            for sid in stock_rs:
                stock_rs[sid]["rank_pct"] = 50.0

        results[sector_id] = {
            "signal":       signal,
            "score":        round(min(max(rs_ratio - 0.8, 0) / 0.4, 1.0), 3) if not np.isnan(rs_ratio) else 0.0,
            "pct_lit":      100.0 if signal else 0.0,
            "rs_ratio":     round(rs_ratio, 4) if not np.isnan(rs_ratio) else None,
            "rs_momentum":  round(rs_moment, 6) if not np.isnan(rs_moment) else None,
            "quadrant":     quadrant,
            "total_stocks": len(avail),
            "stock_rs":     stock_rs,   # per-stock RS 數據（新增）
            "details": (
                f"RS-Ratio={rs_ratio:.3f} | RS-Mom={rs_moment:.4f} | {quadrant}"
                if not np.isnan(rs_ratio) else "數據不足"
            ),
        }

    return results


def _empty() -> Dict[str, Any]:
    return {
        "signal": False, "score": 0.0, "pct_lit": 0.0,
        "rs_ratio": None, "rs_momentum": None,
        "quadrant": "insufficient_data", "total_stocks": 0,
        "stock_rs": {}, "details": "無數據",
    }
