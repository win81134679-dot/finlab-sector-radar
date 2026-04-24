"""
05_finlab_sector_expansion.py — 全面擴充個股及板塊

策略：
  1. 讀取 custom_sectors.csv 現有板塊定義
  2. 從 FinLab security_industry_themes 抓取官方分類
  3. 對每個現有板塊：合集現有股票 + FinLab 映射股票（排除非活躍）
  4. 新增 FinLab 原生板塊（14 個）
  5. 輸出 output/proposed_sectors.csv 供審核
  6. 印出差異報告

執行方式：
  python tests_explore/05_finlab_sector_expansion.py

輸出：
  output/proposed_sectors.csv  ← 審核用，不自動覆蓋 custom_sectors.csv
"""

import sys
import ast
import csv
import io
from pathlib import Path

# UTF-8 輸出（避免 cp950 問題）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401 — 必須最早 import
from src.config import FINLAB_API_TOKEN, OUTPUT_DIR, CUSTOM_SECTORS_CSV

import finlab
finlab.login(api_token=FINLAB_API_TOKEN)
from finlab import data

# ─────────────────────────────────────────────
# 1. 讀取現有 custom_sectors.csv
# ─────────────────────────────────────────────
print("=" * 60)
print("步驟 1：讀取現有板塊定義")
print("=" * 60)

existing_sectors = {}
with open(CUSTOM_SECTORS_CSV, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        sid = row["sector_id"].strip()
        stocks = [s.strip() for s in row.get("stock_ids", "").split(",") if s.strip()]
        existing_sectors[sid] = {
            "sector_id": sid,
            "sector_name": row["sector_name"].strip(),
            "sector_type": row["sector_type"].strip(),
            "parent_sector": row.get("parent_sector", "").strip(),
            "stock_ids": set(stocks),
        }

print(f"現有板塊數: {len(existing_sectors)}")

# ─────────────────────────────────────────────
# 2. 從 FinLab 抓取主題分類表
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("步驟 2：下載 FinLab security_industry_themes")
print("=" * 60)

themes = data.get("security_industry_themes")
print(f"themes shape: {themes.shape}")

# 建立「頂層分類 → stock_id set」的查找表
top_to_stocks: dict[str, set] = {}
full_to_stocks: dict[str, set] = {}  # 含子類完整分類

for _, row in themes.iterrows():
    sid = str(row["stock_id"]).strip()
    try:
        cats = ast.literal_eval(str(row["category"]))
        if not isinstance(cats, list):
            cats = [str(row["category"])]
    except Exception:
        cats = [str(row["category"])]
    for c in cats:
        c = str(c).strip()
        top = c.split(":")[0].strip()
        top_to_stocks.setdefault(top, set()).add(sid)
        full_to_stocks.setdefault(c, set()).add(sid)

print(f"頂層分類數: {len(top_to_stocks)}")

# ─────────────────────────────────────────────
# 3. 抓取活躍股清單（最近 20 天有收盤價）
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("步驟 3：取得活躍股清單")
print("=" * 60)

close = data.get("price:收盤價")
active_stocks = set(
    str(s) for s in close.iloc[-20:].columns[close.iloc[-20:].notna().any()]
)
print(f"活躍股數: {len(active_stocks)}")


def filter_active(stocks: set) -> set:
    """只保留有活躍交易的股票，排除 ETF（代碼含字母）。"""
    result = set()
    for s in stocks:
        s = str(s).strip()
        if not s.isdigit():
            continue  # 排除 ETF/TDR
        if s in active_stocks:
            result.add(s)
    return result


# ─────────────────────────────────────────────
# 4. 現有板塊 → FinLab 映射規則
# ─────────────────────────────────────────────

# 每個 sector_id 對應的 FinLab 頂層分類清單（取聯集）
SECTOR_FINLAB_MAP: dict[str, list[str]] = {
    "foundry":            ["半導體"],
    "ic_design":          ["半導體"],
    "memory":             ["半導體"],
    "ai_server":          ["電腦及週邊設備", "人工智慧"],
    "networking":         ["通信網路"],
    "power_components":   ["被動元件"],
    "ev_supply":          ["電動車輛產業"],
    "solar":              ["太陽能產業"],
    "pcb":                ["印刷電路板"],
    "display":            ["平面顯示器", "觸控面板"],
    "biotech":            ["製藥", "再生醫療", "食品生技"],
    "banking":            ["金融"],
    "insurance":          ["金融"],
    "shipping":           ["交通運輸及航運"],
    "construction":       ["建材營造"],
    "steel":              ["鋼鐵"],
    "semiconductor_equip":["半導體"],
    "thermal":            ["電機機械"],
    "optical_comm":       ["通信網路"],
    "packaging":          ["半導體"],
    "power_infra":        ["電機機械", "智慧電網"],
    "robotics":           ["自動化", "電機機械"],
    "power_semi":         ["半導體"],
    "ip_design":          ["半導體"],
    "wind_energy":        ["風力發電"],
    "lens_optics":        ["電腦及週邊設備"],
    "connector":          ["連接器"],
    "vehicle_elec":       ["汽車", "電動車輛產業"],
    "software_saas":      ["軟體服務", "雲端運算"],
    "ecommerce":          ["電子商務"],
    "gaming":             ["休閒娛樂"],
    "petrochemical":      ["石化及塑橡膠"],
    "textile":            ["紡織"],
    "cement":             ["水泥"],
    "food":               ["食品", "食品生技"],
    "rubber":             ["石化及塑橡膠"],
    "paper":              ["造紙"],
    "securities":         ["金融"],
    "financial_holding":  ["金融"],
    "telecom":            ["通信網路"],
    "energy_storage":     ["能源元件"],
    "gas_energy":         ["油電燃氣", "汽電共生"],
    "defense":            ["航太週邊"],
    "tourism":            ["休閒娛樂"],
    "medical_device":     ["醫療器材"],
}

# ─────────────────────────────────────────────
# 5. 新增 FinLab 原生板塊（14 個）
# ─────────────────────────────────────────────
NEW_SECTORS: list[dict] = [
    {
        "sector_id":    "ai_themes",
        "sector_name":  "人工智慧主題",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["人工智慧"],
    },
    {
        "sector_id":    "cloud_computing",
        "sector_name":  "雲端運算",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["雲端運算"],
    },
    {
        "sector_id":    "big_data",
        "sector_name":  "大數據",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["大數據"],
    },
    {
        "sector_id":    "blockchain",
        "sector_name":  "區塊鏈",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["區塊鏈"],
    },
    {
        "sector_id":    "metaverse",
        "sector_name":  "元宇宙",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["元宇宙"],
    },
    {
        "sector_id":    "space_satellite",
        "sector_name":  "太空衛星科技",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["太空衛星科技"],
    },
    {
        "sector_id":    "fintech",
        "sector_name":  "金融科技",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["金融科技"],
    },
    {
        "sector_id":    "cybersecurity",
        "sector_name":  "資安",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["資通訊安全"],
    },
    {
        "sector_id":    "smart_grid",
        "sector_name":  "智慧電網",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["智慧電網"],
    },
    {
        "sector_id":    "led_lighting",
        "sector_name":  "LED照明",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["LED照明產業"],
    },
    {
        "sector_id":    "trading",
        "sector_name":  "貿易百貨",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["貿易百貨"],
    },
    {
        "sector_id":    "sports_tech",
        "sector_name":  "運動科技",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["運動科技"],
    },
    {
        "sector_id":    "experience_tech",
        "sector_name":  "體驗科技",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["體驗科技"],
    },
    {
        "sector_id":    "creative_industry",
        "sector_name":  "文化創意",
        "sector_type":  "finlab",
        "parent_sector":"",
        "finlab_tops":  ["文化創意業"],
    },
]

# ─────────────────────────────────────────────
# 6. 合併現有板塊 + FinLab
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("步驟 4：合併板塊（現有 + FinLab 映射）")
print("=" * 60)

merged_sectors = {}

for sid, sector in existing_sectors.items():
    old_stocks = sector["stock_ids"].copy()

    # 從 FinLab 補充
    finlab_tops = SECTOR_FINLAB_MAP.get(sid, [])
    finlab_pool: set = set()
    for top in finlab_tops:
        finlab_pool |= top_to_stocks.get(top, set())

    # 過濾活躍股
    finlab_active = filter_active(finlab_pool)

    # 合集：保留手工 + 補充 FinLab 活躍股
    new_stocks = old_stocks | finlab_active

    added = new_stocks - old_stocks
    merged_sectors[sid] = {
        **sector,
        "stock_ids": new_stocks,
        "_old_count": len(old_stocks),
        "_new_count": len(new_stocks),
        "_added": added,
    }

    if added:
        print(f"  [{sid}] {sector['sector_name']}: {len(old_stocks)} → {len(new_stocks)} (+{len(added)} 股)")

# 新增 FinLab 原生板塊
print()
print("新增 FinLab 原生板塊：")
for ns in NEW_SECTORS:
    if ns["sector_id"] in merged_sectors:
        print(f"  跳過（已存在）: {ns['sector_id']}")
        continue
    pool: set = set()
    for top in ns["finlab_tops"]:
        pool |= top_to_stocks.get(top, set())
    active_pool = filter_active(pool)
    merged_sectors[ns["sector_id"]] = {
        "sector_id":    ns["sector_id"],
        "sector_name":  ns["sector_name"],
        "sector_type":  ns["sector_type"],
        "parent_sector": ns["parent_sector"],
        "stock_ids":    active_pool,
        "_old_count":   0,
        "_new_count":   len(active_pool),
        "_added":       active_pool,
    }
    print(f"  [新增] {ns['sector_id']} {ns['sector_name']}: {len(active_pool)} 股")

# ─────────────────────────────────────────────
# 7. 輸出 proposed_sectors.csv
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("步驟 5：輸出 output/proposed_sectors.csv")
print("=" * 60)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
proposed_path = OUTPUT_DIR / "proposed_sectors.csv"

with open(proposed_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["sector_id", "sector_name", "sector_type", "parent_sector", "stock_ids"])
    for sid, sector in merged_sectors.items():
        stock_str = ",".join(sorted(sector["stock_ids"]))
        writer.writerow([
            sector["sector_id"],
            sector["sector_name"],
            sector["sector_type"],
            sector["parent_sector"],
            stock_str,
        ])

print(f"已輸出：{proposed_path}")

# ─────────────────────────────────────────────
# 8. 差異摘要報告
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("差異摘要報告")
print("=" * 60)

total_old = sum(s["_old_count"] for s in merged_sectors.values())
total_new = sum(s["_new_count"] for s in merged_sectors.values())
added_sectors = [k for k, v in merged_sectors.items() if v["_old_count"] == 0]
expanded_sectors = [k for k, v in merged_sectors.items() if v["_old_count"] > 0 and v["_added"]]

print(f"板塊總數:  {len([k for k in merged_sectors if merged_sectors[k]['_old_count'] > 0])} → {len(merged_sectors)}")
print(f"新增板塊:  {len(added_sectors)} 個")
print(f"擴充板塊:  {len(expanded_sectors)} 個")
print(f"個股覆蓋:  {total_old} → {total_new} （去重前）")

print()
print("─ 擴充板塊（個股增加）─")
for sid in expanded_sectors:
    s = merged_sectors[sid]
    print(f"  {s['sector_name']:<16} {s['_old_count']:>4} → {s['_new_count']:>4}  (+{len(s['_added'])} 股)")

print()
print("─ 新增板塊 ─")
for sid in added_sectors:
    s = merged_sectors[sid]
    print(f"  {s['sector_name']:<16} {s['_new_count']:>4} 股")

print()
print("✅ 完成！請審核 output/proposed_sectors.csv")
print("   確認無誤後，執行以下指令覆蓋正式板塊：")
print("   copy output\\proposed_sectors.csv custom_sectors.csv")
