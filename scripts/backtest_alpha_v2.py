"""
backtest_alpha_v2.py — 投信因子 v2 細化 + 盤性診斷量價驗證（一次跑完）

【A】盤性診斷驗證（回答「法人盤判斷有沒有根據」）：
  regime.ts 判「溫和放量=主力佈局(+2)」「量增不漲=派發(−3)」是否真有預測力？
  → 溫和放量 alpha 應 > 0、量增不漲 alpha 應 < 0 才算 regime 判斷成立。

【B】投信因子 v2（再榨 alpha）：
  B1 投信買超「相對自身20日均量」標準化（對小型股公平）
  B2 投信連3日 AND 站上 MA20（雙因子：籌碼+技術確認）
  B3 投信連3日 AND 帶量（量比≥1.3）
  B4 投信連3日 AND 基本面好（EPS YoY≥0，point-in-time 揭露日對齊）

全部 point-in-time、命中=贏 TAIEX、與 baseline 比 alpha。需 FINLAB_API_TOKEN。
用法：python -u scripts/backtest_alpha_v2.py
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

import numpy as np
import pandas as pd

_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
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

    log("拉取資料…")
    price = f.get("price:收盤價")
    volume = f.get("price:成交股數")
    trust = f.get(_TRUST)
    eps = f.get("fundamental_features:稅後淨利成長率")
    try:
        eps = eps.index_str_to_date() if eps is not None else None
    except Exception:
        pass
    taiex_df = f.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if any(x is None for x in (price, volume, trust, taiex)):
        log("資料缺失"); return 1

    pidx = price.index
    trust = trust.reindex(index=pidx)
    volume = volume.reindex(index=pidx)
    eps_d = eps.reindex(pidx, method="ffill") if eps is not None else None

    me = pd.Series(pidx, index=pidx).groupby([pidx.year, pidx.month]).last().tolist()
    me = [d for d in me if (pidx > d).sum() >= HOLD]
    beat_me = bk.forward_beat_matrix(price, taiex, HOLD).reindex(me, method="ffill")
    log(f"期間 {me[0].date()} ~ {me[-1].date()}（{len(me)} rebalance, 持有 {HOLD} 日）")

    rows = []

    # ── 【A】盤性診斷量價驗證 ──────────────────────────────────────────
    mild = bk.reindex_month_end(bk.mild_volume_signal(volume, price), me)
    rows.append(("【A】溫和放量(regime:佈局+2)", bk.evaluate_factor(mild, beat_me), "應>0"))
    vupf = bk.reindex_month_end(bk.vol_up_price_flat_signal(volume, price), me)
    rows.append(("【A】量增不漲(regime:派發−3)", bk.evaluate_factor(vupf, beat_me), "應<0"))

    # ── 【B】投信 v2 ─────────────────────────────────────────────────
    base3 = bk.consecutive_buy_signal(trust, 3)

    # B1 標準化：投信買超 / 自身20日均量，近3日皆 > 門檻（相對自身放量）
    tvol20 = volume.rolling(20).mean()
    trust_norm = (trust / tvol20.replace(0, np.nan))
    b1 = (trust_norm.rolling(3).min() > 0.05)  # 近3日投信淨買皆 ≥自身均量5%
    rows.append(("【B1】投信連3日+相對量≥5%", bk.evaluate_factor(bk.reindex_month_end(b1, me), beat_me), ""))

    # B2 投信連3日 AND 站上 MA20
    ma20 = price.ffill().rolling(20).mean()
    above20 = price.ffill() > ma20
    b2 = base3 & above20
    rows.append(("【B2】投信連3日 AND 站上MA20", bk.evaluate_factor(bk.reindex_month_end(b2, me), beat_me), ""))

    # B3 投信連3日 AND 帶量（量比≥1.3）
    vr = bk.vol_ratio(volume, 3, 20)
    b3 = base3 & (vr >= 1.3)
    rows.append(("【B3】投信連3日 AND 帶量1.3x", bk.evaluate_factor(bk.reindex_month_end(b3, me), beat_me), ""))

    # B4 投信連3日 AND 基本面好（EPS YoY≥0，揭露日對齊）
    if eps_d is not None:
        eps_ok = eps_d.reindex(columns=price.columns) >= 0
        b4 = base3 & eps_ok.reindex(index=pidx).fillna(False)
        rows.append(("【B4】投信連3日 AND EPS YoY≥0", bk.evaluate_factor(bk.reindex_month_end(b4, me), beat_me), ""))

    # 對照：原始投信連3日 + 排除季末（目前最佳 +4.3pp）
    best_prev = bk.exclude_quarter_end(base3, 10)
    rows.append(("[對照] 投信連3日+排季末", bk.evaluate_factor(bk.reindex_month_end(best_prev, me), beat_me), "現最佳"))

    # B5 組合：投信連3日 + 排季末 + 帶量1.3x（疊加兩個有效因子）
    b5 = bk.exclude_quarter_end(base3 & (vr >= 1.3), 10)
    rows.append(("【B5】投信連3日+排季末+帶量", bk.evaluate_factor(bk.reindex_month_end(b5, me), beat_me), "組合"))

    base = rows[0][1]["base_rate"]
    log("\n" + "=" * 82)
    log(f"alpha v2：盤性驗證【A】+ 投信細化【B】（持有 {HOLD} 日，baseline {base*100:.1f}%）")
    log("=" * 82)
    log(f"{'因子':<36}{'命中率':>9}{'alpha':>9}{'樣本':>10}{'  備註':<10}")
    log("-" * 82)
    for name, r, note in sorted(rows, key=lambda x: -x[1]["alpha"]):
        log(f"{name:<36}{r['hit_rate']*100:>8.1f}%{r['alpha']*100:>+8.1f}%{r['n']:>10,}  {note}")
    log("=" * 82)
    log("\n判讀：")
    log("【A】溫和放量 alpha>0 且 量增不漲 alpha<0 → regime.ts 量價判斷有根據；否則該頁標未驗證。")
    log("【B】哪個 v2 顯著高於對照 +4.3pp 才採用；樣本<2000 的高 alpha 警惕雜訊。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
