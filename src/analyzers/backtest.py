"""
backtest.py — MAGA 訊號回測引擎

策略邏輯：
  - 每次 composite_score(sector) >= entry_threshold → 買入
  - composite_score(sector) <  exit_threshold       → 賣出
  - 使用 output/ohlcv/{ticker}.json 作為歷史價格

輸出：output/portfolio/backtest.json
{
  "ran_at":          "ISO",
  "strategy":        {entry_threshold, exit_threshold, lookback_days, initial_capital},
  "tickers_tested":  int,
  "results": {
    ticker: {
      "name_zh":    str,
      "trades":     [{buy_date, buy_price, sell_date, sell_price, pnl_pct, hold_days}],
      "total_return_pct": float,
      "win_rate":         float,   # 勝率 0.0-1.0
      "trade_count":      int,
      "max_drawdown_pct": float,
    }
  },
  "portfolio_summary": {
    "avg_return_pct":  float,
    "avg_win_rate":    float,
    "best_ticker":     str,
    "worst_ticker":    str,
  }
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_OHLCV_DIR   = Path(__file__).parents[2] / "output" / "ohlcv"
_OUTPUT_DIR  = Path(__file__).parents[2] / "output" / "portfolio"

# 預設策略參數
DEFAULT_ENTRY_THRESHOLD = 0.25
DEFAULT_EXIT_THRESHOLD  = 0.05
DEFAULT_LOOKBACK_DAYS   = 252   # 約 1 年交易日
DEFAULT_INITIAL_CAPITAL = 1_000_000.0


def _load_ohlcv(ticker: str) -> list[dict]:
    """讀取 output/ohlcv/{ticker}.json，回傳 [{date, close, volume, ...}, ...]。"""
    p = _OHLCV_DIR / f"{ticker}.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)

    # 支援兩種格式：
    # 1) [{date, close, ...}, ...]
    # 2) {dates:[...], closes:[...], ...}  (ohlcv 壓縮格式)
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        dates  = raw.get("dates",  raw.get("date",  []))
        closes = raw.get("closes", raw.get("close", []))
        highs  = raw.get("highs",  raw.get("high",  [None] * len(dates)))
        lows   = raw.get("lows",   raw.get("low",   [None] * len(dates)))
        vols   = raw.get("volumes",raw.get("volume",[None] * len(dates)))
        return [
            {"date": d, "close": c, "high": h, "low": l, "volume": v}
            for d, c, h, l, v in zip(dates, closes, highs, lows, vols)
        ]
    return []


def _max_drawdown(equity_curve: list[float]) -> float:
    """計算最大回撤 %（負值）。"""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
    return round(max_dd, 2)


def backtest_ticker(
    ticker: str,
    name_zh: str,
    sector: str,
    composite_series: list[tuple[str, float]],  # [(date_str, score), ...] 由舊到新
    entry_threshold: float = DEFAULT_ENTRY_THRESHOLD,
    exit_threshold:  float = DEFAULT_EXIT_THRESHOLD,
    lookback_days:   int   = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any] | None:
    """
    對單支股票執行回測。

    Parameters
    ----------
    composite_series : [(date, composite_score), ...]，日期由舊到新
    """
    ohlcv = _load_ohlcv(ticker)
    if not ohlcv:
        return None

    # 轉成 date → close 查找表
    price_map: dict[str, float] = {}
    for row in ohlcv[-lookback_days:]:
        d = row.get("date") or row.get("Date") or ""
        c = row.get("close") or row.get("Close")
        if d and c and float(c) > 0:
            price_map[str(d)[:10]] = float(c)

    if not price_map:
        return None

    sorted_dates = sorted(price_map.keys())

    # 將 composite_series 轉為 {date: score}
    score_map: dict[str, float] = {str(d)[:10]: s for d, s in composite_series}

    # ── 回測主邏輯 ────────────────────────────────────────────────────────
    in_position = False
    buy_date: str | None = None
    buy_price: float | None = None

    trades: list[dict] = []
    equity_curve: list[float] = [DEFAULT_INITIAL_CAPITAL]
    cash = DEFAULT_INITIAL_CAPITAL
    shares = 0.0

    for dt in sorted_dates:
        price = price_map[dt]
        score = score_map.get(dt, 0.0)

        if not in_position and score >= entry_threshold:
            # 全倉買入
            shares = cash / price
            buy_date  = dt
            buy_price = price
            in_position = True

        elif in_position and score < exit_threshold:
            # 賣出
            sell_price = price
            pnl_pct = (sell_price - buy_price) / buy_price * 100  # type: ignore[operator]
            hold_days = (
                datetime.fromisoformat(dt) - datetime.fromisoformat(buy_date)  # type: ignore[arg-type]
            ).days

            cash = shares * sell_price
            trades.append({
                "buy_date":   buy_date,
                "buy_price":  round(buy_price, 2),  # type: ignore[arg-type]
                "sell_date":  dt,
                "sell_price": round(sell_price, 2),
                "pnl_pct":    round(pnl_pct, 2),
                "hold_days":  hold_days,
            })
            in_position = False
            shares = 0.0

        # 資金曲線
        current_value = cash if not in_position else shares * price
        equity_curve.append(current_value)

    # 若期末仍持倉，按最後價格計算
    if in_position and sorted_dates:
        last_price = price_map[sorted_dates[-1]]
        last_pnl   = (last_price - buy_price) / buy_price * 100  # type: ignore[operator]
        trades.append({
            "buy_date":   buy_date,
            "buy_price":  round(buy_price, 2),  # type: ignore[arg-type]
            "sell_date":  "(持有中)",
            "sell_price": round(last_price, 2),
            "pnl_pct":    round(last_pnl, 2),
            "hold_days":  (datetime.fromisoformat(sorted_dates[-1]) - datetime.fromisoformat(buy_date)).days,  # type: ignore[arg-type]
        })
        cash = shares * last_price

    total_return = (cash - DEFAULT_INITIAL_CAPITAL) / DEFAULT_INITIAL_CAPITAL * 100
    win_rate = (
        len([t for t in trades if t["pnl_pct"] > 0]) / len(trades)
        if trades else 0.0
    )

    return {
        "name_zh":          name_zh,
        "sector":           sector,
        "trades":           trades,
        "total_return_pct": round(total_return, 2),
        "win_rate":         round(win_rate, 3),
        "trade_count":      len(trades),
        "max_drawdown_pct": _max_drawdown(equity_curve),
    }


def run_backtest(
    composite_result: dict,
    maga_stocks: list[dict],
    entry_threshold: float = DEFAULT_ENTRY_THRESHOLD,
    exit_threshold:  float = DEFAULT_EXIT_THRESHOLD,
    lookback_days:   int   = DEFAULT_LOOKBACK_DAYS,
    write_output:    bool  = True,
) -> dict[str, Any]:
    """
    對所有受益板塊股票執行回測。

    composite_result 的 scores 用於建構 composite_series（
    以單一當前分數模擬「整個歷史都是這個分數」，作為簡化假設）。
    若日後有歷史 composite 時間序列，可傳入更精確的 composite_series_map。
    """
    scores = composite_result.get("scores", {})
    results: dict[str, Any] = {}

    for stock in maga_stocks:
        if stock.get("category") != "beneficiary":
            continue
        ticker   = stock["id"]
        sector   = stock.get("sector_id", "")
        name_zh  = stock.get("name_zh", ticker)
        composite_score = scores.get(sector, {}).get("composite", 0.0)

        # 簡化：用當前分數填滿所有歷史日期
        ohlcv = _load_ohlcv(ticker)
        if not ohlcv:
            continue

        dates = []
        for row in ohlcv[-lookback_days:]:
            d = row.get("date") or row.get("Date") or ""
            if d:
                dates.append(str(d)[:10])

        composite_series = [(d, composite_score) for d in dates]

        res = backtest_ticker(
            ticker, name_zh, sector, composite_series,
            entry_threshold, exit_threshold, lookback_days,
        )
        if res:
            results[ticker] = res

    # 組合摘要
    portfolio_summary: dict[str, Any] = {}
    if results:
        returns  = [r["total_return_pct"] for r in results.values()]
        winrates = [r["win_rate"] for r in results.values()]
        tickers  = list(results.keys())

        best_t  = max(tickers, key=lambda t: results[t]["total_return_pct"])
        worst_t = min(tickers, key=lambda t: results[t]["total_return_pct"])

        portfolio_summary = {
            "avg_return_pct": round(sum(returns) / len(returns), 2),
            "avg_win_rate":   round(sum(winrates) / len(winrates), 3),
            "best_ticker":    best_t,
            "worst_ticker":   worst_t,
        }

    output = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "strategy": {
            "entry_threshold": entry_threshold,
            "exit_threshold":  exit_threshold,
            "lookback_days":   lookback_days,
            "initial_capital": DEFAULT_INITIAL_CAPITAL,
        },
        "tickers_tested":  len(results),
        "results":         results,
        "portfolio_summary": portfolio_summary,
    }

    if write_output:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_OUTPUT_DIR / "backtest.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    return output


def load_backtest() -> dict | None:
    p = _OUTPUT_DIR / "backtest.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)
