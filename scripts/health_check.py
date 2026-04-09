"""一次性健檢腳本：檢查 signals_latest.json 的各項指標。"""
import json
import math
import sys

path = "output/signals_latest.json"
d = json.loads(open(path, encoding="utf-8").read())

# ── 1. Macro ──
m = d["macro"]
print("=== MACRO ===")
print(f"  signal: {m['signal']}  warning: {m['warning']}")
print(f"  positive: {m['positive_count']} / {m['total_available']}")
print(f"  ip_trend: {m.get('ip_trend')}  bond_trend: {m.get('bond_trend')}")
print(f"  sox_trend: {m.get('sox_trend')}  twd_trend: {m.get('twd_trend')}")
for k, v in m.get("details", {}).items():
    print(f"    {k}: {v}")

# ── 2. Levels ──
print("\n=== LEVELS ===")
levels = {}
for s in d["sectors"].values():
    l = s["level"]
    levels[l] = levels.get(l, 0) + 1
for k in ["強烈關注", "觀察中", "忽略"]:
    print(f"  {k}: {levels.get(k, 0)}")

# ── 3. Top 10 ──
print("\n=== TOP 10 ===")
ranked = sorted(d["sectors"].items(), key=lambda x: -x[1]["total"])
for sid, s in ranked[:10]:
    sc = len(s.get("stocks", []))
    print(f"  {s['name_zh']:<12s} total={s['total']}  level={s['level']}  cycle={s.get('cycle_stage')}  stocks={sc}")

# ── 4. 忽略 sectors with stocks ──
print("\n=== 忽略 SECTORS ===")
ignore = [(sid, s) for sid, s in d["sectors"].items() if s["level"] == "忽略"]
for sid, s in ignore[:8]:
    sc = len(s.get("stocks", []))
    print(f"  {sid} ({s['name_zh']}): stocks={sc} total={s['total']}")

# ── 5. NaN check ──
print("\n=== NaN CHECK ===")
raw = open(path, encoding="utf-8").read()
nan_count = raw.count("NaN")
inf_count = raw.count("Infinity")
print(f"  NaN occurrences: {nan_count}")
print(f"  Infinity occurrences: {inf_count}")

# ── 6. homogeneity null check ──
null_homo = sum(1 for s in d["sectors"].values() if s.get("homogeneity") is None)
print(f"  homogeneity=null: {null_homo} / {len(d['sectors'])}")

# ── 7. Stock counts in 強烈關注/觀察中 ──
print("\n=== STOCK COUNTS (強烈關注/觀察中) ===")
empty_stock_sectors = []
for sid, s in d["sectors"].items():
    if s["level"] in ("強烈關注", "觀察中"):
        sc = len(s.get("stocks", []))
        if sc == 0:
            empty_stock_sectors.append(f"{sid} ({s['name_zh']})")
if empty_stock_sectors:
    print(f"  ⚠️ {len(empty_stock_sectors)} sectors with stocks=[]: {empty_stock_sectors[:5]}")
else:
    print("  ✅ All 強烈關注/觀察中 sectors have stocks data")

# ── 8. Schema version ──
print(f"\n=== META ===")
print(f"  schema_version: {d.get('schema_version')}")
print(f"  date: {d.get('date')}")
print(f"  run_at: {d.get('run_at')}")
print(f"  last_trading_date: {d.get('last_trading_date')}")

# ── 9. History index check ──
print("\n=== HISTORY INDEX ===")
try:
    idx = json.loads(open("output/history/history_index.json", encoding="utf-8").read())
    dates = idx.get("dates", [])
    print(f"  dates: {len(dates)} entries, last 5: {dates[-5:]}")
    # Check 4/9 entry
    if "2026-04-09" in dates:
        pos = dates.index("2026-04-09")
        sample = list(idx["sectors"].keys())[:3]
        for sid in sample:
            e = idx["sectors"][sid]
            print(f"  4/9 {sid}: total={e['totals'][pos]} level={e['levels'][pos]}")
except Exception as e:
    print(f"  ❌ Error: {e}")
