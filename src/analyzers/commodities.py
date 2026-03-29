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
    ("btc",           None,              "比特幣 BTC",         "crypto"),
    ("eth",           None,              "以太坊 ETH",         "crypto"),
    ("sol",           None,              "Solana SOL",         "crypto"),
    ("sp500",         "^GSPC",           "S&P 500",            "index"),
]

# CoinGecko slug → ID 對應
COINGECKO_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
}

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


# ── 學術信號計算 ──────────────────────────────────────────────────────────

def _compute_signals(slug: str, ohlcv: List[Dict],
                     all_closes: Dict[str, float]) -> List[Dict]:
    """依資產類型計算學術信號，回傳信號列表。"""
    signals: List[Dict] = []
    if not ohlcv:
        return signals

    closes = [bar["c"] for bar in ohlcv]
    latest = closes[-1] if closes else None

    def _ema(prices: List[float], n: int) -> float:
        alpha = 2 / (n + 1)
        val = prices[0]
        for p in prices[1:]:
            val = alpha * p + (1 - alpha) * val
        return val

    # VIX 信號（Whaley 2000）
    if slug == "vix" and latest is not None:
        if latest > 40:
            signals.append({
                "key": "vix_extreme", "triggered": True, "severity": "high",
                "commentary": f"VIX={latest:.1f}，已達極端恐慌水準（>40）。根據 Whaley (2000) 的反向情緒指標理論，極端恐慌往往預示短期底部，但波動性仍高。",
                "source": "Whaley (2000), J. Portfolio Mgmt.",
            })
        elif latest > 30:
            signals.append({
                "key": "vix_spike", "triggered": True, "severity": "medium",
                "commentary": f"VIX={latest:.1f}，突破 30 警戒線。市場情緒急速惡化，選擇權隱含波動率大幅抬升，注意避險需求上升。",
                "source": "Whaley (2000), J. Portfolio Mgmt.",
            })
        else:
            signals.append({
                "key": "vix_normal", "triggered": False, "severity": "low",
                "commentary": f"VIX={latest:.1f}，市場情緒平穩，未見恐慌信號。",
                "source": "Whaley (2000), J. Portfolio Mgmt.",
            })

    # 殖利率倒掛（Campbell & Shiller 1991）
    if slug == "us10y" and "us2y" in all_closes and "us10y" in all_closes:
        us2y = all_closes.get("us2y", 0)
        us10y_val = all_closes.get("us10y", 0)
        if us2y and us10y_val:
            spread = us10y_val - us2y
            inverted = spread < 0
            signals.append({
                "key": "yield_inversion", "triggered": inverted, "severity": "high" if inverted else "low",
                "commentary": (
                    f"2-10Y 利差 = {spread:+.2f}%。殖利率曲線{'倒掛（負利差），歷史上為衰退領先指標（Campbell & Shiller 1991），平均領先經濟衰退 12-18 個月。' if inverted else '正常（正利差），衰退風險尚低。'}"
                ),
                "source": "Campbell & Shiller (1991), Rev. Financial Studies.",
            })

    # 黃金 200MA 信號（Baur & Lucey 2010）
    if slug == "gold" and latest is not None and len(closes) >= 200:
        ma200 = sum(closes[-200:]) / 200
        above = latest > ma200
        signals.append({
            "key": "gold_above_200ma", "triggered": above, "severity": "medium" if above else "low",
            "commentary": (
                f"黃金現價 ${latest:.2f}，200日均線 ${ma200:.2f}。"
                + ("站上 200MA，避險資金流入確認，符合 Baur & Lucey (2010) 黃金避險功能啟動條件。" if above else "位於 200MA 下方，避險需求尚未全面啟動。")
            ),
            "source": "Baur & Lucey (2010), J. Banking & Finance.",
        })

    # 油價衝擊信號（Hamilton 2009）
    if slug == "wti" and latest is not None:
        oil_shock = latest > 85
        signals.append({
            "key": "oil_shock", "triggered": oil_shock, "severity": "high" if oil_shock else "low",
            "commentary": (
                f"WTI 原油 ${latest:.2f}/桶。"
                + ("突破 $85，達 Hamilton (2009) 定義的供給衝擊門檻，歷史上此水準對經濟增長有顯著負向影響。" if oil_shock else "低於 $85，油價尚未達衝擊門檻。")
            ),
            "source": "Hamilton (2009), J. Economic Perspectives.",
        })

    # BTC 風險信號（Bouri et al. 2017）
    if slug == "btc" and len(ohlcv) >= 7:
        price_7d_ago = ohlcv[-7]["c"]
        if price_7d_ago and latest:
            chg_7d = (latest - price_7d_ago) / price_7d_ago * 100
            if chg_7d > 10:
                signals.append({
                    "key": "btc_risk_on", "triggered": True, "severity": "medium",
                    "commentary": f"BTC 7日漲幅 {chg_7d:+.1f}%，超過 +10% 閾值。根據 Bouri et al. (2017)，加密市場急漲往往反映全球高風險偏好情緒升溫。",
                    "source": "Bouri et al. (2017), Finance Research Letters.",
                })
            elif chg_7d < -15:
                signals.append({
                    "key": "btc_risk_off", "triggered": True, "severity": "high",
                    "commentary": f"BTC 7日跌幅 {chg_7d:+.1f}%，超過 -15% 閾值。加密市場大跌通常伴隨風險資產全面撤退，需留意系統性流動性風險。",
                    "source": "Bouri et al. (2017), Finance Research Letters.",
                })
            else:
                signals.append({
                    "key": "btc_neutral", "triggered": False, "severity": "low",
                    "commentary": f"BTC 7日漲跌 {chg_7d:+.1f}%，維持正常波動區間。",
                    "source": "Bouri et al. (2017), Finance Research Letters.",
                })

    # DXY 強勢美元（FRB 2024 參考水準）
    if slug == "dxy" and latest is not None:
        strong = latest > 105
        signals.append({
            "key": "dxy_strong", "triggered": strong, "severity": "medium" if strong else "low",
            "commentary": (
                f"美元指數 DXY={latest:.2f}。"
                + ("突破 105，美元強勢壓制全球商品與新興市場資產，資金回流美國趨勢明顯。" if strong else "低於 105，美元強勢暫緩，有利新興市場及大宗商品資產。")
            ),
            "source": "FRB (2024), Federal Reserve Trade-Weighted Index.",
        })

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

    # ── Step 2: 抓取 CoinGecko 加密貨幣 ──────────────────────────────────
    for slug, cg_id in COINGECKO_IDS.items():
        logger.info(f"  CoinGecko: {cg_id} ({slug})…")
        df = _fetch_coingecko(cg_id)
        all_ohlcv[slug] = _df_to_ohlcv(df) if df is not None else []
        # CoinGecko 無 Volume，補空 df 供後續使用
        all_dfs[f"CG_{cg_id}"] = df
        time.sleep(2)  # 避免 CoinGecko free tier 限速

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

    # ── Step 5: 收益率曲線 ───────────────────────────────────────────────
    yield_curve = _build_yield_curve(all_dfs)
    yield_curve_path = OUT_DIR / "yield_curve.json"
    try:
        yield_curve_path.write_text(json.dumps(yield_curve, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"寫出 yield_curve.json 失敗: {e}")

    # ── Step 6: 寫出摘要 latest.json ─────────────────────────────────────
    latest_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "assets":     summary_assets,
        "yield_curve": yield_curve,
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
