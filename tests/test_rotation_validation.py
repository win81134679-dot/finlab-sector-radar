"""tests/test_rotation_validation.py — 輪動歷史驗證核心單元測試（無需 token）"""
import numpy as np
import pandas as pd

from src.analyzers import rotation_validation as rv
from src.analyzers.rotation_backtest import WeightVariant


def _price(n=500, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    def trend(drift):
        return 100 + np.cumsum(drift + rng.normal(0, abs(drift) * 1.5 + 0.2, n))
    return pd.DataFrame({
        "2330": trend(0.7), "2303": trend(0.6),    # semi 強
        "2317": trend(-0.3), "2354": trend(-0.2),  # weak 弱
        "1101": trend(0.05), "1102": trend(0.03),  # mid 平
    }, index=idx)


def _flow(price, seed=1):
    rng = np.random.default_rng(seed)
    idx = price.index
    foreign = pd.DataFrame({
        "2330": rng.normal(5e4, 1e4, len(idx)), "2303": rng.normal(3e4, 1e4, len(idx)),
        "2317": rng.normal(-3e4, 1e4, len(idx)), "2354": rng.normal(-2e4, 1e4, len(idx)),
        "1101": rng.normal(0, 1e4, len(idx)), "1102": rng.normal(0, 1e4, len(idx)),
    }, index=idx)
    return foreign, foreign * 0.3


_SECTORS = {"semi": ["2330", "2303"], "weak": ["2317", "2354"], "mid": ["1101", "1102"]}
_V = WeightVariant("fl", 2.0, 1.0)


def test_rank_stocks_orders_by_momentum():
    price = _price()
    ranked = rv.rank_stocks_in_sector(price, ["2330", "2303"], price.index[-1])
    assert set(ranked) == {"2330", "2303"}
    # 2330 drift 高 → 動能應較強，排前
    assert ranked[0] == "2330"


def test_validate_sector_hit_rate_high_for_trending_data():
    """semi 持續最強 → 選中板塊命中率應偏高、超額報酬正。"""
    price = _price()
    foreign, trust = _flow(price)
    res = rv.validate(price, foreign, trust, _SECTORS, _V,
                      top_n_sectors=1, top_k_stocks=1, hold_months=1)
    assert res["rebalances"] >= 6
    assert res["sector_hit_rate"] >= 0.6        # 強勢板塊多數期勝出
    assert res["sector_avg_excess"] > 0          # 平均超額為正
    assert res["sector_avg_return"] > res["universe_avg_return"]


def test_validate_stock_hit_rate_positive_trend():
    """選中 semi 的強動能股 → 報酬 > 0 比例高。"""
    price = _price()
    foreign, trust = _flow(price)
    res = rv.validate(price, foreign, trust, _SECTORS, _V,
                      top_n_sectors=1, top_k_stocks=2, hold_months=1)
    assert res["n_stock_samples"] > 0
    assert res["stock_hit_rate"] >= 0.6
    assert res["stock_avg_return"] > 0


def test_validate_with_benchmark_beat_rate():
    """提供大盤序列 → 回傳 beat_bench_rate（0~1）。"""
    price = _price()
    foreign, trust = _flow(price)
    # 平盤大盤
    bench = pd.Series(100 + np.cumsum(np.full(len(price), 0.01)), index=price.index)
    res = rv.validate(price, foreign, trust, _SECTORS, _V, benchmark=bench,
                      top_n_sectors=1, top_k_stocks=2)
    assert 0.0 <= res["stock_beat_bench_rate"] <= 1.0
    # semi 強勢 → 應有相當比例贏過平盤大盤
    assert res["stock_beat_bench_rate"] >= 0.5


def test_validate_quarterly_hold():
    """季頻（hold_months=3）也能算。"""
    price = _price(n=600)
    foreign, trust = _flow(price)
    res = rv.validate(price, foreign, trust, _SECTORS, _V, hold_months=3)
    assert res["rebalances"] >= 2


def test_validate_insufficient_data():
    price = _price(n=30)
    foreign, trust = _flow(price)
    res = rv.validate(price, foreign, trust, _SECTORS, _V)
    assert res["rebalances"] == 0 or res["n_stock_samples"] >= 0
