#!/usr/bin/env python
"""
stock_entry_check.py — 個股下週一進場分析工具

功能：
  重用現有七燈分析器，對指定股票執行完整個股層級信號分析，
  並輸出含條件清單、燈號、進場建議與技術參數的 Markdown 報告。

用法：
  python scripts/stock_entry_check.py 2330,2454,3034
  python scripts/stock_entry_check.py --stocks 2330,2454
  python scripts/stock_entry_check.py           （互動式輸入）

輸出：
  local_analysis/股票進場分析_YYYYMMDD_HHMM.md

注意：
  - 若股票不在 custom_sectors.csv 任何板塊內，將以獨立個股分析，
    並在報告中標示「不在趨勢板塊」的說明。
  - 燈4（技術突破）採個股層級計算（現有分析器為板塊層級），
    直接計算個股 MA60 距離與量比。
  - 不修改任何現有模組，純脚本新增。
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 路徑設定：讓 src.* 可被 import ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.ssl_fix  # noqa: F401 — 必須在 yfinance / finlab 之前 import

logging.basicConfig(
    level=logging.WARNING,          # 靜音依賴函式庫的 INFO 日誌
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── 輸出目錄（不上傳 GitHub，已加入 .gitignore）─────────────────────────────
OUTPUT_DIR = ROOT / "local_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# 一、板塊地圖建構
# ════════════════════════════════════════════════════════════════════════════

def _build_targeted_map(
    target_stocks: List[str],
    base_map,
) -> Tuple[Any, Dict[str, Tuple[str, str, bool]]]:
    """
    基於目標股票清單，建立含最小範圍板塊的 SectorMap 副本。
    不在任何板塊的股票會被加入臨時 standalone 板塊（單股自分析）。

    Returns
    -------
    targeted_map      : 僅含相關板塊的 SectorMap 實例
    stock_sector_info : {stock_id: (sector_id, sector_name, is_standalone)}
    """
    from src.sector_map import SectorMap

    # 反向索引：stock_id → [sector_id, ...]（按 CSV 順序，custom 優先）
    stock_to_sectors: Dict[str, List[str]] = defaultdict(list)
    for s_id in base_map.all_sector_ids():
        for stock_id in base_map.get_stocks(s_id):
            stock_to_sectors[stock_id].append(s_id)

    targeted_sectors: Dict[str, Any] = {}
    stock_sector_info: Dict[str, Tuple[str, str, bool]] = {}

    for stock_id in target_stocks:
        found = stock_to_sectors.get(stock_id, [])
        if found:
            # 使用第一個（最高優先）板塊
            primary = found[0]
            if primary not in targeted_sectors:
                targeted_sectors[primary] = dict(base_map._sectors[primary])
            stock_sector_info[stock_id] = (
                primary,
                base_map.get_sector_name(primary),
                False,  # 非 standalone
            )
        else:
            # 建立臨時獨立板塊
            s_id = f"standalone_{stock_id}"
            targeted_sectors[s_id] = {
                "name":   f"獨立個股 {stock_id}",
                "type":   "standalone",
                "parent": "",
                "stocks": [stock_id],
                "source": "standalone",
            }
            stock_sector_info[stock_id] = (
                s_id,
                f"獨立個股 {stock_id}",
                True,
            )

    # 建立新的 SectorMap 並注入板塊
    targeted_map = SectorMap()
    targeted_map._sectors = targeted_sectors
    targeted_map._loaded = True
    return targeted_map, stock_sector_info


# ════════════════════════════════════════════════════════════════════════════
# 二、七燈分析執行
# ════════════════════════════════════════════════════════════════════════════

def _run_all_analyzers(fetcher, targeted_map, config) -> Dict[str, Any]:
    """
    對目標 SectorMap 執行 7 燈分析。
    回傳 raw_results 字典（key 名稱與 stock_scorer 期望的一致）。
    """
    from src.analyzers.revenue import analyze as analyze_revenue
    from src.analyzers.institutional import analyze as analyze_institutional
    from src.analyzers.inventory import analyze as analyze_inventory
    from src.analyzers.technical import analyze as analyze_technical
    from src.analyzers.rs_ratio import analyze as analyze_rs
    from src.analyzers.chipset import analyze as analyze_chipset
    from src.analyzers.macro import analyze as analyze_macro

    steps = [
        ("🌐 燈7 宏觀環境...",     "macro",        lambda: analyze_macro(fetcher, config)),
        ("💰 燈1 月營收拐點...",   "燈1 月營收拐點", lambda: analyze_revenue(fetcher, targeted_map, config)),
        ("🏦 燈2 法人籌碼共振...", "燈2 法人共振",   lambda: analyze_institutional(fetcher, targeted_map, config)),
        ("📦 燈3 庫存循環偵測...", "燈3 庫存循環",   lambda: analyze_inventory(fetcher, targeted_map, config)),
        ("📈 燈4 技術突破...",     "燈4 技術突破",   lambda: analyze_technical(fetcher, targeted_map, config)),
        ("🔀 燈5 相對強度 RRG...", "燈5 相對強度",   lambda: analyze_rs(fetcher, targeted_map, config)),
        ("💎 燈6 籌碼集中...",     "燈6 籌碼集中",   lambda: analyze_chipset(fetcher, targeted_map, config)),
    ]

    results: Dict[str, Any] = {}
    for label, key, fn in steps:
        print(f"  {label}")
        try:
            results[key] = fn()
        except Exception as e:
            logger.error("%s 執行失敗: %s", key, e)
            results[key] = {}

    macro_result = results.pop("macro", {})
    return {
        "macro": macro_result,
        "raw": {
            **{k: v for k, v in results.items()},
            "學術_季節動能": {},
            "學術_營收加速": {},
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# 三、燈4 個股層級技術計算
# ════════════════════════════════════════════════════════════════════════════

def _compute_lamp4_stock(stock_id: str, fetcher, config) -> Dict[str, Any]:
    """
    燈4 個股層級：計算個股 MA60 距離與量比。
    現有 technical.py 只輸出板塊均線；此函式補充逐股計算。
    """
    try:
        price_df = fetcher.get("price:收盤價")
        vol_df   = fetcher.get("price:成交股數")

        if price_df is None or stock_id not in price_df.columns:
            return {"error": "無收盤價資料"}

        prices = price_df[stock_id].dropna().iloc[-180:]
        if len(prices) < config.TECHNICAL_MA_LONG:
            return {"error": f"歷史資料不足 {config.TECHNICAL_MA_LONG} 日（僅 {len(prices)} 日）"}

        current_price = float(prices.iloc[-1])
        ma60 = float(prices.rolling(config.TECHNICAL_MA_LONG).mean().iloc[-1])
        dist_pct = (current_price - ma60) / ma60 * 100
        above_ma60 = current_price > ma60

        vol_ratio: Optional[float] = None
        vol_surge = False
        if vol_df is not None and stock_id in vol_df.columns:
            vols = vol_df[stock_id].dropna().iloc[-60:]
            if len(vols) >= config.TECHNICAL_MA_SHORT:
                ma20_vol = float(vols.rolling(config.TECHNICAL_MA_SHORT).mean().iloc[-1])
                current_vol = float(vols.iloc[-1])
                if ma20_vol > 0:
                    vol_ratio = round(current_vol / ma20_vol, 2)
                    vol_surge = vol_ratio >= config.TECHNICAL_VOLUME_MULTIPLIER

        # tech_score: 2 = 帶量站 MA60, 1 = 無量站 MA60, 0 = MA60 下方
        tech_score = 2 if (above_ma60 and vol_surge) else (1 if above_ma60 else 0)

        return {
            "current_price": round(current_price, 2),
            "ma60":          round(ma60, 2),
            "dist_pct":      round(dist_pct, 2),
            "above_ma60":    above_ma60,
            "vol_ratio":     vol_ratio,
            "vol_surge":     vol_surge,
            "tech_score":    tech_score,
        }
    except Exception as e:
        logger.warning("燈4 個股計算失敗 %s: %s", stock_id, e)
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════════════
# 四、個股信號彙整與進場建議
# ════════════════════════════════════════════════════════════════════════════

def _extract_stock_signals(
    stock_id: str,
    sector_id: str,
    is_standalone: bool,
    analysis: Dict[str, Any],
    tech4: Dict[str, Any],
    fetcher,
    config,
) -> Dict[str, Any]:
    """
    從 7 燈原始結果提取某股票的個別信號，
    注入個股層級燈4計算結果後呼叫 stock_scorer 取得評分。
    """
    raw   = analysis["raw"]
    macro = analysis["macro"]

    # ── 各燈結果（板塊層級字典，再取個股）────────────────────────────────
    lamp1 = raw.get("燈1 月營收拐點", {}).get(sector_id, {})
    lamp2 = raw.get("燈2 法人共振",   {}).get(sector_id, {})
    lamp3 = raw.get("燈3 庫存循環",   {}).get(sector_id, {})
    lamp4 = raw.get("燈4 技術突破",   {}).get(sector_id, {})
    lamp5 = raw.get("燈5 相對強度",   {}).get(sector_id, {})
    lamp6 = raw.get("燈6 籌碼集中",   {}).get(sector_id, {})

    # ── 燈1：月營收 YoY 拐點
    l1_lit = stock_id in lamp1.get("lit_stocks", [])
    l1_mom = stock_id in lamp1.get("mom_accel_stocks", [])

    # ── 燈2：法人籌碼共振
    l2_resonate = stock_id in lamp2.get("lit_stocks", [])
    l2_foreign  = stock_id in lamp2.get("foreign_only", [])
    l2_trust    = stock_id in lamp2.get("trust_only", [])
    l2_market_state    = lamp2.get("market_state", "unknown")
    l2_resonance_label = lamp2.get("resonance_label", "")

    # ── 燈3：庫存循環
    l3_lit = stock_id in lamp3.get("lit_stocks", [])

    # ── 燈4：技術突破（個股層級，覆蓋板塊層級）
    l4_above = tech4.get("above_ma60", False)
    l4_surge = tech4.get("vol_surge", False)
    l4_dist  = tech4.get("dist_pct")
    l4_score = tech4.get("tech_score", 0)

    # ── 燈5：相對強度 RRG
    stock_rs  = lamp5.get("stock_rs", {}).get(stock_id, {})
    l5_ratio  = stock_rs.get("rs_ratio")
    l5_mom    = stock_rs.get("rs_momentum")
    l5_rank   = stock_rs.get("rank_pct")
    l5_quad   = lamp5.get("quadrant", "")
    l5_lit    = l5_ratio is not None and l5_ratio >= 1.0

    # ── 燈6：籌碼集中
    l6_lit   = stock_id in lamp6.get("lit_stocks", [])
    l6_cover = stock_id in lamp6.get("short_cover", [])
    l6_add   = stock_id in lamp6.get("short_add", [])

    # ── 燈7：全局宏觀（非板塊個別）
    l7_signal = macro.get("signal", False)
    l7_pos    = macro.get("positive_count", 0)
    l7_total  = macro.get("total_available", 0)

    # ── 亮燈計數（燈1~6，各 1 票，半亮燈2外資/投信獨買算 0.5）
    lamp_bools = {
        "l1": bool(l1_lit or l1_mom),
        "l2": bool(l2_resonate or l2_foreign or l2_trust),
        "l3": bool(l3_lit),
        "l4": bool(l4_above),           # 個股站上 MA60
        "l5": bool(l5_lit),
        "l6": bool(l6_lit or l6_cover),
    }
    # 加權計數：完整共振 = 1，外資/投信獨買 = 0.5
    lit_count_weighted = (
        (1.0 if (l1_lit or l1_mom)     else 0)
        + (1.0 if l2_resonate          else (0.5 if (l2_foreign or l2_trust) else 0))
        + (1.0 if l3_lit               else 0)
        + (1.0 if l4_above             else 0)
        + (1.0 if l5_lit               else 0)
        + (1.0 if l6_lit               else (0.5 if l6_cover else 0))
    )
    lit_count_whole = sum(1 for v in lamp_bools.values() if v)

    # ── 進場建議
    recommendation, rec_icon, rec_reason = _make_recommendation(
        lit_count_whole, lit_count_weighted,
        l7_signal, l7_pos, l7_total,
        l4_above, l4_dist, l4_surge,
    )

    # ── 呼叫 stock_scorer（注入個股層級燈4）
    score_data = _call_scorer(
        stock_id, sector_id, raw,
        l4_score, l4_dist, l4_above, l4_surge,
        fetcher, config,
    )

    return {
        "stock_id":      stock_id,
        "sector_id":     sector_id,
        "is_standalone": is_standalone,
        "lamp_bools":    lamp_bools,
        "lit_count":     lit_count_whole,
        "lit_count_w":   round(lit_count_weighted, 1),
        # 燈1
        "l1_lit": l1_lit, "l1_mom": l1_mom,
        # 燈2
        "l2_resonate": l2_resonate, "l2_foreign": l2_foreign, "l2_trust": l2_trust,
        "l2_market_state": l2_market_state, "l2_resonance_label": l2_resonance_label,
        # 燈3
        "l3_lit": l3_lit,
        # 燈4
        "l4_above": l4_above, "l4_surge": l4_surge,
        "l4_dist": l4_dist, "l4_score": l4_score,
        "current_price": tech4.get("current_price"),
        "ma60":          tech4.get("ma60"),
        "vol_ratio":     tech4.get("vol_ratio"),
        "tech4_error":   tech4.get("error"),
        # 燈5
        "l5_lit": l5_lit, "l5_ratio": l5_ratio, "l5_mom": l5_mom,
        "l5_rank": l5_rank, "l5_quad": l5_quad,
        # 燈6
        "l6_lit": l6_lit, "l6_cover": l6_cover, "l6_add": l6_add,
        # 燈7
        "l7_signal": l7_signal, "l7_pos": l7_pos, "l7_total": l7_total,
        # 建議
        "recommendation": recommendation, "rec_icon": rec_icon, "rec_reason": rec_reason,
        # 評分
        "score_data": score_data,
    }


def _call_scorer(
    stock_id: str,
    sector_id: str,
    raw: Dict[str, Any],
    l4_score: int,
    l4_dist: Optional[float],
    l4_above: bool,
    l4_surge: bool,
    fetcher,
    config,
) -> Dict[str, Any]:
    """
    呼叫 stock_scorer.score_stocks()，
    注入個股層級燈4資料（覆蓋板塊均線數據）。
    """
    try:
        from src.analyzers.stock_scorer import score_stocks

        # 建立 raw_results 副本，注入個股燈4
        raw_copy = dict(raw)
        lamp4_copy = dict(raw_copy.get("燈4 技術突破", {}))
        sector_lamp4 = dict(lamp4_copy.get(sector_id, {}))
        stock_signals = dict(sector_lamp4.get("stock_signals", {}))
        stock_signals[stock_id] = {
            "tech_score":    l4_score,
            "dist_60ma_pct": l4_dist,
            "above_60ma":    l4_above,
            "vol_surge":     l4_surge,
        }
        sector_lamp4["stock_signals"] = stock_signals
        lamp4_copy[sector_id] = sector_lamp4
        raw_copy["燈4 技術突破"] = lamp4_copy

        scored = score_stocks(
            sector_id=sector_id,
            stock_ids=[stock_id],
            raw_results=raw_copy,
            fetcher=fetcher,
            config=config,
            change_pct_map=None,
        )
        return scored.get(stock_id, {})
    except Exception as e:
        logger.warning("stock_scorer 失敗 %s: %s", stock_id, e)
        return {}


def _make_recommendation(
    lit_count: int,
    lit_count_weighted: float,
    l7_signal: bool,
    l7_pos: int,
    l7_total: int,
    l4_above: bool,
    l4_dist: Optional[float],
    l4_surge: bool,
) -> Tuple[str, str, str]:
    """決定進場建議，回傳 (建議文字, icon, 理由)。"""
    near_ma60 = l4_dist is not None and -3.0 <= l4_dist < 0.0  # 在 MA60 附近尚未突破

    if not l7_signal:
        # 宏觀環境偏弱
        if lit_count_weighted >= 4:
            return (
                "小量試倉（宏觀警示）", "⚠️",
                f"個股基本面/技術面/籌碼條件佳（加權 {lit_count_weighted}/6 燈），"
                f"但宏觀環境不理想（{l7_pos}/{l7_total} 項達標）。"
                "建議小量試倉並嚴設停損，等宏觀好轉後再加碼。",
            )
        elif lit_count_weighted >= 2:
            return (
                "觀察等待（宏觀偏弱）", "⏳",
                f"宏觀環境偏弱（{l7_pos}/{l7_total} 項達標），個股信號尚不充分（{lit_count}/6 燈）。"
                "建議暫時觀望，等待宏觀轉好或信號強化後再評估。",
            )
        else:
            return (
                "不建議進場", "❌",
                f"宏觀環境偏弱且個股信號不足（{lit_count}/6 燈，加權 {lit_count_weighted}）。"
                "整體市場偏防禦，建議等待更優質進場時機。",
            )

    # 宏觀環境 OK
    if lit_count >= 4 and l4_above:
        qty_note = "帶量突破" if l4_surge else "無量突破，建議等放量確認"
        return (
            "可進場", "✅",
            f"宏觀環境良好（{l7_pos}/{l7_total} 項達標），"
            f"{lit_count}/6 燈點亮且站上 MA60（{qty_note}）。"
            "下週一可考慮分批建倉。",
        )
    if lit_count >= 4 and near_ma60:
        return (
            "待突破確認", "🔍",
            f"個股信號充足（{lit_count}/6 燈），宏觀 OK，"
            f"現價距 MA60 約 {l4_dist:+.1f}%（尚未站上）。"
            "等待收盤站穩 MA60 後再進場，可設條件單掛突破價。",
        )
    if lit_count >= 3 and l4_above:
        return (
            "可小量試倉", "🟡",
            f"宏觀 OK，個股站上 MA60，但亮燈數（{lit_count}/6）尚未達強烈確認門檻。"
            "可小量試倉，等更多燈號確認後加碼。",
        )
    if lit_count >= 2:
        return (
            "觀察等待", "⏳",
            f"宏觀環境 OK，但個股亮燈數不足（{lit_count}/6 燈）。"
            "建議繼續追蹤，等待更多亮燈後確認進場。",
        )
    return (
        "不建議進場", "❌",
        f"個股信號不足（{lit_count}/6 燈），即使宏觀環境 OK，條件仍太弱。",
    )


# ════════════════════════════════════════════════════════════════════════════
# 五、Markdown 報告產生
# ════════════════════════════════════════════════════════════════════════════

def _fmt(val: Optional[float], fmt: str = ".2f", suffix: str = "", na: str = "N/A") -> str:
    """安全格式化浮點數。"""
    if val is None:
        return na
    try:
        return f"{val:{fmt}}{suffix}"
    except (ValueError, TypeError):
        return na


def _icon(flag: bool) -> str:
    return "✅" if flag else "❌"


def _next_monday(dt: datetime) -> str:
    """取得下一個週一的日期字串。"""
    days_ahead = 7 - dt.weekday()   # Monday=0; days_ahead never 0 since 7-0=7
    return (dt.date() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _generate_markdown(
    target_stocks: List[str],
    stock_signals: Dict[str, Any],
    macro_result: Dict[str, Any],
    stock_sector_info: Dict[str, Tuple[str, str, bool]],
    run_time: datetime,
) -> str:
    lines: List[str] = []
    now_str    = run_time.strftime("%Y-%m-%d %H:%M")
    next_mon   = _next_monday(run_time)

    # ─── 標頭 ───────────────────────────────────────────────────────────────
    lines += [
        "# 📊 個股進場分析報告",
        "",
        f"**分析時間**：{now_str}　　**評估目標**：下週一 `{next_mon}` 進場可行性",
        "",
        f"**分析股票**：{', '.join(f'`{s}`' for s in target_stocks)}",
        "",
        "---",
        "",
    ]

    # ─── 宏觀環境橫幅（全局）────────────────────────────────────────────────
    l7_signal  = macro_result.get("signal", False)
    l7_pos     = macro_result.get("positive_count", 0)
    l7_total   = macro_result.get("total_available", 0)
    # macro.py 的子指標明細放在 "details_dict"（dict），"details" 為摘要字串
    l7_details = macro_result.get("details_dict") or macro_result.get("details", {})

    macro_icon   = "✅" if l7_signal else "🔴"
    macro_status = "宏觀環境正常" if l7_signal else "宏觀環境警示"

    lines += [
        f"## {macro_icon} 燈7 宏觀環境（全局指標）",
        "",
        f"**狀態**：{macro_status} — 達標 {l7_pos}/{l7_total} 項指標",
        "",
        "| 子指標 | 狀態說明 |",
        "|--------|----------|",
        f"| 美10年債利率 (DGS10) | {l7_details.get('bond', '未取得')} |",
        f"| 工業生產指數 (INDPRO) | {l7_details.get('pmi', '未取得')} |",
        f"| 費半 ETF (SOXX) | {l7_details.get('sox', '未取得')} |",
        f"| 美元/台幣 (USD/TWD) | {l7_details.get('twd', '未取得')} |",
        "",
    ]

    if not l7_signal:
        lines += [
            "> 🔴 **整體宏觀警示**：目前宏觀環境偏弱，以下各股仍提供分析，",
            "> 但在宏觀好轉前建議降低部位規模或以更嚴格的止損操作。",
            "",
        ]

    lines += ["---", ""]

    # ─── 逐股分析 ───────────────────────────────────────────────────────────
    for stock_id in target_stocks:
        sig = stock_signals.get(stock_id)
        if not sig:
            lines += [f"## ❓ {stock_id}", "", "> 無法取得此股票的分析數據。", "", "---", ""]
            continue

        sector_id, sector_name, is_standalone = stock_sector_info[stock_id]
        sd          = sig.get("score_data", {})
        score       = sd.get("score")
        grade       = sd.get("grade", "")
        breakdown   = sd.get("breakdown", {})
        triggered   = sd.get("triggered", [])

        # 數值格式化
        price_s  = _fmt(sig.get("current_price"), ".2f")
        ma60_s   = _fmt(sig.get("ma60"),          ".2f")
        dist_s   = (_fmt(sig.get("l4_dist"), "+.1f", "%") if sig.get("l4_dist") is not None else "N/A")
        vol_s    = _fmt(sig.get("vol_ratio"), ".2f", "x")
        rs_s     = _fmt(sig.get("l5_ratio"),  ".3f")
        rank_s   = _fmt(sig.get("l5_rank"),   ".0f", "%")
        score_s  = _fmt(score, ".1f")

        lines += [f"## {stock_id}", ""]

        # 板塊說明 / standalone 警告
        if is_standalone:
            lines += [
                f"**歸屬板塊**：❌ **此股未在任何已定義的趨勢板塊中**",
                "",
                "> ⚠️ **注意：該股票目前不在整體市場的任何趨勢板塊中。**",
                "> `custom_sectors.csv` 未收錄此股，以下為**獨立個股評估**，不代表板塊動向共振確認。",
                "> - **燈5（相對強度）** 以整體市場（TAIEX 加權指數）為計算基準，而非板塊對照。",
                "> - **燈1-3、燈6** 若有信號，代表此股個別條件達標，但缺乏板塊共振支撐。",
                "> - 可將此股加入 `custom_sectors.csv` 的適合板塊以獲得更準確的板塊分析。",
                "",
            ]
        else:
            lines += [
                f"**歸屬板塊**：{sector_name}（`{sector_id}`）",
                "",
            ]

        # ── 燈號說明文字構建
        l1_detail = "YoY 拐點確認" + (" + MoM 加速" if sig["l1_mom"] else "") if (sig["l1_lit"] or sig["l1_mom"]) else "未觸發（連續3月 YoY 未達標）"

        if sig["l2_resonate"]:
            l2_detail = f"{sig['l2_resonance_label']}（外資+投信共振）"
        elif sig["l2_foreign"]:
            l2_detail = f"外資獨買（{sig['l2_market_state']} 模式，未達投信共振）"
        elif sig["l2_trust"]:
            l2_detail = "投信獨買（外資未同步，半燈信號）"
        else:
            l2_detail = "無明顯法人動向"

        if sig.get("tech4_error"):
            l4_detail = f"計算失敗：{sig['tech4_error']}"
        elif sig["l4_above"]:
            l4_detail = (f"現價 {price_s} > MA60 {ma60_s}（{dist_s}）"
                         + ("，帶量突破 ✅" if sig["l4_surge"] else f"，量比 {vol_s}（未放量）"))
        else:
            near = sig.get("l4_dist") is not None and sig["l4_dist"] >= -3.0
            l4_detail = (f"現價 {price_s} 低於 MA60 {ma60_s}（{dist_s}）"
                         + ("，距突破僅 -3% 以內 🔍" if near else ""))

        l5_detail = f"RS-Ratio={rs_s}，板塊排名 {rank_s}"
        if sig.get("l5_quad"):
            l5_detail += f"，{sig['l5_quad']}"

        if sig["l6_lit"]:
            l6_detail = "融資↓ + 借券↓（籌碼集中，散戶撤/空頭回補）"
        elif sig["l6_cover"]:
            l6_detail = "借券回補中↑（早期籌碼改善信號）"
        else:
            l6_detail = "未達籌碼集中條件"

        l6_warn_str = " ⚠️ 另有空頭加碼中" if sig["l6_add"] else ""

        # ── 七燈條件清單 ────────────────────────────────────────────────────
        lines += [
            "### 七燈條件清單",
            "",
            "| 燈號 | 名稱 | 狀態 | 說明 |",
            "|------|------|:----:|------|",
            f"| 燈1 | 月營收 YoY 拐點 | {_icon(sig['l1_lit'] or sig['l1_mom'])} | {l1_detail} |",
            f"| 燈2 | 法人籌碼共振 | {_icon(sig['l2_resonate'] or sig['l2_foreign'] or sig['l2_trust'])} | {l2_detail} |",
            f"| 燈3 | 庫存循環偵測 | {_icon(sig['l3_lit'])} | {'存貨週轉率連2季改善（Abernathy et al. 2014）' if sig['l3_lit'] else '存貨週轉率未見持續改善'} |",
            f"| 燈4 | 技術突破（個股） | {_icon(sig['l4_above'])} | {l4_detail} |",
            f"| 燈5 | 相對強度 RRG | {_icon(sig['l5_lit'])} | {l5_detail} |",
            f"| 燈6 | 籌碼集中 | {_icon(sig['l6_lit'] or sig['l6_cover'])} | {l6_detail}{l6_warn_str} |",
            f"| 燈7 | 宏觀環境（全局） | {_icon(sig['l7_signal'])} | {sig['l7_pos']}/{sig['l7_total']} 項宏觀指標達標 |",
            "",
        ]

        # ── 技術關鍵指標 ────────────────────────────────────────────────────
        lines += [
            "### 技術關鍵指標",
            "",
            "| 指標 | 數值 | 評估基準 |",
            "|------|------|----------|",
            f"| 最近收盤價 | `{price_s}` | — |",
            f"| MA60（60日均線） | `{ma60_s}` | 關鍵支撐/進場基準 |",
            f"| 距離 MA60 | `{dist_s}` | 0%~+10% 為甜蜜進場區 |",
            f"| 量比（最新/20MA均量） | `{vol_s}` | ≥ 1.5x 為有效放量 |",
            f"| RS-Ratio（vs TAIEX） | `{rs_s}` | ≥ 1.0 為市場相對強勢 |",
            f"| 板塊內 RS 排名 | `{rank_s}` | ≥ 70% 得技術面加分 |",
            "",
        ]

        # ── 三面合一評分 ────────────────────────────────────────────────────
        f_trig = [t for t in triggered if any(k in t for k in ["燈1", "燈3", "EPS"])]
        t_trig = [t for t in triggered if any(k in t for k in ["燈4", "燈5"])]
        c_trig = [t for t in triggered if any(k in t for k in ["燈2", "燈6", "共振", "外資", "投信", "借券"])]
        b_trig = [t for t in triggered if any(k in t for k in ["PE", "ROE", "加速", "季節"])]

        lines += [
            "### 三面合一評分（O'Neil CAN SLIM + Greenblatt Magic Formula）",
            "",
            f"**總分**：{'`' + score_s + '`' if score_s != 'N/A' else '—（分數未達顯示門檻或計算失敗）'} 分　{grade}",
            "",
            "| 評分面向 | 得分 | 滿分 | 已觸發條件 |",
            "|----------|:----:|:----:|-----------|",
            f"| 基本面 | {_fmt(breakdown.get('fundamental'), '.1f')} | 5.5 | {', '.join(f_trig) or '—'} |",
            f"| 技術面 | {_fmt(breakdown.get('technical'),   '.1f')} | 3.5 | {', '.join(t_trig) or '—'} |",
            f"| 籌碼面 | {_fmt(breakdown.get('chipset'),     '.1f')} | 4.0 | {', '.join(c_trig) or '—'} |",
            f"| 加分項 | {_fmt(breakdown.get('bonus'),       '.1f')} | 2.0 | {', '.join(b_trig) or '—'} |",
            "",
        ]

        # ── 進場建議 ────────────────────────────────────────────────────────
        stop_loss = ""
        if sig.get("ma60") and sig.get("current_price"):
            stop_loss = f"\n>\n> **參考停損**：收盤跌破 MA60（`{ma60_s}`）視為技術止損點。"

        lines += [
            "### 進場建議",
            "",
            f"> {sig['rec_icon']} **{sig['recommendation']}**",
            ">",
            f"> {sig['rec_reason']}",
            f">",
            f"> 亮燈：**{sig['lit_count']}/6**（加權 {sig['lit_count_w']}）　評分：**{score_s}** {grade}",
            stop_loss,
            "",
            "---",
            "",
        ]

    # ─── 摘要對比表 ─────────────────────────────────────────────────────────
    def _b(flag: bool) -> str:
        return "✅" if flag else "❌"

    lines += [
        "## 📋 整體摘要對比",
        "",
        "| 股票 | 板塊 | 燈1 | 燈2 | 燈3 | 燈4站MA60 | 燈5強勢 | 燈6籌碼 | 亮燈數 | 評分 | 宏觀 | 建議 |",
        "|------|------|:---:|:---:|:---:|:---------:|:-------:|:-------:|:------:|:----:|:----:|------|",
    ]
    for stock_id in target_stocks:
        sig = stock_signals.get(stock_id)
        if not sig:
            continue
        _, sname, is_s = stock_sector_info[stock_id]
        sname_short = (sname[:5] + "…") if len(sname) > 5 else sname
        if is_s:
            sname_short = "⚠️獨立"
        sd_  = sig.get("score_data", {})
        scr_ = sd_.get("score")
        grd_ = sd_.get("grade", "")
        scr_d = f"{scr_:.1f}{grd_}" if scr_ is not None else "—"
        lines.append(
            f"| {stock_id} | {sname_short} "
            f"| {_b(sig['l1_lit'] or sig['l1_mom'])} "
            f"| {_b(sig['l2_resonate'] or sig['l2_foreign'] or sig['l2_trust'])} "
            f"| {_b(sig['l3_lit'])} "
            f"| {_b(sig['l4_above'])} "
            f"| {_b(sig['l5_lit'])} "
            f"| {_b(sig['l6_lit'] or sig['l6_cover'])} "
            f"| **{sig['lit_count']}/6** "
            f"| {scr_d} "
            f"| {_b(sig['l7_signal'])} "
            f"| {sig['rec_icon']} {sig['recommendation']} |"
        )

    lines += [
        "",
        "---",
        "",
        f"*📌 本報告由 `scripts/stock_entry_check.py` 自動生成 · {now_str}*",
        "",
        "> **燈號說明**：燈1 月營收拐點 / 燈2 法人共振 / 燈3 庫存循環 / 燈4 技術突破（個股MA60）/ 燈5 相對強度 / 燈6 籌碼集中 / 燈7 全局宏觀",
        "> **進場門檻**：宏觀OK + 燈4站MA60 + ≥4燈點亮 → ✅ 可進場",
        "",
    ]

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 六、CLI 入口
# ════════════════════════════════════════════════════════════════════════════

def _parse_stocks() -> List[str]:
    parser = argparse.ArgumentParser(
        description="個股下週一進場分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python scripts/stock_entry_check.py 2330,2454,3034\n"
            "  python scripts/stock_entry_check.py --stocks 2330\n"
        ),
    )
    parser.add_argument(
        "stocks_positional", nargs="?", metavar="STOCKS",
        help="逗號分隔的股票代號，如 2330,2454,3034",
    )
    parser.add_argument(
        "--stocks", type=str, default=None,
        help="逗號分隔的股票代號（與位置引數擇一）",
    )
    args = parser.parse_args()
    raw = args.stocks_positional or args.stocks
    if not raw:
        raw = input("請輸入股票代號（逗號分隔，如 2330,2454）：").strip()
    stocks = [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]
    if not stocks:
        print("錯誤：未提供有效的股票代號。", file=sys.stderr)
        sys.exit(1)
    return stocks


def main() -> None:
    target_stocks = _parse_stocks()

    print(f"\n{'='*60}")
    print(f"📊 個股進場分析：{', '.join(target_stocks)}")
    print(f"{'='*60}\n")

    # ── 初始化
    import src.config as config
    from src.data_fetcher import DataFetcher
    from src.sector_map import SectorMap

    print("🔑 連線 FinLab...")
    fetcher = DataFetcher()
    if not fetcher.login():
        print("❌ FinLab 登入失敗，請確認 .env 中的 FINLAB_API_TOKEN。", file=sys.stderr)
        sys.exit(1)

    print("📂 載入板塊定義...")
    base_map = SectorMap()
    base_map.load()

    print("🗺️  建立目標板塊地圖...")
    targeted_map, stock_sector_info = _build_targeted_map(target_stocks, base_map)

    # 顯示 standalone 警告
    standalone = [s for s, (_, _, is_s) in stock_sector_info.items() if is_s]
    if standalone:
        print(f"\n⚠️  以下股票未收錄於任何板塊（將以獨立個股分析）：")
        for s in standalone:
            print(f"   • {s} — 不在整體市場趨勢板塊中，可加入 custom_sectors.csv 以強化分析")
        print()

    # ── 執行分析
    print("🔦 執行七燈分析...")
    analysis = _run_all_analyzers(fetcher, targeted_map, config)

    # ── 逐股信號提取
    print("\n📊 提取個股信號...")
    stock_signals: Dict[str, Any] = {}
    for stock_id in target_stocks:
        sector_id, _, is_standalone = stock_sector_info[stock_id]
        print(f"  [{stock_id}] 計算燈4 個股技術指標...")
        tech4 = _compute_lamp4_stock(stock_id, fetcher, config)
        print(f"  [{stock_id}] 彙整七燈信號 + 評分...")
        stock_signals[stock_id] = _extract_stock_signals(
            stock_id, sector_id, is_standalone,
            analysis, tech4, fetcher, config,
        )

    # ── 產生報告
    print("\n📝 產生 Markdown 報告...")
    run_time = datetime.now()
    md = _generate_markdown(
        target_stocks, stock_signals, analysis["macro"],
        stock_sector_info, run_time,
    )

    filename = f"股票進場分析_{run_time.strftime('%Y%m%d_%H%M')}.md"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(md, encoding="utf-8")

    # ── 終端摘要
    print(f"\n{'='*60}")
    print("📋 進場建議摘要：")
    for stock_id in target_stocks:
        sig = stock_signals.get(stock_id, {})
        if sig:
            scr = sig.get("score_data", {}).get("score")
            scr_str = f"評分 {scr:.1f}" if scr else ""
            print(f"  {stock_id:>6}：{sig['rec_icon']} {sig['recommendation']:<18} "
                  f"({sig['lit_count']}/6 燈)  {scr_str}")
    print(f"{'='*60}")
    print(f"\n✅ 報告已儲存：{out_path.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
