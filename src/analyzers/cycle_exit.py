"""
cycle_exit.py — 週期出場風險評估器

學術依據：
  - de Kempenaer (2014) "Relative Rotation Graphs", Journal of Technical Analysis
    RRG Weakening 象限 (RS-Ratio > 1 but RS-Momentum < 0) 是最可靠的提前出場信號
  - Grinblatt, Titman & Wermers (1995) "Momentum Investment Strategies",
    Journal of Finance: 機構拋售（借券上升）先於股價高點約 3–5 日
  - Da, Gurun & Warachka (2014) "Frog in the Pan", Review of Financial Studies:
    大量累積漲幅的離散跳躍比漸進動能更容易反轉

出場風險分數 (0–100)：
  RRG Weakening 象限     → +40
  籌碼燈熄滅 (chip=0)    → +25
  接近過熱期 (total≥6.0)  → +20
  宏觀逆風 + 加速/過熱期  → +15

行動建議：
  0–30  → 持有 (綠)
  31–55 → 留意 (黃)
  56–75 → 減碼 (橙)
  76+   → 出場 (紅)
"""
from typing import Any, Dict, Optional


def calc_exit_risk(
    sector_id: str,
    signals: list,
    total: float,
    cycle_stage: Optional[str],
    macro_warning: bool,
    raw_results: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    計算加速期/過熱期板塊的出場風險分。
    僅在 cycle_stage ∈ {"加速期", "過熱期"} 時計算，否則回傳 None。
    """
    if cycle_stage not in ("加速期", "過熱期"):
        return None

    score = 0
    triggers: list[str] = []

    # ── 1. RRG Weakening 象限 (+40) ──────────────────────────────────
    rs_data = raw_results.get("燈5 相對強度", {}).get(sector_id, {})
    rs_quadrant = rs_data.get("quadrant", "")
    rs_momentum = rs_data.get("rs_momentum")

    if "轉弱" in rs_quadrant or "Right-Lower" in rs_quadrant:
        score += 40
        triggers.append("RRG 轉弱象限（de Kempenaer 2014）")
    elif rs_momentum is not None and rs_momentum < 0:
        # RS-Momentum 剛轉負但 ratio 還沒到轉弱象限
        score += 20
        triggers.append("RS-Momentum 轉負")

    # ── 2. 籌碼燈熄滅 (+25) ─────────────────────────────────────────
    if len(signals) >= 6:
        chip = float(signals[5])
        if chip == 0 and total >= 4:
            score += 25
            triggers.append("籌碼燈熄滅（Grinblatt et al. 1995）")

    # ── 3. 接近過熱 (+20) ───────────────────────────────────────────
    if total >= 6.0:
        score += 20
        triggers.append("接近過熱（Da et al. 2014）")

    # ── 4. 宏觀逆風 (+15) ───────────────────────────────────────────
    if macro_warning:
        score += 15
        triggers.append("宏觀環境逆風")

    # 上限 100
    score = min(score, 100)

    # 行動建議
    if score >= 76:
        action = "出場"
    elif score >= 56:
        action = "減碼"
    elif score >= 31:
        action = "留意"
    else:
        action = "持有"

    return {
        "score": score,
        "action": action,
        "triggers": triggers,
        "rs_quadrant": rs_quadrant or "N/A",
    }
