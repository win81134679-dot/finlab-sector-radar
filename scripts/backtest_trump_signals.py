#!/usr/bin/env python3
"""
backtest_trump_signals.py — Trump 推文事件研究法回測
======================================================
方法論：Brown & Warner (1985) 事件研究法
  - 估計窗口：事件日前 T-120 ~ T-10 交易日（共 110 天）
  - 事件窗口：[0,+1], [0,+2], [0,+5]
  - 市場模型：OLS — AR_it = R_it - (α_i + β_i × R_mt)
  - 市場指數：台灣加權指數 ^TWII（yfinance）
  - 板塊代表股：等權組合

資料來源
--------
  - Twitter/X 歷史推文 (2016-2021)：
    Kaggle「Trump Twitter Archive」CSV，欄位：date, text
    下載：https://www.kaggle.com/datasets/codebreaker619/trump-twitter-archive
  - Truth Social RSS（2022 以後）：
    透過 scripts/fetch_truth_social.py 抓取後存為 JSON

輸出
----
  - output/backtest/trump_backtest_report.json   — 機器可讀結果
  - output/backtest/trump_backtest_summary.txt   — 人類可讀摘要

用法
----
  python scripts/backtest_trump_signals.py \
    --csv data/trump_tweets.csv \
    [--truth_json data/truth_social_posts.json] \
    [--min_impact 0.05] \
    [--estimation_days 110] \
    [--out output/backtest]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

# ── 確保可 import src/ ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analyzers.trump_nlp import analyze_post  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 板塊代表股（等權組合）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTOR_REPR: dict[str, list[str]] = {
    "foundry":    ["2330.TW"],
    "ic_design":  ["2454.TW", "2303.TW"],
    "shipping":   ["2603.TW", "2609.TW", "2615.TW"],
    "packaging":  ["3711.TW"],
    "display":    ["3481.TW", "2409.TW"],
    "steel":      ["2002.TW"],
    "memory":     ["4863.TW"],
    "server":     ["2382.TW"],
    "network":    ["2345.TW"],
    "banking":    ["2882.TW", "2881.TW"],
}

MARKET_TICKER = "^TWII"

# 事件窗口（以交易日計算，0 = 事件日）
EVENT_WINDOWS: list[tuple[int, int]] = [(0, 1), (0, 2), (0, 5)]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 資料載入
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class RawPost:
    text:      str
    date:      pd.Timestamp
    source:    str   # "twitter" | "truth_social"

def load_twitter_csv(csv_path: str) -> list[RawPost]:
    """讀取 Kaggle Trump Twitter Archive CSV。
    
    支援兩種常見欄位命名：
      - (date, text) — 最常見版本
      - (created_at, full_text) — Twitter API 版本
    """
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = df.columns.str.strip().str.lower()

    # 正規化欄位名稱
    col_date = next((c for c in ["date", "created_at"] if c in df.columns), None)
    col_text = next((c for c in ["text", "full_text", "tweet"] if c in df.columns), None)
    if col_date is None or col_text is None:
        raise ValueError(
            f"CSV 欄位不符合預期。現有欄位：{list(df.columns)}"
        )

    df["_date"] = pd.to_datetime(df[col_date], errors="coerce", utc=True)
    df = df.dropna(subset=["_date"])
    df["_text"] = df[col_text].fillna("").astype(str)

    # 只取 2016-2021 年（確保台股有足夠樣本）
    df = df[(df["_date"].dt.year >= 2016) & (df["_date"].dt.year <= 2021)]

    posts = [
        RawPost(text=row["_text"], date=row["_date"].tz_convert("Asia/Taipei"), source="twitter")
        for _, row in df.iterrows()
    ]
    log.info("Twitter CSV 載入 %d 則（2016-2021）", len(posts))
    return posts


def load_truth_social_json(json_path: str) -> list[RawPost]:
    """讀取 JSON 格式的 Truth Social 貼文（陣列，每個元素含 text + timestamp）。"""
    with open(json_path, encoding="utf-8") as f:
        items: list[dict[str, Any]] = json.load(f)
    posts = []
    for item in items:
        text = item.get("text", item.get("content", ""))
        ts_str = item.get("timestamp", item.get("created_at", ""))
        try:
            ts = pd.Timestamp(ts_str, tz="UTC").tz_convert("Asia/Taipei")
        except Exception:
            continue
        posts.append(RawPost(text=str(text), date=ts, source="truth_social"))
    log.info("Truth Social JSON 載入 %d 則", len(posts))
    return posts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NLP 篩選
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class TaggedEvent:
    post:      RawPost
    impacts:   dict[str, float]   # sector → -1.0 ~ +1.0
    keywords:  list[str]
    compound:  float

def tag_events(posts: list[RawPost], min_impact: float = 0.05) -> list[TaggedEvent]:
    """對每則貼文跑 NLP，保留至少一個板塊衝擊 >= min_impact 的事件。"""
    events: list[TaggedEvent] = []
    for post in posts:
        result = analyze_post(post.text)
        impacts = {k: v for k, v in result["impacts"].items() if abs(v) >= min_impact}
        if not impacts:
            continue
        events.append(TaggedEvent(
            post=post,
            impacts=impacts,
            keywords=result.get("keywords", []),
            compound=result.get("sentiment", {}).get("compound", 0.0),
        ))
    log.info("NLP 篩選後保留 %d 則事件（min_impact=%.2f）", len(events), min_impact)
    return events


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 行情抓取與快取
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """下載調整後收盤價，返回 DataFrame（日期 index，ticker columns）。"""
    log.info("下載行情：%s …", tickers[:5])
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    # yfinance 多股票回傳 MultiIndex columns ("Close", ticker)
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw
    prices.index = pd.to_datetime(prices.index)
    return prices.dropna(how="all")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 市場模型 OLS — 估計 alpha, beta
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fit_market_model(
    stock_ret: pd.Series,
    market_ret: pd.Series,
) -> tuple[float, float, float]:
    """OLS 回歸：stock_ret = α + β * market_ret。返回 (alpha, beta, r_squared)。"""
    common = stock_ret.index.intersection(market_ret.index)
    if len(common) < 20:
        return 0.0, 1.0, 0.0
    y = stock_ret.loc[common].values
    x = market_ret.loc[common].values
    # 加截距
    X = np.column_stack([np.ones_like(x), x])
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0, 1.0, 0.0
    alpha, beta = float(coef[0]), float(coef[1])
    y_hat = alpha + beta * x
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return alpha, beta, r2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 異常報酬計算
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class CARResult:
    sector:        str
    window:        tuple[int, int]
    event_count:   int
    CAR_mean:      float   # 平均累積異常報酬
    CAR_std:       float
    t_stat:        float
    direction_correct_rate: float   # NLP 預測方向 vs 實際 AR 方向
    suggested_action: str           # "加強" | "減弱" | "維持"

def compute_car_for_sector(
    sector: str,
    tickers: list[str],
    events: list[TaggedEvent],
    prices: pd.DataFrame,
    market_rets: pd.Series,
    window: tuple[int, int],
    estimation_days: int,
) -> CARResult | None:
    """計算一個板塊在指定事件窗口的平均 CAR。"""
    # 計算板塊等權報酬
    avail = [t for t in tickers if t in prices.columns]
    if not avail:
        log.warning("板塊 %s 無可用 ticker，跳過", sector)
        return None
    sector_price = prices[avail].mean(axis=1)
    sector_ret   = sector_price.pct_change().dropna()

    trade_dates = sector_ret.index.tolist()

    CARs: list[float] = []
    directions_correct: list[bool] = []

    for ev in events:
        if sector not in ev.impacts:
            continue
        predicted_sign = np.sign(ev.impacts[sector])

        # 找事件日（台股交易日）
        ev_date = ev.post.date.normalize().tz_localize(None)
        try:
            t0_idx = next(
                i for i, d in enumerate(trade_dates)
                if d >= ev_date
            )
        except StopIteration:
            continue

        # 估計窗口
        est_start = t0_idx - estimation_days - 10
        est_end   = t0_idx - 10
        if est_start < 0 or est_end <= est_start + 20:
            continue

        est_stock  = sector_ret.iloc[est_start:est_end]
        est_market = market_rets.reindex(est_stock.index).dropna()
        alpha, beta, _ = fit_market_model(est_stock, est_market)

        # 事件窗口
        win_start = t0_idx + window[0]
        win_end   = t0_idx + window[1] + 1
        if win_end > len(trade_dates):
            continue

        ev_stock  = sector_ret.iloc[win_start:win_end]
        ev_market = market_rets.reindex(ev_stock.index).dropna()
        common    = ev_stock.index.intersection(ev_market.index)
        if len(common) == 0:
            continue

        AR = ev_stock.loc[common] - (alpha + beta * ev_market.loc[common])
        CAR = float(AR.sum())
        CARs.append(CAR)
        directions_correct.append(np.sign(CAR) == predicted_sign)

    if len(CARs) < 5:
        log.info("板塊 %s 窗口 [%d,%d] 樣本不足 (%d)，跳過", sector, *window, len(CARs))
        return None

    arr = np.array(CARs)
    mean_car = float(arr.mean())
    std_car  = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    t_stat   = mean_car / (std_car / np.sqrt(len(arr))) if std_car > 0 else 0.0
    dcr      = float(np.mean(directions_correct))

    # 建議：方向正確率 > 55% 且 |t| > 1.65 → 加強權重
    if dcr > 0.55 and abs(t_stat) > 1.65:
        action = "加強 NLP 權重"
    elif dcr < 0.45 or abs(t_stat) < 0.5:
        action = "減弱 NLP 權重"
    else:
        action = "維持現有權重"

    return CARResult(
        sector=sector,
        window=window,
        event_count=len(CARs),
        CAR_mean=mean_car,
        CAR_std=std_car,
        t_stat=t_stat,
        direction_correct_rate=dcr,
        suggested_action=action,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主流程
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    parser = argparse.ArgumentParser(description="Trump 訊號事件研究法回測")
    parser.add_argument("--csv", required=True, help="Kaggle Trump Twitter CSV 路徑")
    parser.add_argument("--truth_json", default="", help="Truth Social JSON 路徑（可選）")
    parser.add_argument("--min_impact", type=float, default=0.05, help="最低板塊衝擊門檻（預設 0.05）")
    parser.add_argument("--estimation_days", type=int, default=110, help="估計窗口交易日數（預設 110）")
    parser.add_argument("--out", default="output/backtest", help="輸出目錄（預設 output/backtest）")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 載入貼文
    posts: list[RawPost] = load_twitter_csv(args.csv)
    if args.truth_json:
        posts += load_truth_social_json(args.truth_json)

    # 2. NLP 篩選
    events = tag_events(posts, min_impact=args.min_impact)
    if not events:
        log.error("無符合條件的事件，請檢查 CSV 格式或降低 --min_impact")
        sys.exit(1)

    cohort_dates = sorted({e.post.date.normalize().tz_localize(None) for e in events})
    start_date = (cohort_dates[0] - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
    end_date   = (cohort_dates[-1] + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    log.info("行情下載範圍：%s ~ %s", start_date, end_date)

    # 3. 下載行情
    all_tickers = [MARKET_TICKER] + [t for lst in SECTOR_REPR.values() for t in lst]
    all_tickers = list(dict.fromkeys(all_tickers))  # dedup
    prices = fetch_prices(all_tickers, start=start_date, end=end_date)

    if MARKET_TICKER not in prices.columns:
        log.error("^TWII 下載失敗，無法進行回測")
        sys.exit(1)
    market_rets = prices[MARKET_TICKER].pct_change().dropna()

    # 4. 計算 CAR（每個板塊 × 每個事件窗口）
    results: list[CARResult] = []
    for sector, tickers in SECTOR_REPR.items():
        for window in EVENT_WINDOWS:
            log.info("計算 %s [%d,+%d] …", sector, *window)
            r = compute_car_for_sector(
                sector=sector,
                tickers=tickers,
                events=events,
                prices=prices,
                market_rets=market_rets,
                window=window,
                estimation_days=args.estimation_days,
            )
            if r:
                results.append(r)

    if not results:
        log.error("所有板塊樣本均不足，無法生成報告")
        sys.exit(1)

    # 5. 輸出 JSON
    report = {
        "methodology": "Brown & Warner (1985) event study",
        "estimation_window_days": args.estimation_days,
        "gap_days": 10,
        "market_benchmark": MARKET_TICKER,
        "min_impact_threshold": args.min_impact,
        "total_posts_loaded": len(posts),
        "events_filtered": len(events),
        "results": [
            {
                "sector":       r.sector,
                "window":       f"[0,+{r.window[1]}]",
                "n":            r.event_count,
                "CAR_mean":     round(r.CAR_mean, 5),
                "CAR_std":      round(r.CAR_std, 5),
                "t_stat":       round(r.t_stat, 3),
                "t_sig_90pct":  abs(r.t_stat) > 1.645,
                "t_sig_95pct":  abs(r.t_stat) > 1.960,
                "direction_correct_rate": round(r.direction_correct_rate, 3),
                "suggested_action": r.suggested_action,
            }
            for r in results
        ],
    }
    json_path = out_dir / "trump_backtest_report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("✅ JSON 報告已輸出至 %s", json_path)

    # 6. 輸出人類可讀摘要
    lines = [
        "=" * 72,
        "  Trump 訊號回測摘要  （Brown & Warner 1985 事件研究法）",
        "=" * 72,
        f"  總貼文數：{len(posts):,}  │  符合門檻事件：{len(events):,}  │  最低衝擊：{args.min_impact}",
        f"  估計窗口：{args.estimation_days} 交易日（前 10 日 gap）",
        f"  市場基準：{MARKET_TICKER}",
        "",
        f"  {'板塊':<12} {'窗口':<8} {'N':>5} {'CAR%':>8} {'t':>7} {'90%?':>6} {'方向正確率':>10} {'建議'}",
        "  " + "-" * 68,
    ]
    for r in sorted(results, key=lambda x: abs(x.t_stat), reverse=True):
        lines.append(
            f"  {r.sector:<12} [0,+{r.window[1]}]   "
            f"{r.event_count:>5} "
            f"{r.CAR_mean*100:>7.2f}% "
            f"{r.t_stat:>7.2f} "
            f"{'✓' if abs(r.t_stat) > 1.645 else '':>6} "
            f"{r.direction_correct_rate:>9.1%} "
            f"  {r.suggested_action}"
        )
    lines += [
        "",
        "  ★ 建議操作說明：",
        "    「加強 NLP 權重」= 方向正確且顯著，可提高 composite.py 中 NLP 比重",
        "    「減弱 NLP 權重」= 方向不穩定或不顯著，應降低 NLP 比重",
        "    「維持現有權重」= 目前 50:50 分配合理",
        "=" * 72,
    ]
    txt_path = out_dir / "trump_backtest_summary.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("✅ 文字摘要已輸出至 %s", txt_path)

    # 7. 列印到 stdout
    print("\n".join(lines))


if __name__ == "__main__":
    main()
