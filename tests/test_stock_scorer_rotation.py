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


def _raw_trust(trust_only_ids, in_window_dressing):
    """構造含燈2 投信獨買 + 季末作帳旗標的 raw_results。"""
    return {
        "燈2 法人共振": {
            "semi": {
                "lit_stocks": [], "foreign_only": [], "trust_only": trust_only_ids,
                "in_window_dressing": in_window_dressing,
            }
        },
    }


def test_trust_only_scores_when_not_window_dressing():
    """非季末作帳期：投信獨買 → 籌碼面 +1.0 + 燈2_投信✓。"""
    raw = _raw_trust(["2330"], in_window_dressing=False)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["chipset"] == 1.0
    assert "燈2_投信✓" in res["2330"]["triggered"]


def test_trust_only_downgraded_in_window_dressing():
    """季末作帳期：投信獨買不計分（§9.4.2 排除季末提升 alpha）。"""
    raw = _raw_trust(["2330"], in_window_dressing=True)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg())
    assert res["2330"]["breakdown"]["chipset"] == 0.0
    assert any("季末作帳" in t for t in res["2330"]["triggered"])


def test_volume_bonus_with_trust_and_volume():
    """投信獨買(非季末) + 量比≥1.3 → 籌碼面額外 +0.5（帶量加分）。"""
    raw = _raw_trust(["2330"], in_window_dressing=False)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg(),
                                    vol_ratio_map={"2330": 1.8})
    # 投信獨買 +1.0 + 帶量 +0.5 = 1.5
    assert res["2330"]["breakdown"]["chipset"] == 1.5
    assert any("帶量" in t for t in res["2330"]["triggered"])


def test_no_volume_bonus_without_trust_signal():
    """無投信訊號 → 即使帶量也不加分（帶量只在投信訊號上疊加）。"""
    raw = {"燈2 法人共振": {"semi": {"lit_stocks": [], "foreign_only": ["2330"],
                                     "trust_only": [], "in_window_dressing": False}}}
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg(),
                                    vol_ratio_map={"2330": 2.0})
    # 外資獨買 +0.5，無帶量加分（外資非投信）
    assert res["2330"]["breakdown"]["chipset"] == 0.5
    assert not any("帶量" in t for t in res["2330"]["triggered"])


def test_no_volume_bonus_when_volume_low():
    """投信獨買但量比 <1.3 → 無帶量加分。"""
    raw = _raw_trust(["2330"], in_window_dressing=False)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg(),
                                    vol_ratio_map={"2330": 1.0})
    assert res["2330"]["breakdown"]["chipset"] == 1.0  # 只有投信 +1.0
    assert not any("帶量" in t for t in res["2330"]["triggered"])


def test_no_volume_bonus_in_window_dressing():
    """季末作帳期：投信不計分，帶量也不疊加（無投信訊號基底）。"""
    raw = _raw_trust(["2330"], in_window_dressing=True)
    res = stock_scorer.score_stocks("semi", ["2330"], raw, _Fetcher(), _Cfg(),
                                    vol_ratio_map={"2330": 2.0})
    assert res["2330"]["breakdown"]["chipset"] == 0.0
