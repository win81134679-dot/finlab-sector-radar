"""
notifier.py — Discord Webhook 推播通知

四個頻道，各對應獨立 Webhook URL（GitHub Secrets）：
  DISCORD_WEBHOOK_DAILY   → #板塊-日報       每日完整板塊速覽
  DISCORD_WEBHOOK_ALERT   → #板塊-強烈關注   板塊等級升星時
  DISCORD_WEBHOOK_MACRO   → #宏觀-警示       macro_warning 由 False→True 時
  DISCORD_WEBHOOK_SYSTEM  → #系統-通知       執行成功/失敗

均為 Discord Webhook HTTP POST，無需 Bot 常駐。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # Webhook POST 超時秒數

# 等級 Emoji 對照
_LEVEL_EMOJI = {
    "強烈關注": "🔥",
    "觀察中":   "👀",
    "忽略":     "💤",
}

# 等級顏色（Discord Embed 側邊條顏色，十進位）
_LEVEL_COLOR = {
    "強烈關注": 0xFF4D4F,   # 紅
    "觀察中":   0xFAAD14,   # 橙黃
    "忽略":     0x52525B,   # 灰
}


# ── 低階 Webhook 發送 ─────────────────────────────────────────────────────

def _post(webhook_url: str, payload: Dict[str, Any]) -> bool:
    """
    發送 Discord Webhook POST。
    回傳 True 表示成功（HTTP 204），失敗只 warning 不拋出（非阻塞）。
    """
    if not webhook_url or not webhook_url.strip():
        logger.debug("Discord Webhook URL 未設定，跳過通知")
        return False
    try:
        resp = requests.post(
            webhook_url.strip(),
            json=payload,
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 204):
            return True
        logger.warning("Discord Webhook 回傳 %s: %s", resp.status_code, resp.text[:200])
        return False
    except requests.exceptions.Timeout:
        logger.warning("Discord Webhook POST 超時（%ss）", _TIMEOUT)
        return False
    except Exception as e:
        logger.warning("Discord Webhook POST 失敗: %s", e)
        return False


# ── 高階通知函式 ──────────────────────────────────────────────────────────

def send_daily_report(config: Any, result: Dict[str, Any]) -> None:
    """
    每日完整板塊速覽 → #板塊-日報
    發送所有「強烈關注」與「觀察中」板塊的 Embed 卡片。
    """
    webhook_url = getattr(config, "DISCORD_WEBHOOK_DAILY", "")
    if not webhook_url:
        return

    sectors = result.get("sector_results", {})
    summary = result.get("summary", {})
    strong  = summary.get("strong", [])
    watch   = summary.get("watch", [])
    macro_warning = result.get("macro_warning", False)
    run_at  = result.get("run_at", "")

    # 建立板塊摘要 embed fields
    fields = []
    for sid in strong + watch:
        v = sectors.get(sid, {})
        level = v.get("level", "")
        total = v.get("total", 0)
        signals = v.get("signals", [])
        sig_str = "".join(
            "🟢" if s >= 1.0 else ("🟡" if s >= 0.5 else "⚫")
            for s in signals
        )
        name = v.get("name", sid)
        fields.append({
            "name": f"{_LEVEL_EMOJI.get(level, '')} {name}（{total:.1f}燈）",
            "value": f"燈1-7：{sig_str}",
            "inline": True,
        })
        if len(fields) >= 24:  # Discord 限制 25 個 field
            break

    color = 0xFF4D4F if strong else (0xFAAD14 if watch else 0x52525B)
    description_lines = [
        f"🔥 強烈關注 {len(strong)} 個板塊",
        f"👀 觀察中   {len(watch)} 個板塊",
    ]
    if macro_warning:
        description_lines.append("⚠️ **宏觀警示啟動** — 請謹慎評估倉位")

    embed = {
        "title":       "📊 FinLab 板塊偵測日報",
        "description": "\n".join(description_lines),
        "color":       color,
        "fields":      fields,
        "footer":      {"text": f"執行時間：{run_at[:19]}"},
        "timestamp":   datetime.utcnow().isoformat(),
    }
    _post(webhook_url, {"embeds": [embed]})


def send_sector_alert(config: Any, result: Dict[str, Any]) -> None:
    """
    板塊等級升為「強烈關注」時通知 → #板塊-強烈關注
    透過比對 output/signals_latest.json（執行前的舊版本）來判斷是否升星。
    """
    webhook_url = getattr(config, "DISCORD_WEBHOOK_ALERT", "")
    if not webhook_url:
        return

    import json as _json
    from pathlib import Path

    # 讀取前一個 signals_latest.json（本次執行前的狀態）
    # 注意：多_signal.py 在 _save_snapshot 已覆寫 signals_latest.json，
    # 因此這裡需依賴舊時間戳快照（最近第二個）來比較。
    prev_levels: Dict[str, str] = {}
    try:
        snap_files = sorted(
            Path(config.OUTPUT_DIR).glob("signals_2*.json"),
            reverse=True,
        )
        if len(snap_files) >= 2:
            prev_data = _json.loads(snap_files[1].read_text(encoding="utf-8"))
            for sid, sv in prev_data.get("sectors", {}).items():
                prev_levels[sid] = sv.get("level", "忽略")
    except Exception as e:
        logger.debug("讀取前次快照失敗（首次執行屬正常）: %s", e)

    sectors = result.get("sector_results", {})
    upgraded: list = []
    for sid, v in sectors.items():
        curr_level = v.get("level", "忽略")
        prev_level = prev_levels.get(sid, "忽略")
        if curr_level == "強烈關注" and prev_level != "強烈關注":
            upgraded.append((sid, v))

    if not upgraded:
        return

    for sid, v in upgraded:
        name    = v.get("name", sid)
        total   = v.get("total", 0)
        signals = v.get("signals", [])
        sig_str = "".join(
            "🟢" if s >= 1.0 else ("🟡" if s >= 0.5 else "⚫")
            for s in signals
        )
        # Top 3 個股
        rankings = v.get("stock_rankings", {})
        top3 = list(rankings.items())[:3]
        top3_str = "\n".join(
            f"• {stock_id}（{sd.get('score')}分 {sd.get('grade','')} "
            f"漲跌幅：{sd.get('change_pct') or 'N/A'}%）"
            for stock_id, sd in top3
        ) or "（無評分資料）"

        embed = {
            "title":       f"🚨 板塊升星：{name} 達強烈關注！",
            "description": f"總燈：**{total:.1f}** 燈（7 燈）\n信號：{sig_str}",
            "color":       0xFF4D4F,
            "fields": [
                {"name": "Top 3 個股", "value": top3_str, "inline": False},
            ],
            "footer":    {"text": f"板塊 ID: {sid}"},
            "timestamp": datetime.utcnow().isoformat(),
        }
        _post(webhook_url, {"embeds": [embed]})


def send_macro_alert(config: Any, result: Dict[str, Any]) -> None:
    """
    宏觀警示狀態推播 → #宏觀-警示
    僅在 macro_warning=True 時發送。
    """
    webhook_url = getattr(config, "DISCORD_WEBHOOK_MACRO", "")
    if not webhook_url:
        return

    if not result.get("macro_warning", False):
        return

    macro = result.get("macro_signal", {})
    details = macro.get("details_dict", {})
    pos = macro.get("positive_count", 0)
    tot = macro.get("total_available", 0)

    bullets = "\n".join(f"• {v}" for v in details.values()) or "（無詳細資料）"

    embed = {
        "title":       "⚠️ 宏觀警示：市場環境轉趨謹慎",
        "description": (
            f"**{pos}/{tot} 項指標正面**（需 ≥2 項才解除警示）\n\n"
            f"{bullets}\n\n"
            "> 建議降低倉位預期、縮短持有週期"
        ),
        "color":     0xFAAD14,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _post(webhook_url, {"embeds": [embed]})


def send_error(config: Any, error_msg: str) -> None:
    """
    執行失敗通知 → #系統-通知
    GitHub Actions 失敗時呼叫。
    """
    webhook_url = getattr(config, "DISCORD_WEBHOOK_SYSTEM", "")
    if not webhook_url:
        # 嘗試環境變數直接讀取（Actions 環境可能 config 未初始化）
        webhook_url = os.getenv("DISCORD_WEBHOOK_SYSTEM", "")
    if not webhook_url:
        return

    embed = {
        "title":       "❌ FinLab 板塊分析執行失敗",
        "description": f"```\n{error_msg[:800]}\n```",
        "color":       0xCF1322,
        "fields": [
            {"name": "處理方式", "value": "請前往 GitHub Actions 查看完整日誌", "inline": False},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }
    _post(webhook_url, {"embeds": [embed]})


def send_system_ok(config: Any, result: Dict[str, Any]) -> None:
    """
    執行成功通知 → #系統-通知
    """
    webhook_url = getattr(config, "DISCORD_WEBHOOK_SYSTEM", "")
    if not webhook_url:
        webhook_url = os.getenv("DISCORD_WEBHOOK_SYSTEM", "")
    if not webhook_url:
        return

    run_at = result.get("run_at", "N/A")
    strong_count = len(result.get("summary", {}).get("strong", []))
    watch_count  = len(result.get("summary", {}).get("watch", []))

    embed = {
        "title":       "✅ FinLab 板塊分析執行完成",
        "description": (
            f"🔥 強烈關注：{strong_count} 板塊\n"
            f"👀 觀察中：{watch_count} 板塊\n"
            f"📅 資料時間：{run_at[:19]}"
        ),
        "color":     0x52C41A,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _post(webhook_url, {"embeds": [embed]})
