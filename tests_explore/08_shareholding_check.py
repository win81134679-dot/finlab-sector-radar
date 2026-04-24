"""
08_shareholding_check.py — 討論點C：主力性質辨識資料可用性確認

確認 FinLab 是否提供以下數據，以判斷板塊「法人型」vs「千張大戶型」主力：

  1. stock_shareholding_distribution:千張以上   — 千張以上大戶持股比例
  2. stock_shareholding_distribution:400~999張  — 中大型散戶
  3. stock_shareholding_distribution:100~399張  — 中型散戶
  4. 外資持股比例（from institutional）          — 法人型指標
  5. 投信持股比例                               — 投信動態

板塊主力類型判斷邏輯：
  法人型  (institutional)  ← 外資持股高 OR 投信持股高
  千張大戶型 (whale)       ← 千張以上持股比例高且持續增加
  散戶型  (retail)         ← 以上皆低，主要是散戶

執行方式（需先啟動 venv）：
  python tests_explore/08_shareholding_check.py

輸出：
  - 資料可用性報告
  - 最新一期各欄位樣本資料（前5筆）
  - 推薦實作方案
"""

import sys
from pathlib import Path

# 確保 ssl_fix 最先 import（Windows 中文路徑 SSL 修正）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src.ssl_fix  # noqa: F401  必須最先載入

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import warnings
warnings.filterwarnings("ignore")

import finlab
finlab.login(os.getenv("FINLAB_API_TOKEN", ""))

import finlab.data as data

KEYS_TO_CHECK = [
    # 持股分佈（主力性質判斷核心）
    "stock_shareholding_distribution:千張以上",
    "stock_shareholding_distribution:400~999張",
    "stock_shareholding_distribution:100~399張",
    "stock_shareholding_distribution:1~9張",
    # 外資持股（法人型指標）
    "institutional_investors_trading_summary:外資持股比例",
    # 基本面（補充）
    "fundamental_features:ROE稅後",
]

print("=" * 60)
print("討論點C：主力性質辨識 — FinLab 資料可用性確認")
print("=" * 60)

results = {}
for key in KEYS_TO_CHECK:
    print(f"\n>> 測試: {key}")
    try:
        df = data.get(key)
        if df is None or df.empty:
            print(f"  [NG] 回傳 None 或空 DataFrame")
            results[key] = "empty"
        else:
            print(f"  [OK] 可用！shape={df.shape}, 最新日期={df.index[-1].strftime('%Y-%m-%d')}")
            # 顯示前5支股票的最新數值
            latest = df.iloc[-1].dropna().head(5)
            print(f"  樣本資料：")
            for stock, val in latest.items():
                print(f"    {stock}: {val:.2f}")
            results[key] = "ok"
    except Exception as e:
        print(f"  [NG] 錯誤：{e}")
        results[key] = f"error: {e}"

print("\n" + "=" * 60)
print(" 可用性摘要")
print("=" * 60)
for key, status in results.items():
    icon = "[OK]" if status == "ok" else "[NG]"
    short_key = key.split(":")[-1]
    print(f"  {icon} {short_key:30s}  {status}")

# ── 推薦實作方案 ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(" 推薦實作方案（依可用性）")
print("=" * 60)

whale_ok    = results.get("stock_shareholding_distribution:千張以上") == "ok"
inst_ok     = results.get("institutional_investors_trading_summary:外資持股比例") == "ok"

if whale_ok and inst_ok:
    print("""
  建議方案：完整版（法人型 vs 千張大戶型 vs 散戶型）
  ─────────────────────────────────────────────────────
  Per-stock 評分：
    外資持股比例 > 20% OR 投信持股增加  → institutional_flag = True
    千張以上持股 > 30% AND 近季增加     → whale_flag = True
    
  Per-sector 彙整：
    institutional_ratio = len(institutional_stocks) / total_stocks
    whale_ratio         = len(whale_stocks) / total_stocks
    
  主力類型判斷：
    dominant_force = "法人型"   if institutional_ratio ≥ 0.3
                   = "千張大戶" if whale_ratio ≥ 0.3
                   = "混合型"   if both ≥ 0.2
                   = "散戶型"   otherwise
    
  進場策略提示：
    法人型   → 跟追外資籌碼，注意法說會
    千張大戶 → 等待公開資訊，避免追高
    散戶型   → 風險最高，需更強技術確認
""")
elif whale_ok:
    print("""
  建議方案：精簡版（千張大戶型 only）
  使用 stock_shareholding_distribution 計算 whale_ratio
  結合燈2法人共振做互補判斷
""")
else:
    print("""
  建議方案：改用代理指標
  FinLab 持股分佈資料不可用，改用：
    - 燈2法人共振（已有）作為法人型指標
    - 燈4技術突破帶量（已有）作為大戶型代理
""")

print("\n完成！請依上方結果決定是否實作主力性質辨識功能。")
