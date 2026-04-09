"""一次性腳本：用修正後的 macro ratio-based 閾值重新計算 4/9 所有快照。"""
import json
import math
import glob
import os

LEVEL_THRESHOLDS = {"強烈關注": 4, "觀察中": 2}


def recalc_level(total):
    if total >= LEVEL_THRESHOLDS["強烈關注"]:
        return "強烈關注"
    elif total >= LEVEL_THRESHOLDS["觀察中"]:
        return "觀察中"
    return "忽略"


def calc_cycle_stage(signals, total, level):
    if level == "忽略" or len(signals) < 6:
        return None
    rev, inst, inv, tech, _rs, chip = (float(signals[i]) for i in range(6))
    if total >= 6.5:
        return "過熱期"
    if total >= 5 or (total >= 4 and chip >= 1):
        return "加速期"
    if inst >= 0.5 and tech >= 0.5:
        return "確認期"
    if (rev >= 0.5 or inv >= 0.5) and inst < 0.5 and tech < 0.5:
        return "萌芽期"
    return None


def sanitize_nans(obj):
    """遞迴清洗 NaN → None"""
    if isinstance(obj, dict):
        return {k: sanitize_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nans(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def patch_snapshot(data):
    m = data.get("macro", {})
    pc = m.get("positive_count", 0)
    ta = m.get("total_available", 0)

    # 重算 macro signal (ratio-based >= 60%)
    if ta >= 2:
        new_signal = pc >= math.ceil(ta * 0.6)
    else:
        new_signal = (ta >= 1) and (pc >= 1)

    old_signal = m.get("signal", False)
    delta = float(new_signal) - float(old_signal)

    m["signal"] = new_signal
    data["macro_warning"] = not new_signal
    m["warning"] = not new_signal

    # Fix ip_trend: INDPRO 取得失敗 → unknown
    if "INDPRO 取得失敗" in m.get("details", {}).get("pmi", ""):
        m["ip_trend"] = "unknown"

    if delta == 0:
        return None  # no change needed

    before = {}
    after = {}
    for sid, s in data.get("sectors", {}).items():
        old_level = s["level"]
        before[old_level] = before.get(old_level, 0) + 1

        # Update signals[6] (燈7) and total
        if len(s.get("signals", [])) == 7:
            s["signals"][6] = float(new_signal)
        s["total"] = round(s["total"] + delta, 1)
        s["level"] = recalc_level(s["total"])
        s["cycle_stage"] = calc_cycle_stage(s["signals"], s["total"], s["level"])

        after[s["level"]] = after.get(s["level"], 0) + 1

    return {"before": before, "after": after}


def patch_history_index(index_path, date_str, sectors):
    """更新 history_index.json 中 4/9 那天的 totals 和 levels。"""
    if not os.path.exists(index_path):
        return False
    idx = json.loads(open(index_path, encoding="utf-8").read())
    dates = idx.get("dates", [])
    if date_str not in dates:
        return False
    pos = dates.index(date_str)

    changed = False
    for sid, s in sectors.items():
        if sid in idx["sectors"]:
            entry = idx["sectors"][sid]
            if pos < len(entry["totals"]):
                entry["totals"][pos] = s["total"]
                entry["levels"][pos] = s["level"]
                changed = True

    # Update macro entry for this date
    for i, m in enumerate(idx.get("macro", [])):
        if m.get("date") == date_str:
            idx["macro"][i]["warning"] = False
            idx["macro"][i]["signal"] = True
            changed = True
            break

    if changed:
        out = json.dumps(idx, ensure_ascii=False, indent=2, allow_nan=False)
        open(index_path, "w", encoding="utf-8").write(out)
    return changed


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    target_files = sorted(glob.glob("output/signals_20260409_*.json"))
    target_files.append("output/history/2026-04-09.json")

    patched_sectors = None
    for fpath in target_files:
        if not os.path.exists(fpath):
            continue
        data = json.loads(open(fpath, encoding="utf-8").read())
        data = sanitize_nans(data)
        changes = patch_snapshot(data)
        if changes:
            out = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
            open(fpath, "w", encoding="utf-8").write(out)
            b = changes["before"]
            a = changes["after"]
            print(f"  {os.path.basename(fpath)}: {b} -> {a}")
            patched_sectors = data.get("sectors", {})
        else:
            # Still rewrite to fix NaN → null even if macro didn't change
            out = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
            open(fpath, "w", encoding="utf-8").write(out)
            print(f"  {os.path.basename(fpath)}: NaN cleaned (macro unchanged)")

    # Patch history_index.json
    if patched_sectors:
        ok = patch_history_index(
            "output/history/history_index.json", "2026-04-09", patched_sectors
        )
        if ok:
            print("  history_index.json: updated 2026-04-09 entry")

    print("\nDone!")


if __name__ == "__main__":
    main()
