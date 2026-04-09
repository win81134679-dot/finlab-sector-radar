"""
industry_mapping.py — TWSE/TPEx 官方產業碼 → 板塊自動分類

讀取 output/stock_universe.json（含 industry 欄位），
將每檔股票歸入官方產業板塊，產出 output/auto_sectors.csv。

已在 custom_sectors.csv 中的股票不會出現在 auto_sectors.csv，
確保手動板塊永遠最高優先權。
"""
from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# ── TWSE/TPEx 產業碼 → (sector_id, sector_name, parent_sector) 映射 ────
# 資料來源：TWSE OpenAPI t187ap03_L「產業別」欄位 + TPEx「SecuritiesIndustryCode」
# codes 20 (其他) 和 91 (DR) 過於異質，不納入自動分類

INDUSTRY_CODE_MAP: Dict[str, tuple] = {
    "01": ("auto_cement",              "水泥工業",       "material"),
    "02": ("auto_food",                "食品工業",       "consumer"),
    "03": ("auto_plastics",            "塑膠工業",       "material"),
    "04": ("auto_textile",             "紡織纖維",       "material"),
    "05": ("auto_electrical_machinery", "電機機械",      "infrastructure"),
    "06": ("auto_electrical_appliance", "電器電纜",      "infrastructure"),
    "08": ("auto_glass",               "玻璃陶瓷",       "material"),
    "09": ("auto_paper",               "造紙工業",       "material"),
    "10": ("auto_steel",               "鋼鐵工業",       "material"),
    "11": ("auto_rubber",              "橡膠工業",       "material"),
    "12": ("auto_automobile",           "汽車工業",      "consumer"),
    "14": ("auto_construction",         "建材營造",      "infrastructure"),
    "15": ("auto_shipping",             "航運業",        "infrastructure"),
    "16": ("auto_tourism",              "觀光餐旅",      "consumer"),
    "17": ("auto_finance",              "金融保險",      "finance"),
    "18": ("auto_trading",              "貿易百貨",      "consumer"),
    "21": ("auto_chemical",             "化學工業",      "material"),
    "22": ("auto_biotech",              "生技醫療",      "biotech"),
    "23": ("auto_oil_gas",              "油電燃氣",      "energy"),
    "24": ("auto_semiconductor",        "半導體業",      "semiconductor"),
    "25": ("auto_computer_peripheral",  "電腦及週邊",    "electronics"),
    "26": ("auto_optoelectronics",      "光電業",        "electronics"),
    "27": ("auto_communication",        "通信網路業",    "electronics"),
    "28": ("auto_electronic_parts",     "電子零組件",    "electronics"),
    "29": ("auto_electronic_channel",   "電子通路業",    "electronics"),
    "30": ("auto_it_service",           "資訊服務業",    "software"),
    "31": ("auto_other_electronics",    "其他電子業",    "electronics"),
    "33": ("auto_other_tpex",           "其他上櫃",      ""),
    "35": ("auto_green_energy",         "綠能環保",      "energy"),
    "36": ("auto_digital_cloud",        "數位雲端",      "software"),
    "37": ("auto_sports_leisure",       "運動休閒",      "consumer"),
    "38": ("auto_home_living",          "居家生活",      "consumer"),
}

# 不納入自動分類的產業碼
SKIP_CODES = {"20", "91"}


def _load_custom_stock_ids(custom_csv: Path) -> set:
    """讀取 custom_sectors.csv 中所有已分配的股票代碼。"""
    assigned: set = set()
    if not custom_csv.exists():
        return assigned
    with open(custom_csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_ids = row.get("stock_ids", "") or ""
            for part in str(raw_ids).split(","):
                s = part.strip()
                if s:
                    assigned.add(s)
    return assigned


def generate_auto_sectors(
    universe_path: Path | None = None,
    custom_csv: Path | None = None,
    output_csv: Path | None = None,
) -> int:
    """
    從 stock_universe.json 產生 auto_sectors.csv。

    回傳產出的板塊數。
    """
    from src import config

    universe_path = universe_path or config.OUTPUT_DIR / "stock_universe.json"
    custom_csv = custom_csv or config.CUSTOM_SECTORS_CSV
    output_csv = output_csv or config.OUTPUT_DIR / "auto_sectors.csv"

    # 讀取 universe
    if not universe_path.exists():
        logger.error("找不到 stock_universe.json，請先執行 update_stock_universe.py")
        return 0

    raw = json.loads(universe_path.read_text(encoding="utf-8"))

    # 讀取 custom 已分配的股票
    custom_assigned = _load_custom_stock_ids(custom_csv)
    logger.info("custom_sectors.csv 已分配 %d 檔股票", len(custom_assigned))

    # 按產業碼分組
    sector_stocks: Dict[str, List[str]] = {}
    skipped_custom = 0
    skipped_code = 0

    for code, info in raw.items():
        if isinstance(info, str):
            continue  # 舊格式無 industry，跳過

        industry = info.get("industry", "")
        if not industry or industry in SKIP_CODES:
            skipped_code += 1
            continue

        if code in custom_assigned:
            skipped_custom += 1
            continue

        if industry not in INDUSTRY_CODE_MAP:
            skipped_code += 1
            continue

        sector_id = INDUSTRY_CODE_MAP[industry][0]
        sector_stocks.setdefault(sector_id, []).append(code)

    # 過濾掉成員數 < 3 的板塊（太少無統計意義）
    MIN_MEMBERS = 3
    filtered = {k: sorted(v) for k, v in sector_stocks.items() if len(v) >= MIN_MEMBERS}

    # 寫出 CSV（與 custom_sectors.csv 相同格式）
    tmp_path = output_csv.parent / "auto_sectors.tmp.csv"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"])
        for sector_id in sorted(filtered.keys()):
            stocks = filtered[sector_id]
            # 反查映射資訊
            for code_key, (sid, sname, parent) in INDUSTRY_CODE_MAP.items():
                if sid == sector_id:
                    writer.writerow([
                        sector_id,
                        sname,
                        "auto",
                        parent,
                        ",".join(stocks),
                    ])
                    break

    os.replace(str(tmp_path), str(output_csv))

    total_stocks = sum(len(v) for v in filtered.values())
    logger.info(
        "auto_sectors.csv 已產出：%d 個板塊, %d 檔股票 "
        "(跳過 custom %d, 無效碼 %d, <3成員板塊 %d)",
        len(filtered), total_stocks,
        skipped_custom, skipped_code,
        len(sector_stocks) - len(filtered),
    )
    return len(filtered)


def main() -> None:
    """CLI 入口。"""
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="從 TWSE/TPEx 產業碼產生自動板塊分類")
    parser.parse_args()
    count = generate_auto_sectors()
    if count:
        print(f"✅ auto_sectors.csv: {count} 個板塊")
    else:
        print("❌ 產出失敗")


if __name__ == "__main__":
    main()
