"""
portfolio.py — MAGA 訊號驅動投資組合引擎

主要功能：
  1. 根據 composite 評分建立 / 更新「建議持倉」
  2. 追蹤實際損益（P&L）
  3. 寫出 output/portfolio/holdings.json、output/portfolio/pnl.json

資料模型
--------
Holdings（output/portfolio/holdings.json）
{
  "updated_at": "ISO",
  "positions": {
    ticker: {
      "name_zh":      str,
      "sector":       str,
      "category":     "beneficiary"|"victim"|"neutral",
      "composite_score": float,      # 來自 composite.py
      "entry_price":  float | null,  # null = 尚無真實成本
      "shares":       int,           # 建議股數（依 weight 計算）
      "weight":       float,         # 0.0-1.0 組合比重
      "added_at":     "ISO",
      "reason":       str,           # 進場理由摘要
    }
  },
  "total_weight": float,
  "sector_weights": {sector: float},
}

PnL（output/portfolio/pnl.json）
{
  "updated_at": "ISO",
  "positions": {
    ticker: {
      "name_zh":        str,
      "sector":         str,
      "entry_price":    float | null,
      "current_price":  float | null,
      "pnl_pct":        float | null,   # (current - entry) / entry
      "pnl_abs":        float | null,
      "shares":         int,
      "days_held":      int,
    }
  },
  "portfolio_pnl_pct": float | null,
  "best_position":  str | null,
  "worst_position": str | null,
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 輸出目錄
_OUTPUT_DIR = Path(__file__).parents[2] / "output" / "portfolio"
# 用戶自選持倉（由前端 /api/user-holdings 寫入）
_USER_HOLDINGS_PATH = _OUTPUT_DIR / "user_holdings.json"

# 組合限制
MAX_POSITIONS = 20       # 最多持倉數
MAX_SINGLE_WEIGHT = 0.15 # 單支最高比重
MAX_SECTOR_WEIGHT = 0.40 # 單一板塊最高比重

# 最小 composite 分數門檻（進場）
ENTRY_THRESHOLD = 0.25
EXIT_THRESHOLD  = 0.05   # composite 低於此值時建議減碼


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_user_holdings() -> dict | None:
    """載入管理員自選持倉（user_holdings.json）。失敗時回傳 None，不中斷流程。"""
    if not _USER_HOLDINGS_PATH.exists():
        return None
    try:
        with open(_USER_HOLDINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        positions = data.get("positions", {})
        if not isinstance(positions, dict):
            return None
        return data
    except Exception as e:
        logger.warning("載入 user_holdings.json 失敗: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════
# 核心函式
# ══════════════════════════════════════════════════════════════════════════

def build_suggested_holdings(
    composite_result: dict,
    maga_stocks: list[dict],
    budget: float = 1_000_000,  # 建議資金（台幣）
) -> dict[str, Any]:
    """
    根據 composite 評分 + MAGA stocks 建議持倉。

    Parameters
    ----------
    composite_result : composite.py run_composite_analysis() 的輸出
    maga_stocks      : maga_analyzer.py 的 stocks 列表
    budget           : 模擬資金（台幣），用於計算建議股數

    Returns
    -------
    holdings dict（同 holdings.json 格式）
    """
    scores = composite_result.get("scores", {})
    now = datetime.now(timezone.utc).isoformat()

    # 建立 ticker → maga_stock 查找表
    ticker_map: dict[str, dict] = {s["id"]: s for s in maga_stocks}

    # ── 1. 篩選受益板塊得分 > ENTRY_THRESHOLD 的股票 ────────────────────
    candidates: list[tuple[str, float, dict]] = []  # (ticker, composite, stock_info)

    for stock in maga_stocks:
        if stock.get("category") != "beneficiary":
            continue
        sector = stock.get("sector_id", "")
        composite = scores.get(sector, {}).get("composite", 0.0)
        if composite >= ENTRY_THRESHOLD:
            candidates.append((stock["id"], composite, stock))

    # 按 composite 排序，取前 MAX_POSITIONS 支
    candidates.sort(key=lambda x: -x[1])
    candidates = candidates[:MAX_POSITIONS]

    # ── 2. 計算等比重，尊重單板塊上限 ──────────────────────────────────
    sector_alloc: dict[str, float] = {}
    positions: dict[str, dict] = {}

    total_score = sum(c for _, c, _ in candidates) or 1.0

    for ticker, comp, stock in candidates:
        sector = stock.get("sector_id", "unknown")
        raw_weight = comp / total_score
        raw_weight = min(raw_weight, MAX_SINGLE_WEIGHT)

        # 板塊上限
        sector_used = sector_alloc.get(sector, 0.0)
        if sector_used + raw_weight > MAX_SECTOR_WEIGHT:
            raw_weight = max(0.0, MAX_SECTOR_WEIGHT - sector_used)
        if raw_weight <= 0:
            continue

        sector_alloc[sector] = sector_used + raw_weight

        # 計算股數（以收盤價估算，若無則為 null）
        price = stock.get("price") or stock.get("latest_price")
        shares = None
        if price and price > 0:
            alloc_amount = budget * raw_weight
            # 台股以「張」為單位（1張=1000股），取整張
            lots = int(alloc_amount / (price * 1000))
            shares = lots * 1000

        reason_parts = []
        if comp >= 1.2:
            reason_parts.append("複合強烈買入")
        elif comp >= 0.4:
            reason_parts.append("複合買入")
        kws = composite_result.get("keyword_hits", [])[:3]
        if kws:
            reason_parts.append(f"關鍵詞：{','.join(kws)}")

        positions[ticker] = {
            "name_zh":         stock.get("name_zh", ticker),
            "sector":          sector,
            "category":        "beneficiary",
            "composite_score": round(comp, 4),
            "entry_price":     price,
            "shares":          shares,
            "weight":          round(raw_weight, 4),
            "added_at":        now,
            "reason":          "；".join(reason_parts) or "訊號進場",
        }

    # 正規化 weight 至總和 ≤ 1
    total_w = sum(p["weight"] for p in positions.values())
    if total_w > 1.0:
        for p in positions.values():
            p["weight"] = round(p["weight"] / total_w, 4)

    sector_weights: dict[str, float] = {}
    for p in positions.values():
        sector_weights[p["sector"]] = round(
            sector_weights.get(p["sector"], 0.0) + p["weight"], 4
        )

    holdings = {
        "updated_at":     now,
        "positions":      positions,
        "total_weight":   round(sum(p["weight"] for p in positions.values()), 4),
        "sector_weights": sector_weights,
    }

    _save_json(_OUTPUT_DIR / "holdings.json", holdings)
    return holdings


def inject_cycle_acceleration(
    holdings: dict[str, Any],
    snapshot_sectors: dict[str, Any],
) -> dict[str, Any]:
    """
    將加速期/過熱期板塊的所有個股自動注入 holdings.positions。
    每一支加速期個股都納入（不限數量）。
    若板塊有 exit_risk.action ∈ ["減碼","出場"]，標記 exit_alert=True。
    """
    now = datetime.now(timezone.utc).isoformat()
    positions = holdings.get("positions", {})

    for sid, sec in snapshot_sectors.items():
        stage = sec.get("cycle_stage")
        if stage not in ("加速期", "過熱期"):
            continue

        exit_risk = sec.get("exit_risk") or {}
        exit_alert = exit_risk.get("action") in ("減碼", "出場")

        for stock in sec.get("stocks", []):
            stock_id = stock.get("id", "")
            if not stock_id:
                continue
            # 已存在的持倉不覆蓋原始 reason
            if stock_id in positions:
                positions[stock_id]["exit_alert"] = exit_alert
                continue

            positions[stock_id] = {
                "name_zh":         stock_id,
                "sector":          sid,
                "category":        "neutral",
                "composite_score": 0.0,
                "entry_price":     None,
                "shares":          None,
                "weight":          0.0,
                "added_at":        now,
                "reason":          f"cycle_acceleration ({stage})",
                "exit_alert":      exit_alert,
            }

    holdings["positions"] = positions
    holdings["updated_at"] = now

    _save_json(_OUTPUT_DIR / "holdings.json", holdings)
    return holdings


def compute_pnl(
    holdings: dict,
    current_prices: dict[str, float | None],
    *,
    user_holdings: dict | None = None,
) -> dict[str, Any]:
    """
    計算組合損益，包含用戶自選持倉。

    Parameters
    ----------
    holdings       : build_suggested_holdings() 的輸出（演算法建議持倉）
    current_prices : {ticker: latest_price}（可從 maga_stocks 取得）
    user_holdings  : _load_user_holdings() 的輸出（用戶手動持倉），可選

    Returns
    -------
    pnl dict（同 pnl.json 格式）
    """
    now = datetime.now(timezone.utc).isoformat()
    positions_in = holdings.get("positions", {})
    positions_out: dict[str, dict] = {}

    # ── 1. 演算法建議持倉（以 added_at 計算持有天數）────────────────────
    for ticker, pos in positions_in.items():
        entry = pos.get("entry_price")
        current = current_prices.get(ticker)
        shares = pos.get("shares") or 0

        pnl_pct = None
        pnl_abs = None
        if entry and current and entry > 0:
            pnl_pct = round((current - entry) / entry * 100, 2)
            pnl_abs = round((current - entry) * shares, 0)

        added_at_str = pos.get("added_at", "")
        days_held = 0
        if added_at_str:
            try:
                added_dt = datetime.fromisoformat(added_at_str)
                days_held = (datetime.now(timezone.utc) - added_dt).days
            except ValueError:
                pass

        positions_out[ticker] = {
            "name_zh":       pos.get("name_zh", ticker),
            "sector":        pos.get("sector", ""),
            "entry_price":   entry,
            "current_price": current,
            "pnl_pct":       pnl_pct,
            "pnl_abs":       pnl_abs,
            "shares":        shares,
            "days_held":     days_held,
        }

    # ── 2. 用戶自選持倉（以 entry_date 計算持有天數）───────────────────
    if user_holdings:
        user_positions = user_holdings.get("positions", {})
        for ticker, pos in user_positions.items():
            if ticker in positions_out:
                # 已由演算法持倉處理，跳過避免重複
                continue

            entry = pos.get("entry_price")
            current = current_prices.get(ticker)
            shares = pos.get("shares") or 0

            pnl_pct = None
            pnl_abs = None
            if entry and current and entry > 0:
                pnl_pct = round((current - entry) / entry * 100, 2)
                pnl_abs = round((current - entry) * shares, 0)

            # 用 entry_date 計算持有天數（用戶持倉以進場日為準）
            days_held = 0
            entry_date_str = pos.get("entry_date", "")
            if entry_date_str:
                try:
                    entry_dt = datetime.fromisoformat(entry_date_str)
                    # entry_date 可能是純日期字串，需補時區
                    if entry_dt.tzinfo is None:
                        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                    days_held = (datetime.now(timezone.utc) - entry_dt).days
                except ValueError:
                    pass

            positions_out[ticker] = {
                "name_zh":       pos.get("name_zh", ticker),
                "sector":        pos.get("sector", ""),
                "entry_price":   entry,
                "current_price": current,
                "pnl_pct":       pnl_pct,
                "pnl_abs":       pnl_abs,
                "shares":        shares,
                "days_held":     days_held,
            }

    # 加權組合損益（僅演算法持倉使用 weight 加權；user-only 股票 weight=0 不納入計算）
    portfolio_pnl: float | None = None
    weighted_pnls = [
        (positions_out[t]["pnl_pct"], positions_in.get(t, {}).get("weight", 0.0))
        for t in positions_out
        if positions_out[t]["pnl_pct"] is not None
           and positions_in.get(t, {}).get("weight", 0.0) > 0
    ]
    if weighted_pnls:
        portfolio_pnl = round(
            sum(p * w for p, w in weighted_pnls) / sum(w for _, w in weighted_pnls),
            2,
        )

    # 最佳 / 最差
    sorted_by_pnl = sorted(
        [(t, p["pnl_pct"]) for t, p in positions_out.items() if p["pnl_pct"] is not None],
        key=lambda x: x[1],
    )
    best  = sorted_by_pnl[-1][0] if sorted_by_pnl else None
    worst = sorted_by_pnl[0][0]  if sorted_by_pnl else None

    pnl_result = {
        "updated_at":        now,
        "positions":         positions_out,
        "portfolio_pnl_pct": portfolio_pnl,
        "best_position":     best,
        "worst_position":    worst,
    }

    _save_json(_OUTPUT_DIR / "pnl.json", pnl_result)
    return pnl_result


def run_portfolio_update(
    composite_result: dict,
    maga_stocks: list[dict],
    budget: float = 1_000_000,
) -> tuple[dict, dict]:
    """
    一鍵執行：
      1. 建立/更新建議持倉
      2. 計算損益（含用戶自選持倉）
      3. 寫出兩份 JSON

    Returns (holdings, pnl)
    """
    holdings = build_suggested_holdings(composite_result, maga_stocks, budget)

    # 收集演算法持倉的當前價格（從 MAGA stocks）
    current_prices: dict[str, float | None] = {
        s["id"]: s.get("price") or s.get("latest_price")
        for s in maga_stocks
    }

    # 載入用戶自選持倉
    user_h = _load_user_holdings()

    # 補充用戶持倉中不在 MAGA stocks 的股票價格（嘗試從 FinLab 取得）
    if user_h:
        algo_tickers = set(current_prices.keys())
        user_only_tickers = [
            t for t in user_h.get("positions", {}).keys()
            if t not in algo_tickers
        ]
        if user_only_tickers:
            try:
                from finlab import data as _fl_data
                df_close = _fl_data.get("price:收盤價")
                if df_close is not None:
                    for ticker in user_only_tickers:
                        if ticker in df_close.columns:
                            series = df_close[ticker].dropna()
                            if not series.empty:
                                current_prices[ticker] = float(series.iloc[-1])
            except Exception as _e:
                logger.debug("補充用戶持倉股價失敗（不影響主流程）: %s", _e)

    pnl = compute_pnl(holdings, current_prices, user_holdings=user_h)
    return holdings, pnl


def load_holdings() -> dict | None:
    p = _OUTPUT_DIR / "holdings.json"
    return _load_json(p) or None


def load_pnl() -> dict | None:
    p = _OUTPUT_DIR / "pnl.json"
    return _load_json(p) or None
