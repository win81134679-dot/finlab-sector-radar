#!/usr/bin/env python
"""
etf_entry_check.py — ETF 下週一進場分析工具

功能：
  重用現有燈號框架，對指定台灣 ETF 執行 燈2/4/5/6/7 五燈分析，
  並以 yfinance 補充 ETF 特有指標（殖利率、費用率、AUM 趨勢）。
  採用六維學術評分模型輸出 Markdown 報告。

用法：
  python scripts/etf_entry_check.py 0050,0056,00878
  python scripts/etf_entry_check.py --etfs 0050,0056
  python scripts/etf_entry_check.py           （互動式輸入）

輸出：
  local_analysis/ETF進場分析_YYYYMMDD_HHMM.md

學術評分依據：
  Jegadeesh & Titman (1993)        — 動能力
  Levy (1967); DeSouza & Gokcan (2004) — 相對強度
  Nofsinger & Sias (1999)          — 法人共識
  Fama & French (1989)             — 宏觀環境
  Rakowski & Wang (2009)           — 規模趨勢
  Sharpe (1992); French (2008)     — 估值結構

注意：
  - ETF 無月營收（燈1）/ 庫存循環（燈3）→ 標示 N/A，不計入亮燈數
  - 燈6（籌碼）僅適用可融資 ETF；無融資資料者標 N/A
  - yfinance 快取寫入 %TEMP% 避免中文路徑問題
  - 不修改任何現有 src/ 模組
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── yfinance 快取目錄設定（必須在 import yfinance 之前）────────────────────
# 避免 yfinance 嘗試寫入含中文字元的使用者目錄
_TEMP_DIR = Path(os.environ.get("TEMP", tempfile.gettempdir()))
_YF_CACHE_DIR = _TEMP_DIR / "py-yfinance-cache"
_YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── 路徑設定：讓 src.* 可被 import ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.ssl_fix  # noqa: F401 — 必須在 yfinance / finlab 之前 import

import yfinance as yf_module
try:
    yf_module.set_tz_cache_location(str(_YF_CACHE_DIR))
except Exception:
    pass  # 舊版 yfinance 可能不支援此方法，略過

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── 輸出目錄（不上傳 GitHub，已加入 .gitignore）─────────────────────────────
OUTPUT_DIR = ROOT / "local_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# 常數定義
# ════════════════════════════════════════════════════════════════════════════

# 台灣可融資 ETF（具備融資餘額資料的主流 ETF）
MARGINABLE_ETFS = {
    "0050", "0051", "0052", "0053",
    "0056", "006204", "006208",
    "00878", "00900", "00919",
    "00881", "00733", "00892",
}

# ETF 分類字典：代號 → {type, index, company}
ETF_CATALOG: Dict[str, Dict[str, str]] = {
    "0050":  {"type": "寬基指數", "index": "臺灣50指數",              "company": "元大"},
    "0051":  {"type": "寬基指數", "index": "中型100指數",             "company": "元大"},
    "0052":  {"type": "寬基指數", "index": "臺灣科技指數",            "company": "富邦"},
    "006208": {"type": "寬基指數", "index": "富時台灣50指數",         "company": "富邦"},
    "0056":  {"type": "高股息",   "index": "臺灣高股息指數",          "company": "元大"},
    "00878": {"type": "高股息",   "index": "MSCI台灣ESG永續高股息",   "company": "國泰"},
    "00919": {"type": "高股息",   "index": "臺灣優質高股息精選30",    "company": "群益"},
    "00900": {"type": "高股息",   "index": "台灣智能高息等權重",      "company": "富邦"},
    "00713": {"type": "高股息",   "index": "臺灣綜合股利精選30",      "company": "元大"},
    "00881": {"type": "主題",     "index": "納斯達克台灣科技高息",    "company": "國泰"},
    "00733": {"type": "主題",     "index": "臺灣動能指數",            "company": "富邦"},
    "00892": {"type": "主題",     "index": "富時台灣非必需消費",      "company": "富邦"},
    "00679B": {"type": "債券",    "index": "美國20年+國債(TLT)",      "company": "元大"},
    "00772B": {"type": "債券",    "index": "美國IG公司債",            "company": "中信"},
    "00631L": {"type": "槓桿",    "index": "台灣50指數 2x",           "company": "元大"},
    "00632R": {"type": "反向",    "index": "台灣50指數 -1x",          "company": "元大"},
}

# 寬基 ETF（RS 計算對比 TAIEX，不與 0050 自比）
WIDE_BASE_ETFS = {"0050", "006208", "0051"}

# 六維評分模型：維度 → (滿分, 學術依據)
SCORE_DIMS: Dict[str, Tuple[float, str]] = {
    "momentum":      (3.0, "Jegadeesh & Titman (1993)"),
    "relative_str":  (2.5, "Levy (1967); DeSouza & Gokcan (2004)"),
    "institutional": (2.5, "Nofsinger & Sias (1999)"),
    "macro":         (2.0, "Fama & French (1989)"),
    "aum_trend":     (2.5, "Rakowski & Wang (2009)"),
    "valuation":     (2.5, "Sharpe (1992); French (2008)"),
}
SCORE_MAX = sum(v[0] for v in SCORE_DIMS.values())  # 15.0

# ── 五維出場風險評分模型（總分 10 分，分數越高代表出場壓力越大）────────────
# 每維度對應一篇核心 SSCI/JF/JFE 論文，與進場評分完全獨立
EXIT_RISK_DIMS: Dict[str, Tuple[float, str]] = {
    "tech_pressure":         (3.0, "Brock, Lakonishok & LeBaron (1992); De Bondt & Thaler (1985)"),
    "rs_deterioration":      (2.0, "Levy (1967); DeSouza & Gokcan (2004)"),
    "institutional_retreat": (2.0, "Nofsinger & Sias (1999); Sias (2004)"),
    "macro_deterioration":   (2.0, "Fama & French (1989)"),
    "chipset_deterioration": (1.0, "Kaminski & Lo (2014)"),
}
EXIT_RISK_MAX = sum(v[0] for v in EXIT_RISK_DIMS.values())  # 10.0


# ════════════════════════════════════════════════════════════════════════════
# 一、ETF 板塊地圖建構（全為 standalone）
# ════════════════════════════════════════════════════════════════════════════

def _build_etf_map(
    etf_codes: List[str],
) -> Tuple[Any, Dict[str, Tuple[str, str, bool]]]:
    """
    ETF 均以獨立板塊（standalone）處理。
    燈2/5/6 以個別 ETF 計算，不依賴板塊共振。
    回傳 (targeted_map, {etf_id: (sector_id, sector_name, is_standalone)})
    """
    from src.sector_map import SectorMap

    sectors: Dict[str, Any] = {}
    info: Dict[str, Tuple[str, str, bool]] = {}

    for etf_id in etf_codes:
        s_id = f"etf_{etf_id}"
        sectors[s_id] = {
            "name":   f"ETF {etf_id}",
            "type":   "etf_standalone",
            "parent": "",
            "stocks": [etf_id],
            "source": "etf",
        }
        info[etf_id] = (s_id, f"ETF {etf_id}", True)

    targeted_map = SectorMap()
    targeted_map._sectors = sectors
    targeted_map._loaded = True
    return targeted_map, info


# ════════════════════════════════════════════════════════════════════════════
# 二、yfinance 元資料抓取（快取於 %TEMP%）
# ════════════════════════════════════════════════════════════════════════════

def _fetch_etf_yf_metadata(etf_id: str, timeout_secs: float = 6.0) -> Dict[str, Any]:
    """
    以 yfinance 抓取 ETF 基本指標（殖利率、費用率、AUM、歷史月收盤）。
    含 timeout 保護，失敗時回傳空字典（優雅退化，不影響主要分析）。
    快取已設定至 %TEMP%/py-yfinance-cache 避免中文路徑問題。
    """
    tw_code = f"{etf_id}.TW"
    fetched: Dict[str, Any] = {}
    exc_holder: List[Optional[Exception]] = [None]

    def _do_fetch() -> None:
        try:
            ticker = yf_module.Ticker(tw_code)
            info = ticker.info or {}

            fetched["dividend_yield"] = (
                info.get("trailingAnnualDividendYield")
                or info.get("dividendYield")
            )
            fetched["expense_ratio"] = info.get("annualReportExpenseRatio")
            fetched["total_assets"]  = info.get("totalAssets")
            fetched["nav"]           = info.get("navPrice")
            fetched["long_name"]     = info.get("longName") or info.get("shortName", "")
            fetched["currency"]      = info.get("currency", "TWD")

            # 近 3 個月月收盤（用於價格趨勢估算）
            hist = ticker.history(period="3mo", interval="1mo", auto_adjust=True)
            if hist is not None and not hist.empty:
                fetched["hist_monthly"] = hist["Close"].dropna().tolist()
        except Exception as exc:
            exc_holder[0] = exc

    t = threading.Thread(target=_do_fetch, daemon=True)
    t.start()
    t.join(timeout=timeout_secs)

    if t.is_alive():
        logger.warning("yfinance 抓取 %s 超時（%.0f 秒），略過。", etf_id, timeout_secs)
        return {}

    if exc_holder[0]:
        logger.warning("yfinance %s 失敗：%s", etf_id, exc_holder[0])
        return {}

    return fetched


# ════════════════════════════════════════════════════════════════════════════
# 三、ETF 分析器執行（燈2/5/6/7）
# ════════════════════════════════════════════════════════════════════════════

def _run_etf_analyzers(fetcher, etf_map, config) -> Dict[str, Any]:
    """
    執行 ETF 可用燈號分析：燈2（法人）/ 燈5（RS）/ 燈6（籌碼）/ 燈7（宏觀）。
    燈4 在後續逐 ETF 以 _compute_lamp4_stock() 個別計算。
    燈1/3 不適用 ETF，略過。
    """
    from src.analyzers.institutional import analyze as analyze_institutional
    from src.analyzers.rs_ratio      import analyze as analyze_rs
    from src.analyzers.chipset       import analyze as analyze_chipset
    from src.analyzers.macro         import analyze as analyze_macro

    steps = [
        ("🌐 燈7 宏觀環境...",     "macro",       lambda: analyze_macro(fetcher, config)),
        ("🏦 燈2 法人動向...",     "燈2 法人共振", lambda: analyze_institutional(fetcher, etf_map, config)),
        ("🔀 燈5 相對強度 RRG...", "燈5 相對強度", lambda: analyze_rs(fetcher, etf_map, config)),
        ("💎 燈6 籌碼（融資）...", "燈6 籌碼集中", lambda: analyze_chipset(fetcher, etf_map, config)),
    ]

    results: Dict[str, Any] = {}
    for label, key, fn in steps:
        print(f"  {label}")
        try:
            results[key] = fn()
        except Exception as exc:
            logger.error("%s 執行失敗：%s", key, exc)
            results[key] = {}

    macro_result = results.pop("macro", {})
    return {"macro": macro_result, "raw": results}


# ════════════════════════════════════════════════════════════════════════════
# 四、ETF RS 個股層級計算
# ════════════════════════════════════════════════════════════════════════════

def _compute_rs_etf(
    etf_id: str,
    fetcher,
    config,
    benchmark_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    計算 ETF 的 RS-Ratio/Momentum，對比基準：
    - 寬基 ETF（0050、006208 等）→ 對比 TAIEX
    - 高股息/主題 ETF → 對比 0050（更有意義的同類比較）
    - benchmark_id=None 代表使用 TAIEX
    """
    import numpy as np
    from src.analyzers.rs_ratio import _compute_rr, _PRICE_KEY, _TAIEX_KEY, _TAIEX_COL

    try:
        price_df = fetcher.get(_PRICE_KEY)
        taiex_df = fetcher.get(_TAIEX_KEY)

        if price_df is None or etf_id not in price_df.columns:
            return {"error": f"FinLab 無 {etf_id} 收盤價資料（可能不支援此 ETF）"}

        # 取得基準序列
        if benchmark_id and benchmark_id != etf_id and price_df is not None \
                and benchmark_id in price_df.columns:
            benchmark = price_df[benchmark_id].dropna()
        elif taiex_df is not None:
            if _TAIEX_COL in taiex_df.columns:
                benchmark = taiex_df[_TAIEX_COL].dropna()
            else:
                benchmark = taiex_df.iloc[:, 0].dropna()
        else:
            return {"error": "無 TAIEX 基準數據"}

        lookback = config.RS_LOOKBACK_DAYS
        etf_prices = price_df[[etf_id]].iloc[-(lookback * 2):]
        rs_ratio, rs_mom, quadrant = _compute_rr(etf_prices, benchmark, lookback)

        if np.isnan(rs_ratio):
            return {"error": "RS 計算結果 NaN（資料不足）"}

        return {
            "rs_ratio":    round(rs_ratio, 4),
            "rs_momentum": round(rs_mom, 6),
            "quadrant":    quadrant,
            "benchmark":   benchmark_id or "TAIEX",
            "lit":         bool(rs_ratio >= 1.0 and rs_mom >= 0),
        }
    except Exception as exc:
        logger.warning("RS ETF 計算失敗 %s: %s", etf_id, exc)
        return {"error": str(exc)}


# ════════════════════════════════════════════════════════════════════════════
# 五、ETF 出場風險評估（五維學術模型）
# ════════════════════════════════════════════════════════════════════════════

def _score_exit_risk(
    l4_above: bool,
    l4_dist: Optional[float],
    l5_quad: str,
    l2_available: bool,
    l2_resonate: bool,
    l2_foreign: bool,
    l2_trust: bool,
    l7_pos: int,
    l7_total: int,
    l6_available: bool,
    l6_add: bool,
) -> Dict[str, float]:
    """
    五維出場風險評分（總分 EXIT_RISK_MAX=10 分）。
    分數越高代表出場壓力越大。與進場評分（六維 15 分）完全獨立，
    允許「可進場但需注意出場壓力」的複合持倉判斷。

    維度（論文依據）：
      tech_pressure         — Brock, Lakonishok & LeBaron (1992); De Bondt & Thaler (1985)
      rs_deterioration      — Levy (1967); DeSouza & Gokcan (2004)
      institutional_retreat — Nofsinger & Sias (1999); Sias (2004)
      macro_deterioration   — Fama & French (1989)
      chipset_deterioration — Kaminski & Lo (2014)
    """
    scores: Dict[str, float] = {}

    # ── 1. 技術出場壓力（0–3）── Brock et al. (1992) + De Bondt & Thaler (1985) ──
    # 跌破 MA60 為最強出場信號（Brock 1992 MA 規則）
    # 極度超買後均值回歸壓力（De Bondt & Thaler 1985 過度反應理論）
    if not l4_above:
        scores["tech_pressure"] = 3.0              # 已跌破 MA60：技術面出場信號觸發
    elif l4_dist is not None and l4_dist > 25.0:
        scores["tech_pressure"] = 1.5              # 極度超買：均值回歸壓力大
    elif l4_dist is not None and l4_dist > 15.0:
        scores["tech_pressure"] = 1.0              # 超買預警
    elif l4_dist is not None and -3.0 <= l4_dist < 0.0:
        scores["tech_pressure"] = 1.0              # 接近跌破邊緣，潛在壓力
    else:
        scores["tech_pressure"] = 0.0              # 正常甜蜜區間

    # ── 2. 相對強度弱化（0–2）── Levy (1967); DeSouza & Gokcan (2004) ─────────
    # RRG 落後象限（RS < 1.0 且動能向下）代表持續弱勢，為出場依據
    quad_map = {"落後": 2.0, "轉弱": 1.5, "改善": 0.5, "領先": 0.0}
    scores["rs_deterioration"] = quad_map.get(l5_quad, 1.0)  # 未知象限→中間值

    # ── 3. 法人撤退（0–2）── Nofsinger & Sias (1999); Sias (2004) RFS 17(1) ────
    # 機構投資人群聚效應逆轉時，通常是高品質出場時機（Nofsinger & Sias 1999）
    if not l2_available:
        scores["institutional_retreat"] = 0.5      # 資料不可用→輕微不確定性
    elif l2_resonate:
        scores["institutional_retreat"] = 0.0      # 共振買進中：無撤退壓力
    elif l2_foreign or l2_trust:
        scores["institutional_retreat"] = 1.0      # 單邊買進：部分撐盤中
    else:
        scores["institutional_retreat"] = 2.0      # 外資+投信均未買進：群聚效應消失

    # ── 4. 宏觀惡化（0–2）── Fama & French (1989) JFE 25(1) ─────────────────
    # 使用連續比例公式（非階梯）避免邊界效應（Fama & French 1989 商業景氣周期）
    if l7_total > 0:
        neg_ratio = (l7_total - l7_pos) / l7_total
        scores["macro_deterioration"] = round(neg_ratio * 2.0, 2)
    else:
        scores["macro_deterioration"] = 1.0        # 無宏觀資料→中間值

    # ── 5. 籌碼惡化（0–1）── Kaminski & Lo (2014) JFM 18:234 ─────────────────
    # 借券增加代表空頭選擇建立放空部位，為警示信號（Kaminski & Lo 2014 停損規則）
    if l6_available and l6_add:
        scores["chipset_deterioration"] = 1.0      # 借券增加 = 空頭建倉
    else:
        scores["chipset_deterioration"] = 0.0

    return {k: round(v, 2) for k, v in scores.items()}


def _make_exit_signal(
    total_risk: float,
    breakdown: Dict[str, float],
) -> Tuple[str, str, str]:
    """
    依五維出場風險總分決定出場建議，回傳 (signal, icon, reason)。
    閾值設計參考 Brock et al. (1992) 停損邊界與 Kaminski & Lo (2014) 停損規則。

    ≥ 7.0 → 🔴 立即出場（多重關鍵訊號同步觸發）
    5.0–6.9 → 🟠 建議減碼（出場壓力顯著）
    3.0–4.9 → 🟡 注意警示（存在隱憂，設停損觀察）
    < 3.0  → 🟢 持有（出場壓力低）
    """
    dim_names = {
        "tech_pressure":         "技術出場壓力",
        "rs_deterioration":      "相對強度弱化",
        "institutional_retreat": "法人撤退訊號",
        "macro_deterioration":   "宏觀環境惡化",
        "chipset_deterioration": "籌碼惡化",
    }
    if breakdown:
        top_dim = max(breakdown, key=lambda k: breakdown[k])
        top_score = breakdown[top_dim]
        trigger = f"首要壓力：{dim_names.get(top_dim, top_dim)}（{top_score:.1f} 分）"
    else:
        trigger = "—"

    if total_risk >= 7.0:
        return (
            "立即出場", "🔴",
            f"出場風險 {total_risk:.1f}/{EXIT_RISK_MAX:.0f}，多重關鍵訊號同步觸發，持股風險極高。{trigger}。",
        )
    if total_risk >= 5.0:
        return (
            "建議減碼", "🟠",
            f"出場風險 {total_risk:.1f}/{EXIT_RISK_MAX:.0f}，出場壓力顯著，{trigger}，宜降低持倉至 50% 以下。",
        )
    if total_risk >= 3.0:
        return (
            "注意警示", "🟡",
            f"出場風險 {total_risk:.1f}/{EXIT_RISK_MAX:.0f}，存在隱憂，{trigger}，建議持有但設停損單密切追蹤。",
        )
    return (
        "持有",
        "🟢",
        f"出場風險 {total_risk:.1f}/{EXIT_RISK_MAX:.0f}，{trigger}，出場壓力低，維持部位。",
    )


# ════════════════════════════════════════════════════════════════════════════
# 六、ETF 信號提取與六維評分
# ════════════════════════════════════════════════════════════════════════════

def _extract_etf_signals(
    etf_id: str,
    sector_id: str,
    analysis: Dict[str, Any],
    tech4: Dict[str, Any],
    rs_data: Dict[str, Any],
    ymeta: Dict[str, Any],
    fetcher,
    config,
) -> Dict[str, Any]:
    """彙整 ETF 的各燈信號並計算六維評分。"""
    raw   = analysis["raw"]
    macro = analysis["macro"]

    # ── 燈2：法人動向（部分 ETF 可能無三大法人資料）
    lamp2 = raw.get("燈2 法人共振", {}).get(sector_id, {})
    # total_stocks==0 代表此 ETF 代號不在法人資料欄位中
    l2_available    = bool(lamp2) and lamp2.get("total_stocks", 0) > 0
    l2_resonate     = etf_id in lamp2.get("lit_stocks", [])
    l2_foreign      = etf_id in lamp2.get("foreign_only", [])
    l2_trust        = etf_id in lamp2.get("trust_only", [])
    l2_market_state = lamp2.get("market_state", "unknown")

    # ── 燈4：技術突破（個股層級）
    l4_above = tech4.get("above_ma60", False)
    l4_surge = tech4.get("vol_surge", False)
    l4_dist  = tech4.get("dist_pct")
    l4_score = tech4.get("tech_score", 0)

    # ── 燈5：相對強度（個別計算）
    l5_ratio   = rs_data.get("rs_ratio")
    l5_mom     = rs_data.get("rs_momentum")
    l5_quad    = rs_data.get("quadrant", "")
    l5_lit     = rs_data.get("lit", False)
    l5_bm      = rs_data.get("benchmark", "TAIEX")

    # ── 燈6：籌碼（僅可融資 ETF 有意義）
    lamp6          = raw.get("燈6 籌碼集中", {}).get(sector_id, {})
    is_marginable  = etf_id in MARGINABLE_ETFS
    l6_available   = is_marginable and bool(lamp6) and lamp6.get("total_stocks", 0) > 0
    l6_lit         = etf_id in lamp6.get("lit_stocks", [])
    l6_cover       = etf_id in lamp6.get("short_cover", [])
    l6_add         = etf_id in lamp6.get("short_add", [])

    # ── 燈7：全局宏觀
    l7_signal = macro.get("signal", False)
    l7_pos    = macro.get("positive_count", 0)
    l7_total  = macro.get("total_available", 0)

    # ── 亮燈計數（ETF 採動態燈數，不可用燈不計）
    # 燈1/3 固定 N/A；燈2 看資料可用性；燈6 看是否可融資
    lamp_bools: Dict[str, Optional[bool]] = {
        "l2": (l2_resonate or l2_foreign or l2_trust) if l2_available else None,
        "l4": bool(l4_above),
        "l5": bool(l5_lit),
        "l6": (l6_lit or l6_cover) if l6_available else None,
        "l7": bool(l7_signal),
    }
    active_lamps = {k: v for k, v in lamp_bools.items() if v is not None}
    lit_count  = sum(1 for v in active_lamps.values() if v)
    total_lamps = len(active_lamps)

    # 加權計數（外資/投信獨買 = 0.5）
    l2_weight = (1.0 if l2_resonate else (0.5 if (l2_foreign or l2_trust) else 0.0)) \
                if l2_available else 0.0
    l6_weight = (1.0 if l6_lit else (0.5 if l6_cover else 0.0)) \
                if l6_available else 0.0
    lit_weighted = round(
        l2_weight
        + (1.0 if l4_above else 0.0)
        + (1.0 if l5_lit else 0.0)
        + l6_weight
        + (1.0 if l7_signal else 0.0),
        1
    )

    # ── 六維評分
    score_breakdown = _score_etf(
        l4_above=l4_above, l4_dist=l4_dist, l4_surge=l4_surge, l4_score=l4_score,
        l5_lit=l5_lit, l5_ratio=l5_ratio, l5_mom=l5_mom,
        l2_available=l2_available, l2_resonate=l2_resonate,
        l2_foreign=l2_foreign, l2_trust=l2_trust,
        l7_signal=l7_signal, l7_pos=l7_pos, l7_total=l7_total,
        ymeta=ymeta,
    )
    total_score = round(sum(score_breakdown.values()), 1)

    # ── 進場建議
    rec, rec_icon, rec_reason = _make_etf_recommendation(
        total_score=total_score,
        lit_count=lit_count,
        total_lamps=total_lamps,
        l7_signal=l7_signal,
        l4_above=l4_above,
        l4_dist=l4_dist,
    )

    # ── 出場風險評估（五維，與進場評分完全獨立）
    exit_breakdown = _score_exit_risk(
        l4_above=l4_above, l4_dist=l4_dist,
        l5_quad=l5_quad,
        l2_available=l2_available, l2_resonate=l2_resonate,
        l2_foreign=l2_foreign, l2_trust=l2_trust,
        l7_pos=l7_pos, l7_total=l7_total,
        l6_available=l6_available, l6_add=l6_add,
    )
    exit_risk_total = round(sum(exit_breakdown.values()), 1)
    exit_signal, exit_icon, exit_reason = _make_exit_signal(exit_risk_total, exit_breakdown)

    return {
        "etf_id":     etf_id,
        "sector_id":  sector_id,
        # 燈2
        "l2_available":  l2_available,
        "l2_resonate":   l2_resonate,
        "l2_foreign":    l2_foreign,
        "l2_trust":      l2_trust,
        "l2_market_state": l2_market_state,
        # 燈4
        "l4_above":  l4_above,
        "l4_surge":  l4_surge,
        "l4_dist":   l4_dist,
        "l4_score":  l4_score,
        "current_price": tech4.get("current_price"),
        "ma60":          tech4.get("ma60"),
        "vol_ratio":     tech4.get("vol_ratio"),
        "tech4_error":   tech4.get("error"),
        # 燈5
        "l5_lit":       l5_lit,
        "l5_ratio":     l5_ratio,
        "l5_mom":       l5_mom,
        "l5_quad":      l5_quad,
        "l5_benchmark": l5_bm,
        "rs_error":     rs_data.get("error"),
        # 燈6
        "l6_available": l6_available,
        "is_marginable": is_marginable,
        "l6_lit":   l6_lit,
        "l6_cover": l6_cover,
        "l6_add":   l6_add,
        # 燈7
        "l7_signal": l7_signal,
        "l7_pos":    l7_pos,
        "l7_total":  l7_total,
        # 統計
        "lamp_bools":  lamp_bools,
        "lit_count":   lit_count,
        "total_lamps": total_lamps,
        "lit_weighted": lit_weighted,
        # 評分
        "score_breakdown": score_breakdown,
        "total_score":     total_score,
        # 建議
        "recommendation": rec,
        "rec_icon":       rec_icon,
        "rec_reason":     rec_reason,
        # 出場風險（五維 EXIT_RISK_MAX=10，與進場評分獨立）
        "exit_breakdown":  exit_breakdown,
        "exit_risk":       exit_risk_total,
        "exit_signal":     exit_signal,
        "exit_icon":       exit_icon,
        "exit_reason":     exit_reason,
        # yfinance 元資料
        "ymeta": ymeta,
    }


def _score_etf(
    l4_above: bool,
    l4_dist: Optional[float],
    l4_surge: bool,
    l4_score: int,
    l5_lit: bool,
    l5_ratio: Optional[float],
    l5_mom: Optional[float],
    l2_available: bool,
    l2_resonate: bool,
    l2_foreign: bool,
    l2_trust: bool,
    l7_signal: bool,
    l7_pos: int,
    l7_total: int,
    ymeta: Dict[str, Any],
) -> Dict[str, float]:
    """
    六維評分計算。
    各維度分數上限見 SCORE_DIMS；總分上限 SCORE_MAX = 15.0。
    """
    scores: Dict[str, float] = {}

    # ── 1. 動能（滿分 3.0）— Jegadeesh & Titman (1993) ─────────────────────
    if not l4_above:
        scores["momentum"] = 0.0
    elif l4_surge:
        scores["momentum"] = 3.0                          # 帶量站上 MA60
    else:
        dist_bonus = 0.5 if (l4_dist is not None and 0 <= l4_dist < 5) else 0.0
        scores["momentum"] = 1.5 + dist_bonus             # 無量站上

    # ── 2. 相對強度（滿分 2.5）— Levy (1967); DeSouza & Gokcan (2004) ───────
    if l5_ratio is None:
        scores["relative_str"] = 0.0
    elif l5_lit:
        mom_bonus = 0.5 if (l5_mom is not None and l5_mom > 0) else 0.0
        scores["relative_str"] = 2.0 + mom_bonus
    elif l5_ratio >= 0.95:
        scores["relative_str"] = 1.0                      # 接近基準線
    else:
        scores["relative_str"] = 0.0

    # ── 3. 法人共識（滿分 2.5）— Nofsinger & Sias (1999) ─────────────────────
    if not l2_available:
        scores["institutional"] = 1.25                    # 無資料→中間值，不懲罰
    elif l2_resonate:
        scores["institutional"] = 2.5
    elif l2_foreign or l2_trust:
        scores["institutional"] = 1.5
    else:
        scores["institutional"] = 0.0

    # ── 4. 宏觀環境（滿分 2.0）— Fama & French (1989) ────────────────────────
    if l7_total > 0:
        scores["macro"] = round(l7_pos / l7_total * 2.0, 2)
    else:
        scores["macro"] = 1.0                             # 無資料→中間值

    # ── 5. 規模/AUM 趨勢（滿分 2.5）— Rakowski & Wang (2009) ─────────────────
    hist_close = ymeta.get("hist_monthly", [])
    total_assets = ymeta.get("total_assets")
    if hist_close and len(hist_close) >= 2:
        trend_pct = (hist_close[-1] - hist_close[0]) / hist_close[0] * 100
        if trend_pct > 5:
            scores["aum_trend"] = 2.5
        elif trend_pct > 0:
            scores["aum_trend"] = 1.5
        elif trend_pct > -5:
            scores["aum_trend"] = 0.75
        else:
            scores["aum_trend"] = 0.0
    elif total_assets and total_assets > 1e9:              # 規模 > 10 億，無趨勢資料
        scores["aum_trend"] = 1.5
    else:
        scores["aum_trend"] = 1.25                        # 無資料→中間值

    # ── 6. 估值/結構（滿分 2.5）— Sharpe (1992); French (2008) ───────────────
    dy  = ymeta.get("dividend_yield")
    er  = ymeta.get("expense_ratio")
    nav = ymeta.get("nav")
    hist_last = (ymeta.get("hist_monthly") or [None])[-1]

    val_score = 0.0
    if dy is not None:
        # 殖利率 3%~8% 視為合理（主要對高股息 ETF 有意義）
        if 0.03 <= dy <= 0.08:
            val_score += 1.0
        elif dy > 0.01:
            val_score += 0.5

    if er is not None:
        # 費用率 < 0.5% 為優，< 1% 為良
        if er < 0.005:
            val_score += 0.75
        elif er < 0.01:
            val_score += 0.5

    if nav and hist_last:
        # 折溢價在 ±2% 以內視為合理
        prem = (hist_last - nav) / nav
        if -0.02 <= prem <= 0.02:
            val_score += 0.75

    # 若 yfinance 完全無資料，給予中間分數
    if dy is None and er is None:
        val_score = 1.25

    scores["valuation"] = min(val_score, 2.5)

    return {k: round(v, 2) for k, v in scores.items()}


def _make_etf_recommendation(
    total_score: float,
    lit_count: int,
    total_lamps: int,
    l7_signal: bool,
    l4_above: bool,
    l4_dist: Optional[float],
) -> Tuple[str, str, str]:
    """依六維評分 + 燈號狀態決定進場建議，回傳 (建議文字, icon, 理由)。"""
    near_ma60   = l4_dist is not None and -3.0 <= l4_dist < 0.0
    score_ratio = total_score / SCORE_MAX  # 0.0 ~ 1.0

    if not l7_signal:
        if score_ratio >= 0.65:
            return (
                "小量試倉（宏觀警示）", "⚠️",
                f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}（{score_ratio:.0%}）達中高水準，"
                "但宏觀環境偏弱，建議小量試倉並嚴設停損，等宏觀好轉後再加碼。",
            )
        return (
            "觀察等待", "⏳",
            f"宏觀環境偏弱，六維評分 {total_score:.1f}/{SCORE_MAX:.0f}（{score_ratio:.0%}），"
            "建議暫時觀望。",
        )

    if score_ratio >= 0.73 and l4_above:
        return (
            "可進場", "✅",
            f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}（{score_ratio:.0%}），"
            f"站上 MA60，亮燈 {lit_count}/{total_lamps}，宏觀環境良好。"
            "下週一可考慮分批建倉。",
        )
    if score_ratio >= 0.60 and l4_above:
        return (
            "可小量試倉", "🟡",
            f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}，站上 MA60，"
            f"但信號尚未達強烈確認水準（亮燈 {lit_count}/{total_lamps}）。可小量試倉。",
        )
    if score_ratio >= 0.60 and near_ma60:
        return (
            "待突破確認", "🔍",
            f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}，現價接近 MA60（距離 {l4_dist:+.1f}%），"
            "等待收盤站穩 MA60 後再進場，可設條件單掛突破價。",
        )
    if score_ratio >= 0.40:
        return (
            "觀察等待", "⏳",
            f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}（{score_ratio:.0%}），"
            f"信號尚不充分（亮燈 {lit_count}/{total_lamps}），建議繼續追蹤。",
        )
    return (
        "不建議進場", "❌",
        f"六維評分 {total_score:.1f}/{SCORE_MAX:.0f}（{score_ratio:.0%}），"
        "整體條件不足，建議等待更優質進場時機。",
    )


# ════════════════════════════════════════════════════════════════════════════
# 六、Markdown 報告產生
# ════════════════════════════════════════════════════════════════════════════

def _fmt(val: Optional[float], fmt: str = ".2f", suffix: str = "", na: str = "N/A") -> str:
    """安全格式化浮點數。"""
    if val is None:
        return na
    try:
        return f"{val:{fmt}}{suffix}"
    except (ValueError, TypeError):
        return na


def _icon(flag: Optional[bool], na: str = "➖") -> str:
    """將 bool/None 轉換為 Markdown icon。None 代表不適用。"""
    if flag is None:
        return na
    return "✅" if flag else "❌"


def _next_monday(dt: datetime) -> str:
    """取得下一個週一的日期字串。"""
    days_ahead = 7 - dt.weekday()  # Monday=0；7-0=7，確保不含今天
    return (dt.date() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _grade(score_ratio: float) -> str:
    if score_ratio >= 0.80:  return "🏆 A+"
    if score_ratio >= 0.67:  return "🥇 A"
    if score_ratio >= 0.53:  return "🥈 B"
    if score_ratio >= 0.40:  return "🥉 C"
    return "⛔ D"


def _generate_etf_markdown(
    etf_codes: List[str],
    etf_signals: Dict[str, Any],
    macro_result: Dict[str, Any],
    run_time: datetime,
) -> str:
    lines: List[str] = []
    now_str  = run_time.strftime("%Y-%m-%d %H:%M")
    next_mon = _next_monday(run_time)

    # ─── 標頭 ───────────────────────────────────────────────────────────────
    lines += [
        "# 📈 ETF 進場分析報告",
        "",
        f"**分析時間**：{now_str}　　**評估目標**：下週一 `{next_mon}` 進場可行性",
        "",
        f"**分析 ETF**：{', '.join(f'`{e}`' for e in etf_codes)}",
        "",
        "> **進場評分模型**：六維學術評分（動能 / 相對強度 / 法人共識 / 宏觀環境 / 規模趨勢 / 估值結構），總分 15 分",
        ">",
        "> **出場風險模型**：五維學術評分（技術壓力 / RS弱化 / 法人撤退 / 宏觀惡化 / 籌碼惡化），風險指數 10 分，與進場評分獨立並列",
        ">",
        "> 燈1（月營收）、燈3（庫存循環）對 ETF **不適用**，採 5 燈配置（燈2/4/5/6/7）",
        "> ➖ 表示不適用或資料不可用，不計入亮燈數",
        "",
        "---",
        "",
    ]

    # ─── 宏觀環境橫幅 ────────────────────────────────────────────────────────
    l7_signal  = macro_result.get("signal", False)
    l7_pos     = macro_result.get("positive_count", 0)
    l7_total   = macro_result.get("total_available", 0)
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
    ]
    if isinstance(l7_details, dict):
        lines += [
            f"| 美10年債利率 (DGS10) | {l7_details.get('bond', '未取得')} |",
            f"| 工業生產指數 (INDPRO) | {l7_details.get('pmi', '未取得')} |",
            f"| 費半 ETF (SOXX) | {l7_details.get('sox', '未取得')} |",
            f"| 美元/台幣 (USD/TWD) | {l7_details.get('twd', '未取得')} |",
        ]
    else:
        lines.append(f"| 綜合摘要 | {l7_details} |")
    lines.append("")

    if not l7_signal:
        lines += [
            "> 🔴 **整體宏觀警示**：目前宏觀環境偏弱，以下各 ETF 仍提供分析，",
            "> 建議在宏觀好轉前降低部位規模或以更嚴格的止損措施操作。",
            "",
        ]

    lines += ["---", ""]

    # ─── 逐 ETF 分析 ─────────────────────────────────────────────────────────
    for etf_id in etf_codes:
        sig = etf_signals.get(etf_id)
        if not sig:
            lines += [f"## ❓ {etf_id}", "", "> 無法取得此 ETF 的分析數據。", "", "---", ""]
            continue

        cat       = ETF_CATALOG.get(etf_id, {})
        etf_type  = cat.get("type", "未分類")
        etf_index = cat.get("index", "—")
        etf_co    = cat.get("company", "—")
        ymeta     = sig.get("ymeta", {})

        dy    = ymeta.get("dividend_yield")
        er    = ymeta.get("expense_ratio")
        ta    = ymeta.get("total_assets")
        lname = ymeta.get("long_name", "")

        # 數值格式化
        price_s = _fmt(sig.get("current_price"), ".2f")
        ma60_s  = _fmt(sig.get("ma60"), ".2f")
        dist_s  = (_fmt(sig.get("l4_dist"), "+.1f", "%") if sig.get("l4_dist") is not None else "N/A")
        vol_s   = _fmt(sig.get("vol_ratio"), ".2f", "x")
        rs_s    = _fmt(sig.get("l5_ratio"), ".3f")
        dy_s    = f"{dy:.1%}" if dy is not None else "N/A"
        er_s    = f"{er:.3%}" if er is not None else "N/A"
        ta_s    = (f"{ta / 1e8:.0f} 億元" if ta and ta > 0 else "N/A")
        score_s = f"{sig['total_score']:.1f}"
        score_r = sig["total_score"] / SCORE_MAX

        title = f"## {etf_id}"
        if lname:
            title += f"　{lname}"
        lines += [title, ""]
        lines += [
            f"**類型**：{etf_type}　　**追蹤指數**：{etf_index}　　**發行商**：{etf_co}",
            "",
        ]

        # ── ETF 基本資料 ────────────────────────────────────────────────────
        lines += [
            "### 💼 ETF 基本資料",
            "",
            "| 項目 | 數值 | 備註 |",
            "|------|------|------|",
            f"| ETF 類型 | {etf_type} | — |",
            f"| 追蹤指數 | {etf_index} | — |",
            f"| 年化殖利率 | {dy_s} | yfinance 數據，僅供參考 |",
            f"| 費用率 | {er_s} | 費用率越低越佳（< 0.5% 優） |",
            f"| 資產規模 (AUM) | {ta_s} | yfinance 數據 |",
            f"| 可融資 | {'是 ✅' if sig['is_marginable'] else '否 ❌'} | 影響燈6是否適用 |",
            "",
        ]

        # ── 燈號說明文字 ─────────────────────────────────────────────────────
        # 燈2
        if not sig["l2_available"]:
            l2_icon   = "➖"
            l2_detail = "無三大法人資料（FinLab 法人欄位不含此 ETF）"
        elif sig["l2_resonate"]:
            l2_icon   = "✅"
            l2_detail = "外資+投信共振買超"
        elif sig["l2_foreign"]:
            l2_icon   = "✅"
            l2_detail = f"外資獨買（{'牛市' if sig['l2_market_state'] == 'bull' else '熊市'}模式，投信未跟進）"
        elif sig["l2_trust"]:
            l2_icon   = "✅"
            l2_detail = "投信獨買（外資未跟進，半燈信號）"
        else:
            l2_icon   = "❌"
            l2_detail = "無明顯法人動向"

        # 燈4
        if sig.get("tech4_error"):
            l4_icon   = "❌"
            l4_detail = f"計算失敗：{sig['tech4_error']}"
        elif sig["l4_above"]:
            l4_icon   = "✅"
            qty_note  = "，帶量突破 ✅" if sig["l4_surge"] else f"，量比 {vol_s}（未放量）"
            l4_detail = f"現價 {price_s} > MA60 {ma60_s}（{dist_s}）{qty_note}"
        else:
            l4_icon   = "❌"
            near      = sig.get("l4_dist") is not None and sig["l4_dist"] >= -3.0
            l4_detail = (f"現價 {price_s} 低於 MA60 {ma60_s}（{dist_s}）"
                         + ("，距突破 < 3% 🔍" if near else ""))

        # 燈5
        if sig.get("rs_error"):
            l5_icon   = "❌"
            l5_detail = f"計算失敗：{sig['rs_error']}"
        elif sig["l5_lit"]:
            l5_icon   = "✅"
            l5_detail = f"RS-Ratio={rs_s}（vs {sig.get('l5_benchmark', 'TAIEX')}），{sig.get('l5_quad', '')}"
        else:
            l5_icon   = "❌"
            l5_detail = f"RS-Ratio={rs_s}（vs {sig.get('l5_benchmark', 'TAIEX')}，未達相對強勢），{sig.get('l5_quad', '')}"

        # 燈6
        if not sig["is_marginable"]:
            l6_icon   = "➖"
            l6_detail = "不適用（此 ETF 無融資資料）"
        elif not sig["l6_available"]:
            l6_icon   = "➖"
            l6_detail = "籌碼資料暫不可用"
        elif sig["l6_lit"]:
            l6_icon   = "✅"
            l6_detail = "融資↓ + 借券↓（籌碼往強手集中）"
        elif sig["l6_cover"]:
            l6_icon   = "✅"
            l6_detail = "借券回補中（空頭撤退早期信號）"
        else:
            l6_icon   = "❌"
            l6_detail = "未達籌碼集中條件"
        if sig.get("l6_add"):
            l6_detail += " ⚠️ （另有空頭加碼中）"

        # ── 五燈條件清單 ────────────────────────────────────────────────────
        lines += [
            "### 🔦 燈號分析（ETF 五燈制）",
            "",
            "| 燈號 | 名稱 | 狀態 | 說明 |",
            "|------|------|:----:|------|",
            "| 燈1 | 月營收 YoY 拐點 | ➖ | 不適用（ETF 無月營收資料） |",
            f"| 燈2 | 法人動向 | {l2_icon} | {l2_detail} |",
            "| 燈3 | 庫存循環偵測 | ➖ | 不適用（ETF 無庫存數據） |",
            f"| 燈4 | 技術突破 | {l4_icon} | {l4_detail} |",
            f"| 燈5 | 相對強度 RRG | {l5_icon} | {l5_detail} |",
            f"| 燈6 | 籌碼集中 | {l6_icon} | {l6_detail} |",
            f"| 燈7 | 宏觀環境（全局） | {_icon(sig['l7_signal'])} | {sig['l7_pos']}/{sig['l7_total']} 項宏觀指標達標 |",
            "",
        ]

        # ── 技術關鍵指標 ────────────────────────────────────────────────────
        bm_label = sig.get("l5_benchmark", "TAIEX")
        lines += [
            "### 📊 技術關鍵指標",
            "",
            "| 指標 | 數值 | 評估基準 |",
            "|------|------|----------|",
            f"| 最近收盤價 | `{price_s}` | — |",
            f"| MA60（60日均線） | `{ma60_s}` | 關鍵支撐/進場基準 |",
            f"| 距離 MA60 | `{dist_s}` | 0%~+10% 為甜蜜進場區 |",
            f"| 量比（最新/20MA均量） | `{vol_s}` | ≥ 1.5x 為有效放量 |",
            f"| RS-Ratio（vs {bm_label}） | `{rs_s}` | ≥ 1.0 表示跑贏基準 |",
            "",
        ]

        # ── 六維評分分解 ────────────────────────────────────────────────────
        sb = sig["score_breakdown"]
        dim_names = {
            "momentum":      "動能力（Momentum）",
            "relative_str":  "相對強度（Relative Strength）",
            "institutional": "法人共識（Institutional Consensus）",
            "macro":         "宏觀環境（Macro Filter）",
            "aum_trend":     "規模趨勢（AUM Trend）",
            "valuation":     "估值結構（Valuation/Structure）",
        }
        lines += [
            "### 🎓 六維學術評分",
            "",
            f"**總分**：`{score_s}` / `{SCORE_MAX:.0f}` 分　{_grade(score_r)}",
            "",
            "| 維度 | 得分 | 滿分 | 學術依據 |",
            "|------|:----:|:----:|---------|",
        ]
        for dim_key, (max_v, ref) in SCORE_DIMS.items():
            dim_v = sb.get(dim_key, 0.0)
            lines.append(
                f"| {dim_names[dim_key]} | {dim_v:.2f} | {max_v:.1f} | {ref} |"
            )
        lines.append("")

        # ── 進場建議 ────────────────────────────────────────────────────────
        stop_loss = ""
        if sig.get("ma60"):
            stop_loss = f"\n>\n> **參考停損**：收盤跌破 MA60（`{ma60_s}`）視為技術止損點。"

        lines += [
            "### 📋 進場建議",
            "",
            f"> {sig['rec_icon']} **{sig['recommendation']}**",
            ">",
            f"> {sig['rec_reason']}",
            ">",
            f"> 亮燈：**{sig['lit_count']}/{sig['total_lamps']}**（加權 {sig['lit_weighted']}）　"
            f"六維評分：**{score_s}/{SCORE_MAX:.0f}** {_grade(score_r)}",
            stop_loss,
            "",
        ]

        # ── 出場風險評估 ────────────────────────────────────────────────────
        exit_risk_val  = sig.get("exit_risk", 0.0)
        exit_icon_s    = sig.get("exit_icon", "🟢")
        exit_signal_s  = sig.get("exit_signal", "持有")
        exit_reason_s  = sig.get("exit_reason", "")
        exit_bd        = sig.get("exit_breakdown", {})
        exit_dim_names = {
            "tech_pressure":         "技術出場壓力",
            "rs_deterioration":      "相對強度弱化",
            "institutional_retreat": "法人撤退訊號",
            "macro_deterioration":   "宏觀環境惡化",
            "chipset_deterioration": "籌碼惡化",
        }
        exit_trigger_descs = {
            "tech_pressure": {
                3.0: "已跌破 MA60（最嚴峻出場信號）",
                1.5: "距 MA60 超買 >25%（均值回歸壓力大）",
                1.0: "超買 >15% 或接近跌破邊緣（-3%~0%）",
                0.0: "技術面正常",
            },
            "rs_deterioration": {
                2.0: "RRG 象限：落後（Left-Lower）",
                1.5: "RRG 象限：轉弱（Right-Lower）",
                0.5: "RRG 象限：改善（Left-Upper）",
                0.0: "RRG 象限：領先（Right-Upper）",
            },
            "institutional_retreat": {
                2.0: "外資+投信均未買進",
                1.0: "單邊買進（外資或投信擇一）",
                0.5: "法人資料不可用",
                0.0: "外資+投信共振買進中",
            },
            "chipset_deterioration": {
                1.0: "借券增加（空頭建倉信號）",
                0.0: "借券無顯著增加",
            },
        }
        lines += [
            "### ⚠️ 出場風險評估（五維學術模型）",
            "",
            f"> {exit_icon_s} **{exit_signal_s}**　　風險指數：`{exit_risk_val:.1f}` / `{EXIT_RISK_MAX:.0f}` 分",
            ">",
            f"> {exit_reason_s}",
            "",
            "| 風險維度 | 風險分 | 滿分 | 學術依據 | 觸發說明 |",
            "|---------|:------:|:----:|---------|---------|",
        ]
        for dim_key, (max_v, ref) in EXIT_RISK_DIMS.items():
            dim_v = exit_bd.get(dim_key, 0.0)
            if dim_key == "macro_deterioration":
                neg_count = sig.get("l7_total", 0) - sig.get("l7_pos", 0)
                trigger_desc = f"宏觀負面指標 {neg_count}/{sig.get('l7_total', 0)} 項"
            else:
                t_map = exit_trigger_descs.get(dim_key, {})
                trigger_desc = t_map.get(dim_v, f"風險分 {dim_v:.1f}")
            lines.append(
                f"| {exit_dim_names[dim_key]} | {dim_v:.2f} | {max_v:.1f} | {ref} | {trigger_desc} |"
            )
        lines += ["", "---", ""]

    # ─── 摘要對比表 ─────────────────────────────────────────────────────────
    lines += [
        "## 📋 ETF 整體摘要對比",
        "",
        "| ETF | 類型 | 燈2法人 | 燈4技術 | 燈5強勢 | 燈6籌碼 | 宏觀 | 亮燈數 | 六維評分 | 進場建議 | 出場風險 |",
        "|-----|------|:-------:|:-------:|:-------:|:-------:|:----:|:------:|:--------:|:--------:|:--------:|",
    ]
    for etf_id in etf_codes:
        sig = etf_signals.get(etf_id)
        if not sig:
            continue
        cat   = ETF_CATALOG.get(etf_id, {})
        etype = cat.get("type", "—")

        l2_ico = _icon(
            (sig["l2_resonate"] or sig["l2_foreign"] or sig["l2_trust"]) if sig["l2_available"] else None
        )
        l6_ico = _icon(
            (sig["l6_lit"] or sig["l6_cover"]) if sig["l6_available"] else None
        )
        gr = _grade(sig["total_score"] / SCORE_MAX)
        lines.append(
            f"| {etf_id} | {etype} "
            f"| {l2_ico} | {_icon(sig['l4_above'])} | {_icon(sig['l5_lit'])} "
            f"| {l6_ico} | {_icon(sig['l7_signal'])} "
            f"| **{sig['lit_count']}/{sig['total_lamps']}** "
            f"| {sig['total_score']:.1f}/{SCORE_MAX:.0f}（{gr}） "
            f"| {sig['rec_icon']} {sig['recommendation']} "
            f"| {sig.get('exit_icon', '🟢')} {sig.get('exit_risk', 0.0):.1f}/{EXIT_RISK_MAX:.0f} {sig.get('exit_signal', '持有')} |"
        )

    # ─── 學術引用 ────────────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 📚 學術引用",
        "",
        "| # | 文獻 | 應用維度 |",
        "|---|------|---------|",
        "| 1 | Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. *Journal of Finance*, 48(1), 65–91. | 動能力評分 |",
        "| 2 | Levy, R. A. (1967). Relative strength as a criterion for investment selection. *Journal of Finance*, 22(4), 595–610. | 相對強度 |",
        "| 3 | DeSouza, C., & Gokcan, S. (2004). Hedge fund investing: A quantitative approach to hedge fund manager selection and de-selection. *Journal of Alternative Investments*, 6(4), 37–48. | 相對強度 |",
        "| 4 | Nofsinger, J. R., & Sias, R. W. (1999). Herding and feedback trading by institutional and individual investors. *Journal of Finance*, 54(6), 2263–2295. | 法人共識 |",
        "| 5 | Fama, E. F., & French, K. R. (1989). Business conditions and expected returns on stocks and bonds. *Journal of Financial Economics*, 25(1), 23–49. | 宏觀環境 |",
        "| 6 | Rakowski, D., & Wang, X. (2009). The dynamics of short-term mutual fund flows and returns: A time-series and cross-sectional investigation. *Journal of Banking & Finance*, 33(7), 1228–1240. | 規模趨勢 |",
        "| 7 | Sharpe, W. F. (1992). Asset allocation: Management style and performance measurement. *Journal of Portfolio Management*, 18(2), 7–19. | 估值結構 |",
        "| 8 | French, K. R. (2008). Presidential address: The cost of active investing. *Journal of Finance*, 63(4), 1537–1573. | 費用率評分 |",
        "| 9 | Brock, W., Lakonishok, J., & LeBaron, B. (1992). Simple technical trading rules and the stochastic properties of stock returns. *Journal of Finance*, 47(5), 1731–1764. | 技術出場壓力 |",
        "| 10 | De Bondt, W. F. M., & Thaler, R. H. (1985). Does the stock market overreact? *Journal of Finance*, 40(3), 793–805. | 均值回歸壓力 |",
        "| 11 | Kaminski, K. M., & Lo, A. W. (2014). When do stop-loss rules stop losses? *Journal of Financial Markets*, 18, 234–254. | 籌碼惡化/停損規則 |",
        "| 12 | Sias, R. W. (2004). Institutional herding. *Review of Financial Studies*, 17(1), 165–206. | 法人撤退訊號 |",
        "",
        "---",
        "",
        f"*📌 本報告由 `scripts/etf_entry_check.py` 自動生成 · {now_str}*",
        "",
        "> **免責聲明**：本報告係量化技術分析，不構成任何投資建議。",
        "> ETF 投資仍需自行評估風險承受能力與投資目標。",
        "> yfinance 資料可能存在延遲或不完整，殖利率、費用率、AUM 等數據僅供參考，",
        "> 請以各 ETF 發行商公告之最新公開資訊為準。",
        "",
    ]

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 七、CLI 入口
# ════════════════════════════════════════════════════════════════════════════

def _parse_etfs() -> List[str]:
    parser = argparse.ArgumentParser(
        description="ETF 下週一進場分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python scripts/etf_entry_check.py 0050,0056,00878\n"
            "  python scripts/etf_entry_check.py --etfs 0050\n"
        ),
    )
    parser.add_argument(
        "etfs_positional", nargs="?", metavar="ETFS",
        help="逗號分隔的 ETF 代號，如 0050,0056,00878",
    )
    parser.add_argument(
        "--etfs", type=str, default=None,
        help="逗號分隔的 ETF 代號（與位置引數擇一）",
    )
    args = parser.parse_args()
    raw = args.etfs_positional or args.etfs
    if not raw:
        raw = input("請輸入 ETF 代號（逗號分隔，如 0050,0056）：").strip()
    etfs = [e.strip() for e in raw.replace("，", ",").split(",") if e.strip()]
    if not etfs:
        print("錯誤：未提供有效的 ETF 代號。", file=sys.stderr)
        sys.exit(1)
    return etfs


def main_etf() -> None:
    etf_codes = _parse_etfs()

    print(f"\n{'='*60}")
    print(f"📈 ETF 進場分析：{', '.join(etf_codes)}")
    print(f"{'='*60}\n")

    import src.config as config
    from src.data_fetcher import DataFetcher
    from scripts.stock_entry_check import _compute_lamp4_stock

    print(f"💾 yfinance 快取目錄：{_YF_CACHE_DIR}")

    print("🔑 連線 FinLab...")
    fetcher = DataFetcher()
    if not fetcher.login():
        print("❌ FinLab 登入失敗，請確認 .env 中的 FINLAB_API_TOKEN。", file=sys.stderr)
        sys.exit(1)

    print("🗺️  建立 ETF 板塊地圖...")
    etf_map, etf_sector_info = _build_etf_map(etf_codes)

    print("🔦 執行 ETF 分析器（燈2/5/6/7）...")
    analysis = _run_etf_analyzers(fetcher, etf_map, config)

    print("\n📊 個別 ETF 指標計算...")
    etf_signals: Dict[str, Any] = {}

    for etf_id in etf_codes:
        sector_id = etf_sector_info[etf_id][0]

        print(f"  [{etf_id}] 燈4 技術指標（MA60 + 量比）...")
        tech4 = _compute_lamp4_stock(etf_id, fetcher, config)

        print(f"  [{etf_id}] 燈5 相對強度（RS-Ratio）...")
        bm_id = None if etf_id in WIDE_BASE_ETFS else "0050"
        rs_data = _compute_rs_etf(etf_id, fetcher, config, benchmark_id=bm_id)

        print(f"  [{etf_id}] yfinance 元資料（快取於 %TEMP%）...")
        ymeta = _fetch_etf_yf_metadata(etf_id)
        if ymeta:
            dy_show = f"{ymeta.get('dividend_yield', 0):.1%}" if ymeta.get("dividend_yield") else "N/A"
            er_show = f"{ymeta.get('expense_ratio', 0):.3%}" if ymeta.get("expense_ratio") else "N/A"
            print(f"    ✅ 殖利率={dy_show}  費用率={er_show}")
        else:
            print("    ⚠️  yfinance 資料不可用（不影響主要分析）")

        print(f"  [{etf_id}] 彙整信號與六維評分...")
        etf_signals[etf_id] = _extract_etf_signals(
            etf_id=etf_id,
            sector_id=sector_id,
            analysis=analysis,
            tech4=tech4,
            rs_data=rs_data,
            ymeta=ymeta,
            fetcher=fetcher,
            config=config,
        )

    print("\n📝 產生 Markdown 報告...")
    run_time = datetime.now()
    md = _generate_etf_markdown(etf_codes, etf_signals, analysis["macro"], run_time)

    filename = f"ETF進場分析_{run_time.strftime('%Y%m%d_%H%M')}.md"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(md, encoding="utf-8")

    # ── 終端摘要
    print(f"\n{'='*60}")
    print("📋 ETF 進場建議摘要：")
    for etf_id in etf_codes:
        sig = etf_signals.get(etf_id, {})
        if sig:
            print(
                f"  {etf_id:>6}：{sig['rec_icon']} {sig['recommendation']:<20} "
                f"({sig['lit_count']}/{sig['total_lamps']} 燈)  "
                f"六維評分 {sig['total_score']:.1f}/{SCORE_MAX:.0f}  {_grade(sig['total_score'] / SCORE_MAX)}  "
                f"｜出場 {sig.get('exit_icon', '🟢')} {sig.get('exit_risk', 0.0):.1f}/{EXIT_RISK_MAX:.0f} {sig.get('exit_signal', '持有')}"
            )
    print(f"{'='*60}")
    print(f"\n✅ 報告已儲存：{out_path.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main_etf()
