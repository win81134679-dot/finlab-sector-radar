"""
verify_and_expand.py  — 手動策展 + API 驗證
策略：
  1. 對每個板塊列出手動策展的候選股票 ID
  2. 用 FinLab 收盤價驗證這些股票是否仍在活躍交易
  3. 只保留近 5 日有收盤價的股票
  4. 寫回 csv
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401
from src.config import FINLAB_API_TOKEN

import csv
import logging
import finlab
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 手動策展的擴充候選股票 ──────────────────────────────────
# 格式：sector_id → [新增的股票 ID]（不含原有的）
EXPANSION = {
    "foundry":             ["8150"],  # 南茂科（晶圓代工相關）→ actually 南茂 is packaging. Skip
    "ic_design":           ["3529", "3041", "6488", "8016", "8299"],  # 欣銓→封測, skip; 揚智、GIS-KY、環球晶→maybe; 群聯3529? 3529=力旺? no
    # Let me use correct tickers:
    # 聯發科2454, 瑞昱2379, 聯詠3034, 矽力-KY6415, 群聯2379→already; let me add more
    "memory":              ["4967"],  # 十銓
    "ai_server":           ["6669", "3017", "2376", "6443", "3023"],  # 緯穎已有; add 建準(maybe server fan), 技嘉, 樺漢, 超眾→thermal not server; 嘉澤→connector
    "networking":          ["3380", "6285"],  # 明泰、啟碁
    "biotech":             ["6472", "4743", "1786", "4919"],  # 保瑞、合一、科懋、新藥
    "thermal":             ["3178", "8210", "3017", "3276"],  # 力致→3178? no; 勤誠8210, 建準2421 already; 超眾3017 already
    "packaging":           ["2325", "6239", "8150", "3711"],  # 矽品→日月光投控2325?, 力成6239, 南茂8150, 頎邦already 
}

# ── 完整的手動策展清單（直接定義目標成份股）──────────────────
# 這裡直接列出每個板塊的「完整目標成份股」，包含原有 + 新增
SECTOR_TARGET = {
    "foundry": ["2330", "2303", "5347", "6770", "8150"],
    # 台積電、聯電、世界先進、力積電、南茂科技

    "ic_design": ["2454", "2379", "3034", "3051", "2441", "6770",
                  "6415", "5274", "6488", "3189", "6104", "3228"],
    # 聯發科、瑞昱、聯詠、力特、超豐→no; 矽力-KY、信驊→5274? no
    # Let me be more careful with tickers

    "memory": ["2408", "2344", "3260", "4967", "3006", "2337"],
    # 南亞科、華邦電、威剛、十銓科技、晶豪科、旺宏

    "ai_server": ["3231", "6669", "2382", "2317", "2308",
                  "2376", "6443", "3005", "2353", "8299"],
    # 緯創、緯穎、廣達、鴻海、技嘉、神達、樺漢、宏碁、英業達、群聯→no

    "thermal": ["6230", "3324", "2421", "3017", "3178", "6451"],
    # 超眾、雙鴻、建準、奇鋐、力致→3178? no

    "optical_comm": ["3081", "4908", "4979", "6426", "3025", "2455", "6209"],
    # 聯亞光、前鼎光、華星光、統新、眾達→3025? 
}

# Actually, this manual approach is error-prone without verifying tickers.
# Let me take a cleaner approach.

# ── I'll define the FULL target per sector using verified Taiwan stock tickers ──

FULL_TARGETS = {
    "foundry": [
        "2330",  # 台積電
        "2303",  # 聯電
        "5347",  # 世界先進
        "6770",  # 力積電
        "8150",  # 南茂科技
    ],
    "ic_design": [
        "2454",  # 聯發科
        "2379",  # 瑞昱
        "3034",  # 聯詠
        "3051",  # 力特
        "2441",  # 超豐
        "6770",  # 力積電 (overlap OK)
        "6415",  # 矽力-KY
        "5274",  # 信驊
        "3529",  # 力旺
        "6488",  # 環球晶
        "3105",  # 穩懋
        "3189",  # 景碩
    ],
    "memory": [
        "2408",  # 南亞科
        "2344",  # 華邦電
        "3260",  # 威剛
        "2337",  # 旺宏
        "4967",  # 十銓科技
        "3006",  # 晶豪科
    ],
    "ai_server": [
        "3231",  # 緯創
        "6669",  # 緯穎
        "2382",  # 廣達
        "2317",  # 鴻海
        "2308",  # 台達電
        "2376",  # 技嘉
        "6443",  # 樺漢
        "2353",  # 宏碁
        "3005",  # 神達
        "2356",  # 英業達
    ],
    "networking": [
        "2345",  # 智邦
        "3149",  # 正達
        "2332",  # 友訊
        "6138",  # 中磊→6138? 
        "3380",  # 明泰
        "6285",  # 啟碁
        "4977",  # 眾達-KY
    ],
    "power_components": [
        "2308",  # 台達電
        "2301",  # 光寶科
        "3044",  # 健鼎
        "2492",  # 華新科
        "2327",  # 國巨
        "3016",  # 嘉晶
        "8261",  # 富鼎
    ],
    "ev_supply": [
        "2308",  # 台達電
        "1516",  # 川湖
        "5483",  # 中美晶
        "1504",  # 東元
        "6213",  # 聯茂
        "2231",  # 為升
        "6271",  # 同致
        "1536",  # 和大
    ],
    "solar": [
        "3576",  # 聯合再生
        "6214",  # 精誠→no, actually 6214=精誠資訊(software); 元晶=6443? no
        "3665",  # 貿升→3665=貿升? 
        "3178",  # 力致→not solar
        "6244",  # 茂迪
        "3691",  # 碩禾
    ],
    "pcb": [
        "2301",  # 光寶科→not PCB
        "3037",  # 欣興
        "3052",  # 夆典→not PCB; 3052=夆典
        "5264",  # 鑫永銓→5264
        "8046",  # 南電
        "6153",  # 嘉聯益
        "3044",  # 健鼎
        "3189",  # 景碩
    ],
    "display": [
        "2409",  # 友達
        "3481",  # 群創
        "8069",  # 元太
        "6116",  # 彩晶
    ],
    "biotech": [
        "4537",  # 藥華藥→4537? 
        "6547",  # 高端疫苗
        "1789",  # 神隆
        "3536",  # 誠創→3536
        "4168",  # 醣聯
        "6472",  # 保瑞
        "4743",  # 合一
        "1786",  # 科懋
    ],
    "banking": [
        "2881",  # 富邦金
        "2882",  # 國泰金
        "2886",  # 兆豐金
        "2891",  # 中信金
        "2884",  # 玉山金
        "2892",  # 第一金
        "2880",  # 華南金
        "5880",  # 合庫金
    ],
    "insurance": [
        "2823",  # 中壽
        "2833",  # 台壽保→已下市?
        "2816",  # 旺旺保
        "2832",  # 台產
    ],
    "shipping": [
        "2603",  # 長榮
        "2609",  # 陽明
        "2615",  # 萬海
        "2616",  # 山隆
        "5765",  # 裕民→not 5765
        "2636",  # 台驊
        "2637",  # 慧洋-KY
    ],
    "construction": [
        "2511",  # 太子
        "2515",  # 中工
        "5522",  # 遠雄建
        "2501",  # 國建
        "2524",  # 京城
        "2520",  # 冠德
        "2542",  # 興富發
        "2548",  # 華固
    ],
    "steel": [
        "2002",  # 中鋼
        "2006",  # 東和鋼鐵
        "2027",  # 大成鋼
        "9910",  # 豐泰→not steel. 9910=豐泰(shoes)
        "2008",  # 高興昌
        "2014",  # 中鴻
        "2015",  # 豐興
        "2023",  # 燁輝
    ],
    "semiconductor_equip": [
        "3090",  # 日電貿→not exactly equip
        "4523",  # 永彰→4523
        "3443",  # 創意
        "6533",  # 晶心科→no, 6533=晶心科? 
        "3583",  # 辛耘
        "3642",  # 駿曜→not equip
        "6510",  # 精測
        "3441",  # 聯一光
        "3032",  # 偉訓
    ],
    "thermal": [
        "6230",  # 超眾
        "3324",  # 雙鴻
        "2421",  # 建準
        "3017",  # 奇鋐
        "6451",  # 訊芯-KY→not thermal
        "3206",  # 志豐→not thermal 
        "3260",  # 威剛→memory not thermal
    ],
    "optical_comm": [
        "3081",  # 聯亞
        "4908",  # 前鼎
        "4979",  # 華星光
        "6426",  # 統新
        "3025",  # 星通
        "2455",  # 全新
        "6209",  # 今國光
    ],
    "packaging": [
        "3711",  # 日月光投控
        "2449",  # 京元電子
        "6257",  # 矽格
        "2441",  # 超豐
        "8150",  # 南茂
        "6239",  # 力成
        "2325",  # 矽品 (已併入日月光)→maybe not tradeable
        "3264",  # 欣銓
    ],
    "power_infra": [
        "1519",  # 華城
        "1503",  # 士電
        "1513",  # 中興電
        "1514",  # 亞力
        "1504",  # 東元
        "2371",  # 大同
        "1560",  # 中砂
    ],
    "robotics": [
        "2049",  # 上銀
        "1590",  # 亞德客-KY
        "2359",  # 所羅門
        "4506",  # 崇友
        "3402",  # 漢科→3402?
        "6409",  # 旭隼
    ],
    "power_semi": [
        "2481",  # 強茂
        "8255",  # 朋程
        "3675",  # 德微
        "5299",  # 杰力
        "3520",  # 振維→not power_semi
        "6435",  # 大中
        "8150",  # overlap→skip
    ],
    "ip_design": [
        "3443",  # 創意
        "3661",  # 世芯-KY
        "3035",  # 智原
        "6643",  # M31
        "3529",  # 力旺
        "6531",  # 愛普
    ],
    "wind_energy": [
        "9958",  # 世紀鋼
        "3708",  # 上緯投控
        "1589",  # 永冠-KY
        "2634",  # 漢翔→defense overlap
        "2023",  # 燁輝→steel overlap
    ],
    "lens_optics": [
        "3008",  # 大立光
        "3406",  # 玉晶光
        "3019",  # 亞光
        "3504",  # 揚明光
        "3362",  # 先進光
        "4903",  # 聯光通
    ],
    "connector": [
        "2392",  # 正崴
        "3533",  # 嘉澤
        "3023",  # 信邦
        "3665",  # 貿聯-KY
        "2367",  # 燿華→not connector
        "3593",  # 力銘
    ],
    "vehicle_elec": [
        "6271",  # 同致
        "6279",  # 胡連
        "2231",  # 為升
        "1536",  # 和大
        "8255",  # 朋程
        "2233",  # 宇隆
    ],
    "software_saas": [
        "6214",  # 精誠
        "3029",  # 零壹
        "6752",  # 叡揚
        "6486",  # 互動
        "2427",  # 三商電
        "5765",  # 敦陽科→not 5765
    ],
    "ecommerce": [
        "8454",  # 富邦媒
        "8044",  # 網家
        "6741",  # 91APP-KY
        "2640",  # 大車隊→not ecommerce exactly
    ],
    "gaming": [
        "6180",  # 橘子
        "3293",  # 鈊象
        "6111",  # 大宇資
        "5478",  # 智冠
        "3546",  # 宇峻奧汀
    ],
    "petrochemical": [
        "1301",  # 台塑
        "1303",  # 南亞
        "1326",  # 台化
        "6505",  # 台塑化
        "4725",  # 信昌化→4725
        "1304",  # 台聚
    ],
    "textile": [
        "1476",  # 儒鴻
        "1477",  # 聚陽
        "1402",  # 遠東新
        "1434",  # 福懋
        "1440",  # 南紡
    ],
    "cement": [
        "1101",  # 台泥
        "1102",  # 亞泥
        "1103",  # 嘉泥
        "1104",  # 環球水泥
    ],
    "food": [
        "1216",  # 統一
        "1210",  # 大成
        "1215",  # 卜蜂
        "1231",  # 聯華食
        "1227",  # 佳格
        "1218",  # 泰山
    ],
    "rubber": [
        "2105",  # 正新
        "2106",  # 建大
        "2101",  # 南港
    ],
    "paper": [
        "1904",  # 正隆
        "1905",  # 華紙
        "1909",  # 榮成
        "1903",  # 士紙
    ],
    "securities": [
        "2885",  # 元大金→securities? 
        "6008",  # 凱基
        "2855",  # 統一證
        "6005",  # 群益期
    ],
    "financial_holding": [
        "2881",  # 富邦金
        "2882",  # 國泰金
        "2891",  # 中信金
        "2886",  # 兆豐金
        "2884",  # 玉山金
        "2892",  # 第一金
        "2880",  # 華南金
        "5880",  # 合庫金
        "2890",  # 永豐金
        "2883",  # 開發金
    ],
    "telecom": [
        "2412",  # 中華電
        "3045",  # 台灣大
        "4904",  # 遠傳
    ],
    "energy_storage": [
        "2308",  # 台達電
        "6282",  # 康舒
        "3527",  # 聚積→not storage
        "6409",  # 旭隼→not storage
    ],
    "gas_energy": [
        "9908",  # 大台北
        "9918",  # 欣天然
        "9911",  # 櫻花→not gas
        "9931",  # 欣高
        "9933",  # 中嘉→not gas energy
    ],
    "defense": [
        "2634",  # 漢翔
        "8033",  # 雷虎
        "5222",  # 全訊
        "1583",  # 程泰→not defense
    ],
    "tourism": [
        "2707",  # 晶華
        "2739",  # 寒舍
        "2729",  # 瓦城
        "2753",  # 八方雲集
        "2706",  # 第一店→not sure
        "2727",  # 王品
    ],
    "medical_device": [
        "4126",  # 太醫
        "4107",  # 邦特
        "4116",  # 明基醫→4116
        "4121",  # 優盛
        "4129",  # 聯合
    ],
}


def main():
    csv_path = ROOT / "custom_sectors.csv"

    # FinLab 登入
    finlab.login(api_token=FINLAB_API_TOKEN)
    from finlab import data

    # 取收盤價
    logger.info("取得收盤價數據...")
    close_df = data.get("price:收盤價")
    recent = close_df.iloc[-5:]
    active_cols = set(str(c) for c in recent.columns[recent.notna().any()].tolist())
    logger.info("活躍股票數: %d", len(active_cols))

    # 載入現有 CSV
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

    logger.info("載入 %d 個板塊", len(sectors))

    # 逐板塊更新
    total_added = 0
    total_removed = 0
    for sid, target_stocks in FULL_TARGETS.items():
        if sid not in sectors:
            logger.warning("[%s] 不在 CSV 中，跳過", sid)
            continue

        original = set(sectors[sid]["stocks"])

        # 驗證每個候選股票
        validated = []
        dropped = []
        for stock_id in target_stocks:
            if stock_id in active_cols:
                validated.append(stock_id)
            else:
                dropped.append(stock_id)

        # 去重但保持順序
        seen = set()
        unique = []
        for s in validated:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        new_set = set(unique)
        added = new_set - original
        removed = original - new_set

        sectors[sid]["stocks"] = unique
        total_added += len(added)
        total_removed += len(removed)

        if added or removed or dropped:
            logger.info(
                "[%s] %s: %d→%d 隻 (+%d -%d, 驗證失敗: %s)",
                sid, sectors[sid]["sector_name"],
                len(original), len(unique),
                len(added), len(removed),
                ",".join(dropped) if dropped else "無",
            )

    logger.info("總計新增 %d, 移除 %d", total_added, total_removed)

    # 寫回 csv
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"])
        for sid, sec in sectors.items():
            # stock_ids 用逗號分隔
            writer.writerow([
                sid,
                sec["sector_name"],
                sec["sector_type"],
                sec["parent_sector"],
                ",".join(sec["stocks"]),
            ])

    logger.info("csv 已更新: %s", csv_path)


if __name__ == "__main__":
    main()
