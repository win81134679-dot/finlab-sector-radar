"""tests/test_regime_factor_bakeoff.py — 盤性型態因子驗證核心測試（無需 token）"""
import numpy as np
import pandas as pd

from src.analyzers import regime_factor_bakeoff as rf


def test_consecutive_limit_up():
    idx = pd.date_range("2024-01-01", periods=4, freq="B")
    # 連2日漲停（收/開 ≥ 9.5%）
    o = pd.DataFrame({"A": [100, 100, 100, 100], "B": [100, 100, 100, 100]}, index=idx)
    c = pd.DataFrame({"A": [100, 100, 110, 111], "B": [100, 101, 102, 103]}, index=idx)
    sig = rf.consecutive_limit_up(o, c, n=2)
    assert sig["A"].iloc[-1] == True    # noqa: E712  最後兩日 +10%,+11%
    assert sig["B"].iloc[-1] == False   # B 漲幅小


def test_long_upper_shadow_highpos():
    idx = pd.date_range("2024-01-01", periods=8, freq="B")
    # 先漲一段(>5%)，最後兩根長上影線
    o = pd.DataFrame({"A": [100, 104, 108, 112, 116, 120, 120, 120]}, index=idx)
    c = pd.DataFrame({"A": [104, 108, 112, 116, 120, 121, 121, 121]}, index=idx)
    # 最後兩根上影線很長（high 遠高於 max(o,c)）
    h = pd.DataFrame({"A": [105, 109, 113, 117, 121, 135, 135, 135]}, index=idx)
    l = pd.DataFrame({"A": [99, 103, 107, 111, 115, 119, 119, 119]}, index=idx)
    sig = rf.long_upper_shadow_highpos(o, h, l, c, count_days=7, min_count=2, rise_thr=5.0)
    assert sig["A"].iloc[-1] == True   # noqa: E712


def test_kdj_low_golden_cross():
    # 構造一段先跌後反彈的序列 → 低位金叉
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    vals = np.concatenate([np.linspace(120, 90, 20), np.linspace(90, 100, 10)])
    c = pd.DataFrame({"A": vals}, index=idx)
    h = c + 1
    l = c - 1
    sig = rf.kdj_low_golden_cross(c, h, l)
    # 反彈段某處應出現低位金叉（不強制最後一日，檢查整體有觸發）
    assert sig["A"].any()


def test_kdj_high_death_cross():
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    # 先漲到高位後回落 → 高位死叉
    vals = np.concatenate([np.linspace(90, 130, 20), np.linspace(130, 120, 10)])
    c = pd.DataFrame({"A": vals}, index=idx)
    h = c + 1
    l = c - 1
    sig = rf.kdj_high_death_cross(c, h, l)
    assert sig["A"].any()


def test_kdj_no_crash_short_data():
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    c = pd.DataFrame({"A": [100.0] * 5}, index=idx)
    # 資料短於 n=9 → 不崩潰（rolling 產生 NaN）
    sig = rf.kdj_low_golden_cross(c, c + 1, c - 1)
    assert sig.shape == c.shape
