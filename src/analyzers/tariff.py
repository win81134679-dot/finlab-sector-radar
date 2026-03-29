"""
tariff.py — MAGA 靜態關稅衝擊矩陣

情境：10% (溫和) / 25% (標準) / 60% (極端)
板塊鍵值對應 custom_sectors.csv sector_id

每個值代表相對衝擊係數（-1.0 ~ +1.0）
  正值 = 關稅受益（替代中國供應商）
  負值 = 關稅受害（直接成本上升 / 中國市場依賴）
"""

from typing import Literal

TariffScenario = Literal["10%", "25%", "60%"]

# ── 基礎矩陣（25% 標準情境）────────────────────────────────────────────────
_BASE_MATRIX: dict[str, float] = {
    # 受益板塊（台灣替代中國供應商）
    "foundry":             +0.60,  # 台積電地位提升，替代中國芯
    "packaging":           +0.50,  # 先進封測轉移台灣
    "semiconductor_equip": +0.45,  # 美廠設備採購轉向台廠
    "ai_server":           +0.35,  # AI 供應鏈重組有利台廠
    "optical_comm":        +0.30,  # 資料中心遷離中國
    "networking":          +0.25,  # 網路設備替代
    "ip_design":           +0.20,  # 矽智財脫中受益
    "thermal":             +0.15,  # 散熱模組替代中國廠
    "robotics":            +0.10,  # 自動化設備替代
    "defense":             +0.05,  # 國防採購提升
    "power_infra":         +0.05,  # 電力設備轉單

    # 微幅影響
    "pcb":                 -0.05,  # PCB 有部分中國客戶
    "memory":              -0.10,  # DRAM 中國需求略降
    "power_components":    -0.05,  # 部分中國出口

    # 受害板塊
    "ic_design":           -0.45,  # 聯發科等中國客戶佔比高
    "display":             -0.50,  # 面板對中國市場依賴
    "ev_supply":           -0.35,  # 電池材料成本上升
    "solar":               -0.30,  # 太陽能原材料關稅
    "shipping":            -0.55,  # 貿易量萎縮最直接
    "petrochemical":       -0.30,  # 原料關稅轉嫁困難
    "textile":             -0.25,  # 紡織中國訂單依賴
    "steel":               -0.20,  # 鋼鐵關稅雙向衝擊
    "rubber":              -0.15,  # 原料成本上升

    # 中性
    "biotech":             +0.00,
    "banking":             +0.00,
    "insurance":           +0.00,
    "construction":        +0.00,
    "telecom":             +0.00,
    "food":                -0.05,
    "cement":              -0.05,
    "paper":               -0.10,
    "securities":          +0.00,
    "financial_holding":   +0.00,
    "energy_storage":      -0.10,
    "gas_energy":          +0.05,
    "wind_energy":         -0.20,
    "lens_optics":         -0.05,
    "connector":           -0.05,
    "vehicle_elec":        -0.20,
    "software_saas":       +0.00,
    "ecommerce":           +0.00,
    "gaming":              +0.00,
    "power_semi":          +0.10,
    "tourism":             -0.05,
    "medical_device":      +0.05,
}

# ── 情境縮放比例 ───────────────────────────────────────────────────────────
_SCENARIO_SCALE: dict[TariffScenario, float] = {
    "10%": 0.4,
    "25%": 1.0,
    "60%": 2.2,
}

# ── 公開 API ──────────────────────────────────────────────────────────────

def get_tariff_impact(scenario: TariffScenario = "25%") -> dict[str, float]:
    """
    回傳 {sector_id: impact_float} 指定關稅情境的衝擊係數。
    值域 -1.0 ~ +1.0（25% 基準），其他情境依縮放比例調整後 clamp。
    """
    scale = _SCENARIO_SCALE.get(scenario, 1.0)
    return {
        sector: max(-1.0, min(1.0, round(v * scale, 3)))
        for sector, v in _BASE_MATRIX.items()
    }


def get_all_scenarios() -> dict[str, dict[str, float]]:
    """回傳三個情境的完整矩陣，供前端比較用。"""
    return {s: get_tariff_impact(s) for s in ("10%", "25%", "60%")}


def list_scenarios() -> list[TariffScenario]:
    return list(_SCENARIO_SCALE.keys())
