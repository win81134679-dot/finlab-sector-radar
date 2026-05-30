"""
backtest_chip_factors.py — 法人籌碼因子 bakeoff（point-in-time，讓數據選贏家）

把 P1–P6 每個假說當獨立選股因子，持有1季、命中=贏 TAIEX，與 baseline(全股贏大盤率)
比較 → alpha = 命中率 − baseline。alpha 顯著為正才值得裝進燈2。

因子：
  F1  外資持股比率上升(60日)        P6（最有望，日頻無前視）
  F2  外資連買 ≥10 日               P1
  F2b 外資連買 ≥3 日（現行對照）     P1 對照
  F3  投信連買 ≥3 日                P2/P3
  F4  自營(自行買賣)近20日淨買       P1（預期 ≤baseline，反指標/雜訊驗證）
  F4h 自營(避險)近20日淨買          對照（避險帳方向常與現貨相反）

⚠️ 誠實：alpha 接近 0 或為負就照實寫，不硬湊。需 FINLAB_API_TOKEN。
用法：python -u scripts/backtest_chip_factors.py [--hold 60]
"""
from __future__ import annotations

import argparse
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


def log(m):
    print(m, flush=True)


_FOREIGN = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
_DEALER_SELF = "institutional_investors_trading_summary:自營商買賣超股數(自行買賣)"
_DEALER_HEDGE = "institutional_investors_trading_summary:自營商買賣超股數(避險)"
_HOLDING = "foreign_investors_shareholding:全體外資及陸資持股比率"
_TAIEX = "taiex_total_index:收盤指數"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, default=60, help="持有交易日(預設60≈1季)")
    args = ap.parse_args()
    HOLD = args.hold

    if not config.is_finlab_token_set():
        log("FINLAB_API_TOKEN 未設定"); return 1
    f = DataFetcher()
    if not f.login():
        return 1

    log("拉取資料…")
    price = f.get("price:收盤價")
    foreign = f.get(_FOREIGN)
    trust = f.get(_TRUST)
    dealer_self = f.get(_DEALER_SELF)
    dealer_hedge = f.get(_DEALER_HEDGE)
    holding = f.get(_HOLDING)
    taiex_df = f.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if price is None or taiex is None:
        log("核心資料缺失"); return 1

    pidx = price.index
    # 對齊所有法人/持股到 price index
    def align(df):
        return df.reindex(index=pidx) if df is not None else None
    foreign, trust = align(foreign), align(trust)
    dealer_self, dealer_hedge = align(dealer_self), align(dealer_hedge)
    holding = align(holding)

    # 月底（需未來 HOLD 日）
    me = pd.Series(pidx, index=pidx).groupby([pidx.year, pidx.month]).last().tolist()
    me = [d for d in me if (pidx > d).sum() >= HOLD]
    log(f"期間 {me[0].date()} ~ {me[-1].date()}（{len(me)} rebalance, 持有 {HOLD} 日）")

    log("計算未來贏大盤矩陣 + 各因子訊號…")
    beat = bk.forward_beat_matrix(price, taiex, HOLD)
    beat_me = beat.reindex(me, method="ffill")

    factors = {}
    if holding is not None:
        factors["F1 外資持股比率↑(60日) [P6]"] = bk.holding_uptrend_signal(holding, 60)
    if foreign is not None:
        factors["F2 外資連買≥10日 [P1]"] = bk.consecutive_buy_signal(foreign, 10)
        factors["F2b 外資連買≥3日 [對照]"] = bk.consecutive_buy_signal(foreign, 3)
    if trust is not None:
        factors["F3 投信連買≥3日 [P2/P3]"] = bk.consecutive_buy_signal(trust, 3)
    if dealer_self is not None:
        factors["F4 自營(自行)近20日淨買 [P1反指標?]"] = bk.net_buy_signal(dealer_self, 20)
    if dealer_hedge is not None:
        factors["F4h 自營(避險)近20日淨買 [對照]"] = bk.net_buy_signal(dealer_hedge, 20)

    rows = []
    for name, sig in factors.items():
        sig_me = bk.reindex_month_end(sig, me)
        r = bk.evaluate_factor(sig_me, beat_me)
        rows.append((name, r))

    base = rows[0][1]["base_rate"] if rows else 0.0
    log("\n" + "=" * 78)
    log(f"法人籌碼因子 bakeoff（持有 {HOLD} 日≈1季，命中=贏 TAIEX）")
    log("=" * 78)
    log(f"{'因子':<34}{'命中率':>9}{'baseline':>10}{'alpha':>9}{'樣本':>10}")
    log("-" * 78)
    for name, r in sorted(rows, key=lambda x: -x[1]["alpha"]):
        log(f"{name:<34}{r['hit_rate']*100:>8.1f}%{r['base_rate']*100:>9.1f}%"
            f"{r['alpha']*100:>+8.1f}%{r['n']:>10,}")
    log("=" * 78)
    best = max(rows, key=lambda x: x[1]["alpha"]) if rows else None
    if best:
        log(f"\n🏆 最高 alpha：{best[0]}（+{best[1]['alpha']*100:.1f}pp）")
        if best[1]["alpha"] >= 0.03:
            log("→ alpha ≥ 3pp，值得裝進燈2 / stock_scorer 加分。")
        else:
            log("→ ⚠️ 最高 alpha < 3pp，因子優勢不顯著，誠實標註、勿過度宣稱。")
    log("判讀：alpha = 因子選股贏大盤率 − 全股贏大盤率。自營(自行)若 alpha<0 → 反指標確認。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
