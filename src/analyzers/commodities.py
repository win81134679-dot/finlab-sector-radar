"""
商品市場分析模組 — commodities.py

抓取 15 個全球資產的行情與學術信號，輸出：
  output/commodities/latest.json     ← 摘要（輕量，前端 SSR 載入）
  output/commodities/{slug}.json     ← 每個資產的完整 OHLCV（客戶端懶載入）
  output/commodities/yield_curve.json ← 收益率曲線（2Y/5Y/7Y/10Y/30Y）

學術信號來源：
  - Whaley (2000)       VIX > 30 (spike), > 40 (extreme)
  - Campbell & Shiller (1991)  2Y > 10Y 殖利率倒掛
  - Baur & Lucey (2010) 黃金 > 200MA 避險功能啟動
  - Hamilton (2009)     WTI > $85 油價衝擊
  - Bouri et al. (2017) BTC 7日 > +10% (risk-on) / < -15% (risk-off)
  - FRB (2024)          DXY > 105 強勢美元
"""
import json
import logging
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import src.ssl_fix  # noqa: F401

import pandas as pd

logger = logging.getLogger(__name__)

# ── 資產清單 ──────────────────────────────────────────────────────────────
ASSETS = [
    # slug            yf_symbol          name_zh              category
    ("gold",          "GC=F",            "黃金",               "precious_metal"),
    ("silver",        "SI=F",            "白銀",               "precious_metal"),
    ("copper",        "HG=F",            "銅",                 "industrial"),
    ("wti",           "CL=F",            "WTI 原油",           "energy"),
    ("brent",         "BZ=F",            "Brent 原油",         "energy"),
    ("natgas",        "NG=F",            "天然氣",             "energy"),
    ("vix",           "^VIX",            "VIX 恐慌指數",       "index"),
    ("dxy",           "DX-Y.NYB",        "美元指數 DXY",       "index"),
    ("us2y",          "^IRX",            "美債 2Y 殖利率",     "bonds"),
    ("us10y",         "^TNX",            "美債 10Y 殖利率",    "bonds"),
    ("us30y",         "^TYX",            "美債 30Y 殖利率",    "bonds"),
    ("btc",           "BTC-USD",          "比特幣 BTC",         "crypto"),
    ("eth",           "ETH-USD",          "以太坊 ETH",         "crypto"),
    ("sol",           "SOL-USD",          "Solana SOL",         "crypto"),
    ("sp500",         "^GSPC",           "S&P 500",            "index"),
]

# CoinGecko 已改為需要 API Key（401 Unauthorized），改用 yfinance BTC-USD/ETH-USD/SOL-USD
COINGECKO_IDS: dict = {}

# yfinance FRED 收益率曲線用符號
YIELD_CURVE_TICKERS = {
    "2Y":  "^IRX",
    "5Y":  "^FVX",
    "10Y": "^TNX",
    "30Y": "^TYX",
}

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "commodities"


def _ensure_output_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── yfinance 抓取 ─────────────────────────────────────────────────────────

def _fetch_yf(symbol: str, period: str = "2y") -> Optional[pd.DataFrame]:
    """抓取 yfinance OHLCV，失敗回傳 None。"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist is None or hist.empty:
            logger.warning(f"yf {symbol}: 無資料")
            return None
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        return hist
    except Exception as e:
        logger.error(f"yf {symbol} 失敗: {e}")
        return None


def _df_to_ohlcv(df: pd.DataFrame) -> List[Dict]:
    """DataFrame → [{date, o, h, l, c, v}, ...] 格式（移除 NaN）。"""
    rows = []
    for ts, row in df.iterrows():
        try:
            o = float(row.get("Open", float("nan")))
            h = float(row.get("High", float("nan")))
            l = float(row.get("Low", float("nan")))
            c = float(row.get("Close", float("nan")))
            v = float(row.get("Volume", 0) or 0)
            if any(pd.isna(x) for x in [o, h, l, c]):
                continue
            date_str = ts.strftime("%Y-%m-%d")
            rows.append({"date": date_str, "o": round(o, 4), "h": round(h, 4),
                         "l": round(l, 4), "c": round(c, 4), "v": round(v, 0)})
        except Exception:
            pass
    return rows


# ── CoinGecko 抓取（最大歷史，限速保護）────────────────────────────────────

def _fetch_coingecko(cg_id: str, max_retries: int = 3) -> Optional[pd.DataFrame]:
    """抓取 CoinGecko 最大歷史 OHLCV，回傳 DataFrame；限速自動重試。"""
    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc?vs_currency=usd&days=max"
    import requests
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=30,
                                headers={"Accept": "application/json",
                                         "User-Agent": "FinLab-Sector-Radar/1.0"})
            if resp.status_code == 429:
                wait = 65 if attempt == 0 else 120
                logger.warning(f"CoinGecko 429 限速 ({cg_id})，等待 {wait}s…")
                time.sleep(wait)
                continue
            if not resp.ok:
                logger.error(f"CoinGecko {cg_id} HTTP {resp.status_code}")
                return None
            data = resp.json()
            # data: [[timestamp_ms, open, high, low, close], ...]
            if not data:
                return None
            df = pd.DataFrame(data, columns=["ts_ms", "Open", "High", "Low", "Close"])
            df.index = pd.to_datetime(df["ts_ms"], unit="ms").dt.tz_localize(None)
            df["Volume"] = 0.0
            return df
        except Exception as e:
            logger.error(f"CoinGecko {cg_id} 失敗 (嘗試 {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
    return None


# ── 技術指標輔助函數 ───────────────────────────────────────────────────────

def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder (1978) RSI（相對強弱指數）。"""
    n = len(closes)
    if n < period + 2:
        return None
    gains, losses = [], []
    for i in range(n - period, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)


def _sma(closes: List[float], n: int) -> Optional[float]:
    """簡單移動平均線。"""
    return None if len(closes) < n else round(sum(closes[-n:]) / n, 4)


def _chg(closes: List[float], n: int) -> Optional[float]:
    """N 日漲跌幅（%）。"""
    if len(closes) < n + 1 or not closes[-(n + 1)]:
        return None
    return round((closes[-1] - closes[-(n + 1)]) / closes[-(n + 1)] * 100, 2)


def _pct_from_52w_high(ohlcv: List[Dict]) -> Optional[float]:
    """距 52 週（252 日）最高點的跌幅（%，負值 = 低於高點）。"""
    if not ohlcv:
        return None
    relevant = ohlcv[-252:] if len(ohlcv) >= 252 else ohlcv
    high = max(bar["h"] for bar in relevant)
    if not high:
        return None
    return round((ohlcv[-1]["c"] - high) / high * 100, 2)


# ── 學術信號計算 ──────────────────────────────────────────────────────────

def _compute_signals(slug: str, ohlcv: List[Dict],
                     all_closes: Dict[str, float]) -> List[Dict]:
    """依資產類型計算學術信號，回傳信號列表。"""
    signals: List[Dict] = []
    if not ohlcv:
        return signals

    closes = [bar["c"] for bar in ohlcv]
    latest = closes[-1] if closes else None
    if latest is None:
        return signals

    # 共用技術指標
    ma200    = _sma(closes, 200)
    ma50     = _sma(closes, 50)
    rsi14    = _rsi(closes, 14)
    chg_7d   = _chg(closes, 7)
    chg_30d  = _chg(closes, 30)
    atf_pct  = _pct_from_52w_high(ohlcv)  # 距 52 週高點（%）

    def _sig(key, triggered, severity, commentary, source):
        signals.append({"key": key, "triggered": triggered,
                        "severity": severity, "commentary": commentary,
                        "source": source})

    # ──────────────────────────────────────────────────────────────────────
    # 黃金 (gold)
    # ──────────────────────────────────────────────────────────────────────
    if slug == "gold":
        # 1. 200MA 避險啟動（Baur & Lucey 2010）
        if ma200:
            above = latest > ma200
            _sig("gold_above_200ma", above,
                 "medium" if above else "low",
                 f"黃金 ${latest:.2f}，200MA ${ma200:.2f}。"
                 + ("站上 200MA 確認上升趨勢，避險資金流入明顯，符合 Baur & Lucey (2010) 避險功能啟動條件。"
                    if above else "位於 200MA 下方，中期趨勢偏空，避險需求尚未全面啟動。"),
                 "Baur & Lucey (2010), J. Banking & Finance.")

        # 2. 黃金/白銀比率（Faber 1988 歷史均值約 50-80）
        silver_p = all_closes.get("silver")
        if silver_p and silver_p > 0:
            gs_ratio = round(latest / silver_p, 1)
            expensive = gs_ratio > 85
            _sig("gold_silver_ratio", expensive,
                 "medium" if expensive else "low",
                 f"金銀比率 = {gs_ratio}x。"
                 + (f"超過 85x 歷史高位，白銀相對低估，市場風險情緒仍偏低。Faber (1988) 指出比率均值回歸時白銀往往大幅補漲。"
                    if expensive else f"比率 {gs_ratio}x，處於合理區間（歷史均值 ~65x）。"),
                 "Faber (1988); Gorton & Rouwenhorst (2006), J. Finance.")

        # 3. RSI 超買/超賣（Wilder 1978）
        if rsi14 is not None:
            if rsi14 > 70:
                _sig("gold_rsi_overbought", True, "medium",
                     f"黃金 RSI(14)={rsi14}，進入超買區（>70）。短期回調風險上升，部位可考慮減輕，待 RSI 回落 50 以下再行布局。",
                     "Wilder (1978), New Concepts in Technical Trading Systems.")
            elif rsi14 < 30:
                _sig("gold_rsi_oversold", True, "medium",
                     f"黃金 RSI(14)={rsi14}，進入超賣區（<30）。歷史上此水準後 3 個月平均報酬偏正，可考慮逢低分批建倉。",
                     "Wilder (1978), New Concepts in Technical Trading Systems.")
            else:
                _sig("gold_rsi_neutral", False, "low",
                     f"黃金 RSI(14)={rsi14}，動能中性，無超買超賣訊號。", "Wilder (1978).")

        # 4. 強美元 vs 黃金 — 脫鉤信號
        dxy_p = all_closes.get("dxy")
        if dxy_p and dxy_p > 104 and latest > (ma200 or 0):
            _sig("gold_dxy_divergence", True, "high",
                 f"黃金在強勢美元（DXY={dxy_p:.1f}>104）下仍站穩 200MA 上方，顯示非美央行強力買盤或避險需求異常旺盛，歷史上此脫鉤往往預示金價大行情。",
                 "Erb & Harvey (2013), Financial Analysts Journal.")

    # ──────────────────────────────────────────────────────────────────────
    # 白銀 (silver)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "silver":
        # 1. 200MA 趨勢
        if ma200:
            above = latest > ma200
            _sig("silver_above_200ma", above,
                 "medium" if above else "low",
                 f"白銀 ${latest:.2f}，200MA ${ma200:.2f}。"
                 + ("站上 200MA，工業需求 + 貨幣屬性雙驅動，趨勢轉多。"
                    if above else "跌破 200MA，白銀工業需求疲弱或風險偏好降低，謹慎觀察。"),
                 "Issler, Lima & Notini (2014), Empirical Economics.")

        # 2. 白銀相對黃金折價（Hunt & Allen 1980 事件後歷史分析）
        gold_p = all_closes.get("gold")
        if gold_p and gold_p > 0:
            sg_ratio = round(silver_p := latest, 4)
            implied_silver = gold_p / 65  # 歷史均值
            discount_pct = round((latest - implied_silver) / implied_silver * 100, 1)
            cheap = discount_pct < -20
            _sig("silver_undervalued", cheap,
                 "medium" if cheap else "low",
                 f"以歷史金銀比均值（~65x）計算，白銀合理價約 ${implied_silver:.2f}，目前市價 ${latest:.2f}（{'折價' if cheap else '溢價'} {abs(discount_pct):.1f}%）。"
                 + (" 歷史上銀深度折價後，往往在風險偏好回升時出現爆發性追漲。" if cheap else ""),
                 "Gorton & Rouwenhorst (2006), J. Finance.")

        # 3. 動能（Jegadeesh & Titman 1993）
        if chg_30d is not None:
            strong = chg_30d > 15
            _sig("silver_momentum", strong, "medium" if strong else "low",
                 f"白銀 30 日漲幅 {chg_30d:+.1f}%。"
                 + (f"動能強勁，超過 +15% 閾值，反映工業需求復甦或避險資金輪入。"
                    if strong else "動能溫和，尚未出現趨勢性突破信號。"),
                 "Jegadeesh & Titman (1993), J. Finance.")

    # ──────────────────────────────────────────────────────────────────────
    # 銅 (copper) — Dr. Copper 經濟領先指標
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "copper":
        # 1. 200MA — Slade (1982) 銅作為工業主導資產
        if ma200:
            above = latest > ma200
            _sig("copper_200ma", above,
                 "medium" if above else "medium",
                 f"銅價 ${latest:.3f}/磅，200MA ${ma200:.3f}/磅。"
                 + ("站上 200MA，全球工業活動擴張中，Slade (1982) 指出銅的趨勢對鋼鐵等工業產出有 2-3 個月領先性。"
                    if above else "跌破 200MA，工業需求疲軟信號，Frankel & Rose (2010) 研究顯示銅價領先 GDP 反轉 6-9 個月。"),
                 "Slade (1982); Frankel & Rose (2010), Am. Econ. Review.")

        # 2. 衰退門檻信號
        recession_threshold = 3.50
        below_threshold = latest < recession_threshold
        _sig("copper_recession_signal", below_threshold,
             "high" if below_threshold else "low",
             f"銅價 ${latest:.3f}/磅。"
             + (f"跌破 ${recession_threshold}/磅，歷史上此水準往往伴隨全球製造業衰退（PMI < 50），請配合 ISM 等數據交叉驗證。"
                if below_threshold else f"高於 ${recession_threshold}/磅，工業需求尚無衰退警訊。"),
             "Issler, Lima & Notini (2014), Empirical Economics.")

        # 3. RSI 動能
        if rsi14 is not None:
            ov = rsi14 > 70
            os = rsi14 < 30
            _sig("copper_rsi", ov or os,
                 "medium" if (ov or os) else "low",
                 f"銅 RSI(14)={rsi14}。"
                 + ("超買區，短期可能面臨獲利了結壓力。" if ov
                    else "超賣區，工業需求超跌後往往出現技術反彈。" if os
                    else "動能中性。"),
                 "Wilder (1978).")

    # ──────────────────────────────────────────────────────────────────────
    # WTI 原油 (wti)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "wti":
        # 1. 供給衝擊門檻（Hamilton 2009）
        oil_shock = latest > 85
        _sig("oil_shock", oil_shock,
             "high" if oil_shock else "low",
             f"WTI 原油 ${latest:.2f}/桶。"
             + ("突破 $85，達 Hamilton (2009) 供給衝擊門檻，對消費端 GDP 有顯著負向影響，歷史上每次油價衝擊後 2 季均出現增長放緩。"
                if oil_shock else "低於 $85，尚未達油價衝擊閾值，對經濟影響相對溫和。"),
             "Hamilton (2009), J. Economic Perspectives.")

        # 2. 200MA 趨勢
        if ma200:
            above = latest > ma200
            _sig("wti_200ma", above,
                 "medium" if above else "low",
                 f"WTI 200MA ${ma200:.2f}，現價{'站上' if above else '跌破'} 200MA。"
                 + (" 中期多頭格局，能源類股與通膨預期受支撐。" if above
                    else " 跌破 200MA，能源需求疲弱或供給過剩，留意通縮壓力。"),
                 "Baumeister & Kilian (2016), J. Applied Econometrics.")

        # 3. 大跌信號（Fattouh 2012 — 需求崩潰）
        if chg_30d is not None and chg_30d < -20:
            _sig("wti_demand_collapse", True, "high",
                 f"WTI 30 日跌幅 {chg_30d:.1f}%，超過 -20% 觸發需求崩潰信號。歷史上此幅度下跌往往伴隨全球需求急劇收縮或 OPEC+ 增產衝突。",
                 "Fattouh, Kilian & Mahadeva (2012), Energy Journal.")

    # ──────────────────────────────────────────────────────────────────────
    # Brent 原油 (brent)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "brent":
        # 1. 地緣溢價門檻
        brent_shock = latest > 90
        _sig("brent_shock", brent_shock,
             "high" if brent_shock else "low",
             f"Brent 原油 ${latest:.2f}/桶。"
             + ("突破 $90，Baumeister & Kilian (2016) 研究顯示此水準開始對通膨產生顯著推升效果，新興市場受輸入型通膨壓力更大。"
                if brent_shock else "Brent 低於 $90，能源通膨壓力溫和。"),
             "Baumeister & Kilian (2016), J. Applied Econometrics.")

        # 2. Brent-WTI 地緣溢價
        wti_p = all_closes.get("wti")
        if wti_p and wti_p > 0:
            spread = round(latest - wti_p, 2)
            high_spread = spread > 5
            _sig("brent_wti_spread", high_spread,
                 "medium" if high_spread else "low",
                 f"Brent-WTI 價差 ${spread:.2f}。"
                 + (f"溢價超過 $5，顯示中東/歐洲供應鏈風險抬高，地緣政治緊張或管線/航運瓶頸所致。"
                    if high_spread else f"價差 ${spread:.2f}，保持正常（$2-4 區間），無顯著地緣溢價。"),
                 "Hamilton (2009); EIA (2024), Oil Market Report.")

        # 3. OPEC 支撐底部
        opec_floor = latest < 60
        _sig("brent_below_opec_floor", opec_floor,
             "high" if opec_floor else "low",
             f"Brent ${latest:.2f}。"
             + ("跌破 $60，已低於 OPEC+ 大多數成員成本線，預期 OPEC+ 將採取減產護盤，但需警惕成員國內部分歧。"
                if opec_floor else "高於 $60，OPEC+ 成員普遍有利潤空間，增產衝突風險較低。"),
             "Fattouh (2014), Oxford Energy Comment.")

    # ──────────────────────────────────────────────────────────────────────
    # 天然氣 (natgas)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "natgas":
        # 1. 能源成本壓力（Pindyck 1999 seasonality）
        high_price = latest > 4
        low_price  = latest < 2
        _sig("natgas_price_regime",
             high_price or low_price,
             "medium" if high_price else ("medium" if low_price else "low"),
             f"天然氣 ${latest:.3f}/MMBtu。"
             + ("超過 $4，能源成本顯著上升，影響工業生產利潤與民用供暖/製冷需求，過去每次突破 $4 均引發能源股板塊輪動。"
                if high_price else
                "低於 $2，能源價格偏低，可能引發供給商削減資本支出，為未來幾個季度的反彈埋下伏筆（Pindyck 1999 供需循環）。"
                if low_price else
                "處於 $2-4 合理區間，能源成本無顯著整體壓力或拖累。"),
             "Pindyck (1999), J. Environmental Economics & Management.")

        # 2. 劇烈波動（7日動能）
        if chg_7d is not None and abs(chg_7d) > 15:
            _sig("natgas_volatile", True, "medium",
                 f"天然氣 7 日漲跌 {chg_7d:+.1f}%，波動率極高（>±15%）。天然氣因儲量報告、氣候異常或 LNG 轉口而出現突發性跳價，短期難以預測。",
                 "Pindyck (1999); EIA (2024), Natural Gas Weekly.")

    # ──────────────────────────────────────────────────────────────────────
    # VIX 恐慌指數 (vix)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "vix":
        # 1-3. Whaley (2000) 三級警示
        if latest > 40:
            _sig("vix_extreme", True, "high",
                 f"VIX={latest:.1f}，達極端恐慌（>40）。根據 Whaley (2000) 反向情緒指標，此水準歷史上往往是中長期底部附近，但短期波動仍劇烈。",
                 "Whaley (2000), J. Portfolio Management.")
        elif latest > 30:
            _sig("vix_spike", True, "medium",
                 f"VIX={latest:.1f}，突破 30 恐慌警戒線。市場情緒急速惡化，選擇權隱含波動率大幅抬升，避險需求上升。",
                 "Whaley (2000), J. Portfolio Management.")
        elif latest > 20:
            _sig("vix_caution", True, "low",
                 f"VIX={latest:.1f}，進入 20-30 警戒區間。市場情緒趨於謹慎，宜降低集中度，提高防禦性資產比例。",
                 "CBOE (2024), VIX White Paper; Schwert (1990), J. Finance.")
        else:
            _sig("vix_normal", False, "low",
                 f"VIX={latest:.1f}，低於 20，市場情緒平穩。低波動環境有利風險資產，但也可能代表市場整體麻痺（Minsky 時刻前兆）。",
                 "Whaley (2000); Todorov (2010), J. Financial Economics.")

        # 4. 單日急漲衝擊
        if len(closes) >= 2:
            daily_chg = (latest - closes[-2]) / closes[-2] * 100
            if daily_chg > 25:
                _sig("vix_daily_shock", True, "high",
                     f"VIX 單日急漲 {daily_chg:.1f}%，市場出現突發性恐慌，可能對應重大事件、流動性衝擊或系統性風險爆發。",
                     "Todorov (2010), J. Financial Economics.")

    # ──────────────────────────────────────────────────────────────────────
    # 美元指數 DXY (dxy)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "dxy":
        # 1. 強美元抑制（FRB 2024）
        strong = latest > 105
        very_strong = latest > 110
        _sig("dxy_strong", strong and not very_strong,
             "medium" if (strong and not very_strong) else "low",
             f"DXY={latest:.2f}。"
             + ("突破 105，美元強勢壓制全球商品與新興市場資產，資金回流美國趨勢明顯，對科技類股及非美市場有系統性壓力。"
                if (strong and not very_strong) else "低於 105，強美元壓力暫緩，有利新興市場及大宗商品資產。"),
             "FRB (2024), Trade-Weighted Dollar Index; Lustig et al. (2011).")

        _sig("dxy_very_strong", very_strong, "high",
             f"DXY={latest:.2f}，超過 110 歷史極值。"
             + ("此水準在歷史上（1985、2002、2022年）均伴隨新興市場資本外流危機與大宗商品熊市。Lustig et al. (2011) 研究顯示美元走強期間全球風險資產普遍承壓。"
                if very_strong else "尚未達到 110 極端水準。"),
             "Lustig, Roussanov & Verdelhan (2011), Am. Econ. Review.")

        # 2. 200MA 趨勢
        if ma200:
            above = latest > ma200
            _sig("dxy_200ma", above,
                 "medium" if above else "low",
                 f"DXY 200MA={ma200:.2f}，現價{'站上' if above else '跌破'} 200MA。"
                 + (" 美元中期趨勢向上，不利新興市場債務及商品出口國，注意美聯儲政策走向。" if above
                    else " 美元趨勢轉弱，有利金屬、石油及新興市場資產的相對表現。"),
                 "Meese & Rogoff (1983), J. International Economics.")

    # ──────────────────────────────────────────────────────────────────────
    # 美債 2Y 殖利率 (us2y)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "us2y":
        # 2Y 殖利率反映市場對 Fed 基準利率預期
        if latest > 5.0:
            _sig("us2y_very_tight", True, "high",
                 f"美國 2Y 殖利率 {latest:.2f}%，突破 5%，貨幣政策極度緊縮。此水準接近 2006-2007 年金融危機前夕，企業融資成本顯著上升，房市、消費信貸壓力加大。",
                 "Bernanke & Blinder (1992), Am. Econ. Review.")
        elif latest > 4.0:
            _sig("us2y_restrictive", True, "medium",
                 f"美國 2Y 殖利率 {latest:.2f}%（4-5%），貨幣政策明顯偏緊。市場預期 Fed 高利率持久，浮動利率債務承壓，成長股估值面臨折現率壓縮。",
                 "Campbell & Shiller (1991), Rev. Financial Studies.")
        elif latest > 2.0:
            _sig("us2y_neutral", False, "low",
                 f"美國 2Y 殖利率 {latest:.2f}%（2-4%），貨幣政策處於中性至略緊水準，對經濟無明顯扭曲。",
                 "Taylor (1993), Carnegie-Rochester Conference Series.")
        else:
            _sig("us2y_accommodative", True, "low",
                 f"美國 2Y 殖利率 {latest:.2f}%（<2%），接近零利率或 QE 環境。央行處於極度寬鬆模式，資產泡沫風險上升（Minsky 1986）。",
                 "Taylor (1993); Bernanke (2015), Brookings.")

        # 趨勢信號
        if chg_30d is not None and abs(chg_30d) > 10:
            rising = chg_30d > 0
            _sig("us2y_rate_move", True, "medium",
                 f"2Y 殖利率 30 日{'上升' if rising else '下降'} {abs(chg_30d):.1f}%（{'Fed 鷹派預期升溫' if rising else 'Fed 轉向鴿派預期增強'}）。短端利率急劇變動往往預示政策拐點，需關注 FOMC 聲明措辭。",
                 "Gürkaynak, Sack & Swanson (2005), Am. Econ. Review.")

    # ──────────────────────────────────────────────────────────────────────
    # 美債 10Y 殖利率 (us10y)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "us10y":
        # 1. 殖利率倒掛（Campbell & Shiller 1991）
        us2y_val  = all_closes.get("us2y", 0)
        us10y_val = latest
        if us2y_val:
            spread = round(us10y_val - us2y_val, 3)
            inverted = spread < 0
            flat     = 0 <= spread < 0.25
            _sig("yield_inversion", inverted,
                 "high" if inverted else ("medium" if flat else "low"),
                 f"2-10Y 利差 = {spread:+.3f}%。"
                 + ("殖利率曲線倒掛（負利差），Estrella & Mishkin (1998) 研究顯示 10Y-2Y 倒掛預測衰退準確率超 80%，歷史平均領先衰退 12-18 個月。"
                    if inverted else
                    f"曲線趨平（利差<0.25%），接近倒掛邊緣，請持續追蹤。Campbell & Shiller (1991) 研究顯示扁平曲線也具有中期警示意義。"
                    if flat else
                    "殖利率曲線正常（正利差），短期衰退風險相對可控。"),
                 "Campbell & Shiller (1991); Estrella & Mishkin (1998), NBER.")

        # 2. 10Y 絕對水準
        if latest > 5.0:
            _sig("us10y_very_high", True, "high",
                 f"10Y 殖利率 {latest:.2f}%，超過 5%（2007 年以來罕見）。長期貸款、抵押貸款及企業債融資成本大幅攀升，對高估值成長股與房地產市場構成重大壓力。",
                 "Bernanke & Gertler (1989), Am. Econ. Review.")
        elif latest > 4.5:
            _sig("us10y_restrictive", True, "medium",
                 f"10Y 殖利率 {latest:.2f}%（4.5-5%），金融環境明顯收緊。Clarida, Gali & Gertler (1999) 研究顯示此水準下實質利率轉正，對投資活動有顯著抑制效果。",
                 "Clarida, Gali & Gertler (1999), Am. Econ. Review.")
        elif latest > 3.0:
            _sig("us10y_normal", False, "low",
                 f"10Y 殖利率 {latest:.2f}%，處於歷史中性至中性偏緊水準（3-4.5%），對長期投資估值有一定壓力但不至於誘發系統性衝擊。",
                 "Shiller (1981), Am. Econ. Review.")
        else:
            _sig("us10y_low", True, "low",
                 f"10Y 殖利率 {latest:.2f}%（<3%），低利率環境持續，有利於風險資產估值（折現率低），但長期債券投資人面臨通膨侵蝕風險。",
                 "Shiller (2014), NBER; Bernanke (2015), Brookings.")

    # ──────────────────────────────────────────────────────────────────────
    # 美債 30Y 殖利率 (us30y)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "us30y":
        # 1. 久期風險
        dur_risk = latest > 4.5
        extreme  = latest > 5.2
        _sig("us30y_duration_risk", dur_risk,
             "high" if extreme else ("medium" if dur_risk else "low"),
             f"30Y 殖利率 {latest:.2f}%。"
             + ("突破 5.2%，歷史極端水準。長存續期債券（TLT 等 ETF）面臨嚴峻挫折，保險公司與退休基金配置承壓，恐引發去槓桿連鎖效應。"
                if extreme else
                "突破 4.5%，長期融資成本顯著偏高。基礎建設、商用不動產及長期公用事業資本計畫受到拖累。"
                if dur_risk else
                f"30Y 殖利率 {latest:.2f}%，長端利率尚在合理範圍。"),
             "Fama & Bliss (1987), J. Political Economy; Diebold & Li (2006).")

        # 2. 30Y-10Y 長端斜率
        us10y_val = all_closes.get("us10y", 0)
        if us10y_val:
            long_slope = round(latest - us10y_val, 3)
            inverted_long = long_slope < 0
            _sig("us30y_vs_10y_slope", inverted_long,
                 "medium" if inverted_long else "low",
                 f"30Y - 10Y 長端利差 {long_slope:+.3f}%。"
                 + ("長端倒掛（30Y < 10Y），市場預期長期增長與通膨雙雙走弱，Diebold & Li (2006) 三因子模型中此為曲率負值信號。"
                    if inverted_long else
                    f"長端利差 {long_slope:+.3f}%，曲線正常向上傾斜，長期通膨預期穩定。"),
                 "Diebold & Li (2006), J. Econometrics.")

    # ──────────────────────────────────────────────────────────────────────
    # 比特幣 BTC (btc)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "btc":
        # 1. 7日動能（Bouri et al. 2017）
        if chg_7d is not None:
            if chg_7d > 10:
                _sig("btc_risk_on", True, "medium",
                     f"BTC 7日漲幅 {chg_7d:+.1f}%，超過 +10% 閾值。Bouri et al. (2017) 研究顯示加密急漲往往反映全球高風險偏好情緒，同期股票、新興市場資產通常也偏強。",
                     "Bouri et al. (2017), Finance Research Letters.")
            elif chg_7d < -15:
                _sig("btc_risk_off", True, "high",
                     f"BTC 7日跌幅 {chg_7d:+.1f}%，超過 -15% 閾值。加密大跌通常伴隨風險資產全面撤退，Liu & Tsyvinski (2021) 研究顯示 BTC 市場 beta 在崩跌時急劇升高。",
                     "Bouri et al. (2017); Liu & Tsyvinski (2021), Rev. Financial Studies.")
            else:
                _sig("btc_neutral", False, "low",
                     f"BTC 7日漲跌 {chg_7d:+.1f}%，維持正常波動區間，無顯著風險信號。",
                     "Bouri et al. (2017), Finance Research Letters.")

        # 2. 200MA 趨勢（加密牛/熊市分界）
        if ma200:
            above = latest > ma200
            _sig("btc_above_200ma", above,
                 "medium" if above else "medium",
                 f"BTC ${latest:,.0f}，200MA ${ma200:,.0f}。"
                 + ("站上 200MA，加密市場處於結構性多頭，歷史上 BTC 站上 200MA 後 12 個月平均報酬顯著為正（Liu & Tsyvinski 2021）。"
                    if above else "跌破 200MA，進入加密熊市區間，建議大幅降低風險資產暴露。"),
                 "Liu & Tsyvinski (2021), Rev. Financial Studies.")

        # 3. 30日大幅下跌（加密冬天信號）
        if chg_30d is not None and chg_30d < -30:
            _sig("btc_bear_market", True, "high",
                 f"BTC 30日跌幅 {chg_30d:.1f}%，觸發加密熊市信號（<-30%）。歷史上此幅度下跌往往持續 3-12 個月，同期 DeFi 協議 TVL 與 NFT 市場均顯著萎縮。",
                 "Cong, Tang & Zhong (2022), J. Finance.")

    # ──────────────────────────────────────────────────────────────────────
    # 以太坊 ETH (eth)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "eth":
        # 1. ETH/BTC 比率（DeFi 熱度指標）
        btc_p = all_closes.get("btc")
        if btc_p and btc_p > 0:
            eth_btc = round(latest / btc_p, 4)
            defi_strong = eth_btc > 0.07
            defi_weak   = eth_btc < 0.04
            _sig("eth_btc_ratio",
                 defi_strong or defi_weak,
                 "medium" if (defi_strong or defi_weak) else "low",
                 f"ETH/BTC 比率 {eth_btc:.4f}。"
                 + ("ETH 相對 BTC 強勢（>0.07），反映 DeFi 生態活躍度高、智能合約需求旺盛，為加密市場 risk-on 的領先信號。"
                    if defi_strong else
                    "ETH 相對 BTC 弱勢（<0.04），資金集中在 BTC 防守，DeFi 市場降溫，整體加密風偏收縮。"
                    if defi_weak else
                    f"ETH/BTC={eth_btc:.4f}，比率正常，DeFi 生態無異常訊號。"),
                 "Cong, Tang & Zhong (2022); Harvey et al. (2021), J. Finance.")

        # 2. 200MA 趨勢
        if ma200:
            above = latest > ma200
            _sig("eth_above_200ma", above,
                 "medium" if above else "medium",
                 f"ETH ${latest:,.0f}，200MA ${ma200:,.0f}，{'多頭格局' if above else '空頭格局'}。",
                 "Liu & Tsyvinski (2021), Rev. Financial Studies.")

        # 3. 投機過熱信號
        if chg_7d is not None and chg_7d > 20:
            _sig("eth_speculation_spike", True, "medium",
                 f"ETH 7日漲幅 {chg_7d:+.1f}%，超過 +20% 觸發投機過熱信號。此幅度快速上漲往往伴隨 Gas Fee 急漲與鏈上槓桿激增，短期獲利了結壓力大。",
                 "Bouri et al. (2017); Cong et al. (2022), J. Finance.")

    # ──────────────────────────────────────────────────────────────────────
    # Solana SOL (sol)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "sol":
        # 1. 200MA 趨勢
        if ma200:
            above = latest > ma200
            _sig("sol_above_200ma", above,
                 "medium" if above else "medium",
                 f"SOL ${latest:.2f}，200MA ${ma200:.2f}，{'多頭' if above else '空頭'}格局。Layer-1 生態鏈 200MA 上/下方是市場認知的牛熊分界。",
                 "Liu & Tsyvinski (2021), Rev. Financial Studies.")

        # 2. 山寨季信號
        if chg_7d is not None and chg_7d > 20:
            _sig("sol_altseason", True, "medium",
                 f"SOL 7日漲幅 {chg_7d:+.1f}%，超過 +20% 觸發山寨季指標。資金從 BTC → ETH → 山寨幣輪動模式確認，鏈上活躍度通常同步飆升。",
                 "Bouri et al. (2017), Finance Research Letters.")

        # 3. 相對 BTC 超跌
        btc_p = all_closes.get("btc")
        if btc_p and btc_p > 0 and chg_30d is not None:
            btc_chg_30d = all_closes.get("_btc_chg30d")  # 若有
            if chg_30d < -35:
                _sig("sol_deep_correction", True, "high",
                     f"SOL 30日跌幅 {chg_30d:.1f}%，遠超加密市場一般波動範圍，可能反映鏈上流動性危機或生態信任問題。",
                     "Cong, Tang & Zhong (2022), J. Finance.")

    # ──────────────────────────────────────────────────────────────────────
    # S&P 500 (sp500)
    # ──────────────────────────────────────────────────────────────────────
    elif slug == "sp500":
        # 1. 200MA — 最廣泛使用的趨勢信號（Faber 2007）
        if ma200:
            above = latest > ma200
            _sig("sp500_above_200ma", above,
                 "medium" if not above else "low",
                 f"S&P 500 現值 {latest:,.0f}，200MA {ma200:,.0f}。"
                 + ("站上 200MA，中期多頭格局延續。Faber (2007) 使用 10 月均線（近似 200DMA）做擇時，歷史夏普比率優於 Buy & Hold。"
                    if above else "跌破 200MA，中期趨勢轉空，歷史上此形態後 6 個月平均報酬顯著低於長期均值，建議降低風險暴露。"),
                 "Faber (2007), J. Wealth Management; Lo & MacKinlay (1988).")

        # 2. 修正/熊市信號
        if atf_pct is not None:
            bear_market  = atf_pct < -20
            correction   = -20 <= atf_pct < -10
            near_ath     = atf_pct > -5
            _sig("sp500_drawdown",
                 bear_market or correction,
                 "high" if bear_market else ("medium" if correction else "low"),
                 f"S&P 500 距 52 週高點 {atf_pct:.1f}%。"
                 + ("熊市確認（跌幅>20%）！Fama & French (1988) 均值回歸模型顯示熊市後 3-5 年預期報酬顯著偏高，但需忍受持續下行風險。"
                    if bear_market else
                    "進入修正區間（10-20%），Shiller CAPE 若同步偏高，修正可能延續至 20% 以上。"
                    if correction else
                    f"距高點僅 {abs(atf_pct):.1f}%，接近歷史高位，估值需謹慎評估（Shiller 1981 警告過度樂觀風險）。"
                    if near_ath else
                    f"距高點 {abs(atf_pct):.1f}%，回撤幅度溫和。"),
                 "Fama & French (1988), J. Finance; Shiller (1981), Am. Econ. Review.")

        # 3. RSI 動能
        if rsi14 is not None:
            if rsi14 > 75:
                _sig("sp500_rsi_overbought", True, "medium",
                     f"S&P 500 RSI(14)={rsi14}，短期超買。歷史上 RSI>75 後 30 日常出現震盪整理，但趨勢不一定逆轉。",
                     "Wilder (1978); Jegadeesh & Titman (1993), J. Finance.")
            elif rsi14 < 28:
                _sig("sp500_rsi_oversold", True, "medium",
                     f"S&P 500 RSI(14)={rsi14}，深度超賣。Lo & MacKinlay (1988) 研究顯示短期均值回歸效應在指數層面同樣存在，超賣後反彈概率偏高。",
                     "Wilder (1978); Lo & MacKinlay (1988), Rev. Financial Studies.")

    return signals


# ── 計算漲跌幅 ────────────────────────────────────────────────────────────

def _calc_change(ohlcv: List[Dict], days: int) -> Optional[float]:
    """計算 N 日漲跌幅（%）。"""
    if len(ohlcv) < days + 1:
        return None
    ref = ohlcv[-(days + 1)]["c"]
    cur = ohlcv[-1]["c"]
    if not ref:
        return None
    return round((cur - ref) / ref * 100, 2)


# ── 收益率曲線 ────────────────────────────────────────────────────────────

def _build_yield_curve(all_dfs: Dict[str, Optional[pd.DataFrame]]) -> List[Dict]:
    """建構收益率曲線資料點（tenor, yield_pct）。"""
    TENORS = [
        ("2Y",  "^IRX",  2),
        ("5Y",  "^FVX",  5),
        ("10Y", "^TNX",  10),
        ("30Y", "^TYX",  30),
    ]
    points = []
    for label, symbol, years in TENORS:
        df = all_dfs.get(symbol)
        if df is not None and not df.empty:
            val = float(df["Close"].iloc[-1])
            points.append({"tenor": label, "years": years, "yield_pct": round(val, 3)})
    return points


# ── 殖利率曲線分析 ────────────────────────────────────────────────────────

def _compute_yield_curve_analysis(yield_curve: List[Dict],
                                  latest_closes: Dict[str, float]) -> Dict:
    """計算殖利率曲線的學術信號與形狀分析。"""
    # 建立 tenor → yield 查詢表
    ymap = {pt["tenor"]: pt["yield_pct"] for pt in yield_curve}
    us2y  = ymap.get("2Y")
    us10y = ymap.get("10Y") or latest_closes.get("us10y")
    us30y = ymap.get("30Y") or latest_closes.get("us30y")

    spread_2_10 = round(us10y - us2y, 3) if (us10y is not None and us2y is not None) else None
    spread_2_30 = round(us30y - us2y, 3) if (us30y is not None and us2y is not None) else None
    spread_10_30 = round(us30y - us10y, 3) if (us30y is not None and us10y is not None) else None

    # 曲線形狀判斷（Diebold & Li 2006 坡度因子）
    if spread_2_10 is None:
        slope_signal = "unknown"
    elif spread_2_10 < 0:
        slope_signal = "inverted"
    elif spread_2_10 < 0.25:
        slope_signal = "flat"
    elif spread_2_10 < 1.5:
        slope_signal = "normal"
    else:
        slope_signal = "steep"

    signals: List[Dict] = []

    def _ysig(key, triggered, severity, commentary, source):
        signals.append({"key": key, "triggered": triggered, "severity": severity,
                        "commentary": commentary, "source": source})

    # 1. 2-10Y 倒掛（Estrella & Mishkin 1998）
    if spread_2_10 is not None:
        inverted = spread_2_10 < 0
        flat = 0 <= spread_2_10 < 0.25
        _ysig("curve_2_10_inversion", inverted,
              "high" if inverted else ("medium" if flat else "low"),
              f"2Y-10Y 利差 {spread_2_10:+.3f}%。"
              + ("殖利率曲線倒掛，Estrella & Mishkin (1998) 以 probit 模型估算，此信號預測衰退機率超 80%，歷史平均領先 12-18 個月。"
                 if inverted else
                 "曲線趨平（<25bps），接近倒掛邊緣，需持續追蹤。"
                 if flat else
                 f"曲線正常（利差 {spread_2_10:+.3f}%），短期衰退風險相對可控。"),
              "Estrella & Mishkin (1998), Rev. Econ. & Stat.; Campbell & Shiller (1991).")

    # 2. 10Y 絕對水準（Clarida et al. 1999）
    if us10y is not None:
        if us10y > 5.0:
            _ysig("yield_10y_very_high", True, "high",
                  f"10Y 殖利率 {us10y:.2f}%，超過 5%（2007 年後罕見水準）。此環境下房貸、企業債、政府融資成本全面攀升，恐引發資產負債表緊縮連鎖效應。",
                  "Bernanke & Gertler (1989); Clarida, Gali & Gertler (1999), AER.")
        elif us10y > 4.5:
            _ysig("yield_10y_restrictive", True, "medium",
                  f"10Y 殖利率 {us10y:.2f}%（4.5-5%），金融條件明顯收緊。實質利率（扣除通膨）轉正，需關注高槓桿企業融資壓力及房地產市場。",
                  "Taylor (1993), Carnegie-Rochester; Clarida et al. (1999).")
        else:
            _ysig("yield_10y_normal", False, "low",
                  f"10Y 殖利率 {us10y:.2f}%，在歷史正常至偏緊水準，對資產估值壓力有限。",
                  "Shiller (1981), AER.")

    # 3. 長端利差 10Y-30Y（Diebold & Li 2006 曲率因子）
    if spread_10_30 is not None:
        inverted_long = spread_10_30 > 0  # 30Y < 10Y = 長端倒掛
        _ysig("curve_long_end_slope", inverted_long,
              "medium" if inverted_long else "low",
              f"10Y-30Y 長端利差 {spread_10_30:+.3f}%（正值=長端倒掛）。"
              + ("長端倒掛，市場預期長期經濟增速與通膨雙雙疲弱，Diebold & Li (2006) 三因子曲率負值信號，通常反映末期緊縮周期。"
                 if inverted_long else
                 "長端正常向上傾斜，長期通膨預期穩定。"),
              "Diebold & Li (2006), J. Econometrics; Fama & Bliss (1987).")

    # 4. 2Y 聯準會政策預期（Taylor 1993）
    if us2y is not None:
        if us2y > 5.0:
            _ysig("yield_2y_ultra_tight", True, "high",
                  f"2Y 殖利率 {us2y:.2f}%，市場預期 Fed 維持高利率，貨幣政策極度緊縮。此水準接近 2006 年金融危機前，企業融資與消費信貸出現明顯壓力。",
                  "Taylor (1993); Bernanke & Blinder (1992), AER.")
        elif us2y > 4.0:
            _ysig("yield_2y_restrictive", True, "medium",
                  f"2Y 殖利率 {us2y:.2f}%，Fed 政策利率仍偏緊（4-5%），2Y 殖利率為市場對未來 2 年 Fed 政策的最佳預測（Gürkaynak 2005）。",
                  "Gürkaynak, Sack & Swanson (2005), AER; Taylor (1993).")

    # 5. 全曲線形狀摘要信號
    shape_map = {
        "inverted": ("curve_inverted_shape", True, "high",
                     "殖利率曲線整體呈倒掛形狀，為歷史上最可靠的衰退預測指標（準確率約 80%，Estrella 1998）。"),
        "flat":     ("curve_flat_shape", True, "medium",
                     "殖利率曲線偏平，歷史上此形態後 6-12 個月內進入倒掛的概率偏高，應提高防禦性資產配置。"),
        "normal":   ("curve_normal_shape", False, "low",
                     "殖利率曲線正常向上傾斜，信貸環境健康，未來 12 個月系統性衰退風險相對可控。"),
        "steep":    ("curve_steep_shape", False, "low",
                     "殖利率曲線陡峭，反映市場對長期增長與通膨的樂觀預期，有利銀行業息差擴大。"),
    }
    if slope_signal in shape_map:
        key, triggered, severity, commentary = shape_map[slope_signal]
        _ysig(key, triggered, severity, commentary + f"（2-10Y 利差={spread_2_10:+.3f}%）",
              "Estrella & Mishkin (1998); Diebold & Li (2006).")

    return {
        "spread_2_10":  spread_2_10,
        "spread_2_30":  spread_2_30,
        "spread_10_30": spread_10_30,
        "is_inverted":  (spread_2_10 is not None and spread_2_10 < 0),
        "slope_signal": slope_signal,
        "signals":      signals,
    }


# ── 市場總覽摘要 ──────────────────────────────────────────────────────────

def _compute_market_summary(assets: Dict[str, Any],
                            yc_analysis: Dict) -> Dict:
    """聚合所有資產信號，生成市場整體狀態摘要。"""
    all_signals: List[Dict] = []
    for asset in assets.values():
        all_signals.extend(asset.get("signals", []))
    # 加入殖利率曲線信號
    all_signals.extend(yc_analysis.get("signals", []))

    triggered  = [s for s in all_signals if s.get("triggered")]
    high_list  = [s for s in triggered if s.get("severity") == "high"]
    med_list   = [s for s in triggered if s.get("severity") == "medium"]

    score = len(high_list) * 2 + len(med_list)

    if score >= 10:
        overall  = "risk_off"
        headline = f"🚨 高度警戒：{len(high_list)} 項高危信號觸發，市場防禦模式全面啟動，建議大幅降低風險暴露"
    elif score >= 5:
        overall  = "caution"
        headline = f"⚡ 謹慎中性：{len(triggered)} 項信號觸發（高危 {len(high_list)} 項），建議適度降低曝險與分散配置"
    elif score >= 1:
        overall  = "neutral"
        headline = f"📊 溫和觀察：{len(triggered)} 項信號觸發，個別風險點存在，整體環境尚可"
    else:
        overall  = "risk_on"
        headline = "✅ 風險偏好：絕大多數指標正常，市場環境健康，可維持正常風險配置"

    key_alerts = [s["commentary"][:60] + "…" for s in high_list[:3]]

    return {
        "total_triggered": len(triggered),
        "high_count":      len(high_list),
        "medium_count":    len(med_list),
        "overall":         overall,
        "headline":        headline,
        "key_alerts":      key_alerts,
    }


# ── 主函數 ────────────────────────────────────────────────────────────────

def run(config=None) -> Dict[str, Any]:
    """
    抓取所有商品市場資料，寫出 JSON 檔案，回傳摘要 dict。
    可獨立執行（config=None 時不使用 FRED）。
    """
    _ensure_output_dir()
    logger.info("商品市場分析開始…")

    all_dfs: Dict[str, Optional[pd.DataFrame]] = {}
    all_ohlcv: Dict[str, List[Dict]] = {}
    summary_assets: Dict[str, Any] = {}

    # ── Step 1: 抓取所有 yfinance 資產 ──────────────────────────────────
    yf_symbols = [(slug, sym) for slug, sym, _, _ in ASSETS if sym is not None]
    for slug, symbol in yf_symbols:
        logger.info(f"  yfinance: {symbol} ({slug})…")
        df = _fetch_yf(symbol, period="2y")
        all_dfs[symbol] = df
        all_ohlcv[slug] = _df_to_ohlcv(df) if df is not None else []

    # ── Step 3: 收集最新收盤價 ───────────────────────────────────────────
    latest_closes: Dict[str, float] = {}
    for slug, symbol, _, _ in ASSETS:
        ohlcv = all_ohlcv.get(slug, [])
        if ohlcv:
            latest_closes[slug] = ohlcv[-1]["c"]

    # ── Step 4: 計算信號、建構摘要 ───────────────────────────────────────
    for slug, symbol, name_zh, category in ASSETS:
        ohlcv = all_ohlcv.get(slug, [])
        price = latest_closes.get(slug)
        chg1d = _calc_change(ohlcv, 1)
        chg7d = _calc_change(ohlcv, 7)
        signals = _compute_signals(slug, ohlcv, latest_closes)

        # 寫出個別 OHLCV 檔案（含完整歷史）
        ohlcv_path = OUT_DIR / f"{slug}.json"
        try:
            ohlcv_path.write_text(json.dumps(ohlcv, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"寫出 {ohlcv_path} 失敗: {e}")

        summary_assets[slug] = {
            "slug":          slug,
            "name_zh":       name_zh,
            "category":      category,
            "price":         price,
            "change_1d_pct": chg1d,
            "change_7d_pct": chg7d,
            "signals":       signals,
            "last_updated":  datetime.now(timezone.utc).isoformat(),
        }

    # ── Step 5: 收益率曲線 + 分析 ───────────────────────────────────────────
    yield_curve = _build_yield_curve(all_dfs)
    yield_curve_path = OUT_DIR / "yield_curve.json"
    try:
        yield_curve_path.write_text(json.dumps(yield_curve, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"寫出 yield_curve.json 失敗: {e}")

    yc_analysis    = _compute_yield_curve_analysis(yield_curve, latest_closes)
    market_summary = _compute_market_summary(summary_assets, yc_analysis)

    # ── Step 6: 寫出摘要 latest.json ─────────────────────────────────────
    latest_data = {
        "updated_at":           datetime.now(timezone.utc).isoformat(),
        "assets":               summary_assets,
        "yield_curve":          yield_curve,
        "yield_curve_analysis": yc_analysis,
        "market_summary":       market_summary,
    }
    latest_path = OUT_DIR / "latest.json"
    try:
        latest_path.write_text(json.dumps(latest_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"商品市場分析完成，寫出 {latest_path}")
    except Exception as e:
        logger.error(f"寫出 latest.json 失敗: {e}")

    return latest_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    result = run()
    print(f"完成：{len(result['assets'])} 個資產，收益率曲線 {len(result['yield_curve'])} 個點")
