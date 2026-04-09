"""一次性：補 history_index.json 缺少的 2026-04-10 條目。"""
import json

# Load 4/10 history file
h = json.loads(open("output/history/2026-04-10.json", encoding="utf-8").read())
sectors = h["sectors"]
macro = h["macro"]

# Load history_index
idx = json.loads(open("output/history/history_index.json", encoding="utf-8").read())
dates = idx["dates"]
date_str = "2026-04-10"

if date_str in dates:
    print("Already in index!")
    exit(0)

dates.append(date_str)
idx["dates"] = sorted(dates)
pos = idx["dates"].index(date_str)

for sid, v in sectors.items():
    if sid not in idx["sectors"]:
        idx["sectors"][sid] = {"name_zh": v["name_zh"], "totals": [], "levels": []}
    entry = idx["sectors"][sid]
    while len(entry["totals"]) < pos:
        entry["totals"].append(None)
    while len(entry["levels"]) < pos:
        entry["levels"].append(None)
    entry["totals"].insert(pos, v["total"])
    entry["levels"].insert(pos, v["level"])

# Pad sectors not in this snapshot
for sid, entry in idx["sectors"].items():
    while len(entry["totals"]) < len(idx["dates"]):
        entry["totals"].append(None)
    while len(entry["levels"]) < len(idx["dates"]):
        entry["levels"].append(None)

# Add macro entry
macro_entry = {
    "date": date_str,
    "warning": macro.get("warning", False),
    "signal": macro.get("signal", False),
    "positive_count": macro.get("positive_count", 0),
    "us_bond_10y": macro.get("us_bond_10y"),
    "sox_price": macro.get("sox_price"),
}
idx.setdefault("macro", []).append(macro_entry)
idx["macro"] = sorted(idx["macro"], key=lambda x: x.get("date", ""))

out = json.dumps(idx, ensure_ascii=False, indent=2, allow_nan=False)
open("output/history/history_index.json", "w", encoding="utf-8").write(out)
print("Added", date_str, "to history_index at pos", pos)
print("Now", len(idx["dates"]), "dates:", idx["dates"])
