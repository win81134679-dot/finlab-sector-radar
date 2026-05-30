"""
rotation_eval_fast.py — 輪動系統快速歷史驗證（優化版，unbuffered）

一次回答三件事，且效能優化（預先算好各板塊指數/籌碼序列，避免逐月重切 DataFrame）：

  A. 板塊命中率：每期選前 N 強板塊，未來報酬是否贏過全板塊平均？
  B. 個股命中率：選中板塊內動能前 K 檔，未來報酬 > 0 / 贏大盤的比例？
  C. 策略績效：對比三種設計
       - naive_monthly：月頻、單壓前 3（原始）
       - quarterly_div：季頻、前 6 板塊分散
       - regime_gated：季頻、前 6、且大盤 < 200MA 時空手（防禦）
     全部扣成本、對標 TAIEX 買進持有。

⚠️ 誠實：論文/快照僅描述「現在」，這裡測「照訊號做的歷史報酬」。個股排名為動能代理。
需 FINLAB_API_TOKEN。用法：python -u scripts/rotation_eval_fast.py
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
from src.sector_map import SectorMap

import numpy as np
import pandas as pd


def log(msg):
    print(msg, flush=True)


_FOREIGN = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
_TAIEX = "taiex_total_index:收盤指數"

MOM_LOOKBACK = 60
CHIP_WINDOW = 20
COST = 0.00585


def metrics(nav: pd.Series, ppy: int) -> dict:
    if len(nav) < 2:
        return {"annual": 0, "sharpe": 0, "calmar": 0, "mdd": 0}
    rets = nav.pct_change().dropna()
    n = len(rets)
    annual = float((nav.iloc[-1] / nav.iloc[0]) ** (ppy / max(n, 1)) - 1)
    vol = float(rets.std() * np.sqrt(ppy))
    sharpe = annual / vol if vol > 0 else 0
    cummax = nav.cummax()
    mdd = float(((nav - cummax) / cummax).min())
    calmar = annual / abs(mdd) if mdd < 0 else 0
    return {"annual": annual, "sharpe": sharpe, "calmar": calmar, "mdd": mdd}


def main() -> int:
    if not config.is_finlab_token_set():
        log("FINLAB_API_TOKEN 未設定"); return 1
    fetcher = DataFetcher()
    if not fetcher.login():
        return 1
    sm = SectorMap(); sm.load()

    log("拉取資料…")
    price = fetcher.get("price:收盤價")
    foreign = fetcher.get(_FOREIGN)
    trust = fetcher.get(_TRUST)
    taiex_df = fetcher.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if price is None or foreign is None or trust is None:
        log("核心資料缺失"); return 1

    # ── 預先算：各板塊日指數（等權累積報酬）+ 合力流入（外資2+投信1）──────
    log("預算板塊指數與籌碼序列…")
    foreign = foreign.fillna(0)
    trust = trust.reindex(index=price.index).fillna(0)
    foreign = foreign.reindex(index=price.index).fillna(0)
    ret = price.ffill().pct_change(fill_method=None)

    sector_idx: dict[str, pd.Series] = {}
    sector_chip: dict[str, pd.Series] = {}
    sector_members: dict[str, list] = {}
    for sid in sm.all_sector_ids():
        avail = [s for s in sm.get_stocks(sid) if s in price.columns]
        if len(avail) < 2:
            continue
        sector_members[sid] = avail
        sector_idx[sid] = (1 + ret[avail].mean(axis=1).fillna(0)).cumprod()
        fcols = [s for s in avail if s in foreign.columns]
        tcols = [s for s in avail if s in trust.columns]
        flow = (foreign[fcols].sum(axis=1) * 2.0 if fcols else 0) + \
               (trust[tcols].sum(axis=1) * 1.0 if tcols else 0)
        sector_chip[sid] = flow.rolling(CHIP_WINDOW).sum()

    idx_df = pd.DataFrame(sector_idx)            # date × sector 指數
    chip_df = pd.DataFrame(sector_chip)          # date × sector 近20日合力
    # 月底 rebalance 日
    me = pd.Series(price.index, index=price.index).groupby(
        [price.index.year, price.index.month]).last().tolist()
    log(f"期間 {me[0].date()} ~ {me[-1].date()}（{len(me)} 月）")

    # 每板塊在每個月底的：動能(60交易日報酬) + 籌碼(近20日合力)
    idx_me = idx_df.reindex(me, method="ffill")
    mom_me = idx_me.pct_change(3)                # 月底序列，3≈60交易日(~3個月) 近似動能
    # 用交易日精確動能：對 idx_df 算 60 日 pct 再 reindex 到月底
    mom_daily = idx_df.pct_change(MOM_LOOKBACK)
    mom_me = mom_daily.reindex(me, method="ffill")
    chip_me = chip_df.reindex(me, method="ffill")

    def zrow(row: pd.Series) -> pd.Series:
        v = row.dropna()
        if len(v) < 2 or v.std() == 0:
            return pd.Series(0.0, index=row.index)
        return (row - v.mean()) / v.std()

    # 各月底綜合強度排名（z動能 + z籌碼）
    strength_me = {}
    for d in me:
        s = (zrow(mom_me.loc[d]) + zrow(chip_me.loc[d])) / 2
        strength_me[d] = s.dropna().sort_values(ascending=False)

    # 板塊月報酬（下一月底 / 本月底 - 1）
    sec_fwd = idx_me.pct_change().shift(-1)      # 各板塊「下一期」報酬

    taiex_me = taiex.reindex(me, method="ffill") if taiex is not None else None

    # ── A/B：命中率（月頻，全期）─────────────────────────────────────────
    log("計算板塊/個股命中率…")
    TOP_N, TOP_K = 3, 3
    sec_wins = sec_excess = sec_cnt = 0
    stk_pos = stk_beat = stk_cnt = 0
    stk_ret_sum = 0.0
    # 個股 60 日動能（reindex 月底）
    stk_mom_daily = price.ffill().pct_change(MOM_LOOKBACK)
    stk_mom_me = stk_mom_daily.reindex(me, method="ffill")
    stk_fwd = price.ffill().reindex(me, method="ffill").pct_change().shift(-1)

    for i, d in enumerate(me[:-1]):
        rank = strength_me[d]
        if rank.empty:
            continue
        picks = rank.index[:TOP_N].tolist()
        fwd = sec_fwd.loc[d]
        pick_r = fwd[picks].dropna()
        all_r = fwd[rank.index].dropna()
        if len(pick_r) and len(all_r):
            pr, ur = pick_r.mean(), all_r.mean()
            sec_cnt += 1; sec_excess += (pr - ur)
            if pr > ur:
                sec_wins += 1
        # 個股：選中板塊內動能前 K
        br = taiex_me.pct_change().shift(-1).loc[d] if taiex_me is not None else None
        for sid in picks:
            members = sector_members.get(sid, [])
            mm = stk_mom_me.loc[d, [m for m in members if m in stk_mom_me.columns]].dropna()
            for st in mm.sort_values(ascending=False).index[:TOP_K]:
                r = stk_fwd.loc[d, st] if st in stk_fwd.columns else np.nan
                if pd.isna(r):
                    continue
                stk_cnt += 1; stk_ret_sum += r
                if r > 0:
                    stk_pos += 1
                if br is not None and not pd.isna(br) and r > br:
                    stk_beat += 1

    log("\n" + "=" * 70)
    log("【A】板塊輪動命中率（月頻，全期）")
    log("=" * 70)
    if sec_cnt:
        log(f"  選中板塊贏過全板塊平均：{sec_wins/sec_cnt*100:.0f}%（{sec_wins}/{sec_cnt} 期）")
        log(f"  平均超額報酬：{sec_excess/sec_cnt*100:+.2f}%/月")
    log("\n【B】個股命中率（選中板塊動能前 3）")
    if stk_cnt:
        log(f"  報酬 > 0：{stk_pos/stk_cnt*100:.0f}%　贏大盤：{stk_beat/stk_cnt*100:.0f}%　"
            f"平均報酬 {stk_ret_sum/stk_cnt*100:+.2f}%/月（{stk_cnt} 樣本）")

    # ── C：三種策略績效 ──────────────────────────────────────────────────
    log("\n" + "=" * 70)
    log("【C】策略績效對比（扣成本 0.585%/換倉）")
    log("=" * 70)

    def run_strategy(hold_months, top_n, regime_gate):
        equity = 1.0; nav = {}; prev = set()
        sel_dates = me[::hold_months]
        for j in range(len(sel_dates) - 1):
            d0, d1 = sel_dates[j], sel_dates[j + 1]
            # regime gate：大盤 < 200MA → 空手
            if regime_gate and taiex is not None:
                ma200 = taiex.loc[taiex.index <= d0].tail(200)
                if len(ma200) >= 200 and float(taiex.loc[taiex.index <= d0].iloc[-1]) < float(ma200.mean()):
                    nav[d1] = equity; prev = set(); continue
            rank = strength_me.get(d0, pd.Series(dtype=float))
            if rank.empty:
                nav[d1] = equity; continue
            picks = set(rank.index[:top_n])
            # 期間報酬：picks 板塊在 d0→d1 的等權報酬
            rr = []
            for sid in picks:
                a = idx_me.loc[d0, sid] if sid in idx_me.columns else np.nan
                b = idx_me.loc[d1, sid] if sid in idx_me.columns else np.nan
                if not pd.isna(a) and not pd.isna(b) and a:
                    rr.append(b / a - 1)
            pr = float(np.mean(rr)) if rr else 0.0
            turnover = len(picks ^ prev) / (2 * max(len(picks), 1))
            equity *= (1 + pr) * (1 - COST * turnover)
            nav[d1] = equity; prev = picks
        return pd.Series(nav)

    ppy_map = {1: 12, 3: 4}
    strategies = [
        ("naive_monthly (月頻單壓3)", 1, 3, False),
        ("quarterly_div (季頻前6分散)", 3, 6, False),
        ("regime_gated (季頻前6+200MA防禦)", 3, 6, True),
    ]
    log(f"{'策略':<34}{'年化':>9}{'夏普':>8}{'卡瑪':>8}{'MDD':>9}")
    log("-" * 70)
    for name, hold, tn, gate in strategies:
        nav = run_strategy(hold, tn, gate)
        m = metrics(nav, ppy_map.get(hold, 12))
        log(f"{name:<34}{m['annual']*100:>8.1f}%{m['sharpe']:>8.2f}{m['calmar']:>8.2f}{m['mdd']*100:>8.1f}%")
    if taiex_me is not None:
        bench_nav = taiex_me / taiex_me.iloc[0]
        bm = metrics(bench_nav, 12)
        log("-" * 70)
        log(f"{'TAIEX 買進持有':<34}{bm['annual']*100:>8.1f}%{bm['sharpe']:>8.2f}{bm['calmar']:>8.2f}{bm['mdd']*100:>8.1f}%")
    log("=" * 70)
    log("\n判讀：個股命中率 > 50% 且贏大盤 > 50% → 選股加分有效（系統實際用法）。")
    log("      策略若仍輸大盤 → 輪動訊號當『選股加分』用，不單獨當完整策略。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
