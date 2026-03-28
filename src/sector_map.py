"""
sector_map.py — 板塊定義載入器

資料來源：custom_sectors.csv（雙層結構：TWSE大類 + 自訂子板塊）
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
        回傳載入的板塊數量。
        """
        from src import config
        csv_path = csv_path or config.CUSTOM_SECTORS_CSV

        if not csv_path.exists():
            logger.error(f"找不到板塊定義檔: {csv_path}")
            return 0

        self._sectors = {}
        count = 0

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row.get("sector_id", "").strip()
                if not sid:
                    continue

                # 收集所有 stock_ids（支援引號包住的逗號分隔字串）
                stocks: List[str] = []
                raw_ids = row.get("stock_ids", "") or ""
                # raw_ids 可能是 str（正確格式），也可能因 CSV 無引號而被
                # DictReader 拆成多欄 — 統一轉 str 後分割
                if isinstance(raw_ids, list):
                    raw_ids = ",".join(str(x) for x in raw_ids)
                for part in str(raw_ids).split(","):
                    s = part.strip()
                    if s:
                        stocks.append(s)

                self._sectors[sid] = {
                    "name":    row.get("sector_name", sid).strip(),
                    "type":    row.get("sector_type", "custom").strip(),
                    "parent":  row.get("parent_sector", "").strip(),
                    "stocks":  stocks,
                }
                count += 1

        self._loaded = True
        logger.info(f"載入 {count} 個板塊定義")
        return count

    # ── 查詢接口 ──────────────────────────────────────────────────────────

    def get_stocks(self, sector_id: str) -> List[str]:
        return self._sectors.get(sector_id, {}).get("stocks", [])

    def get_sector_name(self, sector_id: str) -> str:
        return self._sectors.get(sector_id, {}).get("name", sector_id)

    def get_sector_type(self, sector_id: str) -> str:
        return self._sectors.get(sector_id, {}).get("type", "custom")

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

    @property
    def loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._sectors)


# 全域單例
sector_map = SectorMap()
