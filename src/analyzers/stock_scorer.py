"""
stock_scorer.py
個股三面合一評分引擎（台股適配版）

評分維度：
  基本面  5.5 pts  — 燈1 YoY +2 / MoM +0.5 / 燈3 +1 / EPS YoY>25% +2
  技術面  3.5 pts  — 燈4 tech_score=2 +2 / =1 +1 / dist_60ma 0-10% +0.5 / 燈5 rank>70 +1
  籌碼面  4.0 pts  — 燈2 共振 +2 / 外資獨買 +0.5 / 投信獨買 +0.5 / 燈6 +1
  加分    2.0 pts  — PE<板塊均值 +1 / ROE>15% +1

學術依據：
  - EPS YoY ≥ 25%：O'Neil (2009) CAN SLIM "C" (Current quarterly EPS growth ≥ 25%)
    實證驗證：Lutey, Crum & Rayome (2014, J. Accounting & Finance, cited 10)
    Lutey & Mukherjee (2023, SSRN) 簡化模型仍保持 25% 門檻
  - ROE ≥ 15%：Buffett 護城河標準；Greenblatt (2006) Magic Formula 排名因子

最高約 15 分；僅回傳分數 ≥ STOCK_MIN_DISPLAY 的個股
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── 常數（與 config 保持一致，避免循環 import） ────────────────────────────
_DIST_MAX   = 10.0   # dist_60ma_pct 甜蜜區上限 %（0 < dist ≤ 10% → +0.5）
_ROE_MIN    = 15.0   # ROE 加分下限 %（Greenblatt 2006 Magic Formula）
_EPS_YOY_T  = 25.0   # EPS YoY 加分門檻 %（O'Neil 2009 CAN SLIM "C"；Lutey et al. 2014 驗證）


# ────────────────────────────────────────────────────────────────────────────
def _latest_value(df: Optional[pd.DataFrame], stock_id: str) -> Optional[float]:
    """取 DataFrame 中指定欄位最新非 NaN 值（支援 ffill 後資料）。"""
    if df is None or stock_id not in df.columns:
        return None
    s = df[stock_id].dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _fundamental_date_label(df: Optional[pd.DataFrame]) -> str:
    """回傳基本面資料的最新日期標籤（如 2024-Q3）。"""
    if df is None or df.empty:
        return "N/A"
    try:
        idx = df.dropna(how="all").index
        if idx.empty:
            return "N/A"
        latest = pd.Timestamp(idx[-1])
        q = (latest.month - 1) // 3 + 1
        return f"{latest.year}-Q{q}"
    except Exception:
        return "N/A"


# ────────────────────────────────────────────────────────────────────────────
def score_stocks(
    sector_id: str,
    stock_ids: List[str],
    raw_results: Dict[str, Any],
    fetcher: Any,
    config: Any,
    change_pct_map: Optional[Dict[str, Optional[float]]] = None,
) -> Dict[str, Any]:
    """
    對指定板塊的個股執行三面合一評分。

    Parameters
    ----------
    sector_id       : 板塊 ID
    stock_ids       : 板塊成員股票代號清單
    raw_results     : multi_signal 逐燈原始結果（`raw` dict，key 為燈編號）
    fetcher         : DataFetcher 實例（用於 finlab data.get）
    config          : AppConfig 實例
    change_pct_map  : {stock_id: 漲跌幅%} 字典，由 multi_signal 一次拉取後傳入

    Returns
    -------
    dict  {stock_id: scoring_dict}  僅包含分數 ≥ STOCK_MIN_DISPLAY 的個股
    """
    if not stock_ids:
        return {}

    # ── 0. 讀取基本面 FinLab 數據（整市場一次拉，ffill 補齊季頻）─────────
    try:
        eps_df = fetcher.get("fundamental_features:稅後淨利成長率")
        if isinstance(eps_df, pd.DataFrame):
            eps_df = eps_df.ffill()
        else:
            eps_df = None
    except Exception as e:
        logger.warning("stock_scorer: 無法取得 EPS YoY 數據 — %s", e)
        eps_df = None

    try:
        pe_df = fetcher.get("price_earning_ratio:本益比")
        if isinstance(pe_df, pd.DataFrame):
            pe_df = pe_df.ffill()
        else:
            pe_df = None
    except Exception as e:
        logger.warning("stock_scorer: 無法取得 PE 數據 — %s", e)
        pe_df = None

    try:
        roe_df = fetcher.get("fundamental_features:ROE稅後")
        if isinstance(roe_df, pd.DataFrame):
            roe_df = roe_df.ffill()
        else:
            roe_df = None
    except Exception as e:
        logger.warning("stock_scorer: 無法取得 ROE 數據 — %s", e)
        roe_df = None

    fundamental_date = _fundamental_date_label(eps_df)

    # ── 1. 從各燈原始結果提取成員集合 ──────────────────────────────────────
    lamp1 = raw_results.get("燈1 月營收拐點", {}).get(sector_id, {})
    lamp2 = raw_results.get("燈2 法人共振",  {}).get(sector_id, {})
    lamp3 = raw_results.get("燈3 庫存循環",  {}).get(sector_id, {})
    lamp4 = raw_results.get("燈4 技術突破",  {}).get(sector_id, {})
    lamp5 = raw_results.get("燈5 相對強度",  {}).get(sector_id, {})
    lamp6 = raw_results.get("燈6 籌碼集中",  {}).get(sector_id, {})
    # 學術 bonus 分析器
    lamp_season  = raw_results.get("學術_季節動能",  {}).get(sector_id, {})
    lamp_accel   = raw_results.get("學術_營收加速",  {}).get(sector_id, {})

    lit1       = set(lamp1.get("lit_stocks",      []))   # 燈1 YoY 拐點
    mom_accel  = set(lamp1.get("mom_accel_stocks", []))  # 燈1 MoM 加速
    lit2       = set(lamp2.get("lit_stocks",      []))   # 燈2 共振
    foreign_only = set(lamp2.get("foreign_only",  []))   # 燈2 外資獨買
    trust_only   = set(lamp2.get("trust_only",    []))   # 燈2 投信獨買
    lit3       = set(lamp3.get("lit_stocks",      []))   # 燈3 庫存改善
    lit6       = set(lamp6.get("lit_stocks",      []))   # 燈6 籌碼集中
    short_cover = set(lamp6.get("short_cover",    []))   # 燈6 借券回補↑
    short_add   = set(lamp6.get("short_add",      []))   # 燈6 空頭加碼⚠

    # 學術 bonus
    resonance_label = lamp2.get("resonance_label", "外資牛市共振")  # 燈2 市場狀態標籤
    accel_stocks    = set(lamp_accel.get("accel_stocks", []))        # 學術9 營收加速
    season_bonus_label = lamp_season.get("season_bonus_label")       # 學術8 季節信號

    stock_signals = lamp4.get("stock_signals", {})       # 燈4 per-stock tech
    stock_rs      = lamp5.get("stock_rs",      {})       # 燈5 per-stock RS

    # ── 2. 計算板塊平均 PE（用於 PE<avg 加分）───────────────────────────────
    sector_pe_values: List[float] = []
    if pe_df is not None:
        for sid in stock_ids:
            v = _latest_value(pe_df, sid)
            if v is not None and v > 0:
                sector_pe_values.append(v)
    sector_avg_pe = float(np.median(sector_pe_values)) if sector_pe_values else None

    # ── 3. 逐股評分 ──────────────────────────────────────────────────────────
    scored: Dict[str, Any] = {}

    for sid in stock_ids:
        pts_fundamental = 0.0
        pts_technical   = 0.0
        pts_chipset     = 0.0
        pts_bonus       = 0.0
        triggered: List[str] = []

        # --- 基本面 ---
        if sid in lit1:
            pts_fundamental += 2.0
            triggered.append("燈1✓")
        if sid in mom_accel:
            pts_fundamental += 0.5
            triggered.append("燈1(0.5)")
        if sid in lit3:
            pts_fundamental += 1.0
            triggered.append("燈3✓")

        eps_yoy = _latest_value(eps_df, sid)
        if eps_yoy is not None and eps_yoy >= _EPS_YOY_T:
            pts_fundamental += 2.0
            triggered.append("EPS_YoY✓")

        # --- 技術面 ---
        sig4 = stock_signals.get(sid, {})
        ts = sig4.get("tech_score", 0)
        if ts == 2:
            pts_technical += 2.0
            triggered.append("燈4(2)")
        elif ts == 1:
            pts_technical += 1.0
            triggered.append("燈4(1)")

        dist = sig4.get("dist_60ma_pct")
        if dist is not None and 0.0 < dist <= _DIST_MAX:
            pts_technical += 0.5
            triggered.append("燈4_sweet")

        sig5 = stock_rs.get(sid, {})
        rank_pct = sig5.get("rank_pct")
        if rank_pct is not None and rank_pct > 70.0:
            pts_technical += 1.0
            triggered.append("燈5✓")

        # --- 籌碼面 ---
        if sid in lit2:
            pts_chipset += 2.0
            triggered.append("燈2✓")
        if sid in foreign_only:
            pts_chipset += 0.5
            triggered.append("燈2_外資")
        if sid in trust_only:
            pts_chipset += 0.5
            triggered.append("燈2_投信")
        if sid in lit6:
            pts_chipset += 1.0
            triggered.append("燈6✓")

        # 學術燈2 — 市場狀態標籤（牛市共振 vs 熊市防守）
        if sid in lit2 and resonance_label:
            triggered.append(resonance_label)

        # 學術燈6 — 借券方向信號（Hu et al. 2009）
        if sid in short_cover and sid not in lit6:
            triggered.append("借券回補↑")
        if sid in short_add:
            triggered.append("空頭加碼⚠")     # 警示，不加分

        # --- 加分 ---
        pe_val = _latest_value(pe_df, sid)
        if pe_val is not None and sector_avg_pe is not None and pe_val > 0 and pe_val < sector_avg_pe:
            pts_bonus += 1.0
            triggered.append("PE<avg✓")

        roe_val = _latest_value(roe_df, sid)
        if roe_val is not None and roe_val >= _ROE_MIN:
            pts_bonus += 1.0
            triggered.append("ROE✓")

        # 學術燈9 — 月營收連加速超預期（Lu & Xin 2024）
        if sid in accel_stocks:
            pts_bonus += 0.5
            triggered.append("營收加速↑✓")

        # 學術燈8 — 季節動能（Fu & Hsieh 2024）— 板塊級別信號，注入個股
        if season_bonus_label:
            triggered.append(season_bonus_label)

        total = pts_fundamental + pts_technical + pts_chipset + pts_bonus

        # 低於最低顯示門檻，跳過
        if total < float(getattr(config, "STOCK_MIN_DISPLAY", 3.0)):
            continue

        # 評等
        tier1 = float(getattr(config, "STOCK_SCORE_TIER1", 9.0))
        tier2 = float(getattr(config, "STOCK_SCORE_TIER2", 6.0))
        watch = float(getattr(config, "STOCK_SCORE_WATCH", 3.0))
        if total >= tier1:
            grade = "⭐⭐⭐"
        elif total >= tier2:
            grade = "⭐⭐"
        elif total >= watch:
            grade = "⭐"
        else:
            grade = ""

        scored[sid] = {
            "score":      round(total, 2),
            "grade":      grade,
            "change_pct": (change_pct_map or {}).get(sid) if change_pct_map is not None else None,
            "triggered":  triggered,
            "breakdown": {
                "fundamental": round(pts_fundamental, 2),
                "technical":   round(pts_technical,   2),
                "chipset":     round(pts_chipset,      2),
                "bonus":       round(pts_bonus,        2),
            },
            "fundamental_date":   fundamental_date,
            "manual_adjustments": {},   # 保留欄位：未來千張大戶等手動加分
        }

    # 按分數由高到低排序
    sorted_scored = dict(
        sorted(scored.items(), key=lambda kv: kv[1]["score"], reverse=True)
    )

    # 龍頭股上限：只保留前 N 支（避免跟風股塞爆前端）
    max_n = int(getattr(config, "STOCK_MAX_DISPLAY", 8))
    if len(sorted_scored) > max_n:
        top_keys = list(sorted_scored.keys())[:max_n]
        sorted_scored = {k: sorted_scored[k] for k in top_keys}

    return sorted_scored
