"""tests/test_rotation_integration.py — 輪動層整合（_compute_rotation_scores + 註冊）"""
from src.analyzers.multi_signal import _compute_rotation_scores


def _raw(rsi_map, chip_map):
    return {
        "輪動_產業RSI": rsi_map,
        "輪動_板塊籌碼": chip_map,
    }


def test_rotation_score_combines_three_dims():
    """綜合強度 = z(動能) + z(RSI斜率) + z(籌碼) 的平均；強板塊應 > 弱板塊。"""
    rsi_map = {
        "semi": {"sector_momentum_pct": 40.0, "rsi_slope_5d": 8.0},
        "weak": {"sector_momentum_pct": -10.0, "rsi_slope_5d": -3.0},
        "mid":  {"sector_momentum_pct": 5.0,  "rsi_slope_5d": 1.0},
    }
    chip_map = {
        "semi": {"chip_flow": {"score": 5}},
        "weak": {"chip_flow": {"score": 0}},
        "mid":  {"chip_flow": {"score": 2}},
    }
    scores = _compute_rotation_scores(_raw(rsi_map, chip_map), ["semi", "weak", "mid"])
    assert scores["semi"] is not None
    assert scores["semi"] > scores["mid"] > scores["weak"]


def test_rotation_score_none_when_no_data():
    """無輪動資料的板塊 → None（不崩潰）。"""
    scores = _compute_rotation_scores(_raw({}, {}), ["a", "b"])
    assert scores == {"a": None, "b": None}


def test_rotation_score_partial_dims():
    """只有部分維度有資料時仍可計算（用可得維度平均）。"""
    rsi_map = {"a": {"sector_momentum_pct": 10.0}, "b": {"sector_momentum_pct": -10.0}}
    scores = _compute_rotation_scores(_raw(rsi_map, {}), ["a", "b"])
    assert scores["a"] is not None and scores["b"] is not None
    assert scores["a"] > scores["b"]


def test_rotation_analyzers_registered_in_run_all():
    """確認 run_all 的 steps 註冊了兩個輪動分析器（防止漏接）。"""
    import inspect
    from src.analyzers import multi_signal
    src = inspect.getsource(multi_signal.run_all)
    assert "輪動_產業RSI" in src
    assert "輪動_板塊籌碼" in src


def test_rotation_modules_importable():
    """兩個輪動分析器模組可正常 import 且有 analyze。"""
    from src.analyzers import sector_rsi, sector_chips
    assert callable(sector_rsi.analyze)
    assert callable(sector_chips.analyze)
