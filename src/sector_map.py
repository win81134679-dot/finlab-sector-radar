"""
sector_map.py — 板塊定義載入器（雙源合併）

資料來源：
  1. custom_sectors.csv（手動定義，最高優先權）
  2. output/auto_sectors.csv（官方產業碼自動產生，補充未覆蓋股票）

後續可直接編輯 CSV 新增或修改板塊，不需改 Python 代碼。
"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SectorMap:
    """
    載入並管理板塊定義。

    CSV 欄位：
        sector_id, sector_name, sector_type, parent_sector, stock_ids...
        （stock_ids 可以是單欄逗號分隔，也允許多個後續欄位）
    """

    def __init__(self):
        self._sectors: Dict[str, Dict] = {}
        self._loaded: bool = False

    def load(self, csv_path: Optional[Path] = None) -> int:
        """
        從 CSV 載入板塊定義。
        先讀 custom_sectors.csv（最高優先），再讀 auto_sectors.csv（補充）。
        回傳載入的板塊數量。
        """
        from src import config
        csv_path = csv_path or config.CUSTOM_SECTORS_CSV

        self._sectors = {}
        count = 0

        # 第一源：custom_sectors.csv
        count += self._load_csv(csv_path, source="custom")

        # 第二源：auto_sectors.csv（補充未覆蓋股票）
        auto_path = config.OUTPUT_DIR / "auto_sectors.csv"
        if auto_path.exists():
            count += self._load_csv(auto_path, source="auto")
        else:
            logger.debug("auto_sectors.csv 不存在，僅使用 custom 板塊")

        self._loaded = count > 0
        logger.info(f"載入 {count} 個板塊定義（custom + auto）")
        return count

    def _load_csv(self, csv_path: Path, source: str = "custom") -> int:
        """從單一 CSV 載入板塊定義。"""
        if not csv_path.exists():
            logger.error(f"找不到板塊定義檔: {csv_path}")
            return 0

        count = 0
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row.get("sector_id", "").strip()
                if not sid:
                    continue

                stocks: List[str] = []
                raw_ids = row.get("stock_ids", "") or ""
                if isinstance(raw_ids, list):
                    raw_ids = ",".join(str(x) for x in raw_ids)
                for part in str(raw_ids).split(","):
                    s = part.strip()
                    if s:
                        stocks.append(s)

                if sid in self._sectors:
                    # 已存在的 sector_id（custom 優先），跳過
                    continue

                self._sectors[sid] = {
                    "name":    row.get("sector_name", sid).strip(),
                    "type":    row.get("sector_type", source).strip(),
                    "parent":  row.get("parent_sector", "").strip(),
                    "stocks":  stocks,
                    "source":  source,
                }
                count += 1

        logger.info(f"  [{source}] {csv_path.name}: {count} 個板塊")
        return count

    # ── 查詢接口 ──────────────────────────────────────────────────────────

    def get_stocks(self, sector_id: str) -> List[str]:
        return self._sectors.get(sector_id, {}).get("stocks", [])

    def get_sector_name(self, sector_id: str) -> str:
        return self._sectors.get(sector_id, {}).get("name", sector_id)

    def get_sector_type(self, sector_id: str) -> str:
        return self._sectors.get(sector_id, {}).get("type", "custom")

    def get_sector_source(self, sector_id: str) -> str:
        """回傳板塊來源：'custom' 或 'auto'。"""
        return self._sectors.get(sector_id, {}).get("source", "custom")

    def all_sector_ids(self) -> List[str]:
        return list(self._sectors.keys())

    def list_sectors(self) -> List[Dict]:
        """回傳所有板塊摘要，供 CLI 選單使用。"""
        return [
            {
                "id":     sid,
                "name":   v["name"],
                "type":   v["type"],
                "parent": v["parent"],
                "count":  len(v["stocks"]),
            }
            for sid, v in self._sectors.items()
        ]

    def get_parent_sectors(self) -> List[str]:
        """回傳有子板塊的父板塊清單。"""
        parents = {v["parent"] for v in self._sectors.values() if v["parent"]}
        return sorted(parents)

    def get_children(self, parent_id: str) -> List[str]:
        """回傳指定父板塊下的所有子板塊 ID。"""
        return [
            sid for sid, v in self._sectors.items()
            if v.get("parent") == parent_id
        ]

    def add_stock(self, sector_id: str, stock_code: str) -> bool:
        """動態新增個股到板塊（不持久化，需重新載入 CSV 後消失）。"""
        if sector_id not in self._sectors:
            return False
        if stock_code not in self._sectors[sector_id]["stocks"]:
            self._sectors[sector_id]["stocks"].append(stock_code)
        return True

    def create_filtered(self, filtered_stocks: Dict[str, List[str]]) -> "SectorMap":
        """
        建立一個新的 SectorMap，板塊成員替換為過濾後的股票清單。
        用於 correlation gate 過濾異質股後的分析器調用。

        Parameters
        ----------
        filtered_stocks : dict
            {sector_id: [filtered_stock_ids, ...]}
        """
        import copy
        new_sm = SectorMap()
        new_sm._sectors = copy.deepcopy(self._sectors)
        new_sm._loaded = True
        for sid, stocks in filtered_stocks.items():
            if sid in new_sm._sectors:
                new_sm._sectors[sid]["stocks"] = list(stocks)
        return new_sm

    @property
    def loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._sectors)


# 全域單例
sector_map = SectorMap()
