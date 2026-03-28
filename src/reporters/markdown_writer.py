"""
markdown_writer.py — Markdown 報告輸出

支援兩種模式：
  標準模式：完整格式，本地閱讀最佳
  Notion 模式（--notion）：表格使用 df.to_markdown()，空行分隔，貼入 Notion 不跑版

報告結構（兩層輸出）：
  1. 宏觀環境摘要（燈7）
  2. 全板塊速覽大表（所有板塊，7燈 + 總分 + 等級，不展開詳細）
  3. 精華摘要：Top-N 板塊完整分析（score ≥ TOP_SCORE_THRESHOLD 或趨勢上升）
     - 強烈關注板塊個股清單
     - 各燈詳細分析（只展開精華板塊）
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# 只展開詳細分析的精華板塊門檻（總分 ≥ 此值 或 4週趨勢上升末值 ≥ 此值）
TOP_SCORE_THRESHOLD = 2

_SIGNAL_EMOJI = {True: "🟢", False: "⚫"}
_LEVEL_EMOJI = {"強烈關注": "🔥", "觀察中": "👀", "忽略": "💤"}


def _emoji(v) -> str:
    """支援 float 三態：1.0=🟢, 0.5=🟡, 0.0=⚫"""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        fv = 0.0
    if fv >= 1.0:
        return "🟢"
    if fv >= 0.5:
        return "🟡"
    return "⚫"


def _level_badge(level: str) -> str:
    return f"{_LEVEL_EMOJI.get(level, '')} {level}"


def _is_trend_rising(trend_str: str) -> bool:
    """判斷 4週趨勢是否上升（末値 > 首値），支援整數與小數展示。"""
    parts = []
    for p in trend_str.replace("→", " ").split():
        try:
            parts.append(float(p.strip()))
        except (ValueError, AttributeError):
            pass
    if len(parts) >= 2:
        return parts[-1] > parts[0]
    return False


def _delta_from_trend(trend_str: str) -> str:
    """從趨勢字串計算最新一期 vs 上一期差异，回傳如 '▲1' / '▼1' / ''。"""
    parts = []
    for p in trend_str.replace("→", " ").split():
        try:
            parts.append(float(p.strip()))
        except (ValueError, AttributeError):
            pass
    if len(parts) < 2:
        return "新" if len(parts) == 1 else ""
    delta = parts[-1] - parts[-2]
    if delta == 0:
        return ""
    abs_d = abs(delta)
    fmt = str(int(abs_d)) if abs_d == int(abs_d) else f"{abs_d:.1f}"
    return f"▲{fmt}" if delta > 0 else f"▼{fmt}"


def _select_top_sectors(sector_results: Dict, history, threshold: int) -> Set[str]:
    """選出需要展開詳細分析的精華板塊 ID。"""
    from src.analyzers.multi_signal import build_trend_string
    top = set()
    for sid, v in sector_results.items():
        if v["total"] >= threshold:
            top.add(sid)
        else:
            trend = build_trend_string(sid, history)
            if _is_trend_rising(trend):
                top.add(sid)
    return top


def write_report(
    result: Dict[str, Any],
    config,
    notion_mode: bool = False,
    output_path: Path = None,
) -> Path:
    """
    輸出 Markdown 報告，回傳實際寫入路徑。
    """
    from src.analyzers.multi_signal import load_history, build_trend_string

    ts = datetime.now()
    history = load_history(config, n=4)

    lines: List[str] = []

    # ── 標題 ────────────────────────────────────────────────────────────
    lines += [
        "# FinLab 台股板塊偵測報告",
        "",
        f"> 產生時間：{ts.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # ── 燈7 宏觀摘要 ────────────────────────────────────────────────────
    macro = result.get("macro_signal", {})
    macro_ok = macro.get("signal", False)
    macro_warning = result.get("macro_warning", False)
    pos = macro.get("positive_count", "-")
    tot = macro.get("total_available", "-")

    lines += [
        "## 🌐 燈7 宏觀環境",
        "",
        f"**狀態：{'✅ 正面' if macro_ok else '⚠️ 謹慎（啟動全局警告）'} — {pos}/{tot} 項指標正面**",
        "",
    ]
    for val in macro.get("details_dict", {}).values():
        lines.append(f"- {val}")
    lines.append("")
    if macro_warning:
        lines += [
            "> ⚠️ **宏觀燈熄滅**：所有板塊訊號僅供參考，建議降低倉位預期、縮短持有週期。",
            "",
        ]

    # ── 全板塊速覽大表 ──────────────────────────────────────────────────
    sector_results = result.get("sector_results", {})
    top_sids = _select_top_sectors(sector_results, history, TOP_SCORE_THRESHOLD)
    total_count = len(sector_results)
    top_count   = len(top_sids)

    lines += [
        f"## 📊 全板塊速覽（{total_count} 個板塊）",
        "",
        f"> 🔍 共 {total_count} 個板塊，以下 **{top_count} 個**達精華門檻（總分≥{TOP_SCORE_THRESHOLD} 或趨勢上升），展開完整分析。",
        "",
        "| 板塊 | 4週趨勢 | Δ | 燈1 | 燈2 | 燈3 | 燈4 | 燈5 | 燈6 | 燈7 | 總分 | 等級 |",
        "|------|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:----:|------|",
    ]

    for sid, v in sector_results.items():
        name   = v["name"]
        sigs   = v["signals"]
        total  = v["total"]
        level  = v["level"]
        trend  = build_trend_string(sid, history)
        delta  = _delta_from_trend(trend)
        warn   = " ⚠️" if v.get("macro_warning") and sigs[6] < 1.0 else ""
        star   = " ★" if sid in top_sids else ""  # 標示精華板塊
        total_display = str(int(total)) if total == int(total) else f"{total:.1f}"
        row = (
            f"| {name}{star} | {trend} | {delta} | "
            + " | ".join(_emoji(s) for s in sigs)
            + f" | **{total_display}** | {_level_badge(level)}{warn} |"
        )
        lines.append(row)

    lines += [
        "",
        "> ★ 標記板塊將展開完整各燈分析，🟡 = 0.5 分半亮",
        "",
    ]

    # ── 本週上升最快 Top 5 板塊 ──────────────────────────────────
    rising = []
    for sid, v in sector_results.items():
        trend = build_trend_string(sid, history)
        delta_str = _delta_from_trend(trend)
        if delta_str.startswith("▲"):
            try:
                delta_val = float(delta_str[1:])
            except ValueError:
                delta_val = 0.0
            rising.append((sid, v["name"], v["total"], delta_val, trend))
    rising.sort(key=lambda x: (-x[3], -x[2]))
    top5 = rising[:5]

    if top5:
        total_top5 = len(top5)
        lines += [
            f"## 🚀 本週上升最快板塊 Top {total_top5}",
            "",
            "| # | 板塊 | 趨勢 | Δ | 總分 |",
            "|---|------|------|:---:|:----:|",
        ]
        for i, (sid, name, total, dv, trend) in enumerate(top5, 1):
            total_display = str(int(total)) if total == int(total) else f"{total:.1f}"
            dv_display = str(int(dv)) if dv == int(dv) else f"{dv:.1f}"
            lines.append(f"| {i} | {name} | {trend} | ▲{dv_display} | **{total_display}** |")
        lines.append("")

    # ── 精華板塊個股清單 ────────────────────────────────────────────────
    strong = result["summary"]["strong"]
    if strong:
        lines += ["## 🔥 強烈關注板塊 — 個股清單", ""]
        for sid in strong:
            if sid not in sector_results:
                continue
            v = sector_results[sid]
            lines += [f"### {v['name']}", ""]
            for sig_name, sig_data in v.get("detail", {}).items():
                lit = sig_data.get("lit_stocks", [])
                if lit:
                    lines.append(f"**{sig_name}** 亮燈個股：{', '.join(lit)}")
            lines.append("")

    # ── 個股三面合一評分排名 ─────────────────────────────────────────────
    _write_stock_rankings(lines, sector_results, result, config)

    # ── 精華板塊各燈詳細分析 ────────────────────────────────────────────
    if top_sids:
        lines += [
            "---",
            "",
            f"## 📋 精華板塊詳細分析（{top_count} 個）",
            "",
        ]

        sig_keys = [
            ("燈1_月營收拐點", "燈1 月營收拐點"),
            ("燈2_法人共振",   "燈2 法人共振"),
            ("燈3_庫存循環",   "燈3 庫存循環"),
            ("燈4_技術突破",   "燈4 技術突破"),
            ("燈5_相對強度",   "燈5 相對強度"),
            ("燈6_籌碼集中",   "燈6 籌碼集中"),
        ]

        # 只傳入精華板塊的子集
        top_results = {sid: v for sid, v in sector_results.items() if sid in top_sids}

        for sig_field, sig_title in sig_keys:
            lines += [f"### {sig_title}", ""]
            if notion_mode:
                lines += _detail_table_notion(top_results, sig_field)
            else:
                lines += _detail_table_standard(top_results, sig_field)
            lines.append("")

    # ── 頁腳 ────────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        f"*本報告由 FinLab 台股板塊偵測系統自動產生 · {ts.strftime('%Y-%m-%d %H:%M')}*",
    ]

    # ── 寫入檔案 ────────────────────────────────────────────────────────
    if output_path is None:
        suffix = "_notion" if notion_mode else ""
        output_path = config.OUTPUT_DIR / f"板塊偵測報告_{ts.strftime('%Y%m%d_%H%M')}{suffix}.md"

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"報告已儲存: {output_path}")
    return output_path


def _write_stock_rankings(
    lines: list,
    sector_results: Dict,
    result: Dict,
    config,
) -> None:
    """
    在報告中輸出「板塊個股評分排名」區塊。
    只顯示 STOCK_SCORE_TARGET_LEVELS（強烈關注/觀察中）且有 stock_rankings 的板塊。
    """
    min_display = getattr(config, "STOCK_MIN_DISPLAY", 3.0)
    target_levels = getattr(config, "STOCK_SCORE_TARGET_LEVELS", ("強烈關注", "觀察中"))

    # 找出有評分數據的板塊
    ranked_sectors = [
        (sid, v)
        for sid, v in sector_results.items()
        if v.get("level") in target_levels and v.get("stock_rankings")
    ]
    if not ranked_sectors:
        return

    # 取任意一個有評分的 fundamental_date（顯示數據截止期）
    fund_date = "N/A"
    for _, v in ranked_sectors:
        for stock_data in v["stock_rankings"].values():
            fd = stock_data.get("fundamental_date", "N/A")
            if fd != "N/A":
                fund_date = fd
                break
        if fund_date != "N/A":
            break

    lines += [
        "---",
        "",
        "## 📋 板塊個股評分排名",
        "",
        f"> 基本面數據截至 **{fund_date}**（季頻，ffill 補齊）｜顯示門檻：{min_display} 分",
        "",
    ]

    for sid, v in ranked_sectors:
        rankings = v["stock_rankings"]
        sector_total = v["total"]
        lines += [
            f"### {v['name']}（板塊總分 {sector_total}）",
            "",
            "| 股票 | 評分 | 等級 | 觸發燈號 | 基本 | 技術 | 籌碼 | 加分 |",
            "|------|:----:|------|---------|:----:|:----:|:----:|:----:|",
        ]
        for stock_id, sd in rankings.items():
            score   = sd["score"]
            grade   = sd["grade"]
            trig    = " ".join(sd.get("triggered", []))
            bd      = sd.get("breakdown", {})
            f_pts   = bd.get("fundamental", 0.0)
            t_pts   = bd.get("technical",   0.0)
            c_pts   = bd.get("chipset",     0.0)
            b_pts   = bd.get("bonus",       0.0)
            lines.append(
                f"| {stock_id} | {score} | {grade} | {trig} "
                f"| {f_pts} | {t_pts} | {c_pts} | {b_pts} |"
            )
        lines.append("")


def _detail_table_standard(sector_results: Dict, sig_field: str) -> List[str]:
    rows = ["| 板塊 | 亮燈 | 比例 | 說明 |", "|------|:----:|:----:|------|"]
    for sid, v in sector_results.items():
        d = v.get("detail", {}).get(sig_field, {})
        signal = d.get("signal", False)
        pct    = d.get("pct_lit", 0)
        detail = d.get("details", "-") or "-"
        rows.append(f"| {v['name']} | {_emoji(signal)} | {pct:.0f}% | {detail} |")
    return rows


def _detail_table_notion(sector_results: Dict, sig_field: str) -> List[str]:
    rows = _detail_table_standard(sector_results, sig_field)
    return [""] + rows + [""]
