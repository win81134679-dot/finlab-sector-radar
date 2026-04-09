"""validate_csv.py — 驗證 custom_sectors.csv 中所有股票 ID 是否活躍"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401
from src.config import FINLAB_API_TOKEN

import csv
import finlab
finlab.login(api_token=FINLAB_API_TOKEN)
from finlab import data

close_df = data.get("price:收盤價")
recent = close_df.iloc[-5:]
active = set(str(c) for c in recent.columns[recent.notna().any()].tolist())
print(f"活躍股票: {len(active)}")

# 取名稱
info = data.get("company_basic_info")
id_to_name = {}
for _, row in info.iterrows():
    sid = str(row.get("stock_id", "")).strip()
    if sid:
        id_to_name[sid] = str(row.get("公司簡稱", ""))

csv_path = ROOT / "custom_sectors.csv"
total = 0
inactive = []
counts = []

with open(csv_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        sid = row["sector_id"]
        stocks = [s.strip() for s in row["stock_ids"].split(",") if s.strip()]
        counts.append((sid, row["sector_name"], len(stocks)))
        for s in stocks:
            total += 1
            if s not in active:
                inactive.append((sid, s, id_to_name.get(s, "?")))

print(f"\n總股票數: {total}")
print(f"不活躍: {len(inactive)}")
for sid, stock, name in inactive:
    print(f"  [{sid}] {stock} ({name})")

print(f"\n板塊統計:")
for sid, name, cnt in counts:
    print(f"  {sid:25s} {name:15s} {cnt:>3d} 隻")

avg = sum(c for _, _, c in counts) / len(counts)
print(f"\n平均: {avg:.1f}, min: {min(c for _,_,c in counts)}, max: {max(c for _,_,c in counts)}")
