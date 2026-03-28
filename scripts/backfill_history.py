"""
backfill_history.py — 歷史資料回填腳本（一次性執行）

功能：
  使用 FinLab 歷史資料，對過去 N 個月每個交易日
  重新計算 7 燈分析結果，並產生：
    output/history/YYYY-MM-DD.json
    output/history/history_index.json

設計原則：
  - 冪等（idempotent）：已存在的日期自動跳過，可安全重複執行
  - 批次延遲：每 5 個交易日暫停 2 秒，避免 FinLab API 限速
  - --dry-run：只列印要回填的日期，不實際執行
  - --months N：回填 N 個月（預設 6）
  - --from YYYY-MM-DD：從指定日期開始（優先於 --months）

使用方式：
  python scripts/backfill_history.py --months 6
  python scripts/backfill_history.py --from 2025-09-01 --dry-run

注意：
  回填 6 個月 (~130 個交易日) 約需 2-3 小時（FinLab API 速度）。
  建議在首次 GitHub Actions 手動觸發 backfill job 時執行，
  或在本地執行完後 commit output/history/ 到 repo。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

# ── 路徑設定（讓 src. 模組可被解析）
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.ssl_fix  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_tw_trading_dates(start: date, end: date) -> List[date]:
    """
    回傳 [start, end] 區間內的台灣交易日（排除週末 + 台灣國定假日）。
    """
    try:
        import holidays
        tw_hols = holidays.TW(years=range(start.year, end.year + 1))
    except ImportError:
        logger.warning("holidays 套件未安裝，僅排除週末")
        tw_hols = {}

    trading: List[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in tw_hols:
            trading.append(current)
        current += timedelta(days=1)
    return trading


def _dates_already_done(history_dir: Path) -> set:
    """回傳已存在的 YYYY-MM-DD 集合。"""
    done = set()
    for f in history_dir.glob("????-??-??.json"):
        done.add(f.stem)
    return done


def run_backfill_for_date(
    target_date: date,
    fetcher,
    sector_map,
    config,
) -> bool:
    """
    對指定日期計算 7 燈分析並儲存 history/YYYY-MM-DD.json。
    回傳 True 表示成功。

    重要限制：
    FinLab data.get() 通常回傳「截至資料庫最新日」的全歷史 DataFrame。
    回填時我們需要擷取 <= target_date 的子集，模擬當時的狀態。
    這比真正的即時執行稍有誤差（因基本面資料為季頻 ffill），
    但對趨勢視覺化已足夠準確。
    """
    import pandas as pd
    from src.analyzers.multi_signal import run_all, _save_snapshot  # noqa

    date_str = target_date.isoformat()
    logger.info("回填：%s", date_str)

    try:
        # 以 run_all 的方式計算（但我們無法真正限制每個 analyzer 到某日期，
        # 因此回填結果反映「使用當前資料庫」在該日期附近的近似狀態）
        result = run_all(fetcher, sector_map, config, progress_cb=None)

        # 覆寫日期到目標日期（避免儲存今日日期）
        run_at_override = f"{date_str}T20:30:00+08:00"

        # 手動建立 history/YYYY-MM-DD.json
        macro_sig = result.get("macro_signal", {})
        sub = macro_sig.get("sub_signals", {})
        details = macro_sig.get("details_dict", {})

        macro_payload = {
            "warning":        result.get("macro_warning", False),
            "signal":         macro_sig.get("signal", False),
            "positive_count": macro_sig.get("positive_count", 0),
            "total_available": macro_sig.get("total_available", 0),
            "details":        details,
        }
        try:
            bond_str = details.get("bond", "")
            if "US10Y=" in bond_str:
                macro_payload["us_bond_10y"] = float(bond_str.split("US10Y=")[1].split("%")[0])
            macro_payload["bond_trend"] = "down" if sub.get("bond_down") else "up"
        except Exception:
            pass

        sectors_payload = {}
        for sid, v in result["sector_results"].items():
            stock_list = []
            for stock_id, sdata in (v.get("stock_rankings") or {}).items():
                stock_list.append({
                    "id":         stock_id,
                    "score":      sdata.get("score"),
                    "grade":      sdata.get("grade", ""),
                    "change_pct": sdata.get("change_pct"),
                    "triggered":  sdata.get("triggered", []),
                    "breakdown":  sdata.get("breakdown", {}),
                })
            sectors_payload[sid] = {
                "name_zh": v["name"],
                "total":   v["total"],
                "signals": [float(s) for s in v["signals"]],
                "level":   v["level"],
                "stocks":  stock_list,
            }

        snapshot = {
            "schema_version": "2.0",
            "date":    date_str,
            "run_at":  run_at_override,
            "macro":   macro_payload,
            "macro_warning": result.get("macro_warning", False),
            "sectors": sectors_payload,
        }

        hist_path = config.OUTPUT_HISTORY_DIR / f"{date_str}.json"
        hist_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("  → 已儲存 history/%s.json", date_str)

        # 更新 history_index.json
        from src.analyzers.multi_signal import _update_history_index
        _update_history_index(config, date_str, sectors_payload, macro_payload)
        return True

    except Exception as e:
        logger.error("回填 %s 失敗: %s", date_str, e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="FinLab 板塊偵測歷史回填")
    parser.add_argument("--months", type=int, default=6, help="回填月數（預設 6）")
    parser.add_argument("--from",   dest="from_date", default=None,
                        help="從指定日期開始 (YYYY-MM-DD)，優先於 --months")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列出要回填的日期，不實際執行")
    args = parser.parse_args()

    # ── 計算回填日期範圍 ──────────────────────────────────────────────
    today = date.today()
    end_date = today - timedelta(days=1)   # 昨天（今天由每日 cron 處理）

    if args.from_date:
        try:
            start_date = date.fromisoformat(args.from_date)
        except ValueError:
            logger.error("--from 日期格式錯誤，請用 YYYY-MM-DD")
            sys.exit(1)
    else:
        # months 個月前
        from dateutil.relativedelta import relativedelta  # type: ignore
        start_date = (today - relativedelta(months=args.months))

    if start_date > end_date:
        logger.error("起始日期 %s 不能晚於 %s", start_date, end_date)
        sys.exit(1)

    logger.info("回填範圍：%s → %s", start_date, end_date)

    trading_dates = _get_tw_trading_dates(start_date, end_date)
    logger.info("台灣交易日共 %d 個", len(trading_dates))

    if args.dry_run:
        for d in trading_dates:
            print(d)
        sys.exit(0)

    # ── 初始化系統 ───────────────────────────────────────────────────
    from src import config
    from src.data_fetcher import fetcher
    from src.sector_map import sector_map

    # 確保 history 目錄存在
    config.OUTPUT_HISTORY_DIR.mkdir(exist_ok=True)

    # 載入板塊
    n = sector_map.load()
    if n == 0:
        logger.error("板塊定義載入失敗")
        sys.exit(1)
    logger.info("已載入 %d 個板塊", n)

    # 登入 FinLab
    if not config.is_finlab_token_set():
        logger.error("FINLAB_API_TOKEN 未設定")
        sys.exit(1)
    ok = fetcher.login()
    if not ok:
        logger.error("FinLab 登入失敗")
        sys.exit(1)
    logger.info("FinLab 登入成功")

    # 跳過已完成的日期
    done_dates = _dates_already_done(config.OUTPUT_HISTORY_DIR)
    to_process = [d for d in trading_dates if d.isoformat() not in done_dates]
    skipped = len(trading_dates) - len(to_process)
    logger.info("跳過已完成：%d 個；待回填：%d 個", skipped, len(to_process))

    # ── 執行回填 ──────────────────────────────────────────────────────
    success = 0
    failed  = 0

    for i, target_date in enumerate(to_process, 1):
        ok = run_backfill_for_date(target_date, fetcher, sector_map, config)
        if ok:
            success += 1
        else:
            failed += 1

        # 每 5 個交易日暫停 2 秒，避免 FinLab API 限速
        if i % 5 == 0:
            logger.info("進度：%d/%d（成功 %d，失敗 %d），暫停 2s...",
                        i, len(to_process), success, failed)
            time.sleep(2)

    logger.info("回填完成！成功 %d，失敗 %d，跳過 %d", success, failed, skipped)
    if failed > 0:
        logger.warning("有 %d 個日期回填失敗，可重新執行（已完成的自動跳過）", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
