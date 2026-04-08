"""tests/test_exit_alert.py — 隔日出場警報產生器單元測試"""
from unittest.mock import patch, MagicMock

import pytest

from src.analyzers.exit_alert import (
    _calc_alert_score,
    _count_systemic_risk_sectors,
    generate_exit_alerts,
    W_RRG,
    W_DELTA,
    W_CHIP,
    W_VOL_PRICE,
    W_SYSTEMIC,
    SYSTEMIC_THRESHOLD,
    SYSTEMIC_SCORE_MIN,
)


def _make_sector(
    exit_score=40,
    rs_quadrant="Leading",
    signals=None,
    cycle_stage="加速期",
    total=5,
    name_zh="測試板塊",
):
    return {
        "exit_risk": {"score": exit_score, "rs_quadrant": rs_quadrant},
        "signals": signals or [1, 1, 1, 1, 1, 1, 1],
        "cycle_stage": cycle_stage,
        "total": total,
        "name_zh": name_zh,
    }


# ── _count_systemic_risk_sectors ─────────────────────────────────────────

class TestCountSystemicRiskSectors:
    def test_no_sectors(self):
        assert _count_systemic_risk_sectors({}) == 0

    def test_below_threshold(self):
        sectors = {"a": _make_sector(exit_score=55)}
        assert _count_systemic_risk_sectors(sectors) == 0

    def test_at_threshold(self):
        sectors = {"a": _make_sector(exit_score=SYSTEMIC_SCORE_MIN)}
        assert _count_systemic_risk_sectors(sectors) == 1

    def test_multiple_above(self):
        sectors = {
            "a": _make_sector(exit_score=60),
            "b": _make_sector(exit_score=70),
            "c": _make_sector(exit_score=40),
        }
        assert _count_systemic_risk_sectors(sectors) == 2


# ── _calc_alert_score ────────────────────────────────────────────────────

class TestCalcAlertScore:
    def test_returns_none_without_exit_risk(self):
        sector = {"cycle_stage": "加速期"}
        assert _calc_alert_score("s1", sector, None, 0) is None

    def test_returns_none_for_non_hot_cycle(self):
        sector = _make_sector(cycle_stage="衰退期")
        assert _calc_alert_score("s1", sector, None, 0) is None

    def test_rrg_weakening_triggers(self):
        # RRG (30) + systemic (10) = 40 → 留意
        sector = _make_sector(rs_quadrant="轉弱中 Weakening")
        result = _calc_alert_score("s1", sector, None, systemic_count=SYSTEMIC_THRESHOLD)
        assert result is not None
        assert result["score"] >= W_RRG
        assert any("RRG" in t for t in result["triggers"])

    def test_delta_triggers(self):
        # delta (25) + systemic (10) = 35 → 留意
        sector = _make_sector(exit_score=50)
        prev = {"sectors": {"s1": {"exit_risk": {"score": 30}}}}
        result = _calc_alert_score("s1", sector, prev, systemic_count=SYSTEMIC_THRESHOLD)
        assert result is not None
        assert result["delta"] == 20
        assert any("急升" in t for t in result["triggers"])

    def test_chip_off_triggers(self):
        # chip (20) + systemic (10) + vol_price may trigger too
        # chip off + high total → at least 留意
        sector = _make_sector(
            signals=[1, 1, 1, 0, 1, 0, 1],
            total=5,
            rs_quadrant="Leading",
        )
        prev = {"sectors": {"s1": {"signals": [1, 1, 1, 1, 1, 1, 1]}}}
        result = _calc_alert_score("s1", sector, prev, 0)
        assert result is not None
        assert any("籌碼" in t or "動能" in t for t in result["triggers"])

    def test_vol_price_triggers(self):
        sector = _make_sector(signals=[1, 1, 1, 0, 1, 1, 1], total=5)
        result = _calc_alert_score("s1", sector, None, 0)
        # tech signal off + total >= 4 → vol_price triggers
        if result:
            assert any("動能" in t for t in result["triggers"])

    def test_systemic_triggers(self):
        sector = _make_sector(rs_quadrant="轉弱中")
        result = _calc_alert_score("s1", sector, None, systemic_count=SYSTEMIC_THRESHOLD)
        assert result is not None
        assert any("系統" in t for t in result["triggers"])

    def test_action_levels(self):
        # 高分 → 出場
        sector = _make_sector(
            exit_score=80,
            rs_quadrant="Weakening",
            signals=[1, 1, 1, 0, 1, 0, 1],
            total=5,
        )
        prev = {"sectors": {"s1": {
            "exit_risk": {"score": 50},
            "signals": [1, 1, 1, 1, 1, 1, 1],
        }}}
        result = _calc_alert_score("s1", sector, prev, systemic_count=SYSTEMIC_THRESHOLD)
        assert result is not None
        assert result["action"] == "出場"
        assert result["score"] >= 71

    def test_score_capped_at_100(self):
        sector = _make_sector(
            exit_score=90,
            rs_quadrant="Lagging",
            signals=[1, 1, 1, 0, 1, 0, 1],
            total=6,
        )
        prev = {"sectors": {"s1": {
            "exit_risk": {"score": 50},
            "signals": [1, 1, 1, 1, 1, 1, 1],
        }}}
        result = _calc_alert_score("s1", sector, prev, systemic_count=5)
        assert result is not None
        assert result["score"] <= 100

    def test_low_score_returns_none(self):
        # 無觸發因子 → score = 0 → action = 無 → return None
        sector = _make_sector(exit_score=20, rs_quadrant="Leading")
        result = _calc_alert_score("s1", sector, None, 0)
        assert result is None


# ── generate_exit_alerts ─────────────────────────────────────────────────

class TestGenerateExitAlerts:
    @patch("src.analyzers.exit_alert._save_json")
    @patch("src.analyzers.exit_alert._load_previous_snapshot", return_value=None)
    def test_empty_sectors(self, mock_load, mock_save):
        result = generate_exit_alerts({})
        assert result["summary"]["exit_count"] == 0
        assert result["summary"]["reduce_count"] == 0
        assert result["summary"]["watch_count"] == 0
        assert result["system_risk_level"] == "low"

    @patch("src.analyzers.exit_alert._save_json")
    @patch("src.analyzers.exit_alert._load_previous_snapshot", return_value=None)
    def test_with_sector_alert_and_holdings(self, mock_load, mock_save):
        sectors = {
            "s1": _make_sector(
                exit_score=60,
                rs_quadrant="Weakening",
                cycle_stage="加速期",
                signals=[1, 1, 1, 0, 1, 0, 1],
                total=5,
            ),
        }
        holdings = {
            "2330": {"sector": "s1", "name_zh": "台積電", "composite_score": 80, "weight": 0.2},
        }
        result = generate_exit_alerts(sectors, holdings)
        assert len(result["position_alerts"]) > 0
        assert "2330" in result["position_alerts"]
        alert = result["position_alerts"]["2330"]
        assert alert["action"] in ("留意", "減碼", "出場")

    @patch("src.analyzers.exit_alert._save_json")
    @patch("src.analyzers.exit_alert._load_previous_snapshot", return_value=None)
    def test_system_risk_elevated(self, mock_load, mock_save):
        sectors = {}
        for i in range(4):
            sectors[f"s{i}"] = _make_sector(
                exit_score=70,
                rs_quadrant="Weakening",
                cycle_stage="加速期",
            )
        result = generate_exit_alerts(sectors)
        assert result["system_risk_level"] == "elevated"
        assert result["systemic_sector_count"] >= SYSTEMIC_THRESHOLD

    @patch("src.analyzers.exit_alert._save_json")
    @patch("src.analyzers.exit_alert._load_previous_snapshot", return_value=None)
    def test_safe_count_calculation(self, mock_load, mock_save):
        sectors = {
            "s1": _make_sector(exit_score=60, rs_quadrant="Weakening"),
        }
        holdings = {
            "2330": {"sector": "s1", "name_zh": "台積電", "composite_score": 80, "weight": 0.2},
            "2317": {"sector": "s2", "name_zh": "鴻海", "composite_score": 70, "weight": 0.1},
        }
        result = generate_exit_alerts(sectors, holdings)
        total_alerted = len(result["position_alerts"])
        assert result["summary"]["safe_count"] == 2 - total_alerted

    @patch("src.analyzers.exit_alert._save_json")
    @patch("src.analyzers.exit_alert._load_previous_snapshot", return_value=None)
    def test_save_json_called(self, mock_load, mock_save):
        generate_exit_alerts({})
        mock_save.assert_called_once()
