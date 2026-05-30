"""
backtest_rotation.py — 輪動策略 Walk-Forward 回測 CLI（決定法人權重）

用本系統真實 FinLab 資料，比較三種法人權重變體的 OOS 績效：
  · foreign_led            外資×2 / 投信×1（中長期假說，P5/P6）
  · trust_led              投信×2 / 外資×1（短線假說，P1/P2/P3）
  · trust_led_dealer_filter 投信×2 / 外資×1 + 自營雜訊濾網

策略：月頻選前 N 強板塊（rotation_score = z動能 + z籌碼）等權持有，扣交易成本。
對照基準：買進持有 TAIEX（等同被動）。

⚠️ 誠實原則：論文數字（如投信 27.82%）僅作先驗；**正式權重以此 OOS 結果為準**。
需要 FINLAB_API_TOKEN（.env 或環境變數）。

用法：
  python scripts/backtest_rotation.py                 # 預設 top_n=3, train=12, test=3
  python scripts/backtest_rotation.py --top-n 5 --train 18 --test 6
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401 — 必須最早 import
from src import config
from src.data_fetcher import DataFetcher
from src.sector_map import SectorMap
from src.analyzers import rotation_backtest as rb

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("backtest_rotation")

_FOREIGN_KEY = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST_KEY = "institutional_investors_trading_summary:投信買賣超股數"
_DEALER_KEY = "institutional_investors_trading_summary:自營商買賣超股數(自行買賣)"
_TAIEX_KEY = "taiex_total_index:收盤指數"


def _taiex_buy_hold(fetcher, rebs) -> dict:
    """TAIEX 買進持有基準指標（同 rebalance 期間）。"""
    import pandas as pd
    df = fetcher.get(_TAIEX_KEY)
    if df is None or df.empty:
        return {}
    s = df.iloc[:, 0].dropna()
    nav_vals = {}
    base = None
    for d in rebs:
        sub = s.loc[s.index <= d]
        if sub.empty:
            continue
        v = float(sub.iloc[-1])
        base = base or v
        nav_vals[d] = v / base
    return rb.metrics(pd.Series(nav_vals)) if nav_vals else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=3)
    ap.add_argument("--train", type=int, default=12, help="train months")
    ap.add_argument("--test", type=int, default=3, help="test months")
    args = ap.parse_args()

    if not config.is_finlab_token_set():
        logger.error("FINLAB_API_TOKEN 未設定，無法回測")
        return 1

    fetcher = DataFetcher()
    if not fetcher.login():
        logger.error("FinLab 登入失敗")
        return 1

    sm = SectorMap()
    if sm.load() == 0:
        logger.error("板塊定義載入失敗")
        return 1
    sector_stocks = {sid: sm.get_stocks(sid) for sid in sm.all_sector_ids()}

    logger.info("拉取價格 + 法人買賣超…")
    price_df = fetcher.get("price:收盤價")
    foreign = fetcher.get(_FOREIGN_KEY)
    trust = fetcher.get(_TRUST_KEY)
    dealer = None
    try:
        dealer = fetcher.get(_DEALER_KEY)
    except Exception:
        logger.warning("自營商(自行買賣)資料不可用，dealer_filter 變體將退化")

    if price_df is None or foreign is None or trust is None:
        logger.error("核心資料缺失，中止")
        return 1

    rebs = rb.month_end_dates(price_df.index)
    logger.info("資料期間 %s ~ %s（%d 個月）", rebs[0].date(), rebs[-1].date(), len(rebs))

    print("\n" + "=" * 78)
    print(f"輪動策略 Walk-Forward 回測  (top_n={args.top_n}, train={args.train}m, test={args.test}m)")
    print("=" * 78)
    print(f"{'變體':<26}{'年化':>8}{'夏普':>8}{'卡瑪':>8}{'MDD':>9}{'OOS段':>7}")
    print("-" * 78)

    rows = []
    for v in rb.VARIANTS:
        m = rb.walk_forward(
            price_df, foreign, trust, sector_stocks, v,
            train_months=args.train, test_months=args.test,
            top_n=args.top_n, dealer_net=dealer,
        )
        rows.append((v.name, m))
        print(f"{v.name:<26}{m['annual']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['calmar']:>8.2f}{m['mdd']*100:>8.1f}%{m.get('oos_segments',0):>7}")

    bench = _taiex_buy_hold(fetcher, rebs)
    if bench:
        print("-" * 78)
        print(f"{'TAIEX 買進持有(基準)':<26}{bench['annual']*100:>7.1f}%{bench['sharpe']:>8.2f}"
              f"{bench['calmar']:>8.2f}{bench['mdd']*100:>8.1f}%")
    print("=" * 78)

    # 勝出變體（依夏普）
    best = max(rows, key=lambda r: r[1]["sharpe"])
    print(f"\n🏆 OOS 夏普最高：{best[0]}（Sharpe {best[1]['sharpe']:.2f}）")
    print("→ 建議將 INST_FLOW_WEIGHT_FOREIGN / _TRUST 設為此變體權重（config.py）。")
    print("⚠️ 樣本期間有限時，差距不顯著就維持現狀並標註，勿過度擬合。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
