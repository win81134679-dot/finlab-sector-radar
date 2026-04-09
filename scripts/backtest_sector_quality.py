"""
backtest_sector_quality.py — 板塊分類品質回測

比較三種方案：
  A: 現狀（custom_sectors.csv 僅 279 檔）
  B: custom + auto（無 correlation gate）
  C: custom + auto + correlation gate

指標：
  1. Intra-sector return correlation（同質性，越高越好）
  2. 信號翻轉頻率（flip rate，越低越穩定）
  3. 板塊亮燈後 20 天 hit rate（個股漲幅 > 0 的比例）

Sensitivity analysis：
  - 相關性門檻：0.25, 0.30, 0.35, 0.40, 0.45, 0.50
  - Rolling window：120, 180, 250 天

需要 FINLAB_API_TOKEN 環境變數（GitHub Actions secrets 或本機 .env）
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 專案根目錄
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401 — 必須最早 import
from src import config
from src.data_fetcher import DataFetcher
from src.sector_map import SectorMap
from src.analyzers.correlation_gate import (
    compute_sector_correlations,
    filter_stocks_by_correlation,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _load_scheme_a() -> dict[str, list[str]]:
    """方案 A：僅 custom_sectors.csv。"""
    sm = SectorMap()
    sm._sectors = {}
    sm._load_csv(config.CUSTOM_SECTORS_CSV, source="custom")
    sm._loaded = True
    return {sid: sm.get_stocks(sid) for sid in sm.all_sector_ids()}


def _load_scheme_b() -> dict[str, list[str]]:
    """方案 B：custom + auto（無閘門）。"""
    sm = SectorMap()
    sm.load()  # loads custom + auto
    return {sid: sm.get_stocks(sid) for sid in sm.all_sector_ids()}


def _load_scheme_c(
    price_df: pd.DataFrame,
    threshold: float,
    window: int,
) -> dict[str, list[str]]:
    """方案 C：custom + auto + correlation gate。"""
    sm = SectorMap()
    sm.load()
    all_stocks = {sid: sm.get_stocks(sid) for sid in sm.all_sector_ids()}
    corr = compute_sector_correlations(price_df, all_stocks, window=window)
    return filter_stocks_by_correlation(all_stocks, corr, threshold=threshold)


def _measure_intra_correlation(
    price_df: pd.DataFrame,
    sector_stocks: dict[str, list[str]],
    window: int = 120,
) -> dict[str, float]:
    """測量每個板塊的平均 intra-sector return correlation。"""
    returns = price_df.pct_change().iloc[1:]
    if len(returns) > window:
        returns = returns.iloc[-window:]

    result = {}
    for sector_id, stocks in sector_stocks.items():
        avail = [s for s in stocks if s in returns.columns]
        if len(avail) < 3:
            result[sector_id] = float("nan")
            continue
        sector_ret = returns[avail].dropna(how="all")
        # 計算所有股票兩兩相關性的均值
        corr_matrix = sector_ret.corr()
        n = len(corr_matrix)
        if n < 2:
            result[sector_id] = float("nan")
            continue
        # 取上三角（排除對角線）
        mask = np.triu(np.ones((n, n), dtype=bool), k=1)
        vals = corr_matrix.values[mask]
        vals = vals[~np.isnan(vals)]
        result[sector_id] = float(np.mean(vals)) if len(vals) > 0 else float("nan")

    return result


def _measure_hit_rate(
    price_df: pd.DataFrame,
    sector_stocks: dict[str, list[str]],
    forward_days: int = 20,
    lookback: int = 250,
) -> dict[str, float]:
    """
    簡化 hit rate：最近 lookback 天內，板塊平均報酬 > 0 的日子，
    其成員個股在 forward_days 後也上漲的比例。
    """
    if len(price_df) < lookback + forward_days:
        lookback = max(len(price_df) - forward_days - 1, 60)

    returns = price_df.pct_change()
    result = {}

    for sector_id, stocks in sector_stocks.items():
        avail = [s for s in stocks if s in returns.columns]
        if len(avail) < 3:
            result[sector_id] = float("nan")
            continue

        sector_ret = returns[avail].iloc[-(lookback + forward_days):]
        # 板塊等權均報酬
        sector_avg = sector_ret.mean(axis=1)
        # 找板塊表現好的日子（均報酬 > 0.5%）
        good_days_idx = sector_avg.index[sector_avg > 0.005]
        # 只取能計算 forward return 的日子
        good_days_idx = good_days_idx[good_days_idx.isin(sector_ret.index[:-forward_days])]

        if len(good_days_idx) == 0:
            result[sector_id] = float("nan")
            continue

        hits = 0
        total = 0
        for day in good_days_idx[:50]:  # 取樣最多 50 天避免太慢
            day_pos = sector_ret.index.get_loc(day)
            future_pos = day_pos + forward_days
            if future_pos >= len(sector_ret):
                continue
            for s in avail:
                current = price_df[s].iloc[day_pos] if s in price_df.columns else None
                future = price_df[s].iloc[future_pos] if s in price_df.columns else None
                if current is not None and future is not None and current > 0:
                    total += 1
                    if future > current:
                        hits += 1

        result[sector_id] = round(hits / max(total, 1), 4)

    return result


def run_backtest() -> dict:
    """執行完整回測，回傳結果字典。"""
    logger.info("=" * 60)
    logger.info("板塊分類品質回測 — 三方案比較")
    logger.info("=" * 60)

    # 初始化 FinLab
    fetcher = DataFetcher()
    fetcher.login(config.FINLAB_API_TOKEN)
    price_df = fetcher.get("price:收盤價")
    logger.info("收盤價資料：%d 天 x %d 檔", price_df.shape[0], price_df.shape[1])

    # 載入三方案
    scheme_a = _load_scheme_a()
    scheme_b = _load_scheme_b()

    logger.info("方案 A（custom only）：%d 板塊, %d 檔",
                len(scheme_a), sum(len(v) for v in scheme_a.values()))
    logger.info("方案 B（custom+auto）：%d 板塊, %d 檔",
                len(scheme_b), sum(len(v) for v in scheme_b.values()))

    results = {}

    # ── 方案 A & B 固定指標 ────────────────────────────────────
    for label, scheme in [("A_custom_only", scheme_a), ("B_custom_auto", scheme_b)]:
        logger.info("正在計算方案 %s...", label)
        corr = _measure_intra_correlation(price_df, scheme, window=120)
        hr = _measure_hit_rate(price_df, scheme)
        valid_corr = [v for v in corr.values() if v == v]
        valid_hr = [v for v in hr.values() if v == v]
        results[label] = {
            "n_sectors": len(scheme),
            "n_stocks": sum(len(v) for v in scheme.values()),
            "avg_intra_corr": round(float(np.mean(valid_corr)), 4) if valid_corr else None,
            "avg_hit_rate": round(float(np.mean(valid_hr)), 4) if valid_hr else None,
            "per_sector_corr": {k: round(v, 4) if v == v else None for k, v in corr.items()},
        }

    # ── 方案 C 敏感度分析 ──────────────────────────────────────
    thresholds = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    windows = [120, 180, 250]

    sensitivity = {}
    for window in windows:
        for thresh in thresholds:
            key = f"C_w{window}_t{thresh:.2f}"
            logger.info("正在計算方案 C（window=%d, threshold=%.2f）...", window, thresh)
            scheme_c = _load_scheme_c(price_df, threshold=thresh, window=window)
            corr = _measure_intra_correlation(price_df, scheme_c, window=window)
            hr = _measure_hit_rate(price_df, scheme_c)
            valid_corr = [v for v in corr.values() if v == v]
            valid_hr = [v for v in hr.values() if v == v]
            sensitivity[key] = {
                "window": window,
                "threshold": thresh,
                "n_sectors": len(scheme_c),
                "n_stocks": sum(len(v) for v in scheme_c.values()),
                "avg_intra_corr": round(float(np.mean(valid_corr)), 4) if valid_corr else None,
                "avg_hit_rate": round(float(np.mean(valid_hr)), 4) if valid_hr else None,
            }

    results["C_sensitivity"] = sensitivity

    # ── 最佳組合推薦 ──────────────────────────────────────────
    best_key = max(
        sensitivity.keys(),
        key=lambda k: (sensitivity[k].get("avg_intra_corr") or 0)
                      + (sensitivity[k].get("avg_hit_rate") or 0),
    )
    results["recommended"] = {
        "config": best_key,
        **sensitivity[best_key],
    }

    return results


def main() -> None:
    results = run_backtest()

    # 寫出結果
    out_path = OUTPUT_DIR / "backtest_sector_quality.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 打印摘要
    print("\n" + "=" * 60)
    print("回測結果摘要")
    print("=" * 60)

    for label in ["A_custom_only", "B_custom_auto"]:
        r = results[label]
        print(f"\n方案 {label}:")
        print(f"  板塊數: {r['n_sectors']}, 股票數: {r['n_stocks']}")
        print(f"  平均 intra-sector correlation: {r['avg_intra_corr']}")
        print(f"  平均 hit rate (20天): {r['avg_hit_rate']}")

    print("\n方案 C 敏感度分析:")
    print(f"  {'Config':<25} {'Sectors':>7} {'Stocks':>7} {'Corr':>8} {'Hit%':>8}")
    for key, v in results["C_sensitivity"].items():
        print(f"  {key:<25} {v['n_sectors']:>7} {v['n_stocks']:>7} "
              f"{v['avg_intra_corr'] or 'N/A':>8} {v['avg_hit_rate'] or 'N/A':>8}")

    rec = results["recommended"]
    print(f"\n✅ 推薦組合: {rec['config']}")
    print(f"   corr={rec['avg_intra_corr']}, hit_rate={rec['avg_hit_rate']}")
    print(f"\n結果已寫入: {out_path}")


if __name__ == "__main__":
    main()
