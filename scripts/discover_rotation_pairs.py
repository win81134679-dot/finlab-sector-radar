"""
discover_rotation_pairs.py — 離線探勘板塊領先落後對

對全部 59 板塊兩兩計算滯後互相關（+ 可選 Granger 因果），找出
「A 領先 B」的候選對，寫 output/rotation/pairs.json。

⚠️ 產出需**人工審核**後才固化（移除過度擬合 / 無經濟邏輯的對），
線上 rotation_pairs.detect_handoffs() 只用審核後的對。

預設只保留 |corr| ≥ 0.35 且 lag ∈ [3, 20] 的對（領先數日到一個月）。
Granger 為可選增強（statsmodels 存在才跑），不是必要依賴。

用法：
  python scripts/discover_rotation_pairs.py                # corr≥0.35
  python scripts/discover_rotation_pairs.py --min-corr 0.4 --top 30
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ssl_fix  # noqa: F401
from src import config
from src.data_fetcher import DataFetcher
from src.sector_map import SectorMap
from src.analyzers.rotation_pairs import lead_lag_correlation

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("discover_pairs")


def _sector_index(price_df, stocks):
    import numpy as np  # noqa: F401
    avail = [s for s in stocks if s in price_df.columns]
    if len(avail) < 2:
        return None
    ret = price_df[avail].ffill().pct_change(fill_method=None).mean(axis=1)
    return (1 + ret.fillna(0)).cumprod()


def _maybe_granger(a, b, max_lag: int):
    """可選 Granger（statsmodels 存在才跑）；回傳最小 p-value 或 None。"""
    try:
        import numpy as np
        from statsmodels.tsa.stattools import grangercausalitytests
        import warnings
        data = np.column_stack([b[-250:], a[-250:]])  # 檢定 a 是否 Granger-cause b
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = grangercausalitytests(data, maxlag=min(max_lag, 10), verbose=False)
        pvals = [res[l][0]["ssr_ftest"][1] for l in res]
        return round(float(min(pvals)), 4)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-corr", type=float, default=0.35)
    ap.add_argument("--max-lag", type=int, default=20)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    if not config.is_finlab_token_set():
        logger.error("FINLAB_API_TOKEN 未設定")
        return 1
    fetcher = DataFetcher()
    if not fetcher.login():
        return 1
    sm = SectorMap()
    sm.load()

    price_df = fetcher.get("price:收盤價")
    if price_df is None:
        logger.error("無價格資料")
        return 1

    # 各板塊指數報酬序列
    import numpy as np
    series = {}
    for sid in sm.all_sector_ids():
        idx = _sector_index(price_df, sm.get_stocks(sid))
        if idx is not None and len(idx) > args.max_lag + 60:
            series[sid] = idx.pct_change(fill_method=None).dropna().to_numpy()

    logger.info("有效板塊序列：%d", len(series))

    candidates = []
    for a, b in permutations(series.keys(), 2):
        lag, corr = lead_lag_correlation(series[a], series[b], max_lag=args.max_lag)
        if abs(corr) >= args.min_corr and 3 <= lag <= args.max_lag:
            candidates.append({
                "leader": a, "leader_name": sm.get_sector_name(a),
                "laggard": b, "laggard_name": sm.get_sector_name(b),
                "lag_days": lag, "corr": corr,
                "granger_p": _maybe_granger(series[a], series[b], args.max_lag),
            })

    candidates.sort(key=lambda x: -abs(x["corr"]))
    candidates = candidates[:args.top]

    out_dir = config.OUTPUT_DIR / "rotation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "pairs_candidates.json"   # 候選；審核後改名 pairs.json
    out_path.write_text(
        json.dumps({"pairs": candidates, "note": "候選對，需人工審核後改名為 pairs.json"},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("寫出 %d 個候選對 → %s", len(candidates), out_path)
    print(f"\n前 10 強候選領先→落後對：")
    for c in candidates[:10]:
        g = f", Granger p={c['granger_p']}" if c["granger_p"] is not None else ""
        print(f"  {c['leader_name']} → {c['laggard_name']}  "
              f"(lag {c['lag_days']}d, corr {c['corr']:+.2f}{g})")
    print(f"\n⚠️ 請人工審核 {out_path.name}，移除無經濟邏輯的對後改名為 pairs.json 才會生效。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
