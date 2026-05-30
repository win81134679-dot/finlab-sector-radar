"""tests/test_scorer_backtest.py — point-in-time 評分回測核心測試（無需 token）"""
import numpy as np
import pandas as pd

from src.analyzers import scorer_backtest as sb


def _price(n=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    def trend(d):
        return 100 + np.cumsum(d + rng.normal(0, abs(d) * 1.5 + 0.2, n))
    return pd.DataFrame({"2330": trend(0.6), "2303": trend(0.2), "2317": trend(-0.3)}, index=idx)


# ── _asof_latest：point-in-time 切片 ─────────────────────────────────────

def test_asof_latest_respects_cutoff():
    """揭露日對齊後，asof 之前才可見。"""
    idx = pd.to_datetime(["2024-05-15", "2024-08-14", "2024-11-14"])
    eps = pd.DataFrame({"2330": [30.0, 40.0, 50.0]}, index=idx)
    # asof 在 8/14 之前 → 只看得到 5/15 那筆(30)
    assert sb._asof_latest(eps, "2330", pd.Timestamp("2024-07-01")) == 30.0
    # asof 在 8/14 當天 → 看得到 40
    assert sb._asof_latest(eps, "2330", pd.Timestamp("2024-08-14")) == 40.0


def test_asof_latest_none_when_no_data_before():
    idx = pd.to_datetime(["2024-08-14"])
    eps = pd.DataFrame({"2330": [40.0]}, index=idx)
    assert sb._asof_latest(eps, "2330", pd.Timestamp("2024-05-01")) is None


# ── score_stock_asof ─────────────────────────────────────────────────────

def test_score_includes_fundamentals():
    """EPS≥25 +2, ROE≥15 +1 → 至少 3 分（基本面）。"""
    price = _price()
    asof = price.index[-1]
    idx = pd.to_datetime(["2024-02-01"])
    eps = pd.DataFrame({"2330": [30.0]}, index=idx)
    roe = pd.DataFrame({"2330": [20.0]}, index=idx)
    score = sb.score_stock_asof(
        "2330", ["2330", "2303", "2317"], asof,
        price_df=price, eps_df=eps, roe_df=roe, pe_df=None,
        sector_mom=None, sector_chip_z=None, sector_pe_median=None,
        with_rotation=False,
    )
    assert score is not None and score >= 3.0


def test_rotation_bonus_adds_score():
    """同股，加輪動(動能轉強+法人進駐) 應比不加多最多 1 分。"""
    price = _price()
    asof = price.index[-1]
    kw = dict(price_df=price, eps_df=None, roe_df=None, pe_df=None,
              sector_pe_median=None)
    no_rot = sb.score_stock_asof("2330", ["2330", "2303", "2317"], asof,
                                 sector_mom=0.2, sector_chip_z=2.0, with_rotation=False, **kw)
    with_rot = sb.score_stock_asof("2330", ["2330", "2303", "2317"], asof,
                                   sector_mom=0.2, sector_chip_z=2.0, with_rotation=True, **kw)
    assert with_rot - no_rot == 1.0   # 動能>0 +0.5 + 籌碼z>1 +0.5


def test_score_none_on_insufficient_price():
    price = _price(n=20)  # < MA60+1
    score = sb.score_stock_asof("2330", ["2330"], price.index[-1],
                                price_df=price, eps_df=None, roe_df=None, pe_df=None,
                                sector_mom=None, sector_chip_z=None, sector_pe_median=None)
    assert score is None


# ── forward_beat ─────────────────────────────────────────────────────────

def test_forward_beat_true_when_stock_outperforms():
    """個股漲、大盤平 → beat=True。"""
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    price = pd.DataFrame({"2330": np.linspace(100, 150, n)}, index=idx)  # 漲
    bench = pd.Series(np.full(n, 1000.0), index=idx)                      # 平
    asof = idx[40]
    assert sb.forward_beat(price, "2330", asof, bench, hold_days=20) is True


def test_forward_beat_false_when_underperforms():
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    price = pd.DataFrame({"2330": np.full(n, 100.0)}, index=idx)          # 平
    bench = pd.Series(np.linspace(1000, 1200, n), index=idx)             # 漲
    asof = idx[40]
    assert sb.forward_beat(price, "2330", asof, bench, hold_days=20) is False


def test_forward_beat_none_insufficient_future():
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    price = pd.DataFrame({"2330": np.linspace(100, 150, n)}, index=idx)
    bench = pd.Series(np.linspace(1000, 1100, n), index=idx)
    # asof 太接近尾端 → 未來不足 60 日
    assert sb.forward_beat(price, "2330", idx[-5], bench, hold_days=60) is None


def test_zscore_map():
    z = sb._zscore_map({"a": 1.0, "b": 2.0, "c": 3.0})
    assert abs(z["b"]) < 1e-9         # 中位 → z≈0
    assert z["c"] > 0 and z["a"] < 0
