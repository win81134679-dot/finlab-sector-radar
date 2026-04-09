"""
expand_sectors.py — 使用 FinLab API 擴充 custom_sectors.csv 成份股

策略：
1. 對每個板塊定義相關的產業子分類關鍵字
2. 用 FinLab data.get("company_basic_info") 取得上市櫃公司基本資料
3. 用 price:收盤價 最新一列篩選有交易的股票
4. 排除 ETF（代號 00 開頭或名稱含 ETF）、TDR、存託憑證、下市股
5. 合併回 csv，保留原有股票 + 新增發現的股票
"""
import sys
import os
from pathlib import Path

# 確保 src 可 import
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401 — 必須最早 import
from src.config import FINLAB_API_TOKEN

import csv
import logging
import finlab
import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 板塊→關鍵字映射（用於 FinLab company_basic_info 的產業分類比對）──────
# 每個板塊定義多組關鍵字，比對公司的「產業類別」或「公司名稱」
SECTOR_KEYWORDS = {
    "foundry":           {"keywords": ["晶圓代工"], "name_kw": ["台積", "聯電", "世界先進", "力積電"]},
    "ic_design":         {"keywords": ["IC設計"], "name_kw": ["聯發科", "瑞昱", "聯詠", "矽力", "群聯", "慧榮", "奇景", "立積", "神盾", "義隆", "晶心科", "信驊", "譜瑞", "昇佳"]},
    "memory":            {"keywords": ["記憶體", "DRAM"], "name_kw": ["南亞科", "華邦電", "旺宏", "威剛"]},
    "ai_server":         {"keywords": ["伺服器"], "name_kw": ["廣達", "緯穎", "英業達", "緯創", "神達", "技嘉", "勤誠", "川湖", "雙鴻"]},
    "networking":        {"keywords": ["網通", "通信設備"], "name_kw": ["智邦", "中磊", "合勤控", "明泰", "啟碁"]},
    "power_components":  {"keywords": ["被動元件", "電源供應"], "name_kw": ["台達電", "國巨", "光頡", "華新科", "禾伸堂", "大毅", "全漢", "康舒"]},
    "ev_supply":         {"keywords": ["電動車", "汽車零件"], "name_kw": ["台達電", "和碩", "鴻海", "貿聯", "乙盛", "和大", "智伸科", "朋程"]},
    "solar":             {"keywords": ["太陽能"], "name_kw": ["元晶", "安集", "茂迪", "聯合再生"]},
    "pcb":               {"keywords": ["印刷電路板", "PCB"], "name_kw": ["臻鼎", "欣興", "華通", "健鼎", "南電", "景碩", "金像電", "博智"]},
    "display":           {"keywords": ["面板", "顯示器"], "name_kw": ["友達", "群創", "瀚宇彩晶", "元太"]},
    "biotech":           {"keywords": ["生技", "醫療"], "name_kw": ["藥華藥", "合一", "中裕", "智擎", "大江", "保瑞", "寶齡富"]},
    "banking":           {"keywords": ["銀行"], "name_kw": ["台新金", "兆豐金", "中信金", "第一金", "華南金", "玉山金", "合庫金", "彰銀"]},
    "insurance":         {"keywords": ["壽險", "保險"], "name_kw": ["國泰金", "富邦金", "新光金", "三商壽"]},
    "shipping":          {"keywords": ["航運", "海運"], "name_kw": ["長榮", "陽明", "萬海", "裕民", "慧洋", "新興"]},
    "construction":      {"keywords": ["建設", "營造"], "name_kw": ["興富發", "華固", "遠雄", "長虹", "達麗", "潤泰新"]},
    "steel":             {"keywords": ["鋼鐵"], "name_kw": ["中鋼", "中鴻", "大成鋼", "春雨", "燁輝", "允強", "新光鋼"]},
    "semiconductor_equip": {"keywords": ["半導體設備"], "name_kw": ["弘塑", "帆宣", "辛耘", "萬潤", "家登", "京鼎", "漢微科"]},
    "thermal":           {"keywords": ["散熱"], "name_kw": ["雙鴻", "奇鋐", "建準", "超眾", "力致", "泰碩", "健策", "尼得科超眾", "高力"]},
    "optical_comm":      {"keywords": ["光通訊", "光纖"], "name_kw": ["眾達", "前鼎", "聯亞", "統新", "華星光", "波若威", "上詮", "光環", "聯鈞"]},
    "packaging":         {"keywords": ["封測", "封裝測試"], "name_kw": ["日月光投控", "矽品", "京元電子", "力成", "南茂", "超豐", "菱生", "頎邦"]},
    "power_infra":       {"keywords": ["重電", "電力設備"], "name_kw": ["士電", "亞力", "華城", "中興電", "東元", "大同"]},
    "robotics":          {"keywords": ["機器人", "自動化"], "name_kw": ["上銀", "亞德客", "所羅門", "台達電", "盟立", "直得"]},
    "power_semi":        {"keywords": ["功率半導體"], "name_kw": ["強茂", "富鼎", "漢磊", "穩懋", "茂矽", "朋程", "杰力"]},
    "ip_design":         {"keywords": ["矽智財", "IP設計"], "name_kw": ["世芯", "創意", "智原", "M31", "力旺", "晶心科"]},
    "wind_energy":       {"keywords": ["風電", "風力發電"], "name_kw": ["世紀鋼", "永冠", "上緯投控", "天力離岸"]},
    "lens_optics":       {"keywords": ["光學", "鏡頭"], "name_kw": ["大立光", "玉晶光", "亞光", "先進光", "佳凌"]},
    "connector":         {"keywords": ["連接器", "電線電纜"], "name_kw": ["正崴", "鴻海", "信邦", "貿聯", "嘉澤", "宣德"]},
    "vehicle_elec":      {"keywords": ["車用電子"], "name_kw": ["同致", "為升", "朋程", "智伸科", "胡連"]},
    "software_saas":     {"keywords": ["軟體", "資訊服務"], "name_kw": ["精誠", "零壹", "敦陽科", "叡揚", "凌群", "中菲行"]},
    "ecommerce":         {"keywords": ["電子商務", "網路"], "name_kw": ["富邦媒", "網家", "91APP", "數字", "創業家"]},
    "gaming":            {"keywords": ["遊戲"], "name_kw": ["橘子", "鈊象", "大宇資", "華義", "宇峻奧汀", "智冠", "傳奇"]},
    "petrochemical":     {"keywords": ["塑膠", "石化"], "name_kw": ["台塑", "南亞", "台化", "台塑化", "長春石化"]},
    "textile":           {"keywords": ["紡織", "成衣"], "name_kw": ["儒鴻", "聚陽", "宏遠", "新纖"]},
    "cement":            {"keywords": ["水泥"], "name_kw": ["台泥", "亞泥", "信大水泥", "幸福水泥"]},
    "food":              {"keywords": ["食品"], "name_kw": ["統一", "大成", "卜蜂", "味全", "聯華食"]},
    "rubber":            {"keywords": ["橡膠", "輪胎"], "name_kw": ["正新", "建大", "南港輪胎"]},
    "paper":             {"keywords": ["造紙", "紙業"], "name_kw": ["永豐餘", "正隆", "榮成"]},
    "securities":        {"keywords": ["證券"], "name_kw": ["日盛金", "群益證", "元大金", "凱基"]},
    "financial_holding": {"keywords": ["金控"], "name_kw": ["台新金", "兆豐金", "中信金", "第一金", "華南金", "玉山金", "合庫金", "富邦金", "國泰金", "開發金", "元大金"]},
    "telecom":           {"keywords": ["電信"], "name_kw": ["中華電", "台灣大", "遠傳", "亞太電"]},
    "energy_storage":    {"keywords": ["儲能", "電池"], "name_kw": ["台達電", "有量", "長園科", "承德油脂", "系統電子", "新普", "加百裕", "順達"]},
    "gas_energy":        {"keywords": ["天然氣", "能源"], "name_kw": ["大台北", "欣天然", "新海", "欣高", "欣雄"]},
    "defense":           {"keywords": ["國防", "軍工"], "name_kw": ["漢翔", "雷虎", "全球防衛", "千附精密"]},
    "tourism":           {"keywords": ["觀光", "餐飲", "旅行"], "name_kw": ["晶華", "雄獅", "王品", "瓦城", "六角"]},
    "medical_device":    {"keywords": ["醫材", "醫療器材"], "name_kw": ["太醫", "邦特", "益安", "明基醫"]},
}


def load_current_csv(csv_path: Path) -> dict:
    """載入現有 csv，回傳 {sector_id: {row_data + stocks set}}"""
    sectors = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["sector_id"].strip()
            stocks = set()
            raw = row.get("stock_ids", "")
            for part in raw.split(","):
                s = part.strip()
                if s:
                    stocks.add(s)
            sectors[sid] = {
                "sector_name": row["sector_name"],
                "sector_type": row["sector_type"],
                "parent_sector": row.get("parent_sector", ""),
                "stocks": stocks,
            }
    return sectors


def get_active_stock_ids(close_df: pd.DataFrame) -> set:
    """從收盤價 DataFrame 取得最近有交易的股票 ID"""
    if close_df is None or close_df.empty:
        return set()
    # 取最近 5 個交易日，有任一天有收盤價就算有在交易
    recent = close_df.iloc[-5:]
    active = recent.columns[recent.notna().any()].tolist()
    return set(str(c) for c in active)


def is_valid_stock(stock_id: str, name: str) -> bool:
    """排除 ETF、TDR、存託憑證、權證、特別股等"""
    sid = str(stock_id)
    # ETF: 00 開頭（0050, 00878 等）
    if sid.startswith("00"):
        return False
    # 權證: 通常 6 碼以上且非正常股票
    if len(sid) > 4 and not sid[-1].isdigit():
        return False
    # 名稱排除
    if not name:
        return True
    excludes = ["ETF", "TDR", "存託", "認購", "認售", "權證", "特別股", "受益", "期貨"]
    for ex in excludes:
        if ex in name:
            return False
    return True


def find_stocks_by_name(
    name_map: dict,
    active_ids: set,
    name_keywords: list,
) -> set:
    """用公司名稱關鍵字搜尋，回傳符合的股票 ID"""
    found = set()
    for sid, name in name_map.items():
        if sid not in active_ids:
            continue
        if not is_valid_stock(sid, name):
            continue
        for kw in name_keywords:
            if kw in name:
                found.add(sid)
                break
    return found


def main():
    csv_path = ROOT / "custom_sectors.csv"
    backup_path = ROOT / "custom_sectors.csv.bak"

    # 備份
    import shutil
    shutil.copy2(csv_path, backup_path)
    logger.info("已備份 csv → %s", backup_path.name)

    # 載入現有定義
    sectors = load_current_csv(csv_path)
    logger.info("載入 %d 個板塊", len(sectors))

    # FinLab 登入
    finlab.login(api_token=FINLAB_API_TOKEN)
    from finlab import data

    # 取收盤價（判斷是否有交易）
    logger.info("取得收盤價數據...")
    close_df = data.get("price:收盤價")
    active_ids = get_active_stock_ids(close_df)
    logger.info("活躍股票數: %d", len(active_ids))

    # 取公司名稱
    logger.info("取得公司基本資料...")
    try:
        basic_info = data.get("company_basic_info")
        if basic_info is not None and "公司簡稱" in basic_info.columns:
            name_map = basic_info["公司簡稱"].dropna().to_dict()
        else:
            # fallback: 用收盤價的 columns 當 ID，名稱靠 stock_names
            name_map = {}
    except Exception as e:
        logger.warning("取得公司資料失敗: %s，改用 stock_names fallback", e)
        name_map = {}

    # fallback: 用 stock_names 模組
    if not name_map:
        logger.info("使用 stock_names 模組取得名稱...")
        try:
            from src.stock_names import load_names, get_name
            load_names(close_df)
            name_map = {str(sid): get_name(str(sid)) for sid in active_ids}
        except Exception as e:
            logger.warning("stock_names fallback 也失敗: %s", e)
            name_map = {}

    # 確保 name_map 的 key 是 str
    name_map = {str(k): str(v) for k, v in name_map.items() if v}

    logger.info("公司名稱數: %d", len(name_map))

    # 逐板塊擴充
    total_added = 0
    for sid, sec_data in sectors.items():
        if sid not in SECTOR_KEYWORDS:
            continue

        kw_config = SECTOR_KEYWORDS[sid]
        existing = sec_data["stocks"]
        new_found = set()

        # 用名稱關鍵字搜尋
        name_kws = kw_config.get("name_kw", [])
        if name_kws:
            found = find_stocks_by_name(name_map, active_ids, name_kws)
            new_found |= found

        # 移除已存在的
        new_found -= existing

        # 驗證新找到的都是活躍且合法的
        validated = set()
        for stock_id in new_found:
            if stock_id in active_ids:
                name = name_map.get(stock_id, "")
                if is_valid_stock(stock_id, name):
                    validated.add(stock_id)

        if validated:
            sec_data["stocks"] |= validated
            total_added += len(validated)
            logger.info(
                "[%s] %s: +%d 隻 → 共 %d 隻 (新增: %s)",
                sid, sec_data["sector_name"],
                len(validated), len(sec_data["stocks"]),
                ", ".join(sorted(validated)),
            )

    logger.info("總計新增 %d 隻股票", total_added)

    # 寫回 csv
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"])
        for sid, sec_data in sectors.items():
            stocks_str = ",".join(sorted(sec_data["stocks"]))
            writer.writerow([
                sid,
                sec_data["sector_name"],
                sec_data["sector_type"],
                sec_data["parent_sector"],
                stocks_str,
            ])

    logger.info("csv 已更新: %s", csv_path)


if __name__ == "__main__":
    main()
