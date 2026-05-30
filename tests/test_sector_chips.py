"""tests/test_sector_chips.py — 板塊級法人籌碼聚合 + 主力進駐單元測試"""
import numpy as np
import pandas as pd

from src.analyzers import sector_chips
from src.analyzers.sector_chips import detect_main_force, _sector_flow_series


class _FakeFetcher:
    def __init__(self, foreign, trust):
        self._f, self._t = foreign, trust

    def get(self, key):
        if "外陸資" in key:
            return self._f
        if "投信" in key:
            return self._t
        return None


class _FakeSectorMap:
    def __init__(self, sectors):
        self._sectors = sectors

    def all_sector_ids(self):
        return list(self._sectors.keys())

    def get_stocks(self, sid):
        return self._sectors.get(sid, [])


class _Cfg:
    INST_FLOW_WEIGHT_FOREIGN = 2.0
    INST_FLOW_WEIGHT_TRUST = 1.0
    INST_FLOW_WINDOW = 20


# ── detect_main_force 五條件 ─────────────────────────────────────────────

def test_strong_accumulation_high_score():
    """持續放大的買超 → 高進駐分數（連買+累積+突破至少 3 條）。"""
    idx = pd.date_range("2025-01-01", periods=80)
    # 前 60 日小幅，後 20 日大幅放大買超（製造加速 + 突破 + 連買）
    vals = np.concatenate([
        np.full(60, 5e3),
        np.linspace(2e4, 8e4, 20),
    ])
    sig = detect_main_force(pd.Series(vals, index=idx), window=20)
    assert sig.score >= 3
    assert sig.consec_buy >= 5
    assert sig.breakout is True


def test_persistent_selling_zero_score():
    """持續賣超 → 0 分。"""
    idx = pd.date_range("2025-01-01", periods=80)
    sig = detect_main_force(pd.Series(np.full(80, -1e4), index=idx), window=20)
    assert sig.score == 0
    assert sig.consec_buy == 0


def test_insufficient_data():
    sig = detect_main_force(pd.Series([1e4, 2e4]), window=20)
    assert sig.score == 0
    assert sig.level == "無訊號"


def test_small_denominator_guard():
    """近 0 均值（正負交錯小額）不應讓加速度爆大。"""
    idx = pd.date_range("2025-01-01", periods=80)
    rng = np.random.default_rng(0)
    # 在 0 附近正負交錯的小額（均值接近 0，低於 _ACCEL_MIN_BASE）
    vals = rng.normal(0, 50, 80)
    sig = detect_main_force(pd.Series(vals, index=idx), window=20)
    assert sig.accel == 0.0   # 小分母防護生效


# ── _sector_flow_series 權重 ─────────────────────────────────────────────

def test_flow_weighting():
    """合力 = 外資×2 + 投信×1。"""
    idx = pd.date_range("2025-01-01", periods=5)
    foreign = pd.DataFrame({"2330": [100] * 5}, index=idx)
    trust = pd.DataFrame({"2330": [10] * 5}, index=idx)
    flow = _sector_flow_series(foreign, trust, ["2330"], 2.0, 1.0)
    # 每日 = 100*2 + 10*1 = 210
    assert abs(flow.iloc[-1] - 210) < 1e-6


def test_flow_handles_missing_one_source():
    idx = pd.date_range("2025-01-01", periods=5)
    foreign = pd.DataFrame({"2330": [100] * 5}, index=idx)
    flow = _sector_flow_series(foreign, None, ["2330"], 2.0, 1.0)
    assert abs(flow.iloc[-1] - 200) < 1e-6


# ── analyze() 整合 ───────────────────────────────────────────────────────

def test_analyze_returns_per_sector():
    idx = pd.date_range("2025-01-01", periods=80)
    strong = np.concatenate([np.full(60, 5e3), np.linspace(2e4, 8e4, 20)])
    weak = np.full(80, -5e3)
    foreign = pd.DataFrame({"2330": strong, "2317": weak}, index=idx)
    trust = pd.DataFrame({"2330": strong * 0.3, "2317": weak * 0.3}, index=idx)
    sm = _FakeSectorMap({"semi": ["2330"], "weak": ["2317"]})

    res = sector_chips.analyze(_FakeFetcher(foreign, trust), sm, _Cfg())
    assert res["semi"]["chip_flow"]["score"] >= 3
    assert res["semi"]["signal"] is True
    assert res["weak"]["chip_flow"]["score"] == 0
    assert res["weak"]["signal"] is False


def test_analyze_handles_no_data():
    sm = _FakeSectorMap({"semi": ["2330"]})

    class _Null:
        def get(self, key):
            return None

    assert sector_chips.analyze(_Null(), sm, _Cfg()) == {}
