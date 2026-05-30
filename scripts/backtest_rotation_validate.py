"""
backtest_rotation_validate.py — 輪動系統歷史驗證 + 權重決勝（一次跑完）

對真實 FinLab 資料，回答：
  1. 哪個法人權重變體 OOS 最好？（WFA：年化/夏普/卡瑪/MDD）
  2. 每月/每季選出的板塊，未來真的贏過全板塊平均嗎？（命中率 + 超額）
  3. 選出的個股，未來命中率（>0）與贏過大盤的比例？

⚠️ 誠實原則：論文數字僅先驗；結論以此 OOS 為準。個股排名為動能代理（非完整 stock_scorer）。
需 FINLAB_API_TOKEN。

用法：
  python scripts/backtest_rotation_validate.py
  python scripts/backtest_rotation_validate.py --top-n 3 --top-k 3 --hold 1
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows cp950 console 無法輸出 emoji/部分 Unicode → 強制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from src import ssl_fix  # noqa: F401
from src import config
from src.data_fetcher import DataFetcher
from src.sector_map import SectorMap
from src.analyzers import rotation_backtest as rb
from src.analyzers import rotation_validation as rvmod

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("validate")

_FOREIGN = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
_DEALER = "institutional_investors_trading_summary:自營商買賣超股數(自行買賣)"
_TAIEX = "taiex_total_index:收盤指數"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=3, help="選前 N 強板塊")
    ap.add_argument("--top-k", type=int, default=3, help="每板塊選前 K 檔個股")
    ap.add_argument("--hold", type=int, default=1, help="持有月數（1=月頻, 3=季頻）")
    ap.add_argument("--train", type=int, default=12)
    ap.add_argument("--test", type=int, default=3)
    args = ap.parse_args()

    if not config.is_finlab_token_set():
        logger.error("FINLAB_API_TOKEN 未設定")
        return 1
    fetcher = DataFetcher()
    if not fetcher.login():
        return 1
    sm = SectorMap()
    sm.load()
    sector_stocks = {sid: sm.get_stocks(sid) for sid in sm.all_sector_ids()}

    logger.info("拉取價格 + 法人 + TAIEX …")
    price_df = fetcher.get("price:收盤價")
    foreign = fetcher.get(_FOREIGN)
    trust = fetcher.get(_TRUST)
    try:
        dealer = fetcher.get(_DEALER)
    except Exception:
        dealer = None
    taiex_df = fetcher.get(_TAIEX)
    benchmark = None
    if taiex_df is not None and not taiex_df.empty:
        benchmark = taiex_df.iloc[:, 0].dropna()

    if price_df is None or foreign is None or trust is None:
        logger.error("核心資料缺失")
        return 1

    rebs = rb.month_end_dates(price_df.index)
    print(f"\n資料期間 {rebs[0].date()} ~ {rebs[-1].date()}（{len(rebs)} 個月）")
    print(f"參數：top_n={args.top_n} 板塊, top_k={args.top_k} 股/板塊, "
          f"持有={args.hold}月, WFA train={args.train}/test={args.test}")

    # ── 1. WFA 權重決勝 ──────────────────────────────────────────
    print("\n" + "=" * 80)
    print("【1】法人權重 Walk-Forward 決勝（OOS）")
    print("=" * 80)
    print(f"{'變體':<26}{'年化':>9}{'夏普':>8}{'卡瑪':>8}{'MDD':>9}{'OOS段':>7}")
    print("-" * 80)
    wfa_rows = []
    for v in rb.VARIANTS:
        m = rb.walk_forward(price_df, foreign, trust, sector_stocks, v,
                            train_months=args.train, test_months=args.test,
                            top_n=args.top_n, dealer_net=dealer)
        wfa_rows.append((v, m))
        print(f"{v.name:<26}{m['annual']*100:>8.1f}%{m['sharpe']:>8.2f}"
              f"{m['calmar']:>8.2f}{m['mdd']*100:>8.1f}%{m.get('oos_segments',0):>7}")
    bench_m = rb.metrics(_bench_nav(benchmark, rebs)) if benchmark is not None else {}
    if bench_m:
        print("-" * 80)
        print(f"{'TAIEX 買進持有':<26}{bench_m['annual']*100:>8.1f}%{bench_m['sharpe']:>8.2f}"
              f"{bench_m['calmar']:>8.2f}{bench_m['mdd']*100:>8.1f}%")
    best_v = max(wfa_rows, key=lambda r: r[1]["sharpe"])[0]
    print(f"\n🏆 OOS 夏普最高：{best_v.name}（外資×{best_v.foreign}/投信×{best_v.trust}）")

    # ── 2+3. 驗證：板塊命中 + 個股命中（用每個變體跑全期）──────────
    print("\n" + "=" * 80)
    print("【2】板塊輪動命中率 +【3】個股命中率（全期，非 OOS）")
    print("=" * 80)
    print(f"{'變體':<26}{'板塊命中':>9}{'板塊超額':>9}{'個股勝率':>9}{'贏大盤':>8}{'個股樣本':>9}")
    print("-" * 80)
    for v in rb.VARIANTS:
        r = rvmod.validate(price_df, foreign, trust, sector_stocks, v,
                           top_n_sectors=args.top_n, top_k_stocks=args.top_k,
                           hold_months=args.hold, benchmark=benchmark, dealer_net=dealer)
        print(f"{v.name:<26}{r['sector_hit_rate']*100:>8.0f}%{r['sector_avg_excess']*100:>8.1f}%"
              f"{r['stock_hit_rate']*100:>8.0f}%{r['stock_beat_bench_rate']*100:>7.0f}%"
              f"{r['n_stock_samples']:>9}")
    print("=" * 80)
    print("\n判讀：板塊命中率 > 50% 且超額為正 → 輪動選板塊有效；")
    print("      個股勝率 > 50% 且贏大盤 > 50% → 選個股可信。")
    print("      樣本期間有限/差距小時，誠實標註不過度宣稱。\n")

    print(f"建議：將 config.py 的 INST_FLOW_WEIGHT_FOREIGN={best_v.foreign}, "
          f"INST_FLOW_WEIGHT_TRUST={best_v.trust}（依本次 OOS 勝出變體）。")
    return 0


def _bench_nav(benchmark, rebs):
    import pandas as pd
    if benchmark is None:
        return pd.Series(dtype=float)
    nav, base = {}, None
    for d in rebs:
        sub = benchmark.loc[benchmark.index <= d]
        if sub.empty:
            continue
        v = float(sub.iloc[-1])
        base = base or v
        nav[d] = v / base
    return pd.Series(nav)


if __name__ == "__main__":
    sys.exit(main())
