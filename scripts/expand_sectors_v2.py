"""
expand_sectors_v2.py — 正確版：使用 FinLab API 擴充 custom_sectors.csv

修正：company_basic_info 的 stock_id 在 column 而非 index
策略：
  1. 用「產業類別」做粗篩（板塊→產業映射）
  2. 用「公司簡稱」做精確名稱匹配
  3. 用收盤價驗證活躍交易
  4. 排除 ETF / TDR / 權證等
"""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401
from src.config import FINLAB_API_TOKEN

import csv
import shutil
import logging
import finlab
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── 板塊 → (產業類別關鍵字, 公司名稱關鍵字) ──────────────────────
# industry_kw: 比對 company_basic_info 的「產業類別」欄位
# name_kw: 比對「公司簡稱」欄位做精確匹配
SECTOR_RULES = {
    "foundry": {
        "industry_kw": [],
        "name_kw": ["台積電", "聯電", "世界先進", "力積電", "南茂"],
    },
    "ic_design": {
        "industry_kw": [],
        "name_kw": [
            "聯發科", "瑞昱", "聯詠", "力特", "超豐",
            "矽力", "信驊", "力旺", "晶心科", "神盾",
            "義隆", "立積", "譜瑞", "昇佳", "驊訊",
        ],
    },
    "memory": {
        "industry_kw": [],
        "name_kw": ["南亞科", "華邦電", "威剛", "旺宏", "十銓", "晶豪科"],
    },
    "ai_server": {
        "industry_kw": [],
        "name_kw": [
            "緯創", "緯穎", "廣達", "鴻海", "台達電",
            "技嘉", "樺漢", "英業達", "神達", "勤誠",
        ],
    },
    "networking": {
        "industry_kw": [],
        "name_kw": ["智邦", "正達", "友訊", "中磊", "明泰", "啟碁", "合勤控"],
    },
    "power_components": {
        "industry_kw": [],
        "name_kw": ["台達電", "光寶科", "健鼎", "華新科", "國巨", "禾伸堂", "大毅", "奇力新"],
    },
    "ev_supply": {
        "industry_kw": [],
        "name_kw": [
            "台達電", "川湖", "中美晶", "東元", "聯茂",
            "為升", "同致", "和大", "朋程", "貿聯",
        ],
    },
    "solar": {
        "industry_kw": [],
        "name_kw": ["聯合再生", "元晶", "茂迪", "安集", "碩禾"],
    },
    "pcb": {
        "industry_kw": [],
        "name_kw": [
            "臻鼎", "欣興", "華通", "健鼎", "南電",
            "景碩", "金像電", "博智", "嘉聯益", "楠梓電",
        ],
    },
    "display": {
        "industry_kw": [],
        "name_kw": ["友達", "群創", "元太", "彩晶"],
    },
    "biotech": {
        "industry_kw": [],
        "name_kw": [
            "藥華藥", "高端疫苗", "神隆", "醣聯",
            "保瑞", "合一", "科懋", "大江",
        ],
    },
    "banking": {
        "industry_kw": ["銀行"],
        "name_kw": [
            "富邦金", "國泰金", "兆豐金", "中信金",
            "玉山金", "第一金", "華南金", "合庫金",
        ],
    },
    "insurance": {
        "industry_kw": [],
        "name_kw": ["中壽", "台壽保", "旺旺保", "台產"],
    },
    "shipping": {
        "industry_kw": ["航運"],
        "name_kw": [
            "長榮", "陽明", "萬海", "山隆",
            "裕民", "台驊投控", "慧洋",
        ],
    },
    "construction": {
        "industry_kw": ["建材營造"],
        "name_kw": [
            "太子", "中工", "遠雄建", "國建",
            "京城", "冠德", "興富發", "華固", "長虹", "達麗",
        ],
    },
    "steel": {
        "industry_kw": ["鋼鐵"],
        "name_kw": [
            "中鋼", "東和鋼鐵", "大成鋼", "中鴻",
            "豐興", "春雨", "燁輝", "允強", "新光鋼",
        ],
    },
    "semiconductor_equip": {
        "industry_kw": [],
        "name_kw": [
            "弘塑", "辛耘", "萬潤", "家登",
            "京鼎", "精測", "帆宣", "漢微科",
        ],
    },
    "thermal": {
        "industry_kw": [],
        "name_kw": [
            "超眾", "雙鴻", "建準", "奇鋐",
            "力致", "泰碩", "尼得科超眾", "高力", "健策",
        ],
    },
    "optical_comm": {
        "industry_kw": [],
        "name_kw": [
            "聯亞", "前鼎", "華星光", "統新",
            "波若威", "上詮", "光環", "聯鈞", "眾達",
        ],
    },
    "packaging": {
        "industry_kw": [],
        "name_kw": [
            "日月光投控", "京元電子", "矽格", "超豐",
            "南茂", "力成", "菱生", "頎邦", "欣銓",
        ],
    },
    "power_infra": {
        "industry_kw": [],
        "name_kw": [
            "華城", "士電", "中興電", "亞力",
            "東元", "大同", "中砂",
        ],
    },
    "robotics": {
        "industry_kw": [],
        "name_kw": ["上銀", "亞德客", "所羅門", "崇友", "直得", "盟立"],
    },
    "power_semi": {
        "industry_kw": [],
        "name_kw": [
            "強茂", "朋程", "德微", "杰力",
            "漢磊", "茂矽", "穩懋", "大中",
        ],
    },
    "ip_design": {
        "industry_kw": [],
        "name_kw": [
            "創意", "世芯", "智原", "M31",
            "力旺", "晶心科", "愛普",
        ],
    },
    "wind_energy": {
        "industry_kw": [],
        "name_kw": ["世紀鋼", "上緯投控", "永冠", "天力離岸"],
    },
    "lens_optics": {
        "industry_kw": [],
        "name_kw": ["大立光", "玉晶光", "亞光", "先進光", "揚明光", "佳凌"],
    },
    "connector": {
        "industry_kw": [],
        "name_kw": ["正崴", "嘉澤", "信邦", "貿聯", "宣德", "詮欣"],
    },
    "vehicle_elec": {
        "industry_kw": [],
        "name_kw": ["同致", "胡連", "為升", "和大", "朋程", "智伸科", "宇隆"],
    },
    "software_saas": {
        "industry_kw": [],
        "name_kw": ["精誠", "零壹", "叡揚", "互動", "凌群", "敦陽科", "三商電"],
    },
    "ecommerce": {
        "industry_kw": [],
        "name_kw": ["富邦媒", "網家", "91APP", "創業家", "數字"],
    },
    "gaming": {
        "industry_kw": [],
        "name_kw": ["橘子", "鈊象", "大宇資", "智冠", "宇峻奧汀", "傳奇"],
    },
    "petrochemical": {
        "industry_kw": ["塑膠"],
        "name_kw": ["台塑", "南亞", "台化", "台塑化", "台聚", "亞聚"],
    },
    "textile": {
        "industry_kw": [],
        "name_kw": ["儒鴻", "聚陽", "遠東新", "福懋", "南紡"],
    },
    "cement": {
        "industry_kw": ["水泥"],
        "name_kw": ["台泥", "亞泥", "嘉泥", "環泥"],
    },
    "food": {
        "industry_kw": [],
        "name_kw": ["統一", "大成", "卜蜂", "聯華食", "佳格", "泰山"],
    },
    "rubber": {
        "industry_kw": [],
        "name_kw": ["正新", "建大", "南港"],
    },
    "paper": {
        "industry_kw": [],
        "name_kw": ["正隆", "華紙", "榮成", "士紙", "永豐餘"],
    },
    "securities": {
        "industry_kw": [],
        "name_kw": ["元大金", "群益期", "凱基", "統一證", "宏遠證"],
    },
    "financial_holding": {
        "industry_kw": ["金控"],
        "name_kw": [
            "富邦金", "國泰金", "中信金", "兆豐金",
            "玉山金", "第一金", "華南金", "合庫金",
            "永豐金", "開發金", "元大金", "新光金", "台新金",
        ],
    },
    "telecom": {
        "industry_kw": [],
        "name_kw": ["中華電", "台灣大", "遠傳"],
    },
    "energy_storage": {
        "industry_kw": [],
        "name_kw": ["台達電", "康舒", "新普", "加百裕", "順達", "有量", "系統電"],
    },
    "gas_energy": {
        "industry_kw": ["瓦斯"],
        "name_kw": ["大台北", "欣天然", "新海", "欣高", "欣雄"],
    },
    "defense": {
        "industry_kw": [],
        "name_kw": ["漢翔", "雷虎", "全訊", "千附精密"],
    },
    "tourism": {
        "industry_kw": [],
        "name_kw": ["晶華", "寒舍", "瓦城", "八方雲集", "王品", "雄獅"],
    },
    "medical_device": {
        "industry_kw": [],
        "name_kw": ["太醫", "邦特", "明基醫", "益安", "優盛", "聯合"],
    },
}


def is_valid_stock(stock_id: str) -> bool:
    """排除 ETF、權證等非普通股"""
    sid = str(stock_id).strip()
    if not sid:
        return False
    # ETF: 00 開頭
    if sid.startswith("00"):
        return False
    # 一般股票為 4 碼數字
    if not re.match(r"^\d{4}$", sid):
        return False
    return True


def load_csv(csv_path: Path) -> dict:
    sectors = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["sector_id"].strip()
            sectors[sid] = {
                "sector_name": row["sector_name"],
                "sector_type": row["sector_type"],
                "parent_sector": row.get("parent_sector", ""),
                "stocks": [s.strip() for s in row["stock_ids"].split(",") if s.strip()],
            }
    return sectors


def main():
    csv_path = ROOT / "custom_sectors.csv"
    backup_path = ROOT / "custom_sectors.csv.bak"

    # 備份
    shutil.copy2(csv_path, backup_path)
    logger.info("已備份 csv → %s", backup_path.name)

    sectors = load_csv(csv_path)
    logger.info("載入 %d 個板塊", len(sectors))

    # FinLab 登入
    finlab.login(api_token=FINLAB_API_TOKEN)
    from finlab import data

    # 收盤價 → 活躍股票
    logger.info("取得收盤價數據...")
    close_df = data.get("price:收盤價")
    recent = close_df.iloc[-5:]
    active_set = set(str(c) for c in recent.columns[recent.notna().any()].tolist())
    logger.info("活躍股票數: %d", len(active_set))

    # company_basic_info → stock_id → (名稱, 產業)
    logger.info("取得公司基本資料...")
    info = data.get("company_basic_info")

    # 正確用法：stock_id 在 column 而非 index
    id_to_name = {}
    id_to_industry = {}
    for _, row in info.iterrows():
        sid = str(row.get("stock_id", "")).strip()
        if not sid:
            continue
        name = str(row.get("公司簡稱", "")).strip()
        industry = str(row.get("產業類別", "")).strip()
        id_to_name[sid] = name
        id_to_industry[sid] = industry

    logger.info("公司資料數: %d", len(id_to_name))

    # 驗證幾個已知股票
    for test in ["2330", "2454", "2303"]:
        logger.info("  驗證 %s → %s (%s)", test, id_to_name.get(test, "?"), id_to_industry.get(test, "?"))

    # 逐板塊擴充
    total_added = 0
    for sid, rules in SECTOR_RULES.items():
        if sid not in sectors:
            continue

        original = set(sectors[sid]["stocks"])
        candidates = set()

        # 1) 產業類別粗篩
        for ind_kw in rules.get("industry_kw", []):
            for stock_id, industry in id_to_industry.items():
                if ind_kw in industry and stock_id in active_set and is_valid_stock(stock_id):
                    # 對於產業粗篩，也要排除名稱中含 ETF 等
                    name = id_to_name.get(stock_id, "")
                    if not any(ex in name for ex in ["ETF", "TDR", "存託", "權證", "特別股"]):
                        candidates.add(stock_id)

        # 2) 名稱精確匹配
        for name_kw in rules.get("name_kw", []):
            for stock_id, name in id_to_name.items():
                if name_kw in name and stock_id in active_set and is_valid_stock(stock_id):
                    candidates.add(stock_id)

        # 合併：原有 + 新增
        new_stocks = candidates - original
        all_stocks = list(original) + sorted(new_stocks)

        if new_stocks:
            # 顯示新增的股票名稱
            new_names = [f"{s}({id_to_name.get(s, '?')})" for s in sorted(new_stocks)]
            logger.info(
                "[%s] %s: %d→%d 隻, +%d: %s",
                sid, sectors[sid]["sector_name"],
                len(original), len(all_stocks), len(new_stocks),
                ", ".join(new_names),
            )
            total_added += len(new_stocks)
            sectors[sid]["stocks"] = all_stocks

    logger.info("總計新增 %d 隻股票", total_added)

    # 驗證：移除不再活躍的舊股票
    total_dropped = 0
    for sid, sec in sectors.items():
        active_stocks = [s for s in sec["stocks"] if s in active_set]
        dropped = set(sec["stocks"]) - set(active_stocks)
        if dropped:
            dropped_names = [f"{s}({id_to_name.get(s, '?')})" for s in dropped]
            logger.info(
                "[%s] 移除不活躍: %s", sid, ", ".join(dropped_names),
            )
            total_dropped += len(dropped)
            sec["stocks"] = active_stocks

    if total_dropped:
        logger.info("移除不活躍股票: %d 隻", total_dropped)

    # 寫回 csv
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"])
        for sid, sec in sectors.items():
            writer.writerow([
                sid,
                sec["sector_name"],
                sec["sector_type"],
                sec["parent_sector"],
                ",".join(sec["stocks"]),
            ])

    logger.info("csv 已更新: %s", csv_path)

    # 統計
    stock_counts = [len(sec["stocks"]) for sec in sectors.values()]
    logger.info(
        "板塊股票數統計：min=%d, max=%d, avg=%.1f",
        min(stock_counts), max(stock_counts),
        sum(stock_counts) / len(stock_counts),
    )


if __name__ == "__main__":
    main()
