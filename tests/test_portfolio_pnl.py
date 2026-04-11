"""tests/test_portfolio_pnl.py — compute_pnl 用戶持倉整合測試"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest


# ── helpers ────────────────────────────────────────────────────────────────


def _make_holdings(*tickers: str) -> dict:
    """建立最小化的演算法建議持倉 dict（含 added_at）。"""
    positions = {}
    now = datetime.now(timezone.utc).isoformat()
    for t in tickers:
        positions[t] = {
            "name_zh": t,
            "sector": "algo_sector",
            "entry_price": 100.0,
            "shares": 1000,
            "weight": 0.1,
            "added_at": now,
        }
    return {"positions": positions}


def _make_user_holdings(*tickers: str, entry_price: float = 80.0, shares: int = 500, days_ago: int = 10) -> dict:
    """建立最小化的用戶自選持倉 dict（含 entry_date）。"""
    entry_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    positions = {}
    for t in tickers:
        positions[t] = {
            "name_zh": t,
            "sector": "user_sector",
            "entry_price": entry_price,
            "entry_date": entry_date,
            "shares": shares,
            "note": "手動加入",
        }
    return {"positions": positions}


# ── tests ──────────────────────────────────────────────────────────────────


def test_compute_pnl_includes_user_only_stock(tmp_path, monkeypatch):
    """User-only 股票（不在演算法持倉中）必須出現在 pnl.positions。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = _make_holdings("2330")
    user_h = _make_user_holdings("2454")
    prices = {"2330": 110.0, "2454": 90.0}

    result = compute_pnl(holdings, prices, user_holdings=user_h)

    assert "2454" in result["positions"], "User-only 股票必須出現在 pnl.positions"
    pos = result["positions"]["2454"]
    assert pos["entry_price"] == 80.0
    assert pos["current_price"] == 90.0
    assert pos["pnl_pct"] is not None
    assert abs(pos["pnl_pct"] - 12.5) < 0.01  # (90-80)/80*100 = 12.5%
    assert pos["pnl_abs"] == round((90.0 - 80.0) * 500, 0)


def test_compute_pnl_user_entry_date_days_held(tmp_path, monkeypatch):
    """User 持倉使用 entry_date（而非 added_at）計算 days_held。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = {"positions": {}}
    user_h = _make_user_holdings("2412", days_ago=15)
    result = compute_pnl(holdings, {}, user_holdings=user_h)

    days = result["positions"]["2412"]["days_held"]
    assert 14 <= days <= 16, f"預期 ~15 days_held，實際 {days}"


def test_compute_pnl_user_no_price(tmp_path, monkeypatch):
    """User 股票無 current_price 時，pnl_pct / pnl_abs 必須為 None。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = {"positions": {}}
    user_h = _make_user_holdings("3008")
    result = compute_pnl(holdings, {}, user_holdings=user_h)

    pos = result["positions"]["3008"]
    assert pos["current_price"] is None
    assert pos["pnl_pct"] is None
    assert pos["pnl_abs"] is None


def test_compute_pnl_user_duplicated_in_algo_no_override(tmp_path, monkeypatch):
    """同時在演算法持倉和 user_holdings 的股票，不應在 pnl.positions 重複出現；
    且應以演算法持倉的 entry_price 為準（先到先得）。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = _make_holdings("2330")  # algo entry_price=100
    user_h = _make_user_holdings("2330")  # user entry_price=80
    prices = {"2330": 120.0}

    result = compute_pnl(holdings, prices, user_holdings=user_h)
    tickers = list(result["positions"].keys())
    assert tickers.count("2330") == 1, "不應重複出現"
    # 演算法持倉優先：entry_price = 100
    assert result["positions"]["2330"]["entry_price"] == 100.0


def test_compute_pnl_no_user_holdings_backward_compat(tmp_path, monkeypatch):
    """不傳 user_holdings 時，行為與舊版完全一致（向下相容）。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = _make_holdings("2330")
    prices = {"2330": 115.0}

    result = compute_pnl(holdings, prices)  # 不傳 user_holdings

    assert "2330" in result["positions"]
    assert result["positions"]["2330"]["pnl_pct"] == round((115 - 100) / 100 * 100, 2)


def test_compute_pnl_user_entry_price_none_no_crash(tmp_path, monkeypatch):
    """User 持倉 entry_price 為 None 時不應崩潰，pnl_pct 保持 None。"""
    monkeypatch.setattr("src.analyzers.portfolio._OUTPUT_DIR", tmp_path)
    from src.analyzers.portfolio import compute_pnl

    holdings = {"positions": {}}
    user_h = {
        "positions": {
            "9999": {
                "name_zh": "測試股",
                "sector": "test",
                "entry_price": None,
                "entry_date": "2026-01-01",
                "shares": 1000,
                "note": "",
            }
        }
    }
    result = compute_pnl(holdings, {"9999": 100.0}, user_holdings=user_h)
    pos = result["positions"]["9999"]
    assert pos["entry_price"] is None
    assert pos["pnl_pct"] is None
