"""一次性：用 4/10 的板塊燈號數據覆蓋 4/9 的歷史資料。"""
import json
import shutil

# 1. 用 4/10 的 history JSON 覆蓋 4/9
src = "output/history/2026-04-10.json"
dst = "output/history/2026-04-09.json"

h10 = json.loads(open(src, encoding="utf-8").read())
# 改 date 欄位為 4/9
h10["date"] = "2026-04-09"
open(dst, "w", encoding="utf-8").write(
    json.dumps(h10, ensure_ascii=False, indent=2, allow_nan=False)
)
print("history/2026-04-09.json <- 2026-04-10.json (overwritten)")

# 2. 更新 history_index.json 中 4/9 的 totals/levels
idx = json.loads(open("output/history/history_index.json", encoding="utf-8").read())
dates = idx["dates"]
p9 = dates.index("2026-04-09")
p10 = dates.index("2026-04-10")

changed = 0
for sid, entry in idx["sectors"].items():
    if p10 < len(entry["totals"]) and p9 < len(entry["totals"]):
        old = entry["totals"][p9]
        entry["totals"][p9] = entry["totals"][p10]
        entry["levels"][p9] = entry["levels"][p10]
        if old != entry["totals"][p9]:
            changed += 1

# Update macro entry for 4/9
for i, m in enumerate(idx.get("macro", [])):
    if m.get("date") == "2026-04-09":
        for j, m10 in enumerate(idx["macro"]):
            if m10.get("date") == "2026-04-10":
                idx["macro"][i] = {**m10, "date": "2026-04-09"}
                break
        break

open("output/history/history_index.json", "w", encoding="utf-8").write(
    json.dumps(idx, ensure_ascii=False, indent=2, allow_nan=False)
)
print(f"history_index.json: 4/9 <- 4/10 ({changed} sectors updated)")

# 3. Verify
for sid in ["pcb", "semi_equip", "ic_design", "optical_comm", "power_components"]:
    e = idx["sectors"][sid]
    t9 = e["totals"][p9]
    t10 = e["totals"][p10]
    print(f"  {sid}: 4/9={t9}  4/10={t10}  match={t9==t10}")
