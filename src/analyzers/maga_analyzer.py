"""
maga_analyzer.py — MAGA 台股衝擊評分引擎

根據川普政策對台股板塊的影響，計算受益/受害評分。
資料流：FinLab OHLCV（複用 DataFetcher）→ 衝擊評分 → output/maga/latest.json

新聞：Google News RSS + feedparser（免費，無需 API Key）
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import src.ssl_fix  # noqa: F401

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "maga"

# ── 政策定義 ──────────────────────────────────────────────────────────────

MAGA_POLICIES: list[dict] = [
    {
        "key": "tariff",
        "label": "對中關稅",
        "active": True,
        "description": "對中國商品徵收 25%+ 關稅，壓縮中國出口競爭力，部分台廠替代受益",
    },
    {
        "key": "china_decoupling",
        "label": "科技脫鉤",
        "active": True,
        "description": "限制中國取得先進半導體技術，強化台積電等台廠的戰略地位",
    },
    {
        "key": "reshoring",
        "label": "製造回流",
        "active": True,
        "description": "美國鼓勵製造業回流，台廠在美設廠 / 供應鏈轉移受益",
    },
    {
        "key": "ai_investment",
        "label": "AI 資本支出",
        "active": True,
        "description": "美國科技巨頭大幅拉升 AI 伺服器、資料中心資本支出",
    },
    {
        "key": "energy_independence",
        "label": "能源獨立",
        "active": True,
        "description": "擴大化石燃料生產，對再生能源政策不友善",
    },
    {
        "key": "deregulation",
        "label": "金融去管制",
        "active": False,
        "description": "寬鬆金融監管，銀行業受益，尚未明顯影響台股",
    },
]

# ── MAGA 板塊分類（sector_id → category）────────────────────────────────

MAGA_SECTOR_CLASSIFICATION: dict[str, str] = {
    # 受益
    "foundry":             "beneficiary",  # 替代中國供應鏈，台積電
    "ai_server":           "beneficiary",  # AI 伺服器資本支出爆炸
    "packaging":           "beneficiary",  # CoWoS 先進封裝需求
    "optical_comm":        "beneficiary",  # 資料中心光纖
    "semiconductor_equip": "beneficiary",  # 美廠設備採購
    "ip_design":           "beneficiary",  # 矽智財技術脫鉤受益
    "networking":          "beneficiary",  # 機房網路設備
    "power_infra":         "beneficiary",  # 能源獨立 + 電廠建設
    "defense":             "beneficiary",  # 防禦支出增加
    "robotics":            "beneficiary",  # 製造回流自動化
    "thermal":             "beneficiary",  # AI 晶片散熱
    # 受害
    "ic_design":           "victim",       # 聯發科等中國客戶受損
    "solar":               "victim",       # 反綠能政策
    "ev_supply":           "victim",       # 取消 EV 補貼
    "display":             "victim",       # 貿易戰衝擊
    "shipping":            "victim",       # 貿易量下滑
    "petrochemical":       "victim",       # 美國石化競爭
}

# ── 政策敏感度矩陣（sector_id → policy_key → sensitivity -1.0~+1.0）──

SECTOR_SENSITIVITY_MATRIX: dict[str, dict[str, float]] = {
    "foundry": {
        "tariff":              -0.2,
        "china_decoupling":    +0.9,
        "reshoring":           +0.6,
        "ai_investment":       +0.7,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "ai_server": {
        "tariff":              -0.1,
        "china_decoupling":    +0.4,
        "reshoring":           +0.3,
        "ai_investment":       +1.0,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "packaging": {
        "tariff":              -0.1,
        "china_decoupling":    +0.7,
        "reshoring":           +0.4,
        "ai_investment":       +0.8,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "optical_comm": {
        "tariff":              -0.1,
        "china_decoupling":    +0.3,
        "reshoring":           +0.2,
        "ai_investment":       +0.9,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "semiconductor_equip": {
        "tariff":              -0.2,
        "china_decoupling":    +0.5,
        "reshoring":           +0.8,
        "ai_investment":       +0.4,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "ip_design": {
        "tariff":              -0.1,
        "china_decoupling":    +0.6,
        "reshoring":           +0.3,
        "ai_investment":       +0.6,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "networking": {
        "tariff":              -0.2,
        "china_decoupling":    +0.3,
        "reshoring":           +0.2,
        "ai_investment":       +0.7,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "power_infra": {
        "tariff":              -0.1,
        "china_decoupling":    +0.1,
        "reshoring":           +0.5,
        "ai_investment":       +0.4,
        "energy_independence": +0.7,
        "deregulation":         0.0,
    },
    "defense": {
        "tariff":               0.0,
        "china_decoupling":    +0.5,
        "reshoring":           +0.2,
        "ai_investment":       +0.2,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "robotics": {
        "tariff":              -0.1,
        "china_decoupling":    +0.3,
        "reshoring":           +0.8,
        "ai_investment":       +0.5,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "thermal": {
        "tariff":              -0.1,
        "china_decoupling":    +0.2,
        "reshoring":           +0.1,
        "ai_investment":       +0.9,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "ic_design": {
        "tariff":              -0.5,
        "china_decoupling":    -0.8,
        "reshoring":           -0.2,
        "ai_investment":       +0.3,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "solar": {
        "tariff":              -0.4,
        "china_decoupling":    -0.3,
        "reshoring":           -0.1,
        "ai_investment":        0.0,
        "energy_independence": -0.8,
        "deregulation":         0.0,
    },
    "ev_supply": {
        "tariff":              -0.5,
        "china_decoupling":    -0.2,
        "reshoring":           -0.1,
        "ai_investment":        0.0,
        "energy_independence": -0.6,
        "deregulation":         0.0,
    },
    "display": {
        "tariff":              -0.6,
        "china_decoupling":    -0.3,
        "reshoring":            0.0,
        "ai_investment":       +0.1,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "shipping": {
        "tariff":              -0.7,
        "china_decoupling":    -0.3,
        "reshoring":           -0.2,
        "ai_investment":        0.0,
        "energy_independence":  0.0,
        "deregulation":         0.0,
    },
    "petrochemical": {
        "tariff":              -0.4,
        "china_decoupling":    -0.2,
        "reshoring":            0.0,
        "ai_investment":        0.0,
        "energy_independence": -0.4,
        "deregulation":         0.0,
    },
}

# ── 股票中文名稱靜態對照表 ─────────────────────────────────────────────────
# price:公司簡稱 不存在於 FinLab，改用靜態查詢
_STOCK_NAMES: dict[str, str] = {
    # 晶圓代工 / 封測
    "2330": "台積電", "2303": "聯電",   "5347": "世界先進", "6770": "力積電",
    "3711": "日月光", "2449": "京元電", "6257": "矽格",    "2441": "超豐",
    # AI 伺服器 / ODM
    "3231": "緯創",  "6669": "緯穎",  "2382": "廣達",   "2317": "鴻海",   "2308": "台達電",
    # 光通訊
    "3081": "聯亞",  "4908": "前鼎",  "4979": "隆達",   "6426": "統部",
    # 半導體設備
    "3090": "日立",  "4523": "永彥",  "6533": "晶豪科",
    # IC設計服務/矽智財
    "3443": "創意",  "3661": "世芯-KY", "3035": "智原", "6643": "M31",
    # 網通
    "2345": "智邦",  "3149": "正文",  "2332": "友訊",  "6138": "茂達",
    # 重電
    "1519": "華城",  "1503": "士電",  "1513": "中興電", "1514": "東元",
    # 國防
    "2634": "漢翔",  "8033": "雷虎",  "5222": "全訊",
    # 機器人/自動化
    "2049": "上銀",  "1590": "亞德客-KY", "2359": "所羅門",
    # 散熱
    "6230": "超眾",  "3324": "雙鴻",  "2421": "建準",  "3017": "奇鋐",
    # IC設計（受害）
    "2454": "聯發科", "2379": "瑞昱", "3034": "聯詠",  "3051": "力旺",
    # 太陽能
    "3576": "新日光", "6214": "精熙", "3665": "貿聯-KY", "3178": "景碩",
    # 電動車
    "1516": "川湖",  "5483": "中美晶", "1504": "東立",  "6213": "聯茂",
    # 面板
    "2409": "友達",  "3481": "群創",
    # 航運
    "2603": "長榮",  "2609": "陽明",  "2615": "萬海",  "2616": "宏海",
    # 塑化
    "1301": "台塑",  "1303": "南亞",  "1326": "台化",  "6505": "台塑石化",
}

# ── 情緒關鍵字 ────────────────────────────────────────────────────────────

_POSITIVE_KEYWORDS = [
    "受益", "利多", "上漲", "突破", "強勢", "訂單", "受惠",
    "benefit", "gain", "surge", "boost", "rally", "rise", "positive",
]
_NEGATIVE_KEYWORDS = [
    "受害", "利空", "下跌", "衝擊", "損失", "警告", "風險",
    "risk", "fall", "drop", "decline", "tariff hit", "negative", "hurt",
]


def _sentiment_from_text(text: str) -> str:
    lower = text.lower()
    pos = sum(1 for k in _POSITIVE_KEYWORDS if k.lower() in lower)
    neg = sum(1 for k in _NEGATIVE_KEYWORDS if k.lower() in lower)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ── 新聞 RSS ──────────────────────────────────────────────────────────────

NEWS_QUERIES = [
    "Trump tariff Taiwan semiconductor",
    "MAGA trade war chip",
    "台積電 美國",
    "關稅 台灣 半導體",
]


def fetch_news_rss(max_per_query: int = 5) -> list[dict]:
    """
    Google News RSS 抓取 MAGA 相關新聞。
    失敗回傳空清單（不影響主流程）。
    """
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser 未安裝，跳過新聞抓取")
        return []

    import urllib.parse
    import email.utils

    seen_urls: set[str] = set()
    results: list[dict] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FinLab-News/1.0)"}

    for query in NEWS_QUERIES:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            feed = feedparser.parse(url, request_headers=headers)

            count = 0
            for entry in feed.entries:
                if count >= max_per_query:
                    break
                link = getattr(entry, "link", "")
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                title = getattr(entry, "title", "")
                published = getattr(entry, "published", "")
                date_str = ""
                try:
                    t = email.utils.parsedate_to_datetime(published)
                    date_str = t.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                except Exception:
                    date_str = published

                results.append({
                    "date": date_str,
                    "headline": title,
                    "url": link,
                    "sentiment": _sentiment_from_text(title),
                })
                count += 1
        except Exception as e:
            logger.warning(f"RSS 抓取失敗 ({query!r}): {e}")

    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    return results[:20]


# ── 核心計算 ──────────────────────────────────────────────────────────────

def _calculate_impact_score(
    sector_id: str,
    active_policy_keys: list[str],
) -> tuple[int, dict[str, int]]:
    """
    回傳 (impact_score [-100~+100], {policy_key: contribution})。
    正規化：以啟動政策數量作分母，避免政策越多評分越高的偏差。
    """
    sensitivity = SECTOR_SENSITIVITY_MATRIX.get(sector_id, {})
    raw_score = 0.0
    contributions: dict[str, int] = {}

    for key in active_policy_keys:
        s = sensitivity.get(key, 0.0)
        contributions[key] = round(s * 100)
        raw_score += s

    n = len(active_policy_keys) or 1
    normalized = raw_score / n * 100
    impact_score = max(-100, min(100, round(normalized)))
    return impact_score, contributions


def _load_watchlist(sector_map) -> tuple[dict[str, str], dict[str, str]]:
    """
    從 SectorMap 載入各板塊的股票，回傳：
    (beneficiary_map, victim_map) 兩個 {stock_id → sector_id}
    """
    beneficiary: dict[str, str] = {}
    victim: dict[str, str] = {}

    for sector_id, category in MAGA_SECTOR_CLASSIFICATION.items():
        for stock_id in sector_map.get_stocks(sector_id):
            if category == "beneficiary":
                # 優先保留最先出現的分類（避免重複股票衝突）
                beneficiary.setdefault(stock_id, sector_id)
            else:
                victim.setdefault(stock_id, sector_id)

    # 確保同一股票不同時出現在兩側（受益優先）
    for sid in list(victim.keys()):
        if sid in beneficiary:
            del victim[sid]

    return beneficiary, victim


# ── 主要入口 ──────────────────────────────────────────────────────────────

def run_maga_analysis(fetcher, sector_map) -> dict:
    """
    執行 MAGA 分析並寫出 output/maga/latest.json。
    複用現有 DataFetcher，不重複登入。
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    active_policy_keys = [p["key"] for p in MAGA_POLICIES if p["active"]]

    # 1. 載入 watchlist
    beneficiary_map, victim_map = _load_watchlist(sector_map)
    all_tickers = list(beneficiary_map.keys()) + list(victim_map.keys())

    # 2. 股價資料（複用 DataFetcher，已含快取）
    change_pct_map = fetcher.get_latest_change_pct()
    ohlcv_map = fetcher.get_ohlcv_batch(all_tickers, days=7)

    # 3. 7 日漲跌幅
    change_7d_map: dict[str, float | None] = {}
    try:
        import pandas as pd
        close_df = fetcher.get("price:收盤價")
        if close_df is not None and not close_df.empty:
            latest = close_df.iloc[-1]
            week_ago = close_df.iloc[-6] if len(close_df) >= 6 else close_df.iloc[0]
            for tid in all_tickers:
                if tid in latest.index and tid in week_ago.index:
                    c = float(latest[tid]) if pd.notna(latest[tid]) else None
                    c7 = float(week_ago[tid]) if pd.notna(week_ago[tid]) else None
                    if c is not None and c7 and c7 != 0:
                        change_7d_map[tid] = round((c - c7) / c7 * 100, 2)
                    else:
                        change_7d_map[tid] = None
    except Exception as e:
        logger.warning(f"7日漲跌幅計算失敗: {e}")

    # 4. 公司名稱（靜態對照表，避免查詢不存在的 FinLab 欄位）
    name_map: dict[str, str] = _STOCK_NAMES

    # 5. 組裝股票清單
    stocks: list[dict] = []
    for category, ticker_sector in [("beneficiary", beneficiary_map), ("victim", victim_map)]:
        for ticker, sector_id in ticker_sector.items():
            impact_score, contributions = _calculate_impact_score(sector_id, active_policy_keys)
            ohlcv = ohlcv_map.get(ticker, [])
            price = ohlcv[-1]["c"] if ohlcv else None

            stocks.append({
                "ticker": f"{ticker}.TW",
                "id": ticker,
                "name_zh": name_map.get(ticker, ticker),
                "sector_id": sector_id,
                "sector_name": sector_map.get_sector_name(sector_id),
                "category": category,
                "impact_score": impact_score,
                "policy_contributions": contributions,
                "price": price,
                "change_1d_pct": change_pct_map.get(ticker),
                "change_7d_pct": change_7d_map.get(ticker),
                "ohlcv_7d": ohlcv,
            })

    # 6. 新聞 RSS
    news = fetch_news_rss()

    # 7. 摘要
    b_stocks = [s for s in stocks if s["category"] == "beneficiary"]
    v_stocks = [s for s in stocks if s["category"] == "victim"]
    avg_b = round(sum(s["impact_score"] for s in b_stocks) / len(b_stocks)) if b_stocks else 0

    # 8. 組裝輸出
    now = datetime.now(timezone(timedelta(hours=8)))
    result = {
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "active_policies": MAGA_POLICIES,
        "stocks": stocks,
        "policy_sensitivity_matrix": {
            sid: SECTOR_SENSITIVITY_MATRIX.get(sid, {})
            for sid in MAGA_SECTOR_CLASSIFICATION
        },
        "sector_names": {
            sid: sector_map.get_sector_name(sid)
            for sid in MAGA_SECTOR_CLASSIFICATION
        },
        "summary": {
            "total_beneficiary": len(b_stocks),
            "total_victim": len(v_stocks),
            "avg_beneficiary_score": avg_b,
        },
        "news": news,
    }

    out_path = OUT_DIR / "latest.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"MAGA 分析完成：受益 {len(b_stocks)} 支，受害 {len(v_stocks)} 支，新聞 {len(news)} 則")
    return result
