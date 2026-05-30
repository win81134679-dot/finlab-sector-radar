"""tests/test_stock_scorer_rotation.py — 輪動層加分整合進個股評分

驗證「板塊輪動 → 選個股」：位於正在輪動板塊的個股獲得 rotation bonus。
"""
import pandas as pd

from src.analyzers import stock_scorer


class _Fetcher:
    """只回基本面 None（隔離輪動邏輯）+ 一個價格 df 供 PE 中位數用。"""
    def get(self, key):
        return None


class _Cfg:
    STOCK_MIN_DISPLAY = 0.0   # 不過濾，方便檢查分數
    STOCK_SCORE_TIER1 = 9.0
    STOCK_SCORE_TIER2 = 6.0
    STOCK_SCORE_WATCH = 3.0


def _raw(rsi_state, rsi_slope, chip_score):
    """構造含輪動層的 raw_results（其餘燈空）。"""
    return {
        "燈1 月營收拐點": {},
        "燈2 法人共振": {},
        "燈3 庫存循環": {},
        "燈4 技術突破": {},
        "燈5 相對強度": {},
        "燈6 籌碼集中": {},
        "輪動_產業RSI": {
            "semi": {"rsi_state": rsi_state, "rsi_slope_5d": rsi_slope},
        },
        "輪動_板塊籌碼": {
            "semi": {"chip_flow": {"score": chip_score}},
        },
    }


def test_rotation_bonus_full_when_rsi_and_chips_strong():
    """RSI 偏多+斜率正 且 法人★以上 → +1.0 bonus + 兩個標籤。"""
    raw = _raw("偏多", 5.0, 4)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert "2330" in res
    assert res["2330"]["breakdown"]["bonus"] == 1.0
    assert "輪動RSI↑" in res["2330"]["triggered"]
    assert "輪動籌碼✓" in res["2330"]["triggered"]


def test_rotation_bonus_rsi_only():
    """只有 RSI 轉強（法人未進駐）→ +0.5。"""
    raw = _raw("超買", 2.0, 1)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["bonus"] == 0.5
    assert "輪動RSI↑" in res["2330"]["triggered"]
    assert "輪動籌碼✓" not in res["2330"]["triggered"]


def test_rotation_bonus_chips_only():
    """只有法人進駐（RSI 偏空）→ +0.5。"""
    raw = _raw("偏空", -3.0, 5)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["bonus"] == 0.5
    assert "輪動籌碼✓" in res["2330"]["triggered"]
    assert "輪動RSI↑" not in res["2330"]["triggered"]


def test_no_rotation_bonus_when_weak():
    """RSI 偏空 + 法人未進駐 → 無加分。"""
    raw = _raw("偏空", -2.0, 1)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["bonus"] == 0.0
    assert "輪動RSI↑" not in res["2330"]["triggered"]
    assert "輪動籌碼✓" not in res["2330"]["triggered"]


def test_rsi_rising_required_not_just_state():
    """RSI 偏多但斜率向下（未轉強）→ 不給 RSI bonus（避免追高轉弱板塊）。"""
    raw = _raw("偏多", -1.0, 0)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert "輪動RSI↑" not in res["2330"]["triggered"]


def test_rotation_missing_data_no_crash():
    """無輪動資料 → 不崩潰、無加分。"""
    raw = {"燈1 月營收拐點": {}, "燈2 法人共振": {}}
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["bonus"] == 0.0
