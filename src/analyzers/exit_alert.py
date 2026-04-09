"""
exit_alert.py — 隔日出場訊號警報產生器

五因子學術加權模型，針對「持倉中個股」生成隔日操作建議。

學術依據：
  1. de Kempenaer (2014) "Relative Rotation Graphs", J. Technical Analysis
     RRG 象限從 Leading/Improving 轉入 Weakening/Lagging → 2-4 週領先出場信號
  2. Da, Engelberg & Gao (2014) "The Sum of All FEARS",
     Review of Financial Studies: 恐慌加速度（exit_risk delta ≥ +15）預示短期反轉
  3. Grinblatt, Titman & Wermers (1995) "Momentum Investment Strategies",
     American Economic Review: 機構拋售（籌碼燈熄滅）先於股價高點 3-5 日
  4. Lo, Mamaysky & Wang (2000) "Foundations of Technical Analysis",
     Journal of Finance: 量價背離（價漲量縮）為上攻乏力的可靠預警
  5. Condorcet (1785) 多數決理論：
     多板塊共振衰退（≥3 板塊同時 exit_risk ≥ 56）= 系統性風險升溫

五因子加權：
  RRG 象限衰退      30 分
  出場風險加速度     25 分
  籌碼信號熄滅      20 分
  量價背離          15 分  (降級為板塊級代理指標：技術燈從亮 → 滅)
  多板塊共振衰退    10 分

警報等級：
  0–30  → 無警報
  31–50 → 留意（明日觀察開盤量能再決定）
  51–70 → 減碼（明日開盤建議減碼 50%）
  71–100 → 出場（明日開盤建議全數出場）
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parents[2] / "output" / "portfolio"
_HISTORY_DIR = Path(__file__).parents[2] / "output" / "history"

# ── 因子權重 ─────────────────────────────────────────────────────────────
W_RRG = 30
W_DELTA = 25
W_CHIP = 20
W_VOL_PRICE = 15
W_SYSTEMIC = 10

# ── 閾值 ─────────────────────────────────────────────────────────────────
DELTA_THRESHOLD = 15        # exit_risk score 單日上升 ≥ 15 視為加速衰退
SYSTEMIC_THRESHOLD = 3      # ≥3 板塊同時 exit_risk ≥ 56 視為系統性風險
SYSTEMIC_SCORE_MIN = 56     # 板塊 exit_risk 達此分數才計入系統性風險
ALERT_SCORE_MAX = 100


def _load_previous_snapshot() -> dict | None:
    """載入 output/history/ 中最近一天的快照，用於 delta 計算。"""
    if not _HISTORY_DIR.exists():
        return None
    json_files = sorted(
        (f for f in _HISTORY_DIR.iterdir()
         if f.suffix == ".json" and f.name != "history_index.json"),
        reverse=True,
    )
    if not json_files:
        return None
    try:
        with open(json_files[0], encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("載入前日快照失敗: %s", e)
        return None


def _get_prev_exit_score(prev_snapshot: dict | None, sector_id: str) -> int | None:
    """從前日快照取得板塊的 exit_risk.score。"""
    if not prev_snapshot:
        return None
    sectors = prev_snapshot.get("sectors", {})
    sec = sectors.get(sector_id, {})
    er = sec.get("exit_risk")
    if er and isinstance(er, dict):
        return er.get("score")
    return None


def _get_prev_chip_signal(prev_snapshot: dict | None, sector_id: str) -> float | None:
    """從前日快照取得板塊的 signals[5]（籌碼燈）。"""
    if not prev_snapshot:
        return None
    sectors = prev_snapshot.get("sectors", {})
    sec = sectors.get(sector_id, {})
    signals = sec.get("signals", [])
    if len(signals) >= 6:
        return float(signals[5])
    return None


_USER_HOLDINGS_PATH = _OUTPUT_DIR / "user_holdings.json"


def _load_user_holdings() -> dict | None:
    """載入管理員自選持倉 (user_holdings.json)。"""
    if not _USER_HOLDINGS_PATH.exists():
        return None
    try:
        with open(_USER_HOLDINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        positions = data.get("positions", {})
        if positions:
            return positions
        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("載入 user_holdings.json 失敗: %s", e)
        return None


def _count_systemic_risk_sectors(snapshot_sectors: dict[str, Any]) -> int:
    """計算當前有多少板塊的 exit_risk.score ≥ SYSTEMIC_SCORE_MIN。"""
    count = 0
    for sec in snapshot_sectors.values():
        er = sec.get("exit_risk")
        if er and isinstance(er, dict) and (er.get("score", 0) >= SYSTEMIC_SCORE_MIN):
            count += 1
    return count


def _calc_alert_score(
    sector_id: str,
    sector: dict[str, Any],
    prev_snapshot: dict | None,
    systemic_count: int,
) -> dict[str, Any] | None:
    """計算單一板塊的隔日出場警報分數。"""
    exit_risk = sector.get("exit_risk")
    if not exit_risk or not isinstance(exit_risk, dict):
        return None

    cycle_stage = sector.get("cycle_stage")
    if cycle_stage not in ("加速期", "過熱期"):
        return None

    current_score = exit_risk.get("score", 0)
    score = 0
    triggers: list[str] = []

    # ── 因子 1: RRG 象限衰退 (30 分) ────────────────────────────────────
    rs_quadrant = exit_risk.get("rs_quadrant", "")
    if "轉弱" in rs_quadrant or "Weakening" in rs_quadrant or "Lagging" in rs_quadrant:
        score += W_RRG
        triggers.append("RRG 轉弱/落後象限（de Kempenaer 2014）")
    elif "Right-Lower" in rs_quadrant:
        score += W_RRG
        triggers.append("RRG 轉弱象限（de Kempenaer 2014）")

    # ── 因子 2: 出場風險加速度 (25 分) ──────────────────────────────────
    prev_exit_score = _get_prev_exit_score(prev_snapshot, sector_id)
    delta = None
    if prev_exit_score is not None:
        delta = current_score - prev_exit_score
        if delta >= DELTA_THRESHOLD:
            score += W_DELTA
            triggers.append(f"出場風險急升 +{delta}（Da et al. 2014）")

    # ── 因子 3: 籌碼信號熄滅 (20 分) ───────────────────────────────────
    signals = sector.get("signals", [])
    current_chip = float(signals[5]) if len(signals) >= 6 else None
    prev_chip = _get_prev_chip_signal(prev_snapshot, sector_id)
    if current_chip is not None and current_chip == 0:
        if prev_chip is not None and prev_chip >= 0.5:
            # 籌碼燈從亮→滅：機構撤出訊號
            score += W_CHIP
            triggers.append("籌碼燈熄滅（Grinblatt et al. 1995）")
        elif prev_chip is None:
            # 無前日資料但當前已熄滅，降低權重
            score += W_CHIP // 2
            triggers.append("籌碼燈已滅（Grinblatt et al. 1995）")

    # ── 因子 4: 量價背離代理指標 (15 分) ────────────────────────────────
    # 使用板塊級代理：技術燈從亮→滅 = 量能消退跡象
    current_tech = float(signals[3]) if len(signals) >= 4 else None
    if current_tech is not None and current_tech == 0:
        total = sector.get("total", 0)
        if total >= 4:
            score += W_VOL_PRICE
            triggers.append("技術動能消退（Lo et al. 2000）")

    # ── 因子 5: 多板塊共振衰退 (10 分) ─────────────────────────────────
    if systemic_count >= SYSTEMIC_THRESHOLD:
        score += W_SYSTEMIC
        triggers.append(f"系統性風險：{systemic_count} 板塊同時警戒（Condorcet 1785）")

    score = min(score, ALERT_SCORE_MAX)

    # 行動建議
    if score >= 71:
        action = "出場"
    elif score >= 51:
        action = "減碼"
    elif score >= 31:
        action = "留意"
    else:
        action = "無"

    if action == "無":
        return None

    return {
        "score": score,
        "action": action,
        "delta": delta,
        "prev_score": prev_exit_score,
        "current_exit_risk": current_score,
        "triggers": triggers,
        "cycle_stage": cycle_stage,
        "sector_name": sector.get("name_zh", sector_id),
    }


def generate_exit_alerts(
    snapshot_sectors: dict[str, Any],
    holdings_positions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    主入口：掃描所有板塊，為持倉中個股生成隔日出場警報。

    Parameters
    ----------
    snapshot_sectors : signals_latest.json 的 sectors dict
    holdings_positions : holdings.json 的 positions dict（可選）

    Returns
    -------
    exit_alerts dict（寫入 output/portfolio/exit_alerts.json）
    """
    prev_snapshot = _load_previous_snapshot()
    systemic_count = _count_systemic_risk_sectors(snapshot_sectors)

    # 板塊級警報
    sector_alerts: dict[str, dict] = {}
    for sid, sec in snapshot_sectors.items():
        alert = _calc_alert_score(sid, sec, prev_snapshot, systemic_count)
        if alert:
            sector_alerts[sid] = alert

    # 個股級警報：優先使用管理員自選持倉，否則用演算法持倉
    user_holdings = _load_user_holdings()
    effective_positions = user_holdings or holdings_positions
    position_alerts: dict[str, dict] = {}
    if effective_positions:
        for ticker, pos in effective_positions.items():
            sector = pos.get("sector", "")
            if sector in sector_alerts:
                sa = sector_alerts[sector]
                position_alerts[ticker] = {
                    "name_zh": pos.get("name_zh", ticker),
                    "sector": sector,
                    "sector_name": sa["sector_name"],
                    "score": sa["score"],
                    "action": sa["action"],
                    "delta": sa["delta"],
                    "prev_score": sa["prev_score"],
                    "current_exit_risk": sa["current_exit_risk"],
                    "triggers": sa["triggers"],
                    "cycle_stage": sa["cycle_stage"],
                    "composite_score": pos.get("composite_score", 0),
                    "weight": pos.get("weight", 0),
                }

    if user_holdings:
        logger.info("出場警報以管理員自選持倉為基準（%d 支）", len(user_holdings))

    # 系統風險等級
    if systemic_count >= SYSTEMIC_THRESHOLD:
        system_risk = "elevated"
    elif len(sector_alerts) >= 2:
        system_risk = "moderate"
    else:
        system_risk = "low"

    now = datetime.now(timezone.utc).isoformat()
    result = {
        "updated_at": now,
        "system_risk_level": system_risk,
        "systemic_sector_count": systemic_count,
        "sector_alerts": sector_alerts,
        "position_alerts": position_alerts,
        "summary": {
            "exit_count": sum(1 for a in position_alerts.values() if a["action"] == "出場"),
            "reduce_count": sum(1 for a in position_alerts.values() if a["action"] == "減碼"),
            "watch_count": sum(1 for a in position_alerts.values() if a["action"] == "留意"),
            "safe_count": (len(effective_positions) - len(position_alerts)) if effective_positions else 0,
        },
    }

    _save_json(result)
    return result


def _save_json(data: dict) -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUTPUT_DIR / "exit_alerts.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
