"""
backtest_trust_refine.py — 投信因子細化 bakeoff（在 +3.7pp 贏家上繼續榨 alpha）

bakeoff 已證投信連買≥3日是唯一真 alpha。本腳本細化：
  ① 連買天數：2/3/4/5/6 日 → 哪個 alpha 最高
  ② 金額門檻：連 n 日 + 近 n 日累積買超金額 ≥ 門檻（過濾小額點火）
  ③ 排除季末作帳期（P2，3/6/9/12 月最後 10 交易日）
  ④ 持有期：20 日（P3 宣稱）vs 60 日（中長期）

全部 point-in-time、命中=贏 TAIEX、與 baseline 比 alpha，讓數據選最佳組合。
⚠️ 誠實：細化後 alpha 沒提升就照實寫。需 FINLAB_API_TOKEN。
用法：python -u scripts/backtest_trust_refine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from src import ssl_fix  # noqa: F401
from src import config
from src.data_fetcher import DataFetcher
from src.analyzers import chip_factor_bakeoff as bk

import pandas as pd

_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
_TAIEX = "taiex_total_index:收盤指數"


def log(m):
    print(m, flush=True)


def main() -> int:
    if not config.is_finlab_token_set():
        log("FINLAB_API_TOKEN 未設定"); return 1
    f = DataFetcher()
    if not f.login():
        return 1

    log("拉取資料…")
    price = f.get("price:收盤價")
    trust = f.get(_TRUST)
    taiex_df = f.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if price is None or trust is None or taiex is None:
        log("資料缺失"); return 1
    pidx = price.index
    trust = trust.reindex(index=pidx)

    def run_bakeoff(hold):
        me = pd.Series(pidx, index=pidx).groupby([pidx.year, pidx.month]).last().tolist()
        me = [d for d in me if (pidx > d).sum() >= hold]
        beat_me = bk.forward_beat_matrix(price, taiex, hold).reindex(me, method="ffill")

        rows = []
        # ① 連買天數
        for n in (2, 3, 4, 5, 6):
            sig = bk.reindex_month_end(bk.consecutive_buy_signal(trust, n), me)
            rows.append((f"投信連買≥{n}日", bk.evaluate_factor(sig, beat_me)))
        # ② 金額門檻（以連3日為基底，門檻單位：元）
        for amt, lab in ((5e7, "5千萬"), (1e8, "1億"), (3e8, "3億")):
            sig = bk.reindex_month_end(bk.amount_filter(trust, price, 3, amt), me)
            rows.append((f"投信連3日+金額≥{lab}", bk.evaluate_factor(sig, beat_me)))
        # ③ 排除季末作帳（連3日）
        base3 = bk.consecutive_buy_signal(trust, 3)
        sig = bk.reindex_month_end(bk.exclude_quarter_end(base3, 10), me)
        rows.append(("投信連3日 排除季末作帳", bk.evaluate_factor(sig, beat_me)))
        # ④ 連3日 + 金額1億 + 排除季末（綜合最佳候選）
        combo = bk.exclude_quarter_end(bk.amount_filter(trust, price, 3, 1e8), 10)
        sig = bk.reindex_month_end(combo, me)
        rows.append(("投信連3日+金額1億+排季末", bk.evaluate_factor(sig, beat_me)))
        return rows, len(me)

    for hold in (60, 20):
        rows, nreb = run_bakeoff(hold)
        base = rows[0][1]["base_rate"]
        log("\n" + "=" * 76)
        log(f"投信因子細化 bakeoff（持有 {hold} 日{'≈1季' if hold==60 else '≈1月'}，{nreb} rebalance）")
        log("=" * 76)
        log(f"{'因子':<32}{'命中率':>9}{'baseline':>10}{'alpha':>9}{'樣本':>10}")
        log("-" * 76)
        for name, r in sorted(rows, key=lambda x: -x[1]["alpha"]):
            log(f"{name:<32}{r['hit_rate']*100:>8.1f}%{r['base_rate']*100:>9.1f}%"
                f"{r['alpha']*100:>+8.1f}%{r['n']:>10,}")
        best = max(rows, key=lambda x: x[1]["alpha"])
        log("-" * 76)
        log(f"🏆 持有{hold}日最高 alpha：{best[0]}（+{best[1]['alpha']*100:.1f}pp, n={best[1]['n']:,}）")
    log("\n判讀：細化版 alpha 若顯著高於原始「連3日+3.7pp」才採用；樣本太少(<2000)的高 alpha 要警惕雜訊。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
