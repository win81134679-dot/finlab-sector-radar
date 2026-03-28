"""
file_scanner.py — 掃描 output/ 資料夾

功能：
  - 列出所有 .md 報告（按時間排序）
  - 列出所有 signals_*.json 歷史快照
  - 讀取並回傳 Markdown 原文（供 CLI 渲染）
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def list_reports(output_dir: Path) -> List[Dict[str, Any]]:
    """
    回傳所有 .md 報告的摘要清單，由新到舊排序。
    [{"name": ..., "path": ..., "size_kb": ..., "mtime": ...}]
    """
    files = sorted(output_dir.glob("*.md"), reverse=True)
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "name":     f.name,
            "path":     f,
            "size_kb":  round(stat.st_size / 1024, 1),
            "mtime":    stat.st_mtime,
        })
    return result


def list_snapshots(output_dir: Path) -> List[Dict[str, Any]]:
    """
    回傳所有 signals_*.json 快照摘要，由新到舊。
    """
    files = sorted(output_dir.glob("signals_*.json"), reverse=True)
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "name":     f.name,
                "path":     f,
                "date":     data.get("date", ""),
                "run_at":   data.get("run_at", ""),
                "sectors":  len(data.get("sectors", {})),
                "macro_ok": not data.get("macro_warning", True),
            })
        except Exception as e:
            logger.warning(f"讀取快照失敗 ({f.name}): {e}")
    return result


def read_report(path: Path) -> Optional[str]:
    """讀取 Markdown 報告原文。"""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"讀取報告失敗 ({path}): {e}")
        return None


def scan_all(output_dir: Path) -> Dict[str, Any]:
    """一次回傳所有掃描結果。"""
    reports   = list_reports(output_dir)
    snapshots = list_snapshots(output_dir)
    return {
        "reports":       reports,
        "snapshots":     snapshots,
        "report_count":  len(reports),
        "snapshot_count": len(snapshots),
        "output_dir":    str(output_dir),
    }
