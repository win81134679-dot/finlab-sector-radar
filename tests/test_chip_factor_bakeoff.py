"""tests/test_chip_factor_bakeoff.py — 法人籌碼因子 bakeoff 核心測試（無需 token）"""
import numpy as np
import pandas as pd

from src.analyzers import chip_factor_bakeoff as bk


def test_consecutive_buy_signal():
    idx = pd.date_range("2024-01-01", periods=6, freq="B")
    net = pd.DataFrame({"A": [1, 1, 1, -1, 1, 1], "B": [1, 1, 1, 1, 1, 1]}, index=idx)
    sig = bk.consecutive_buy_signal(net, 3)
    # A: 連3買在 index2 成立、index3 斷、index5 又需 index3,4,5 → 含 -1 不成立
    assert sig["A"].iloc[2] == True   # noqa: E712  (1,1,1)
    assert sig["A"].iloc[3] == False  # (1,1,-1)
    assert sig["B"].iloc[5] == True   # 全買


def test_holding_uptrend_signal():
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    h = pd.DataFrame({"A": [10, 11, 12, 13, 14], "B": [20, 19, 18, 17, 16]}, index=idx)
    sig = bk.holding_uptrend_signal(h, lookback=2)
    assert sig["A"].iloc[-1] == True    # 14 > 12（上升）
    assert sig["B"].iloc[-1] == False   # 16 < 18（下降）


def test_net_buy_signal():
    idx = pd.date_range("2024-01-01", periods=25, freq="B")
    net = pd.DataFrame({"A": [100] * 25, "B": [-100] * 25}, index=idx)
    sig = bk.net_buy_signal(net, window=20)
    assert sig["A"].iloc[-1] == True
    assert sig["B"].iloc[-1] == False


def test_forward_beat_matrix():
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    price = pd.DataFrame({
        "WIN": np.linspace(100, 200, n),   # 大漲
        "LOSE": np.full(n, 100.0),         # 平
    }, index=idx)
    bench = pd.Series(np.linspace(1000, 1100, n), index=idx)  # 漲 10%
    beat = bk.forward_beat_matrix(price, bench, hold=20)
    # 前段 WIN 漲幅 > 大盤 → True；LOSE 平 < 大盤漲 → False
    assert beat["WIN"].iloc[10] == True
    assert beat["LOSE"].iloc[10] == False
    # 尾端未來不足 → NaN
    assert pd.isna(beat["WIN"].iloc[-1])


def test_evaluate_factor_alpha_positive():
    """構造：訊號精準命中贏家 → alpha > 0。"""
    me = pd.date_range("2024-01-31", periods=4, freq="ME")
    # 訊號：只在 WIN 股觸發
    sig = pd.DataFrame({"WIN": [True] * 4, "LOSE": [False] * 4}, index=me)
    # beat：WIN 全贏、LOSE 全輸
    beat = pd.DataFrame({"WIN": [True] * 4, "LOSE": [False] * 4}, index=me)
    r = bk.evaluate_factor(sig, beat)
    assert r["hit_rate"] == 1.0       # 訊號股全贏
    assert r["base_rate"] == 0.5      # 全體 4 win + 4 lose
    assert r["alpha"] == 0.5          # 1.0 - 0.5


def test_evaluate_factor_no_signal():
    me = pd.date_range("2024-01-31", periods=3, freq="ME")
    sig = pd.DataFrame({"A": [False] * 3}, index=me)
    beat = pd.DataFrame({"A": [True, False, True]}, index=me)
    r = bk.evaluate_factor(sig, beat)
    assert r["n"] == 0
    assert r["hit_rate"] == 0.0


def test_evaluate_factor_ignores_nan_beat():
    """beat 為 NaN（資料不足）的格子不計入。"""
    me = pd.date_range("2024-01-31", periods=3, freq="ME")
    sig = pd.DataFrame({"A": [True, True, True]}, index=me)
    beat = pd.DataFrame({"A": [True, np.nan, False]}, index=me)
    r = bk.evaluate_factor(sig, beat)
    assert r["n"] == 2                # 只有 2 個非 NaN
    assert r["hit_rate"] == 0.5       # 1 win / 2


def test_reindex_month_end():
    didx = pd.date_range("2024-01-01", periods=40, freq="B")
    daily = pd.DataFrame({"A": [True] * 40}, index=didx)
    me = [didx[20], didx[39]]
    out = bk.reindex_month_end(daily, me)
    assert list(out.index) == me
    assert out["A"].all()
