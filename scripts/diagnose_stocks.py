"""
diagnose_stocks.py — 診斷 FinLab 數據格式、找出正確的股票 ID
用途：
  1. 列出所有活躍股票 ID + 名稱
  2. 供人工策展板塊成份股使用
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401
from src.config import FINLAB_API_TOKEN

import finlab
import pandas as pd

finlab.login(api_token=FINLAB_API_TOKEN)
from finlab import data

# 1) 收盤價
print("=== 收盤價 DataFrame 結構 ===")
close_df = data.get("price:收盤價")
print(f"shape: {close_df.shape}")
print(f"columns type: {type(close_df.columns)}")
print(f"前 10 個 column: {list(close_df.columns[:10])}")
print(f"最後 5 個 column: {list(close_df.columns[-5:])}")

# 活躍股票（近 5 日有收盤價）
recent = close_df.iloc[-5:]
active = recent.columns[recent.notna().any()].tolist()
print(f"\n活躍股票數: {len(active)}")

# 2) 公司基本資料
print("\n=== company_basic_info 結構 ===")
try:
    info = data.get("company_basic_info")
    print(f"type: {type(info)}")
    print(f"shape: {info.shape}")
    print(f"columns: {list(info.columns)}")
    print(f"index name: {info.index.name}")
    print(f"index type: {type(info.index)}")
    print(f"前 5 個 index: {list(info.index[:5])}")
    print(f"\n前 5 列:")
    print(info.head())
except Exception as e:
    print(f"ERROR: {e}")

# 3) Try to build stock_id → name mapping
print("\n=== 建立 ID → 名稱映射 ===")
try:
    if "公司簡稱" in info.columns:
        name_col = "公司簡稱"
    elif "公司名稱" in info.columns:
        name_col = "公司名稱"
    else:
        name_col = info.columns[0]
    
    print(f"使用欄位: {name_col}")
    
    # Check if index is stock ID
    sample_idx = str(info.index[0])
    print(f"第一個 index 值: {sample_idx} (type: {type(info.index[0])})")
    
    # Try to get name for known stock
    test_ids = ["2330", "2454", "2303", "3034"]
    for tid in test_ids:
        try:
            name = info.loc[tid, name_col]
            print(f"  {tid} → {name}")
        except KeyError:
            # Maybe need to try different types?
            try:
                name = info.loc[int(tid), name_col]
                print(f"  {tid} (as int) → {name}")
            except Exception:
                print(f"  {tid} → NOT FOUND")
except Exception as e:
    print(f"ERROR: {e}")

# 4) 嘗試用 stock_info 取得股票名稱
print("\n=== 嘗試其他名稱數據源 ===")
try:
    stock_info = data.get("stock_basic_info")
    if stock_info is not None:
        print(f"stock_basic_info: {stock_info.shape}, columns: {list(stock_info.columns[:10])}")
except Exception:
    pass

# 5) 列出特定板塊相關的候選股票名稱
# 用公司名稱搜尋
print("\n=== 關鍵字搜尋候選 ===")
if info is not None and "公司簡稱" in info.columns:
    name_series = info["公司簡稱"].dropna()
    # 確保 index 是字串
    name_series.index = name_series.index.astype(str)
    active_set = set(str(a) for a in active)
    
    keywords_to_search = [
        ("散熱", "thermal"),
        ("光通", "optical_comm"),
        ("封測|封裝", "packaging"),
        ("伺服器|雲端", "ai_server"),
        ("記憶體|DRAM|NAND", "memory"),
        ("儲能|電池|鋰", "energy_storage"),
        ("國防|軍工|航太", "defense"),
        ("醫材|醫療器", "medical_device"),
        ("電商|網購", "ecommerce"),
        ("遊戲|娛樂", "gaming"),
        ("光學|鏡頭", "lens_optics"),
        ("連接|連接器", "connector"),
        ("重電|電力", "power_infra"),
        ("機器人|自動化", "robotics"),
        ("太陽能|光電", "solar"),
        ("風電|風力", "wind_energy"),
        ("車用|車電", "vehicle_elec"),
    ]
    
    for kw_pattern, sector in keywords_to_search:
        import re
        matches = []
        for idx, name in name_series.items():
            if re.search(kw_pattern, str(name)):
                is_active = "✓" if str(idx) in active_set else "✗"
                matches.append(f"{idx}({name}){is_active}")
        
        if matches:
            print(f"\n[{sector}] {kw_pattern}:")
            for m in matches[:15]:
                print(f"  {m}")
