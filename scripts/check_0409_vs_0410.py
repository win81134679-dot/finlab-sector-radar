"""Compare 4/9 vs 4/10 in history_index.json"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "output" / "history"
idx = json.loads((ROOT / "history_index.json").read_text(encoding="utf-8"))

dates = idx["dates"]
print("dates:", dates)
print()

diff_count = 0
total = len(idx["sectors"])
for sid, sdata in idx["sectors"].items():
    t9 = sdata["totals"][7]   # 4/9
    t10 = sdata["totals"][8]  # 4/10
    l9 = sdata["levels"][7]
    l10 = sdata["levels"][8]
    if t9 != t10 or l9 != l10:
        diff_count += 1
        print(f"  {sid}: 4/9={t9}/{l9}  4/10={t10}/{l10}")

print(f"\nDiff: {diff_count}/{total} sectors differ")

# Also check history files
for fname in ["2026-04-09.json", "2026-04-10.json"]:
    fp = ROOT / fname
    if fp.exists():
        data = json.loads(fp.read_text(encoding="utf-8"))
        t = data.get("totals", {})
        print(f"\n{fname}: date={data.get('date')}, totals={t}")
    else:
        print(f"\n{fname}: NOT FOUND")
