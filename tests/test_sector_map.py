"""tests/test_sector_map.py — SectorMap 單元測試"""
import csv
import tempfile
from pathlib import Path

from src.sector_map import SectorMap


def _make_csv(rows: list[dict], path: Path) -> Path:
    """寫一個暫時 CSV 供 SectorMap.load 讀取。"""
    fieldnames = ["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_load_basic():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {
                    "sector_id": "foundry",
                    "sector_name": "晶圓代工",
                    "sector_type": "custom",
                    "parent_sector": "semiconductor",
                    "stock_ids": "2330,2303,3711",
                },
                {
                    "sector_id": "ic_design",
                    "sector_name": "IC 設計",
                    "sector_type": "custom",
                    "parent_sector": "semiconductor",
                    "stock_ids": "2454,3034",
                },
            ],
            csv_path,
        )
        count = sm.load(csv_path)

    assert count == 2
    assert sm.loaded is True
    assert len(sm) == 2


def test_get_stocks():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {
                    "sector_id": "foundry",
                    "sector_name": "晶圓代工",
                    "sector_type": "custom",
                    "parent_sector": "",
                    "stock_ids": "2330,2303,3711",
                },
            ],
            csv_path,
        )
        sm.load(csv_path)

    stocks = sm.get_stocks("foundry")
    assert stocks == ["2330", "2303", "3711"]


def test_get_stocks_missing_sector():
    sm = SectorMap()
    assert sm.get_stocks("nonexistent") == []


def test_get_sector_name():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {
                    "sector_id": "foundry",
                    "sector_name": "晶圓代工",
                    "sector_type": "custom",
                    "parent_sector": "",
                    "stock_ids": "2330",
                },
            ],
            csv_path,
        )
        sm.load(csv_path)

    assert sm.get_sector_name("foundry") == "晶圓代工"
    assert sm.get_sector_name("missing") == "missing"


def test_all_sector_ids():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {"sector_id": "a", "sector_name": "A", "sector_type": "custom", "parent_sector": "", "stock_ids": "1"},
                {"sector_id": "b", "sector_name": "B", "sector_type": "custom", "parent_sector": "", "stock_ids": "2"},
            ],
            csv_path,
        )
        sm.load(csv_path)

    assert set(sm.all_sector_ids()) == {"a", "b"}


def test_list_sectors():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {"sector_id": "x", "sector_name": "X板塊", "sector_type": "custom", "parent_sector": "p", "stock_ids": "1,2,3"},
            ],
            csv_path,
        )
        sm.load(csv_path)

    items = sm.list_sectors()
    assert len(items) == 1
    assert items[0]["id"] == "x"
    assert items[0]["name"] == "X板塊"
    assert items[0]["count"] == 3


def test_get_parent_sectors_and_children():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {"sector_id": "a", "sector_name": "A", "sector_type": "custom", "parent_sector": "p1", "stock_ids": "1"},
                {"sector_id": "b", "sector_name": "B", "sector_type": "custom", "parent_sector": "p1", "stock_ids": "2"},
                {"sector_id": "c", "sector_name": "C", "sector_type": "custom", "parent_sector": "p2", "stock_ids": "3"},
            ],
            csv_path,
        )
        sm.load(csv_path)

    parents = sm.get_parent_sectors()
    assert "p1" in parents
    assert "p2" in parents

    children = sm.get_children("p1")
    assert set(children) == {"a", "b"}


def test_add_stock():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [{"sector_id": "x", "sector_name": "X", "sector_type": "custom", "parent_sector": "", "stock_ids": "1"}],
            csv_path,
        )
        sm.load(csv_path)

    assert sm.add_stock("x", "2") is True
    assert "2" in sm.get_stocks("x")
    # Adding same stock again should not duplicate
    sm.add_stock("x", "2")
    assert sm.get_stocks("x").count("2") == 1
    # Adding to nonexistent sector
    assert sm.add_stock("missing", "3") is False


def test_load_missing_file():
    sm = SectorMap()
    count = sm.load(Path("/nonexistent/path.csv"))
    assert count == 0
    assert sm.loaded is False


def test_load_empty_sector_id_rows_skipped():
    sm = SectorMap()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "sectors.csv"
        _make_csv(
            [
                {"sector_id": "", "sector_name": "Empty", "sector_type": "custom", "parent_sector": "", "stock_ids": "1"},
                {"sector_id": "valid", "sector_name": "Valid", "sector_type": "custom", "parent_sector": "", "stock_ids": "2"},
            ],
            csv_path,
        )
        count = sm.load(csv_path)

    assert count == 1
    assert "valid" in sm.all_sector_ids()
