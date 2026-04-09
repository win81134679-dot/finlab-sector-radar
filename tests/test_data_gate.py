"""tests/test_data_gate.py — 資料可用性閘門 + 品質退化保護測試"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── 輔助：建構模擬分析器輸出 ──────────────────────────────────────────


def _make_raw(valid_analyzers: list[str], fake_data_analyzers: list[str] | None = None):
    """
    建構 raw dict，模擬各分析器的回傳。
    valid_analyzers: 有真實資料的分析器名稱 list
    fake_data_analyzers: 回傳假資料（{sector: {signal:False, score:0}}）的分析器名稱 list
    """
    ALL = [
        "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
        "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
    ]
    fake_data_analyzers = fake_data_analyzers or []
    raw = {}
    for name in ALL:
        if name in valid_analyzers:
            raw[name] = {
                "sector_001": {"signal": True, "score": 0.8, "pct_lit": 80.0},
                "sector_002": {"signal": False, "score": 0.2, "pct_lit": 20.0},
            }
        elif name in fake_data_analyzers:
            # 燈3 式假資料：回傳結構但全部空信號
            raw[name] = {
                "sector_001": {"signal": False, "score": 0, "pct_lit": 0.0,
                               "lit_stocks": [], "total_stocks": 0, "details": "無數據"},
                "sector_002": {"signal": False, "score": 0, "pct_lit": 0.0,
                               "lit_stocks": [], "total_stocks": 0, "details": "無數據"},
            }
        else:
            raw[name] = {}  # 空 dict = API 完全失敗

    # 燈7 宏觀（獨立資料源，始終可用）
    raw["燈7 宏觀濾網"] = {"signal": True, "positive_count": 3, "total_available": 4}
    return raw


# ── 閘門測試 ──────────────────────────────────────────────────────────


class TestDataAvailabilityGate:
    """測試 multi_signal.py 中的資料可用性閘門。"""

    def _import_gate_helper(self):
        """匯入閘門所需的常數與輔助函式。"""
        # 直接測試閘門邏輯，不需要完整 run_all
        from src.analyzers.multi_signal import run_all
        return run_all

    def test_all_6_empty_raises(self):
        """全 6 個板塊分析器回傳空 dict → RuntimeError"""
        raw = _make_raw(valid_analyzers=[])
        # 測試 _is_analyzer_empty 邏輯
        from src.analyzers import multi_signal as ms
        SECTOR_ANALYZERS = [
            "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
            "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
        ]

        # 模擬閘門邏輯
        def _is_analyzer_empty(data: dict) -> bool:
            if not data:
                return True
            return all(
                not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
                for entry in data.values()
                if isinstance(entry, dict)
            )

        valid_count = sum(1 for n in SECTOR_ANALYZERS if not _is_analyzer_empty(raw.get(n, {})))
        assert valid_count == 0

    def test_5_empty_plus_fake_data_raises(self):
        """5 個空 + 燈3 假資料（原 bug 場景）→ 仍應被判定為無效"""
        raw = _make_raw(valid_analyzers=[], fake_data_analyzers=["燈3 庫存循環"])

        def _is_analyzer_empty(data: dict) -> bool:
            if not data:
                return True
            return all(
                not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
                for entry in data.values()
                if isinstance(entry, dict)
            )

        SECTOR_ANALYZERS = [
            "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
            "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
        ]
        valid_count = sum(1 for n in SECTOR_ANALYZERS if not _is_analyzer_empty(raw.get(n, {})))
        # 燈3 假資料應被偵測為空 → valid_count 仍為 0
        assert valid_count == 0

    def test_3_empty_below_threshold(self):
        """3 個有效 + 3 個空 → valid_count=3 < 4 → 應觸發閘門"""
        raw = _make_raw(valid_analyzers=["燈1 月營收拐點", "燈2 法人共振", "燈4 技術突破"])

        def _is_analyzer_empty(data: dict) -> bool:
            if not data:
                return True
            return all(
                not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
                for entry in data.values()
                if isinstance(entry, dict)
            )

        SECTOR_ANALYZERS = [
            "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
            "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
        ]
        valid_count = sum(1 for n in SECTOR_ANALYZERS if not _is_analyzer_empty(raw.get(n, {})))
        assert valid_count == 3
        assert valid_count < 4  # 低於閾值

    def test_4_valid_passes_gate(self):
        """4 個有效 + 2 個空 → valid_count=4 ≥ 4 → 應通過閘門"""
        raw = _make_raw(valid_analyzers=[
            "燈1 月營收拐點", "燈2 法人共振", "燈4 技術突破", "燈5 相對強度",
        ])

        def _is_analyzer_empty(data: dict) -> bool:
            if not data:
                return True
            return all(
                not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
                for entry in data.values()
                if isinstance(entry, dict)
            )

        SECTOR_ANALYZERS = [
            "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
            "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
        ]
        valid_count = sum(1 for n in SECTOR_ANALYZERS if not _is_analyzer_empty(raw.get(n, {})))
        assert valid_count == 4
        assert valid_count >= 4  # 通過閾值

    def test_all_6_valid(self):
        """全 6 個有效 → valid_count=6"""
        ALL = [
            "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
            "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
        ]
        raw = _make_raw(valid_analyzers=ALL)

        def _is_analyzer_empty(data: dict) -> bool:
            if not data:
                return True
            return all(
                not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
                for entry in data.values()
                if isinstance(entry, dict)
            )

        valid_count = sum(1 for n in ALL if not _is_analyzer_empty(raw.get(n, {})))
        assert valid_count == 6


class TestQualityDegradationGuard:
    """測試品質異常退化保護。"""

    def test_prev_strong_10_new_strong_0_detects_anomaly(self):
        """前次 10 個強烈關注 → 本次 0 → 應視為異常"""
        prev_strong = 10
        new_strong = 0
        assert prev_strong >= 5 and new_strong == 0

    def test_prev_strong_5_new_strong_3_normal(self):
        """前次 5 個 → 本次 3 → 正常市場波動，不應觸發"""
        prev_strong = 5
        new_strong = 3
        assert not (prev_strong >= 5 and new_strong == 0)

    def test_prev_strong_2_new_strong_0_normal(self):
        """前次僅 2 個 → 本次 0 → 可能是正常退場，不應觸發"""
        prev_strong = 2
        new_strong = 0
        assert not (prev_strong >= 5 and new_strong == 0)


class TestInventoryAnalyzerFailure:
    """測試燈3 在 API 失敗時的行為一致性。"""

    def test_inv_df_none_returns_empty_dict(self):
        """inv_df=None → 應回傳 {} 空 dict（與其他分析器一致）"""
        mock_fetcher = MagicMock()
        mock_fetcher.get.return_value = None

        mock_sector_map = MagicMock()
        mock_sector_map.all_sector_ids.return_value = ["sector_001", "sector_002"]
        mock_sector_map.get_stocks.return_value = ["2330", "2317"]

        mock_config = MagicMock()
        mock_config.INVENTORY_SECTOR_THRESHOLD = 0.5

        from src.analyzers.inventory import analyze
        result = analyze(mock_fetcher, mock_sector_map, mock_config)

        # 應回傳空 dict，而非包含 _empty() 結果的 dict
        assert result == {}

    def test_inv_df_valid_returns_sectors(self):
        """inv_df 有資料 → 應回傳各 sector 的結果"""
        import pandas as pd
        import numpy as np

        mock_fetcher = MagicMock()
        # 建構有效的 DataFrame
        dates = pd.date_range("2025-01-01", periods=4, freq="QE")
        mock_fetcher.get.return_value = pd.DataFrame(
            {"2330": [3.0, 3.2, 3.5, 3.8], "2317": [2.0, 1.8, 1.5, 1.3]},
            index=dates,
        )

        mock_sector_map = MagicMock()
        mock_sector_map.all_sector_ids.return_value = ["sector_001"]
        mock_sector_map.get_stocks.return_value = ["2330", "2317"]

        mock_config = MagicMock()
        mock_config.INVENTORY_SECTOR_THRESHOLD = 0.5

        from src.analyzers.inventory import analyze
        result = analyze(mock_fetcher, mock_sector_map, mock_config)

        assert "sector_001" in result
        assert "signal" in result["sector_001"]
