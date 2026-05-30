"""tests/test_sector_rsi.py — 產業 RSI 輪動偵測單元測試"""
import numpy as np
import pandas as pd

from src.analyzers import sector_rsi
from src.analyzers.sector_rsi import _wilder_rsi, _sector_index, _rsi_state


# ── 假 fetcher / sector_map ──────────────────────────────────────────────

class _FakeFetcher:
    def __init__(self, price_df):
        self._price = price_df

    def get(self, key):
        return self._price if key == "price:收盤價" else None


class _FakeSectorMap:
    def __init__(self, sectors):
        self._sectors = sectors  # {sid: [stock_ids]}

    def all_sector_ids(self):
        return list(self._sectors.keys())

    def get_stocks(self, sid):
        return self._sectors.get(sid, [])


class _Cfg:
    SECTOR_RSI_PERIOD = 14   # 測試用短週期，資料量需求低
    SECTOR_RSI_PERCENTILE_LOOKBACK = 60
    SECTOR_RSI_SLOPE_DAYS = 5
    SECTOR_RSI_MOMENTUM_LOOKBACK = 20


def _noisy_trend(n: int, drift: float, seed: int) -> np.ndarray:
    """帶雜訊的趨勢序列（避免線性序列讓 RSI 退化）。"""
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0, abs(drift) * 2 + 0.5, n)
    return 100 + np.cumsum(steps)


# ── _wilder_rsi 邊界 ─────────────────────────────────────────────────────

def test_rsi_all_gains_is_100():
    """全漲無跌 → RSI=100（修正的 Wilder 邊界）。"""
    s = pd.Series(np.arange(1, 60, dtype=float))  # 嚴格遞增
    out = _wilder_rsi(s, 14).dropna()
    assert not out.empty
    assert abs(out.iloc[-1] - 100.0) < 1e-6


def test_rsi_all_losses_is_0():
    """全跌無漲 → RSI=0。"""
    s = pd.Series(np.arange(60, 1, -1, dtype=float))  # 嚴格遞減
    out = _wilder_rsi(s, 14).dropna()
    assert not out.empty
    assert abs(out.iloc[-1] - 0.0) < 1e-6


def test_rsi_flat_is_50_not_nan():
    """完全持平 → RSI=50（非 NaN，這是 ETF 專案踩到的真實 bug）。"""
    s = pd.Series([100.0] * 60)
    out = _wilder_rsi(s, 14)
    last = out.iloc[-1]
    assert last == 50.0


def test_rsi_in_range_for_noisy_series():
    """雜訊上升序列 RSI 落在合理區間且 > 50。"""
    s = pd.Series(_noisy_trend(120, drift=0.6, seed=1))
    out = _wilder_rsi(s, 14).dropna()
    assert not out.empty
    assert 0.0 <= out.iloc[-1] <= 100.0
    assert out.iloc[-1] > 50.0  # 上升趨勢


def test_rsi_insufficient_data_is_nan():
    """資料少於週期 → 全 NaN。"""
    s = pd.Series([100.0, 101.0, 102.0])
    out = _wilder_rsi(s, 14)
    assert out.dropna().empty


# ── _sector_index ────────────────────────────────────────────────────────

def test_sector_index_equal_weight_starts_near_one():
    df = pd.DataFrame({
        "2330": _noisy_trend(50, 0.5, 2),
        "2303": _noisy_trend(50, 0.3, 3),
    })
    idx = _sector_index(df, ["2330", "2303"])
    assert not idx.empty
    assert abs(idx.iloc[0] - 1.0) < 0.1  # 從 ~1.0 起算

def test_sector_index_ignores_missing_stocks():
    df = pd.DataFrame({"2330": _noisy_trend(30, 0.5, 4)})
    idx = _sector_index(df, ["2330", "9999"])  # 9999 不存在
    assert not idx.empty


# ── _rsi_state ───────────────────────────────────────────────────────────

def test_rsi_state_uses_percentile_when_available():
    assert _rsi_state(60.0, pctl=85.0) == "超買"
    assert _rsi_state(60.0, pctl=10.0) == "超賣"
    assert _rsi_state(50.0, pctl=50.0) == "中性"

def test_rsi_state_fallback_to_fixed_threshold():
    assert _rsi_state(75.0, pctl=None) == "超買"
    assert _rsi_state(25.0, pctl=None) == "超賣"

def test_rsi_state_nan():
    assert _rsi_state(float("nan"), pctl=None) == "資料不足"


# ── analyze() 整合 ───────────────────────────────────────────────────────

def test_analyze_returns_per_sector():
    n = 120
    price = pd.DataFrame({
        "2330": _noisy_trend(n, 0.6, 10),
        "2303": _noisy_trend(n, 0.5, 11),
        "2317": _noisy_trend(n, -0.4, 12),
    }, index=pd.date_range("2025-01-01", periods=n))
    sm = _FakeSectorMap({"semi": ["2330", "2303"], "weak": ["2317"]})
    res = sector_rsi.analyze(_FakeFetcher(price), sm, _Cfg())

    assert "semi" in res and "weak" in res
    assert res["semi"]["rsi_60"] is not None
    assert 0 <= res["semi"]["rsi_60"] <= 100
    # 上升板塊 RSI 應高於下降板塊
    assert res["semi"]["rsi_60"] > res["weak"]["rsi_60"]

def test_analyze_empty_on_insufficient_data():
    price = pd.DataFrame({"2330": [100.0, 101.0]},
                         index=pd.date_range("2025-01-01", periods=2))
    sm = _FakeSectorMap({"semi": ["2330"]})
    res = sector_rsi.analyze(_FakeFetcher(price), sm, _Cfg())
    assert res["semi"]["rsi_60"] is None
    assert res["semi"]["signal"] is False

def test_analyze_handles_none_price():
    sm = _FakeSectorMap({"semi": ["2330"]})

    class _NullFetcher:
        def get(self, key):
            return None

    res = sector_rsi.analyze(_NullFetcher(), sm, _Cfg())
    assert res == {}
