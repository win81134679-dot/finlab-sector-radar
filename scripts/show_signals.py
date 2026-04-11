import json, sys

path = "output/signals_latest.json"
d = json.load(open(path, encoding="utf-8"))
s = d["sectors"]

print(f"資料日期: {d['date']}  分析時間: {d['run_at']}")
print()

rows = []
for eng, v in s.items():
    rows.append((
        v.get("total", 0),
        eng,
        v.get("name_zh", eng),
        v.get("level", ""),
        v.get("cycle_stage") or "—",
        v.get("signals", []),
        v.get("rs_momentum", 0) or 0,
        v.get("exit_risk"),
        v.get("homogeneity", 0) or 0,
    ))
rows.sort(reverse=True)

# 統計
strong = [r for r in rows if r[3] == "強烈關注"]
watch  = [r for r in rows if r[3] == "觀察中"]
ignore = [r for r in rows if r[3] == "忽略"]
print(f"🔥 強烈關注: {len(strong)} 個   👀 觀察中: {len(watch)} 個   ⬜ 忽略: {len(ignore)} 個")
print()

header = f"{'名稱':<10} {'總分':>4}  {'等級':<6} {'週期':<8} {'1-7燈(●=亮 ◐=半 ○=滅)'}"
print(header)
print("-" * 65)

for tot, eng, zh, lvl, cyc, sigs, rs, exit_r, homo in rows:
    if lvl == "強烈關注":
        icon = "🔥"
    elif lvl == "觀察中":
        icon = "👀"
    else:
        icon = "  "

    sig_str = ""
    for sv in (sigs or []):
        if sv >= 0.9:
            sig_str += "●"
        elif sv >= 0.4:
            sig_str += "◐"
        else:
            sig_str += "○"

    exit_val = exit_r if isinstance(exit_r, (int, float)) else (exit_r.get("score") if isinstance(exit_r, dict) else None)
    exit_tag = f" ⚠️exit={exit_val:.0f}" if exit_val and exit_val > 50 else ""
    print(f"{icon}{zh:<9} {tot:>4.1f}  {lvl:<6} {cyc:<8} {sig_str}{exit_tag}")

print()
print("燈號順序：燈1月營收 燈2法人籌碼 燈3庫存循環 燈4技術突破 燈5板塊強度 燈6籌碼集中 燈7宏觀濾網")
