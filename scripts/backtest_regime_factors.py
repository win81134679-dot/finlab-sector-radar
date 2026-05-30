"""
backtest_regime_factors.py — 校準盤性診斷 regime.ts 手訂權重（point-in-time）

把 regime.ts 各型態判斷當獨立選股因子，持有1季、命中=贏 TAIEX、與 baseline 比 alpha，
回頭校準手訂分數（讓數據說話）。

驗證項（regime.ts 原始手訂分數）：
  連續漲停（K棒 score −2，判大戶攻勢）→ 未來真的偏空嗎？
  高位長上影線（K棒 score −3，判派發）→ 真的偏空嗎？
  KDJ 低位金叉（score +2，判主力啟動）→ 真的偏多嗎？
  KDJ 高位死叉（score −2，判轉弱）→ 真的偏空嗎？

判讀：regime 給正分的型態 alpha 應 > 0、給負分的應 < 0，且幅度與分數成比例。
否則該分數需校準。需 FINLAB_API_TOKEN。用法：python -u scripts/backtest_regime_factors.py
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
from src.analyzers import regime_factor_bakeoff as rf

import pandas as pd

_TAIEX = "taiex_total_index:收盤指數"
HOLD = 60


def log(m):
    print(m, flush=True)


def main() -> int:
    if not config.is_finlab_token_set():
        log("FINLAB_API_TOKEN 未設定"); return 1
    f = DataFetcher()
    if not f.login():
        return 1

    log("拉取 OHLC + TAIEX…")
    o = f.get("price:開盤價")
    h = f.get("price:最高價")
    l = f.get("price:最低價")
    c = f.get("price:收盤價")
    taiex_df = f.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if any(x is None for x in (o, h, l, c, taiex)):
        log("資料缺失"); return 1
    idx = c.index
    o, h, l = o.reindex(index=idx), h.reindex(index=idx), l.reindex(index=idx)

    me = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().tolist()
    me = [d for d in me if (idx > d).sum() >= HOLD]
    beat_me = bk.forward_beat_matrix(c, taiex, HOLD).reindex(me, method="ffill")
    log(f"期間 {me[0].date()} ~ {me[-1].date()}（{len(me)} rebalance, 持有 {HOLD} 日）")

    factors = [
        ("連2漲停 (regime −2 大戶)", rf.consecutive_limit_up(o, c, n=2), "−2→應<0"),
        ("高位長上影線 (regime −3 派發)", rf.long_upper_shadow_highpos(o, h, l, c), "−3→應<0"),
        ("KDJ低位金叉 (regime +2 啟動)", rf.kdj_low_golden_cross(c, h, l), "+2→應>0"),
        ("KDJ高位死叉 (regime −2 轉弱)", rf.kdj_high_death_cross(c, h, l), "−2→應<0"),
    ]

    rows = []
    for name, sig, expect in factors:
        r = bk.evaluate_factor(bk.reindex_month_end(sig, me), beat_me)
        rows.append((name, r, expect))

    base = rows[0][1]["base_rate"]
    log("\n" + "=" * 80)
    log(f"盤性 regime.ts 手訂權重校準（持有 {HOLD} 日，baseline {base*100:.1f}%）")
    log("=" * 80)
    log(f"{'型態 (regime 原分數)':<34}{'命中率':>9}{'alpha':>9}{'樣本':>10}{'  預期':<10}")
    log("-" * 80)
    for name, r, expect in rows:
        flag = ""
        a = r["alpha"]
        if "應>0" in expect and a <= 0: flag = " ❌不符"
        elif "應<0" in expect and a >= 0: flag = " ❌不符"
        elif abs(a) >= 0.02: flag = " ✅顯著"
        else: flag = " ⚠️微弱"
        log(f"{name:<34}{r['hit_rate']*100:>8.1f}%{r['alpha']*100:>+8.1f}%{r['n']:>10,}  {expect}{flag}")
    log("=" * 80)
    log("\n判讀：❌不符 = regime 分數方向與數據相反，應修正；⚠️微弱 = |alpha|<2pp，分數宜縮小；")
    log("      ✅顯著 = 方向對且幅度夠，分數合理。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
