"""
scripts/backtest_academic_signals.py
學術信號月度命中率回測

說明：
  使用 output/history/ 下的日快照 JSON，
  逐月統計各板塊「學術 bonus 信號」的觸發情況，
  並對比下一個月快照的板塊總分變化，計算信號「命中率」。

命中定義：
  板塊在信號觸發月的下一個有效快照中，total 分數 ≥ 上月分數（動能延續）

輸出：
  output/backtest/academic_signals_backtest.json
  output/backtest/academic_signals_backtest_summary.txt

執行：
  python scripts/backtest_academic_signals.py
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# ── 路徑設定 ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = ROOT / "output" / "history"
OUTPUT_DIR  = ROOT / "output" / "backtest"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 學術 bonus 信號清單 ─────────────────────────────────────────────────
ACADEMIC_SIGNALS = [
    "外資牛市共振",
    "外資熊市防守",
    "借券回補↑",
    "空頭加碼⚠",
    "季節動能✓",
    "節後反轉⭐",
    "營收加速↑✓",
]


def load_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ 讀取失敗 {path.name}: {e}")
        return None


def get_sector_totals(snapshot: Dict[str, Any]) -> Dict[str, float]:
    """從快照取各板塊 total 分數：{sector_id: total}。"""
    sectors = snapshot.get("sectors", {})
    return {sid: float(v.get("total", 0)) for sid, v in sectors.items()}


def get_triggered_per_stock(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    """從快照取 {sector_id: {stock_id: triggered[]}}。"""
    result: Dict[str, Dict[str, List[str]]] = {}
    sectors = snapshot.get("sectors", {})
    for sid, sv in sectors.items():
        result[sid] = {}
        for stock in sv.get("stocks", []):
            result[sid][stock.get("id", "")] = stock.get("triggered", [])
    return result


def sector_has_signal(
    triggered_map: Dict[str, Dict[str, List[str]]],
    sector_id: str,
    signal: str,
) -> bool:
    """檢查板塊內是否有任何個股觸發了指定學術信號。"""
    stocks = triggered_map.get(sector_id, {})
    return any(signal in triggers for triggers in stocks.values())


def run_backtest() -> None:
    # ── 載入所有歷史快照（依日期排序）────────────────────────────────
    snapshot_paths = sorted(HISTORY_DIR.glob("*.json"))
    # 排除 history_index.json
    snapshot_paths = [p for p in snapshot_paths if p.name != "history_index.json"]

    if len(snapshot_paths) < 2:
        print("⚠ 歷史快照不足 2 個，無法回測（需至少 2 個日快照）")
        print(f"  目前快照數量：{len(snapshot_paths)}")
        sys.exit(0)

    print(f"✅ 找到 {len(snapshot_paths)} 個歷史快照，開始回測...")

    snapshots: List[Tuple[str, Dict[str, Any]]] = []
    for p in snapshot_paths:
        snap = load_snapshot(p)
        if snap:
            date_str = snap.get("date", p.stem)
            snapshots.append((date_str, snap))

    if len(snapshots) < 2:
        print("⚠ 有效快照不足 2 個，無法回測")
        sys.exit(0)

    # ── 統計各信號命中率 ────────────────────────────────────────────────
    # signal_stats[signal_name][sector_id] = {"hit": int, "miss": int}
    signal_stats: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"hit": 0, "miss": 0, "trigger_dates": []})
    )

    for i in range(len(snapshots) - 1):
        date_t, snap_t  = snapshots[i]
        date_t1, snap_t1 = snapshots[i + 1]

        totals_t  = get_sector_totals(snap_t)
        totals_t1 = get_sector_totals(snap_t1)
        triggered_t = get_triggered_per_stock(snap_t)

        all_sectors = set(totals_t.keys()) | set(totals_t1.keys())

        for signal in ACADEMIC_SIGNALS:
            for sid in all_sectors:
                if not sector_has_signal(triggered_t, sid, signal):
                    continue
                # 信號在 T 期觸發，看 T+1 的 total
                t_total  = totals_t.get(sid, 0.0)
                t1_total = totals_t1.get(sid, 0.0)
                is_hit = t1_total >= t_total   # 命中：維持或改善
                stats = signal_stats[signal][sid]
                if is_hit:
                    stats["hit"] += 1
                else:
                    stats["miss"] += 1
                stats["trigger_dates"].append(date_t)  # type: ignore[attr-defined]

    # ── 彙整結果 ────────────────────────────────────────────────────────
    backtest_result: Dict[str, Any] = {}
    summary_lines: List[str] = [
        "=" * 60,
        "台股板塊偵測系統 — 學術信號月度命中率回測報告",
        f"歷史快照數：{len(snapshots)}",
        f"分析期間：{snapshots[0][0]} → {snapshots[-1][0]}",
        "=" * 60,
        "",
    ]

    all_signal_hit_rates: List[float] = []

    for signal in ACADEMIC_SIGNALS:
        sector_data = signal_stats[signal]
        if not sector_data:
            backtest_result[signal] = {"message": "無觸發記錄"}
            summary_lines.append(f"【{signal}】— 無觸發記錄（history 快照尚無此信號）")
            summary_lines.append("")
            continue

        total_hit  = sum(v["hit"]  for v in sector_data.values())
        total_miss = sum(v["miss"] for v in sector_data.values())
        total_events = total_hit + total_miss
        hit_rate = total_hit / total_events if total_events > 0 else 0.0
        all_signal_hit_rates.append(hit_rate)

        backtest_result[signal] = {
            "total_events":  total_events,
            "hit":           total_hit,
            "miss":          total_miss,
            "hit_rate":      round(hit_rate, 4),
            "hit_rate_pct":  f"{hit_rate * 100:.1f}%",
            "by_sector": {
                sid: {
                    "hit":       v["hit"],
                    "miss":      v["miss"],
                    "hit_rate":  round(v["hit"] / (v["hit"] + v["miss"]), 4) if (v["hit"] + v["miss"]) > 0 else 0,
                    "trigger_dates": v["trigger_dates"],
                }
                for sid, v in sector_data.items()
            },
        }

        summary_lines.append(f"【{signal}】")
        summary_lines.append(f"  事件數：{total_events}  命中：{total_hit}  失敗：{total_miss}")
        summary_lines.append(f"  整體命中率：{hit_rate * 100:.1f}%")

        # 最高命中板塊
        best_sectors = sorted(
            [(sid, v["hit"] / max(v["hit"] + v["miss"], 1)) for sid, v in sector_data.items()],
            key=lambda x: -x[1],
        )[:3]
        if best_sectors:
            top_str = " | ".join(f"{sid}: {r*100:.0f}%" for sid, r in best_sectors)
            summary_lines.append(f"  最佳板塊：{top_str}")
        summary_lines.append("")

    # ── 整體統計 ─────────────────────────────────────────────────────
    if all_signal_hit_rates:
        avg_hit = sum(all_signal_hit_rates) / len(all_signal_hit_rates)
        summary_lines.append("-" * 60)
        summary_lines.append(f"所有學術信號平均命中率：{avg_hit * 100:.1f}%")
        summary_lines.append(f"（基準：隨機 50%；>55% 視為有統計意義）")

    summary_lines.append("")
    summary_lines.append("注意：命中率以「下一快照分數 ≥ 當期」為定義，")
    summary_lines.append("      目前快照量有限，結果僅供參考，待累積 30+ 快照後再做正式評估。")

    backtest_result["_meta"] = {
        "snapshot_count": len(snapshots),
        "period_start":   snapshots[0][0],
        "period_end":     snapshots[-1][0],
        "signals_tested": ACADEMIC_SIGNALS,
        "hit_definition": "next_snapshot_total >= current_total",
    }

    # ── 輸出 JSON ────────────────────────────────────────────────────
    out_json = OUTPUT_DIR / "academic_signals_backtest.json"
    out_json.write_text(json.dumps(backtest_result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 回測結果已儲存：{out_json}")

    # ── 輸出文字摘要 ─────────────────────────────────────────────────
    out_txt = OUTPUT_DIR / "academic_signals_backtest_summary.txt"
    out_txt.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"📝 文字摘要已儲存：{out_txt}")

    print("\n" + "\n".join(summary_lines))


if __name__ == "__main__":
    run_backtest()
