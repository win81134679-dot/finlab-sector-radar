"""
backtest_full_scorer.py — 完整評分卡 point-in-time 個股命中率回測（向量化，無前視偏誤）

回答：「基本面+技術+相對強度+輪動加分」選出的個股，持有 1 季是否贏過大盤？
      輪動加分能否把命中率從動能代理的 ~44% 拉高？

正確性（無 look-ahead）：fundamental_features 先 `.index_str_to_date()`（揭露日對齊），
再 `.reindex(price.index, ffill)` → 每日只帶入**過去已公布**的財報；reindex 到月底取值。

效能：全部向量化（whole-frame reindex/rolling），不逐股 boolean 切片。

命中：持有 60 交易日（≈1季），報酬 > 同期 TAIEX = 命中。
對照：每月底「輪動強度前 50% 板塊」universe 內，分別用含/不含輪動加分評分，
取每板塊前 K 名，比較贏大盤命中率 → 隔離輪動加分的邊際效果。

⚠️ 限制：universe 用輪動強度當七燈 level 代理；評分為評分卡主要可向量化維度複製品。
需 FINLAB_API_TOKEN。用法：python -u scripts/backtest_full_scorer.py
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


def log(m):
    print(m, flush=True)


_FOREIGN = "institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)"
_TRUST = "institutional_investors_trading_summary:投信買賣超股數"
_TAIEX = "taiex_total_index:收盤指數"
HOLD = 60
TOP_SECTOR_FRAC = 0.5
TOP_K = 3
MIN_SCORE = 3.0
EPS_T, ROE_T, DIST_MAX, RS_RANK_MIN, MA_LONG, MOM_LB = 25.0, 15.0, 10.0, 70.0, 60, 60


def aligned_daily(df, price_index):
    """fundamental → 揭露日對齊 → 日頻 ffill（只帶過去已公布資料）。"""
    if df is None:
        return None
    try:
        df = df.index_str_to_date()
    except Exception:
        pass
    return df.reindex(price_index, method="ffill")


def main() -> int:
    if not config.is_finlab_token_set():
        log("FINLAB_API_TOKEN 未設定"); return 1
    fetcher = DataFetcher()
    if not fetcher.login():
        return 1
    sm = SectorMap(); sm.load()

    log("拉取資料（價格 + 基本面[揭露日對齊] + 法人 + TAIEX）…")
    price = fetcher.get("price:收盤價")
    if price is None:
        log("無價格"); return 1
    pidx = price.index
    eps = aligned_daily(fetcher.get("fundamental_features:稅後淨利成長率"), pidx)
    roe = aligned_daily(fetcher.get("fundamental_features:ROE稅後"), pidx)
    pe = aligned_daily(fetcher.get("price_earning_ratio:本益比"), pidx)
    foreign = fetcher.get(_FOREIGN)
    trust = fetcher.get(_TRUST)
    taiex_df = fetcher.get(_TAIEX)
    taiex = taiex_df.iloc[:, 0].dropna() if taiex_df is not None else None
    if taiex is None:
        log("無 TAIEX"); return 1

    foreign = foreign.reindex(index=pidx).fillna(0) if foreign is not None else None
    trust = trust.reindex(index=pidx).fillna(0) if trust is not None else None

    pxf = price.ffill()
    ret = pxf.pct_change(fill_method=None)

    log("向量化預算（動能 / MA60 / 個股報酬rank / 未來季報酬 / 板塊指數）…")
    # 個股層級（whole-frame）
    stock_mom = pxf.pct_change(MOM_LB)                       # 60日報酬
    ma60 = pxf.rolling(MA_LONG).mean()
    above_ma = pxf > ma60
    dist = (pxf - ma60) / ma60 * 100
    sweet = (dist > 0) & (dist <= DIST_MAX)
    fwd = pxf.shift(-HOLD) / pxf - 1                         # 未來 HOLD 日報酬
    bench_fwd_series = (taiex.reindex(pidx, method="ffill").shift(-HOLD) /
                        taiex.reindex(pidx, method="ffill") - 1)

    # 板塊層級
    sector_idx, sector_chip, members = {}, {}, {}
    for sid in sm.all_sector_ids():
        avail = [s for s in sm.get_stocks(sid) if s in price.columns]
        if len(avail) < 3:
            continue
        members[sid] = avail
        sector_idx[sid] = (1 + ret[avail].mean(axis=1).fillna(0)).cumprod()
        fc = [s for s in avail if foreign is not None and s in foreign.columns]
        tc = [s for s in avail if trust is not None and s in trust.columns]
        flow = (foreign[fc].sum(axis=1) * 2.0 if fc else 0) + (trust[tc].sum(axis=1) * 1.0 if tc else 0)
        if not isinstance(flow, int):
            sector_chip[sid] = flow.rolling(20).sum()
    idx_df = pd.DataFrame(sector_idx)
    chip_df = pd.DataFrame(sector_chip) if sector_chip else None
    sec_mom = idx_df.pct_change(60)

    # 月底
    me = pd.Series(pidx, index=pidx).groupby([pidx.year, pidx.month]).last().tolist()
    me = [d for d in me if (pidx > d).sum() >= HOLD]
    log(f"期間 {me[0].date()} ~ {me[-1].date()}（{len(me)} rebalance），開始評分…")

    # reindex 到月底（O(1) 查表）
    mom_me = stock_mom.reindex(me, method="ffill")
    above_me = above_ma.reindex(me, method="ffill")
    sweet_me = sweet.reindex(me, method="ffill")
    eps_me = eps.reindex(me, method="ffill") if eps is not None else None
    roe_me = roe.reindex(me, method="ffill") if roe is not None else None
    pe_me = pe.reindex(me, method="ffill") if pe is not None else None
    fwd_me = fwd.reindex(me, method="ffill")
    bench_fwd_me = bench_fwd_series.reindex(me, method="ffill")
    secmom_me = sec_mom.reindex(me, method="ffill")
    chipz_me = None
    if chip_df is not None:
        cm = chip_df.reindex(me, method="ffill")
        chipz_me = cm.sub(cm.mean(axis=1), axis=0).div(cm.std(axis=1).replace(0, np.nan), axis=0)

    res = {True: [0, 0], False: [0, 0]}   # {with_rot: [hit, n]}

    for d in me:
        smrow = secmom_me.loc[d].dropna()
        if len(smrow) < 4:
            continue
        cutoff = smrow.quantile(1 - TOP_SECTOR_FRAC)
        uni = smrow[smrow >= cutoff].index.tolist()

        for sid in uni:
            mem = [s for s in members.get(sid, []) if s in mom_me.columns]
            if len(mem) < 2:
                continue
            # 板塊內 RS rank（60日報酬百分位）
            mr = mom_me.loc[d, mem].dropna()
            if len(mr) < 2:
                continue
            rank_pct = mr.rank(pct=True) * 100
            pe_row = pe_me.loc[d, [m for m in mem if m in pe_me.columns]].dropna() if pe_me is not None else pd.Series(dtype=float)
            pe_med = float(pe_row[pe_row > 0].median()) if (pe_row > 0).any() else None
            s_mom = float(smrow.get(sid)) if sid in smrow else None
            s_chipz = float(chipz_me.loc[d, sid]) if (chipz_me is not None and sid in chipz_me.columns and not pd.isna(chipz_me.loc[d, sid])) else None

            # 向量化基本面 + 技術分
            base = pd.Series(0.0, index=mem)
            if eps_me is not None:
                e = eps_me.loc[d, [m for m in mem if m in eps_me.columns]]
                base = base.add((e >= EPS_T).astype(float).reindex(mem).fillna(0) * 2.0, fill_value=0)
            if roe_me is not None:
                r = roe_me.loc[d, [m for m in mem if m in roe_me.columns]]
                base = base.add((r >= ROE_T).astype(float).reindex(mem).fillna(0) * 1.0, fill_value=0)
            if pe_med is not None and pe_me is not None:
                p = pe_me.loc[d, [m for m in mem if m in pe_me.columns]]
                base = base.add(((p > 0) & (p < pe_med)).astype(float).reindex(mem).fillna(0) * 1.0, fill_value=0)
            base = base.add(above_me.loc[d, mem].astype(float).fillna(0) * 1.0, fill_value=0)
            base = base.add(sweet_me.loc[d, mem].astype(float).fillna(0) * 0.5, fill_value=0)
            base = base.add((rank_pct > RS_RANK_MIN).astype(float).reindex(mem).fillna(0) * 1.0, fill_value=0)

            rot_bonus = 0.0
            if s_mom is not None and s_mom > 0:
                rot_bonus += 0.5
            if s_chipz is not None and s_chipz > 1.0:
                rot_bonus += 0.5

            for with_rot in (True, False):
                sc = base + (rot_bonus if with_rot else 0.0)
                picks = sc[sc >= MIN_SCORE].sort_values(ascending=False).index[:TOP_K]
                bf = bench_fwd_me.loc[d]
                for st in picks:
                    fr = fwd_me.loc[d, st] if st in fwd_me.columns else np.nan
                    if pd.isna(fr) or pd.isna(bf):
                        continue
                    res[with_rot][1] += 1
                    if fr > bf:
                        res[with_rot][0] += 1

    log("\n" + "=" * 64)
    log(f"完整評分卡個股命中率（持有 {HOLD} 日≈1季，命中=贏 TAIEX）")
    log("=" * 64)
    for wr, lab in ((True, "含輪動加分"), (False, "不含輪動加分")):
        h, n = res[wr]
        log(f"  {lab:<14}贏大盤命中率 {h/n*100 if n else 0:5.1f}%（{h}/{n} 樣本）")
    hA, nA = res[True]; hB, nB = res[False]
    if nA and nB:
        log(f"\n  輪動加分邊際效果：{(hA/nA - hB/nB)*100:+.1f} 個百分點")
    log("=" * 64)
    log("\n判讀：>50% = 完整評分卡選股能贏大盤(持有1季)；輪動加分邊際>0 = 加分有幫助。")
    log("      universe 用輪動閘門代理七燈 level；評分為主要維度複製品。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
