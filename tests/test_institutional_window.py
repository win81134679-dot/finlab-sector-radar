"""tests/test_institutional_window.py — 季末作帳期偵測（燈2 投信降級）單元測試"""
import pandas as pd

from src.analyzers.institutional import _is_quarter_end_window


def _trust_df(dates):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"2330": range(len(idx))}, index=idx)


def test_none_or_empty():
    assert _is_quarter_end_window(None) is False
    assert _is_quarter_end_window(pd.DataFrame()) is False


def test_latest_in_quarter_end_window():
    """最新日落在 3 月最後 10 個交易日 → True。"""
    # 3 月一整月交易日（B=工作日）
    dates = pd.bdate_range("2024-03-01", "2024-03-29")
    assert _is_quarter_end_window(_trust_df(dates), last_n_days=10) is True


def test_latest_early_in_quarter_end_month_is_false():
    """最新日在 3 月初（非最後 10 交易日）→ False。"""
    dates = pd.bdate_range("2024-03-01", "2024-03-08")  # 僅月初幾天
    assert _is_quarter_end_window(_trust_df(dates), last_n_days=10) is False


def test_non_quarter_end_month_is_false():
    """4 月（非季末月）→ 永遠 False。"""
    dates = pd.bdate_range("2024-04-01", "2024-04-30")
    assert _is_quarter_end_window(_trust_df(dates), last_n_days=10) is False


def test_other_quarter_end_months():
    """6/9/12 月底同樣觸發。"""
    for end in ("2024-06-28", "2024-09-30", "2024-12-31"):
        dates = pd.bdate_range(pd.Timestamp(end) - pd.Timedelta(days=20), end)
        assert _is_quarter_end_window(_trust_df(dates), last_n_days=10) is True
