"""
06_finlab_subcategory_expansion.py
-----------------------------------
從 FinLab security_industry_themes 取出所有「頂層:子類」格式的子類板塊，
生成 output/custom_subsectors.csv（方案B獨立檔）。

欄位與 custom_sectors.csv 相同：
  sector_id, sector_name, sector_type, parent_sector, stock_ids

執行方式：
  python tests_explore/06_finlab_subcategory_expansion.py

後續步驟：
  確認輸出後，執行下方合併指令將子類加入主系統：
  python tests_explore/06_merge_subsectors.py  (另一隻腳本，可選)
  或手動把 output/custom_subsectors.csv 的內容附加到 custom_sectors.csv
"""

import sys
import ast
import re
import csv
import io
from pathlib import Path
from collections import defaultdict

# 修正 stdout encoding（Windows 中文路徑）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 設定路徑
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: E402  必須最早 import
from src.config import FINLAB_API_TOKEN  # noqa: E402
import finlab  # noqa: E402
finlab.login(api_token=FINLAB_API_TOKEN)
from finlab import data  # noqa: E402

# ── 頂層分類 中文 → 英文代碼 ───────────────────────────────────────────────
TOP_MAP: dict[str, str] = {
    "人工智慧": "ai",
    "雲端運算": "cloud",
    "大數據": "bigdata",
    "區塊鏈": "blockchain",
    "元宇宙": "metaverse",
    "太空衛星科技": "space",
    "金融科技": "fintech",
    "資通訊安全": "cybersec",
    "智慧電網": "smartgrid",
    "LED照明產業": "led",
    "運動科技": "sportstech",
    "體驗科技": "exptech",
    "文化創意業": "creative",
    "半導體": "semi",
    "電腦及週邊設備": "pc",
    "通信網路": "telecom",
    "電機機械": "machinery",
    "平面顯示器": "display",
    "建材營造": "construct",
    "醫療器材": "meddev",
    "石化及塑橡膠": "chem",
    "印刷電路板": "pcb",
    "製藥": "pharma",
    "紡織": "textile",
    "休閒娛樂": "leisure",
    "軟體服務": "software",
    "汽車": "auto",
    "電動車輛產業": "ev",
    "太陽能產業": "solar",
    "食品": "food",
    "鋼鐵": "steel",
    "連接器": "connector",
    "被動元件": "passive",
    "金融": "finance",
    "觸控面板": "touch",
    "食品生技": "foodbio",
    "交通運輸及航運": "transport",
    "電子商務": "ecommerce",
    "能源元件": "energycomp",
    "風力發電": "wind",
    "油電燃氣": "oilgas",
    "水泥": "cement",
    "汽電共生": "cogen",
    "再生醫療": "regen",
    "造紙": "paper",
    "航太週邊": "aerospace",
    "自動化": "automation",
    "貿易百貨": "retail",
    "其他": "other",
}

# ── 子類詞彙 中文 → 英文縮寫（常見詞對照）────────────────────────────────
TERM_MAP: dict[str, str] = {
    # 通用
    "顧問諮詢": "consult", "系統整合": "sysint", "設備安裝服務": "install",
    "設備管理軟體": "mgmtsw", "資安防護軟體": "secsw", "虛擬化軟體": "virtualize",
    "雲端應用服務": "appservice", "雲端作業系統": "cloudos", "雲端平台": "cloudplat",
    # AI
    "運算設備": "compute", "自然語言處理": "nlp", "機器學習": "ml",
    "智慧設備": "smartdev", "領域解決方案": "solutions", "電腦視覺": "cv",
    "移動控制": "mobility", "資料處理": "dataproc",
    # 雲端
    "伺服器": "server", "伺服器機房": "datacenter", "冷卻設備": "cooling",
    "儲存": "storage", "網路": "network", "電腦設備": "hardware",
    "電力設備": "power",
    # 半導體
    "晶圓製造": "wafer", "記憶體IC": "memoryic", "IC封裝": "icpkg",
    "電源管理IC": "pmic", "特殊應用IC": "asic", "IC設計": "icdesign",
    "射頻IC": "rfic", "感測器IC": "sensoric", "物聯網IC": "iotchip",
    "高電壓IC": "hvic", "車用IC": "automotive", "IP授權": "iplicense",
    "先進製程IC": "advproc", "網通IC": "netiic", "功率半導體IC": "powerchip",
    "LED驅動IC": "leddrive", "光學": "optics", "電源IC": "poweric",
    "基板": "substrate", "MOSFET": "mosfet",
    # PCB
    "軟板": "fpc", "電路板": "pcboard", "軟硬複合板": "rigidflex",
    "高密度板": "hdboard", "硬板": "rigidpcb", "多板類": "multiboard",
    "電路板IC整合": "pca", "特殊功能板": "spcboard", "高層數板": "multilayer",
    "IC載板": "icsub", "背板": "backplane", "散熱模組": "thermal",
    # LED
    "晶粒": "epitaxy", "磊晶": "epi", "封裝": "pkg", "模組": "module",
    "燈具": "luminaire", "燈管": "tube",
    # Display
    "顯示器模組": "dspmod", "觸控面板": "touchpanel", "顯示器整機": "monitor",
    "面板模組": "panelmod", "背光": "backlight", "軟性顯示器": "flexdsp",
    "電子紙": "epaper",
    # 醫療
    "手術": "surgery", "診斷設備": "diagnose", "醫療影像": "medimg",
    "手術機器人": "surgbot", "醫療AI": "medai", "診斷試劑": "reagent",
    "穿戴醫療": "wearmed", "AI診斷": "aidiag", "遠距醫療": "telehealth",
    "醫療資訊": "medinfo", "復健醫療": "rehab", "手術輔助": "surgaid",
    "影像設備": "imgdev", "臨床醫療": "clinical", "可植入醫材": "implant",
    "耗材": "consumable", "影像AI": "imgai", "監控設備": "surveillance",
    "骨科": "ortho", "傷口護理": "wound", "眼科": "ophthal",
    "消化道": "gastro", "齒科": "dental", "心臟科": "cardiac",
    # 資安
    "雲端安全": "cloudsec", "實體安全": "physec", "端點安全": "endpoint",
    "網路安全": "netsec", "應用安全": "appsec", "資安諮詢": "secconsult",
    "辨識認證": "idauth", "零信任": "zerotrust", "數位鑑識": "forensics",
    "滲透測試": "pentest", "防火牆": "firewall", "資料保護": "dataprotect",
    "訓練管理": "trainmgmt", "應用程式": "appdev", "SOC服務": "soc",
    # 智慧電網
    "能源管理": "energymgmt", "充電設備": "evcharger", "電網管理": "gridmgmt",
    "配電設備": "distribution", "再生能源": "renewable", "虛擬電廠": "vpp",
    "電力計量": "metering",
    # 電動車
    "電動車": "evcars", "動力系統": "powertrain", "控制系統": "ctrl",
    "感測器": "sensor",
    # 紡織
    "功能性布料": "funcfabric", "機能性纖維": "funcfiber", "服裝": "apparel",
    "紡紗": "spinning", "織布": "weaving", "特殊紗線": "specyarn",
    "布料": "fabric",
    # 休閒
    "電動遊戲": "videogame", "網路遊戲": "onlinegame", "線上音樂": "streaming",
    "休閒旅遊": "tourism", "電競周邊": "esports", "出版媒體": "media",
    "體驗科技": "xr", "運動科技": "sportst",
    # 再生醫療
    "細胞": "cell", "基因治療": "gene", "幹細胞醫療": "stemcell",
    "生物材料": "biomaterial",
    # 金融
    "銀行": "bank", "保險": "insurance", "支付": "payment",
    "數位身分": "digitalid", "數位銀行": "neobank",
    # 其他
    "太陽能": "solar", "機械零件": "mechparts", "伺服器含儲存": "server_storage",
    "筆記型電腦": "notebook", "工業電腦": "ipc", "工業控制": "industctrl",
    "觸控": "touch", "人機介面": "hmi",
}


def make_sub_slug(sub_name: str) -> str:
    """
    將中文子類名稱轉為安全的英文 slug。
    優先查 TERM_MAP，找不到則：
      1. 保留 ASCII 字元（字母、數字、常見縮寫）
      2. 若結果太短（<3），改用空字串（呼叫者改用流水號）
    """
    # 先試全名
    if sub_name in TERM_MAP:
        return TERM_MAP[sub_name]

    # 拆分 / 後分別查找並合併
    parts = re.split(r"[/\-、，,]", sub_name)
    slugs = []
    for p in parts:
        p = p.strip()
        if p in TERM_MAP:
            slugs.append(TERM_MAP[p])
        else:
            # 保留 ASCII
            ascii_only = re.sub(r"[^A-Za-z0-9]", "", p)
            if len(ascii_only) >= 2:
                slugs.append(ascii_only.lower())
    result = "_".join(slugs) if slugs else ""
    return result[:20]  # 限長


def main() -> None:
    print("=== FinLab 子類板塊擴充 (方案B：獨立檔案) ===\n")

    # ── 載入資料 ──────────────────────────────────────────────────────────
    print("載入 security_industry_themes …")
    themes = data.get("security_industry_themes")
    print(f"  → {len(themes)} 筆主題資料")

    # ── 建立子類 → 股票集合 mapping ──────────────────────────────────────
    sub_stocks: dict[str, set[str]] = defaultdict(set)

    for _, row in themes.iterrows():
        sid = str(row["stock_id"]).strip()
        # 只保留純數字股票代號（排除 ETF 英文代號等）
        if not sid.isdigit():
            continue
        try:
            cats = ast.literal_eval(str(row["category"]))
            if not isinstance(cats, list):
                cats = [str(row["category"])]
        except Exception:
            cats = [str(row["category"])]

        for c in cats:
            c = str(c).strip()
            if ":" in c:
                sub_stocks[c].add(sid)

    print(f"  → 共 {len(sub_stocks)} 個子類（含所有活躍/非活躍股）")

    # ── 依頂層分組，生成 sector_id ────────────────────────────────────────
    by_top: dict[str, list[str]] = defaultdict(list)
    for subcat in sub_stocks:
        top = subcat.split(":")[0].strip()
        by_top[top].append(subcat)

    rows: list[dict] = []
    used_ids: set[str] = set()

    for top in sorted(by_top.keys()):
        top_code = TOP_MAP.get(top, re.sub(r"[^a-z0-9]", "", top.lower())[:8] or "other")
        # 子類依股票數量降序排列
        subcats_sorted = sorted(by_top[top], key=lambda x: -len(sub_stocks[x]))

        for idx, subcat in enumerate(subcats_sorted, start=1):
            sub_name = subcat.split(":", 1)[1].strip()
            slug = make_sub_slug(sub_name)

            if slug:
                candidate = f"{top_code}_{slug}"
            else:
                candidate = f"{top_code}_s{idx:03d}"

            # 確保唯一性
            final_id = candidate
            suffix = 2
            while final_id in used_ids:
                final_id = f"{candidate}_{suffix}"
                suffix += 1
            used_ids.add(final_id)

            stock_ids_str = ",".join(sorted(sub_stocks[subcat]))
            rows.append(
                {
                    "sector_id": final_id,
                    "sector_name": subcat,           # 保留「頂層:子類」完整名
                    "sector_type": "finlab_sub",
                    "parent_sector": top_code,
                    "stock_ids": stock_ids_str,
                    "stock_count": len(sub_stocks[subcat]),
                }
            )

    # ── 排序（頂層 → 股票數量降序）─────────────────────────────────────────
    rows.sort(key=lambda r: (r["parent_sector"], -r["stock_count"]))

    # ── 輸出 custom_subsectors.csv ──────────────────────────────────────
    out_path = ROOT / "output" / "custom_subsectors.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    out_cols = ["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ 寫出 {len(rows)} 個子類 → {out_path}")

    # ── 統計 ──────────────────────────────────────────────────────────────
    top_stats: dict[str, int] = defaultdict(int)
    for r in rows:
        top_stats[r["parent_sector"]] += 1

    print("\n=== 各頂層分類子類數量 ===")
    for top_code, cnt in sorted(top_stats.items(), key=lambda x: -x[1]):
        # 反查中文名
        cn_name = next((k for k, v in TOP_MAP.items() if v == top_code), top_code)
        print(f"  {top_code:12s} ({cn_name}): {cnt} 個子類")

    total_stocks = sum(int(r["stock_count"]) for r in rows)
    print(f"\n合計：{len(rows)} 個子類，股票出現次數（含重複）= {total_stocks}")

    # ── 同時產生合併版（custom_sectors.csv + subsectors）──────────────────
    main_csv = ROOT / "custom_sectors.csv"
    merged_path = ROOT / "output" / "proposed_sectors_v2.csv"

    if main_csv.exists():
        # 用 csv.DictReader 讀取主板塊，再用 csv.DictWriter 寫出，確保格式一致
        main_rows: list[dict] = []
        with open(main_csv, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                main_rows.append(dict(row))

        # 用 csv.DictWriter 合併寫出，完全避免手動字串拼接造成的格式問題
        with open(merged_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=out_cols,
                extrasaction="ignore",
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writeheader()
            writer.writerows(main_rows)
            writer.writerows(rows)

        merged_count = len(main_rows) + len(rows)
        print(f"\n✅ 合併版（主板塊 + 子類）→ {merged_path}")
        print(f"   合計 {merged_count} 個板塊（原 {len(main_rows)} 主板塊 + {len(rows)} 子類）")
        print("\n要套用到正式系統，請執行：")
        print(f"  Copy-Item '{merged_path}' '{main_csv}'")
    else:
        print(f"\n⚠️  找不到 {main_csv}，跳過合併步驟")

    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
