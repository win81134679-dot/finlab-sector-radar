"""
multi_signal.py — 7 燈彙總引擎

執行全部 7 個 analyzer，合併結果並：
1. 計算每個板塊的亮燈總分 + 等級
2. 儲存本次結果到 output/signals_YYYYMMDD_HHMM.json（供歷史趨勢用）
3. 回傳完整結構供 CLI 顯示和 Markdown 輸出
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SIGNAL_NAMES = [
    "燈1_月營收拐點",
    "燈2_法人共振",
    "燈3_庫存循環",
    "燈4_技術突破",
    "燈5_相對強度",
    "燈6_籌碼集中",
    "燈7_宏觀濾網",
]

LEVEL_THRESHOLDS = {
    # 學術依據：Condorcet 陪審團定理 (1785)
    # n=7 獨立信號，多數決最優門檻 = ⌈7/2⌉ = 4
    # Piotroski (2000, J. Accounting Research, cited 3000+): 多信號聚合需品質閘門
    "強烈關注": 4,
    "觀察中":   2,
}


def _level(total: float, scores: list | None = None) -> str:
    """
    判定板塊等級。
    scores: [燈1,燈2,燈3,燈4,燈5,燈6,燈7] 的分數列表（0/0.5/1.0）。
    品質閘門：「強烈關注」需至少一個基本面燈（燈1 營收 or 燈3 庫存）≥ 0.5，
    防止純技術/籌碼驅動的虛假板塊。
    """
    if total >= LEVEL_THRESHOLDS["強烈關注"]:
        # 品質閘門：要求基本面參與 (Piotroski 2000)
        if scores is not None and len(scores) >= 4:
            rev, _inst, inv = float(scores[0]), float(scores[1]), float(scores[2])
            if rev < 0.5 and inv < 0.5:
                return "觀察中"  # 降級：無基本面支撐
        return "強烈關注"
    if total >= LEVEL_THRESHOLDS["觀察中"]:
        return "觀察中"
    return "忽略"


def _get_score(raw: dict, step_name: str, sector_id: str) -> float:
    """從各分析器結果取出分數，優先使用 score_contrib（支援 0.5 半亮）。"""
    d = raw.get(step_name, {}).get(sector_id, {})
    if "score_contrib" in d:
        return float(d["score_contrib"])
    return float(d.get("signal", False))


def run_all(fetcher, sector_map, config,
            progress_cb=None) -> Dict[str, Any]:
    """
    執行全部 7 個分析模組，彙整結果。

    progress_cb: 可選 callable(step_name: str, step_n: int, total: int)
                 用於 CLI 顯示進度條
    """
    from src.analyzers import revenue, institutional, inventory, technical
    from src.analyzers import rs_ratio, chipset, macro
    from src.analyzers import momentum_season, revenue_surprise

    steps = [
        ("燈1 月營收拐點",  lambda: revenue.analyze(fetcher, sector_map, config)),
        ("燈2 法人共振",    lambda: institutional.analyze(fetcher, sector_map, config)),
        ("燈3 庫存循環",    lambda: inventory.analyze(fetcher, sector_map, config)),
        ("燈4 技術突破",    lambda: technical.analyze(fetcher, sector_map, config)),
        ("燈5 相對強度",    lambda: rs_ratio.analyze(fetcher, sector_map, config)),
        ("燈6 籌碼集中",    lambda: chipset.analyze(fetcher, sector_map, config)),
        ("燈7 宏觀濾網",    lambda: macro.analyze(fetcher, config)),
        # 學術 bonus 分析器（不計入七燈總分）
        ("學術_季節動能",   lambda: momentum_season.analyze(fetcher, sector_map, config)),
        ("學術_營收加速",   lambda: revenue_surprise.analyze(fetcher, sector_map, config)),
    ]

    raw: Dict[str, Any] = {}
    # 使用 ThreadPoolExecutor 平行執行各分析器（每步獨立，無互相依賴）
    with ThreadPoolExecutor(max_workers=min(len(steps), 4)) as pool:
        future_map = {
            pool.submit(fn): name for name, fn in steps
        }
        for i, future in enumerate(as_completed(future_map)):
            name = future_map[future]
            if progress_cb:
                progress_cb(name, i + 1, len(steps))
            try:
                raw[name] = future.result()
            except Exception as e:
                logger.error(f"{name} 執行失敗: {e}")
                raw[name] = {}

    # ── 資料可用性閘門 ─────────────────────────────────────────────────
    # 防止 FinLab API 全掛 / 部分掛時覆蓋正常資料（GitHub Actions 預防性機制）
    SECTOR_ANALYZERS = [
        "燈1 月營收拐點", "燈2 法人共振", "燈3 庫存循環",
        "燈4 技術突破", "燈5 相對強度", "燈6 籌碼集中",
    ]
    MIN_VALID_ANALYZERS = 4  # Condorcet: n=7 信號需 ≥4 有效才有正確率優勢

    def _is_analyzer_empty(data: dict) -> bool:
        """判斷分析器輸出是否為無效資料（空 dict 或全部 signal=False/score=0）。"""
        if not data:
            return True
        # 捕捉「回傳了結構但所有 sector 都是空信號」的假資料模式
        return all(
            not entry.get("signal", False) and float(entry.get("score", 0)) <= 0
            for entry in data.values()
            if isinstance(entry, dict)
        )

    valid_names = [n for n in SECTOR_ANALYZERS if not _is_analyzer_empty(raw.get(n, {}))]
    failed_names = [n for n in SECTOR_ANALYZERS if n not in valid_names]
    valid_count = len(valid_names)

    if valid_count < MIN_VALID_ANALYZERS:
        msg = (
            f"⚠️ 資料可用性閘門觸發：僅 {valid_count}/{len(SECTOR_ANALYZERS)} 個板塊分析器有效"
            f"（需 ≥{MIN_VALID_ANALYZERS}），疑似 FinLab API 不可用。\n"
            f"失效分析器：{', '.join(failed_names)}\n"
            f"中止本次分析以保護現有資料。"
        )
        logger.error(msg)
        raise RuntimeError(msg)
    if failed_names:
        logger.warning("部分分析器無有效資料（%d/%d）：%s", len(failed_names), len(SECTOR_ANALYZERS), failed_names)

    # 宏觀是全局燈（dict，非 per-sector）
    macro_result: Dict[str, Any] = raw.get("燈7 宏觀濾網", {})
    macro_signal: bool = macro_result.get("signal", False)
    macro_warning: bool = not macro_signal

    # ── 彙整各板塊 ─────────────────────────────────────────────────────
    sector_results: Dict[str, Dict[str, Any]] = {}

    for sector_id in sector_map.all_sector_ids():
        signals: List[bool] = [
            raw.get("燈1 月營收拐點", {}).get(sector_id, {}).get("signal", False),
            raw.get("燈2 法人共振",  {}).get(sector_id, {}).get("signal", False),
            raw.get("燈3 庫存循環",  {}).get(sector_id, {}).get("signal", False),
            raw.get("燈4 技術突破",  {}).get(sector_id, {}).get("signal", False),
            raw.get("燈5 相對強度",  {}).get(sector_id, {}).get("signal", False),
            raw.get("燈6 籌碼集中",  {}).get(sector_id, {}).get("signal", False),
            macro_signal,                                           # 燈7 全局共享
        ]
        # 分數列表：支援 0.5 半亮（燈2/燈4 僳用 score_contrib）
        scores: List[float] = [
            _get_score(raw, "燈1 月營收拐點",  sector_id),
            _get_score(raw, "燈2 法人共振",   sector_id),
            _get_score(raw, "燈3 庫存循環",   sector_id),
            _get_score(raw, "燈4 技術突破",   sector_id),
            _get_score(raw, "燈5 相對強度",   sector_id),
            _get_score(raw, "燈6 籌碼集中",   sector_id),
            float(macro_signal),
        ]
        total = round(sum(scores), 1)

        sector_results[sector_id] = {
            "name":          sector_map.get_sector_name(sector_id),
            "signals":       scores,          # List[float]: 0.0 / 0.5 / 1.0
            "signals_bool":  signals,         # List[bool]: 主要信號备用
            "signal_names":  SIGNAL_NAMES,
            "total":         total,
            "level":         _level(total, scores),
            "macro_warning": macro_warning,
            "detail": {
                SIGNAL_NAMES[0]: raw.get("燈1 月營收拐點", {}).get(sector_id, {}),
                SIGNAL_NAMES[1]: raw.get("燈2 法人共振",  {}).get(sector_id, {}),
                SIGNAL_NAMES[2]: raw.get("燈3 庫存循環",  {}).get(sector_id, {}),
                SIGNAL_NAMES[3]: raw.get("燈4 技術突破",  {}).get(sector_id, {}),
                SIGNAL_NAMES[4]: raw.get("燈5 相對強度",  {}).get(sector_id, {}),
                SIGNAL_NAMES[5]: raw.get("燈6 籌碼集中",  {}).get(sector_id, {}),
            },
        }

    # ── 排序（強烈關注 → 觀察中 → 忽略；同分按名稱排）─────────────────
    sorted_sectors = dict(
        sorted(sector_results.items(), key=lambda x: -x[1]["total"])
    )

    # ── 逐股評分（僅對「強烈關注」和「觀察中」板塊執行）─────────────────
    if hasattr(config, "STOCK_SCORE_TARGET_LEVELS"):
        # 預先取得當日漲跌幅（一次 API 呼叫，注入給 score_stocks）
        try:
            change_pct_map = fetcher.get_latest_change_pct()
        except Exception as _e:
            logger.warning("取得漲跌幅失敗，個股 change_pct 將為 None: %s", _e)
            change_pct_map = {}

        from src.analyzers.stock_scorer import score_stocks as _score_stocks
        for _sid, _v in sorted_sectors.items():
            if _v["level"] in config.STOCK_SCORE_TARGET_LEVELS:
                _stocks = sector_map.get_stocks(_sid)
                try:
                    _rankings = _score_stocks(
                        _sid, _stocks, raw, fetcher, config,
                        change_pct_map=change_pct_map,
                    )
                    sorted_sectors[_sid]["stock_rankings"] = _rankings
                except Exception as _e:
                    logger.warning("stock_scorer [%s] 失敗: %s", _sid, _e)
                    sorted_sectors[_sid]["stock_rankings"] = {}

    result = {
        "run_at":        datetime.now().isoformat(),
        "sector_results": sorted_sectors,
        "macro_signal":   macro_result,
        "macro_warning":  macro_warning,
        "raw_results":    raw,
        "summary": {
            "strong":  [sid for sid, v in sorted_sectors.items() if v["level"] == "強烈關注"],
            "watch":   [sid for sid, v in sorted_sectors.items() if v["level"] == "觀察中"],
            "ignore":  [sid for sid, v in sorted_sectors.items() if v["level"] == "忽略"],
        },
    }

    # ── 品質異常退化保護（防禦第二道）────────────────────────────────────
    # 若前次有 ≥5 個強烈關注，本次卻變 0，視為資料異常而非真實市場變化
    new_strong_count = len(result["summary"]["strong"])
    try:
        latest_path = Path(config.OUTPUT_DIR) / "signals_latest.json"
        if latest_path.exists():
            import json as _json_mod
            prev_data = _json_mod.loads(latest_path.read_text(encoding="utf-8"))
            prev_strong = sum(
                1 for s in prev_data.get("sectors", {}).values()
                if s.get("level") == "強烈關注"
            )
            if prev_strong >= 5 and new_strong_count == 0:
                msg = (
                    f"⚠️ 品質異常退化保護觸發：前次 {prev_strong} 個強烈關注 → 本次 0 個，"
                    f"市場不可能單日全面崩潰。中止本次分析以保護現有資料。"
                )
                logger.error(msg)
                raise RuntimeError(msg)
    except RuntimeError:
        raise
    except Exception as _e:
        logger.debug("歷史比對讀取失敗（首次執行屬正常）: %s", _e)

    # ── 儲存 JSON 歷史快照 ──────────────────────────────────────────────
    _save_snapshot(result, config, sector_map)

    return result


def _calc_cycle_stage(signals: list, total: float, level: str) -> Optional[str]:
    """
    依七燈 signals 陣列推算板塊所處週期階段。
    優先序：過熱期 > 加速期 > 確認期 > 萌芽期
    signals 索引：[0]=營收 [1]=法人 [2]=庫存 [3]=技術 [4]=相對強度 [5]=籌碼 [6]=宏觀
    """
    if level == "忽略" or len(signals) < 6:
        return None
    rev, inst, inv, tech, _rs, chip = (float(signals[i]) for i in range(6))
    # 過熱期：幾乎全燈，泡沫化跡象
    if total >= 6.5:
        return "過熱期"
    # 加速期：多燈齊亮 + 籌碼進駐
    if total >= 5 or (total >= 4 and chip >= 1):
        return "加速期"
    # 確認期：法人開始入場 + 技術訊號啟動
    # 學術依據：Chen, Yang & Lin (2012, Managerial Finance) 台股外資半燈已具領先意義
    # Chung et al. (2021, QREF) MA 突破 + 法人持股增加之複合有效性
    if inst >= 0.5 and tech >= 0.5:
        return "確認期"
    # 萌芽期：基本面拐點出現，法人與技術尚未確認
    # 對應 Wyckoff Accumulation 階段 (Grimes 2012, cited 60)
    if (rev >= 0.5 or inv >= 0.5) and inst < 0.5 and tech < 0.5:
        return "萌芽期"
    return None


def _save_snapshot(result: Dict[str, Any], config, sector_map) -> Optional[Path]:
    """
    儲存三個 JSON 輸出：
    1. output/signals_YYYYMMDD_HHMM.json   — 舊時間戳快照（供 load_history 使用）
    2. output/signals_latest.json          — 原子覆寫（前端主要讀取）
    3. output/history/YYYY-MM-DD.json      — 按日累積（歷史圖表）
    同時維護 output/history_index.json（前端一次讀取取代 65 個檔案）
    """
    import os

    # ── 從 macro_signal 提取數值欄位 ────────────────────────────────────
    macro_sig = result.get("macro_signal", {})
    sub = macro_sig.get("sub_signals", {})
    details = macro_sig.get("details_dict", {})

    macro_payload: Dict[str, Any] = {
        "warning":      result.get("macro_warning", False),
        "signal":       macro_sig.get("signal", False),
        "positive_count": macro_sig.get("positive_count", 0),
        "total_available": macro_sig.get("total_available", 0),
        "details": details,
    }
    # 嘗試解析數值（details['bond'] 格式: "US10Y=4.25% (↓均線✅)"）
    try:
        bond_str = details.get("bond", "")
        if "US10Y=" in bond_str:
            macro_payload["us_bond_10y"] = float(bond_str.split("US10Y=")[1].split("%")[0])
        macro_payload["bond_trend"] = "down" if sub.get("bond_down") else "up"
    except Exception:
        pass
    try:
        indpro_str = details.get("pmi", "")
        if "INDPRO=" in indpro_str:
            macro_payload["ip_index"] = float(indpro_str.split("INDPRO=")[1].split(" ")[0])
        macro_payload["ip_trend"] = "up" if sub.get("indpro_above_ma") else "down"
    except Exception:
        pass
    try:
        sox_str = details.get("sox", "")
        if "SOXX=" in sox_str:
            macro_payload["sox_price"] = float(sox_str.split("SOXX=")[1].split(" ")[0])
        macro_payload["sox_trend"] = "up" if sub.get("sox_above_ma") else "down"
    except Exception:
        pass
    try:
        twd_str = details.get("twd", "")
        if "USD/TWD=" in twd_str:
            macro_payload["usd_twd"] = float(twd_str.split("USD/TWD=")[1].split(" ")[0])
        twd_sub = sub.get("twd_appreciating")
        macro_payload["twd_trend"] = "down" if twd_sub else "up"
    except Exception:
        pass

    # ── 取得 OHLCV 和交易狀態（一次批次）─────────────────────────
    _last_trading_date = datetime.now().strftime("%Y-%m-%d")  # fallback
    _trading_status: dict = {}
    _ohlcv_full_batch: dict = {}
    _ohlcv_batch: dict = {}
    try:
        from src.data_fetcher import fetcher as _fetcher
        _ltd = _fetcher.get_last_trading_date()
        if _ltd:
            _last_trading_date = _ltd
        # 收集所有需要細項的股票 ID
        _all_sids: List[str] = []
        for _v in result["sector_results"].values():
            _all_sids.extend(_v.get("stock_rankings", {}).keys())
        _all_sids = list(set(_all_sids))
        if _all_sids:
            _trading_status = _fetcher.get_trading_status(_all_sids, _last_trading_date)
            _ohlcv_full_batch = _fetcher.get_ohlcv_batch(_all_sids, days=400)
            # 主快照剛保留最近 10 日（做快預覽用）
            _ohlcv_batch = {sid: bars[-10:] for sid, bars in _ohlcv_full_batch.items()}
    except Exception as _e:
        logger.warning("取得 OHLCV/交易狀態失敗: %s", _e)

    # ── 建立完整板塊快照（含 name_zh + stocks）──────────────────
    from src.stock_names import get_name as _get_stock_name

    sectors_payload: Dict[str, Any] = {}
    for sid, v in result["sector_results"].items():
        stock_list: List[Dict[str, Any]] = []
        rankings = v.get("stock_rankings", {})
        for stock_id, sdata in rankings.items():
            stock_list.append({
                "id":         stock_id,
                "name_zh":    _get_stock_name(stock_id),
                "score":      sdata.get("score"),
                "grade":      sdata.get("grade", ""),
                "change_pct": sdata.get("change_pct"),
                "triggered":  sdata.get("triggered", []),
                "breakdown":  sdata.get("breakdown", {}),
                "price_flag": _trading_status.get(stock_id, "normal"),
                "ohlcv_7d":   _ohlcv_batch.get(stock_id, []),
            })
        _sigs = [float(s) for s in v["signals"]]
        _stage = _calc_cycle_stage(_sigs, v["total"], v["level"])

        # 出場風險評估（僅加速期/過熱期）
        from src.analyzers.cycle_exit import calc_exit_risk as _calc_exit
        _exit_risk = _calc_exit(
            sid, _sigs, v["total"], _stage,
            result.get("macro_warning", False),
            raw_results=result.get("raw_results", {}),
        )

        # 暴露 RS-Momentum 給前端
        _rs_data = result.get("raw_results", {}).get("燈5 相對強度", {}).get(sid, {})
        _rs_mom = _rs_data.get("rs_momentum")

        sectors_payload[sid] = {
            "name_zh":      v["name"],
            "total":        v["total"],
            "signals":      _sigs,
            "level":        v["level"],
            "cycle_stage":  _stage,
            "exit_risk":    _exit_risk,
            "rs_momentum":  round(_rs_mom, 6) if _rs_mom is not None else None,
            "constituent_count": len(sector_map.get_stocks(sid)),
            "stocks":       stock_list,
        }

    # ── 構建完整 snapshot dict ──────────────────────────────────────────
    run_dt  = datetime.now()
    try:
        import zoneinfo
        import datetime as _dt
        run_dt_aware = _dt.datetime.now(zoneinfo.ZoneInfo("Asia/Taipei"))
        run_at_str   = run_dt_aware.isoformat(timespec="seconds")
        date_str     = run_dt_aware.date().isoformat()
    except Exception:
        run_at_str = run_dt.isoformat()
        date_str   = run_dt.strftime("%Y-%m-%d")

    snapshot: Dict[str, Any] = {
        "schema_version": "2.0",
        "date":    date_str,
        "run_at":  run_at_str,
        "last_trading_date": _last_trading_date,
        "macro":   macro_payload,
        # 保留舊欄位向下相容
        "macro_warning": result.get("macro_warning", False),
        "sectors": sectors_payload,
    }

    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

    saved_paths: List[Path] = []

    try:
        # 1. 舊格式時間戳快照（供 load_history 向後相容）
        ts_str = run_dt.strftime("%Y%m%d_%H%M")
        ts_path = config.OUTPUT_DIR / f"signals_{ts_str}.json"
        ts_path.write_text(snapshot_json, encoding="utf-8")
        saved_paths.append(ts_path)
        logger.info("訊號快照已儲存: %s", ts_path.name)
    except Exception as e:
        logger.warning("時間戳快照儲存失敗: %s", e)

    try:
        # 2. signals_latest.json — 原子寫入（先寫 .tmp，再 os.replace）
        latest_path = config.OUTPUT_DIR / "signals_latest.json"
        tmp_path    = config.OUTPUT_DIR / "signals_latest.tmp.json"
        tmp_path.write_text(snapshot_json, encoding="utf-8")
        os.replace(str(tmp_path), str(latest_path))
        saved_paths.append(latest_path)
        logger.info("signals_latest.json 已更新（原子寫入）")
    except Exception as e:
        logger.warning("signals_latest.json 儲存失敗: %s", e)

    try:
        # 3. history/YYYY-MM-DD.json
        history_path = config.OUTPUT_HISTORY_DIR / f"{date_str}.json"
        history_path.write_text(snapshot_json, encoding="utf-8")
        saved_paths.append(history_path)
        logger.info("history/%s.json 已儲存", date_str)
    except Exception as e:
        logger.warning("history JSON 儲存失敗: %s", e)

    try:
        # 4. 更新 history_index.json（前端用，避免 fetch 65 個檔案）
        _update_history_index(config, date_str, sectors_payload, macro_payload)
    except Exception as e:
        logger.warning("history_index.json 更新失敗: %s", e)

    try:
        # 5. stock_names.json — 完整代碼→名稱+板塊對照（前端持倉表單用）
        _generate_stock_names_json(config)
    except Exception as e:
        logger.warning("stock_names.json 產生失敗: %s", e)

    try:
        # 6. 個股 OHLCV 歷史（供前端 K 線多時間框架切換）
        if _ohlcv_full_batch:
            _ohlcv_dir = config.OUTPUT_DIR / "ohlcv"
            _ohlcv_dir.mkdir(exist_ok=True)
            for _sid, _bars in _ohlcv_full_batch.items():
                (_ohlcv_dir / f"{_sid}.json").write_text(
                    json.dumps(_bars, ensure_ascii=False), encoding="utf-8"
                )
            logger.info("個股 OHLCV 已寫出 %d 檔至 output/ohlcv/", len(_ohlcv_full_batch))
    except Exception as e:
        logger.warning("個股 OHLCV 寫出失敗: %s", e)

    return saved_paths[0] if saved_paths else None


def _update_history_index(
    config,
    date_str: str,
    sectors_payload: Dict[str, Any],
    macro_payload: Dict[str, Any],
) -> None:
    """
    維護 output/history_index.json。
    結構：{"dates": [...], "sectors": {sid: {name_zh, totals, levels}}, "macro": [{date, warning, ...}]}
    前端只需 1 次 fetch 就能畫出所有歷史趨勢折線。
    """
    import os

    index_path = config.OUTPUT_HISTORY_DIR / "history_index.json"
    if index_path.exists():
        try:
            idx: Dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            idx = {"dates": [], "sectors": {}, "macro": []}
    else:
        idx = {"dates": [], "sectors": {}, "macro": []}

    dates: List[str] = idx.get("dates", [])
    if date_str in dates:
        pos = dates.index(date_str)
        # 更新同一天的資料（重複執行時覆寫）
        for sid, v in sectors_payload.items():
            if sid in idx["sectors"]:
                idx["sectors"][sid]["totals"][pos] = v["total"]
                idx["sectors"][sid]["levels"][pos] = v["level"]
        # 更新 macro
        for i, m in enumerate(idx.get("macro", [])):
            if m.get("date") == date_str:
                idx["macro"][i] = {**macro_payload, "date": date_str}
                break
    else:
        dates.append(date_str)
        idx["dates"] = sorted(dates)  # 按日期排序
        pos = idx["dates"].index(date_str)

        for sid, v in sectors_payload.items():
            if sid not in idx["sectors"]:
                idx["sectors"][sid] = {
                    "name_zh": v["name_zh"],
                    "totals":  [],
                    "levels":  [],
                }
            # 確保長度對齊（插入到正確位置）
            idx["sectors"][sid]["totals"].insert(pos, v["total"])
            idx["sectors"][sid]["levels"].insert(pos, v["level"])

        macro_entry = {**macro_payload, "date": date_str}
        macro_list: List[Dict] = idx.get("macro", [])
        macro_list.insert(pos, macro_entry)
        idx["macro"] = macro_list

    # 原子寫入
    tmp_path = config.OUTPUT_HISTORY_DIR / "history_index.tmp.json"
    tmp_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(index_path))
    logger.info("history_index.json 已更新（共 %d 天）", len(idx["dates"]))


def load_history(config, n: int = 4) -> List[Dict[str, Any]]:
    """讀取最近 n 次的 signals_*.json，用於趨勢顯示。"""
    files = sorted(config.OUTPUT_DIR.glob("signals_*.json"), reverse=True)[:n]
    history = []
    for f in reversed(files):   # 由舊到新
        try:
            history.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"讀取歷史快照失敗 ({f.name}): {e}")
    return history


def build_trend_string(sector_id: str, history: List[Dict[str, Any]]) -> str:
    """
    從歷史快照中提取該板塊的燈數趨勢。
    例如：[2, 3, 3, 5] → "2→3→3→5"（float 如 3.5 發生時顯示小數）
    """
    values = []
    for snap in history:
        total = snap.get("sectors", {}).get(sector_id, {}).get("total")
        if total is not None:
            v = float(total)
            display = str(int(v)) if v == int(v) else f"{v:.1f}"
            values.append(display)
    return "→".join(values) if values else "-"


def _generate_stock_names_json(config) -> None:
    """
    產生 output/stock_names.json —— 完整台股代碼→{name_zh, sector, sector_name} 對照。
    資料來源優先級：
      1. stock_universe.json（TWSE/TPEx 全市場 ~1,900 筆）
      2. STOCK_NAMES 硬編碼（補充/覆蓋簡稱）
      3. custom_sectors.csv（板塊歸屬）
    非板塊股票的 sector 設為 "other"。
    """
    import os
    from src.stock_names import STOCK_NAMES
    from src.sector_map import SectorMap

    sm = SectorMap()
    sm.load()

    # 建構板塊歸屬反查表：stock_id → (sector_id, sector_name)
    stock_to_sector: Dict[str, tuple] = {}
    for sid in sm.all_sector_ids():
        sname = sm.get_sector_name(sid)
        for stock_id in sm.get_stocks(sid):
            if stock_id not in stock_to_sector:
                stock_to_sector[stock_id] = (sid, sname)

    # 讀取完整市場清單
    universe_path = config.OUTPUT_DIR / "stock_universe.json"
    universe: Dict[str, str] = {}
    if universe_path.exists():
        try:
            universe = json.loads(universe_path.read_text(encoding="utf-8"))
            logger.info("讀取 stock_universe.json：%d 筆", len(universe))
        except Exception as e:
            logger.warning("stock_universe.json 讀取失敗: %s", e)

    # 合併所有來源
    all_ids = set(universe.keys()) | set(stock_to_sector.keys()) | set(STOCK_NAMES.keys())

    lookup: Dict[str, Dict[str, str]] = {}
    for stock_id in sorted(all_ids):
        # 名稱優先級：硬編碼 > universe > 代碼本身
        name = STOCK_NAMES.get(stock_id) or universe.get(stock_id) or stock_id
        # 板塊歸屬
        sec_id, sec_name = stock_to_sector.get(stock_id, ("other", "其他"))
        lookup[stock_id] = {
            "name_zh":     name,
            "sector":      sec_id,
            "sector_name": sec_name,
        }

    out_path = config.OUTPUT_DIR / "stock_names.json"
    tmp_path = config.OUTPUT_DIR / "stock_names.tmp.json"
    tmp_path.write_text(
        json.dumps(lookup, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(str(tmp_path), str(out_path))
    logger.info("stock_names.json 已更新（%d 筆股票）", len(lookup))
