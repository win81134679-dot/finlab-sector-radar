"""tests/test_rotation_backtest.py — 輪動回測核心純函式單元測試（無需 token）"""
import numpy as np
import pandas as pd

from src.analyzers import rotation_backtest as rb
from src.analyzers.rotation_backtest import WeightVariant


def _price(n=400, seed=0):
    """日頻價格：semi 上漲、weak 下跌、mid 平。"""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    def trend(drift):
        return 100 + np.cumsum(drift + rng.normal(0, abs(drift) * 2 + 0.3, n))
    return pd.DataFrame({
        "2330": trend(0.6), "2303": trend(0.5),     # semi
        "2317": trend(-0.4), "2354": trend(-0.3),   # weak
        "1101": trend(0.02), "1102": trend(0.0),    # mid
    }, index=idx)


def _flow(price, seed=1):
    """法人買賣超：semi 外資大買、weak 賣超。"""
    rng = np.random.default_rng(seed)
    idx = price.index
    foreign = pd.DataFrame({
        "2330": rng.normal(5e4, 1e4, len(idx)), "2303": rng.normal(3e4, 1e4, len(idx)),
        "2317": rng.normal(-3e4, 1e4, len(idx)), "2354": rng.normal(-2e4, 1e4, len(idx)),
        "1101": rng.normal(0, 1e4, len(idx)), "1102": rng.normal(0, 1e4, len(idx)),
    }, index=idx)
    trust = foreign * 0.3
    return foreign, trust


_SECTORS = {"semi": ["2330", "2303"], "weak": ["2317", "2354"], "mid": ["1101", "1102"]}


def test_month_end_dates():
    price = _price()
    rebs = rb.month_end_dates(price.index)
    # 每月一個 → 約 n/21 個
    assert len(rebs) >= 12
    # 嚴格遞增
    assert all(rebs[i] < rebs[i + 1] for i in range(len(rebs) - 1))


def test_chip_score_respects_variant_weight():
    price = _price()
    foreign, trust = _flow(price)
    asof = price.index[-1]
    # semi 外資>>投信 → foreign_led 分數應 > trust_led（因外資正、投信也正但小）
    fl = rb.sector_chip_score_at(foreign, trust, _SECTORS["semi"], asof,
                                 WeightVariant("fl", 2.0, 1.0))
    assert fl > 0  # semi 法人淨買


def test_rotation_rank_picks_strong_sector():
    price = _price()
    foreign, trust = _flow(price)
    ranked = rb.rotation_rank(price, foreign, trust, _SECTORS, price.index[-1],
                              WeightVariant("fl", 2.0, 1.0))
    # semi（動能+籌碼皆強）應排第一，weak 應墊底
    assert ranked[0] == "semi"
    assert ranked[-1] == "weak"


def test_simulate_returns_nav_series():
    price = _price()
    foreign, trust = _flow(price)
    nav = rb.simulate(price, foreign, trust, _SECTORS, WeightVariant("fl", 2.0, 1.0), top_n=1)
    assert len(nav) >= 2
    assert nav.iloc[0] == 1.0
    # 選到上漲的 semi → 終值應 > 起始
    assert nav.iloc[-1] > 1.0


def test_cost_reduces_nav():
    price = _price()
    foreign, trust = _flow(price)
    v = WeightVariant("fl", 2.0, 1.0)
    nav_free = rb.simulate(price, foreign, trust, _SECTORS, v, top_n=1, cost=0.0)
    nav_cost = rb.simulate(price, foreign, trust, _SECTORS, v, top_n=1, cost=0.02)
    assert nav_cost.iloc[-1] <= nav_free.iloc[-1]


def test_metrics_math():
    nav = pd.Series([1.0, 1.1, 1.05, 1.2, 1.15],
                    index=pd.date_range("2024-01-31", periods=5, freq="ME"))
    m = rb.metrics(nav)
    assert m["total"] == round(1.15 / 1.0 - 1, 4)
    assert m["mdd"] < 0  # 有回撤
    assert "sharpe" in m and "calmar" in m


def test_metrics_empty():
    m = rb.metrics(pd.Series([1.0]))
    assert m["annual"] == 0.0


def test_walk_forward_runs():
    price = _price(n=500)
    foreign, trust = _flow(price)
    res = rb.walk_forward(price, foreign, trust, _SECTORS,
                          WeightVariant("fl", 2.0, 1.0),
                          train_months=6, test_months=3, top_n=1)
    assert "oos_segments" in res
    assert res["oos_segments"] >= 1


def test_dealer_filter_reduces_score():
    price = _price()
    foreign, trust = _flow(price)
    asof = price.index[-1]
    dealer = foreign.copy()  # 自營同向大買 → 應折減
    v_no = WeightVariant("trust_led", 1.0, 2.0, use_dealer_filter=False)
    v_yes = WeightVariant("trust_led_df", 1.0, 2.0, use_dealer_filter=True)
    s_no = rb.sector_chip_score_at(foreign, trust, _SECTORS["semi"], asof, v_no)
    s_yes = rb.sector_chip_score_at(foreign, trust, _SECTORS["semi"], asof, v_yes, dealer_net=dealer)
    assert s_yes < s_no  # 濾網生效，分數下降
