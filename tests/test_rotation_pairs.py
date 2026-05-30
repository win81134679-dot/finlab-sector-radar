"""tests/test_rotation_pairs.py — 領先落後 / 接棒訊號單元測試（無 statsmodels 依賴）"""
import numpy as np

from src.analyzers import rotation_pairs as rp


# ── lead_lag_correlation ─────────────────────────────────────────────────

def test_lead_lag_detects_known_lag():
    """B 是 A 延遲 5 期的複製 → best_lag 應 ≈ 5、相關高。"""
    rng = np.random.default_rng(0)
    a = np.cumsum(rng.normal(0, 1, 200))
    lag_true = 5
    b = np.concatenate([np.zeros(lag_true), a[:-lag_true]])  # B 落後 A 5 期
    lag, corr = rp.lead_lag_correlation(a, b, max_lag=20)
    assert lag == lag_true
    assert corr > 0.9


def test_lead_lag_insufficient_data():
    lag, corr = rp.lead_lag_correlation(np.arange(5), np.arange(5), max_lag=20)
    assert lag == 0 and corr == 0.0


def test_lead_lag_no_variance():
    a = np.ones(100)
    b = np.ones(100)
    lag, corr = rp.lead_lag_correlation(a, b, max_lag=10)
    assert lag == 0 and corr == 0.0


# ── detect_handoffs ──────────────────────────────────────────────────────

_PAIRS = [{"leader": "shipping", "laggard": "foundry", "lag_days": 14, "corr": 0.45}]


def test_handoff_triggers_when_leader_hot_and_laggard_early():
    """領先 RSI 分位≥80 + 落後在萌芽期 → 接棒候選。"""
    rot = {"shipping": {"rsi_percentile": 88.0}, "foundry": {"rsi_percentile": 40.0}}
    levels = {"foundry": "萌芽期"}
    out = rp.detect_handoffs(rot, levels, _PAIRS)
    assert "foundry" in out
    assert out["foundry"]["from"] == "shipping"
    assert out["foundry"]["signal"] == "接棒候選"


def test_no_handoff_when_leader_not_hot():
    """領先 RSI 分位 < 80 → 不觸發。"""
    rot = {"shipping": {"rsi_percentile": 60.0}, "foundry": {"rsi_percentile": 40.0}}
    levels = {"foundry": "萌芽期"}
    assert rp.detect_handoffs(rot, levels, _PAIRS) == {}


def test_no_handoff_when_laggard_already_launched():
    """落後板塊已在加速期（已發動）→ 不觸發（錯過接棒窗口）。"""
    rot = {"shipping": {"rsi_percentile": 90.0}, "foundry": {"rsi_percentile": 70.0}}
    levels = {"foundry": "加速期"}
    assert rp.detect_handoffs(rot, levels, _PAIRS) == {}


def test_handoff_handles_missing_data():
    assert rp.detect_handoffs({}, {}, _PAIRS) == {}
    assert rp.detect_handoffs({"shipping": {"rsi_percentile": 90}}, {}, _PAIRS) == {}


def test_load_pairs_missing_file_returns_empty(tmp_path):
    class _Cfg:
        OUTPUT_DIR = tmp_path
    assert rp.load_pairs(_Cfg()) == []
