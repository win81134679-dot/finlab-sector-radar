"""tests/test_cycle_clock.py — 景氣循環時鐘單元測試"""
import csv
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.analyzers import cycle_clock


def _taiex(n=260, drift=1.0, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    vals = 15000 + np.cumsum(drift + rng.normal(0, 20, n))
    return pd.DataFrame({"發行量加權股價指數": vals}, index=idx)


class _Fetcher:
    def __init__(self, taiex):
        self._t = taiex

    def get(self, key):
        return self._t if "taiex" in key else None


class _Cfg:
    def __init__(self, base_dir):
        self.BASE_DIR = base_dir


def _write_ndc(base_dir: Path, rows):
    d = base_dir / "data"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "ndc_monitor.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "score"])
        w.writeheader()
        w.writerows(rows)


# ── 官方 NDC 路徑 ────────────────────────────────────────────────────────

def test_ndc_official_blue_light_recovery(tmp_path):
    """藍燈(≤16) + 動能↑ → 復甦，且 source=ndc_official。"""
    _write_ndc(tmp_path, [{"date": "2026-05-27", "score": "14"}])
    fetcher = _Fetcher(_taiex(drift=2.0))  # 上升動能
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["source"] == "ndc_official"
    assert res["ndc_score"] == 14.0
    assert res["phase"] == "recovery"
    assert "banking" in res["favored_sectors"]


def test_ndc_official_red_light_with_up_momentum_expansion(tmp_path):
    """紅燈(≥38) + 動能↑ → 擴張。"""
    _write_ndc(tmp_path, [{"date": "2026-05-27", "score": "39"}])
    fetcher = _Fetcher(_taiex(drift=2.0))
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["phase"] == "expansion"
    assert "foundry" in res["favored_sectors"]


def test_ndc_stale_falls_back_to_proxy(tmp_path):
    """官方分數過期（>45天）→ 改用代理（source=proxy）。"""
    _write_ndc(tmp_path, [{"date": "2026-01-01", "score": "14"}])
    fetcher = _Fetcher(_taiex(drift=2.0))
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["source"] == "proxy"


def test_ndc_picks_latest_row(tmp_path):
    """多筆時取最新日期。"""
    _write_ndc(tmp_path, [
        {"date": "2026-03-27", "score": "20"},
        {"date": "2026-05-27", "score": "40"},
    ])
    fetcher = _Fetcher(_taiex(drift=2.0))
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["ndc_score"] == 40.0


# ── 代理 fallback 路徑 ───────────────────────────────────────────────────

def test_proxy_when_no_csv(tmp_path):
    """無 CSV → 代理。"""
    fetcher = _Fetcher(_taiex(drift=2.0))
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["source"] == "proxy"
    assert res["phase"] in ("recovery", "expansion", "slowdown", "recession")


def test_proxy_unknown_on_short_data(tmp_path):
    """TAIEX 資料不足 200 日 → unknown。"""
    fetcher = _Fetcher(_taiex(n=50))
    res = cycle_clock.analyze(fetcher, _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["phase"] == "unknown"


def test_unknown_when_no_taiex(tmp_path):
    class _Null:
        def get(self, key):
            return None
    res = cycle_clock.analyze(_Null(), _Cfg(tmp_path), now=datetime(2026, 6, 1))
    assert res["phase"] == "unknown"
    assert res["favored_sectors"] == []
