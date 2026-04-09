"""
update_stock_universe.py — 從 TWSE / TPEx 公開 API 下載完整股票代碼→名稱對照表

產出：output/stock_universe.json
格式：{ "2330": "台積電", "3481": "群創", ... }

快取：7 天內重複執行直接跳過（除非 --force）
用途：讓前端持倉表單能辨識所有上市上櫃股票
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
UNIVERSE_PATH = OUTPUT_DIR / "stock_universe.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CACHE_DAYS = 7
REQUEST_TIMEOUT = 30

# 過濾規則：只保留普通股（4 碼數字），排除 ETF、權證、債券等
_STOCK_CODE_RE = re.compile(r"^\d{4}$")


def _is_cache_valid(force: bool = False) -> bool:
    """檢查快取是否在有效期內。"""
    if force:
        return False
    if not UNIVERSE_PATH.exists():
        return False
    mtime = datetime.fromtimestamp(UNIVERSE_PATH.stat().st_mtime)
    return (datetime.now() - mtime) < timedelta(days=CACHE_DAYS)


def _fetch_twse() -> dict[str, str]:
    """從 TWSE 公開 API 取得上市公司清單。"""
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    logger.info("正在取得 TWSE 上市公司清單...")
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        result: dict[str, str] = {}
        for row in data:
            code = str(row.get("公司代號", "")).strip()
            # 優先取簡稱，fallback 到公司全名
            name = str(
                row.get("公司簡稱", "") or row.get("公司名稱", "")
            ).strip()
            if _STOCK_CODE_RE.match(code) and name:
                result[code] = name
        logger.info("TWSE 上市：取得 %d 筆", len(result))
        return result
    except Exception as e:
        logger.warning("TWSE API 失敗: %s", e)
        return {}


def _fetch_tpex() -> dict[str, str]:
    """從 TPEx 公開 API 取得上櫃公司清單。"""
    url = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
    logger.info("正在取得 TPEx 上櫃公司清單...")
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        result: dict[str, str] = {}
        for row in data:
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            # 優先取簡稱，fallback 到公司全名
            name = str(
                row.get("CompanyAbbreviation", "") or row.get("CompanyName", "")
            ).strip()
            if _STOCK_CODE_RE.match(code) and name:
                result[code] = name
        logger.info("TPEx 上櫃：取得 %d 筆", len(result))
        return result
    except Exception as e:
        logger.warning("TPEx API 失敗: %s", e)
        return {}


def update(force: bool = False) -> dict[str, str]:
    """
    更新 stock_universe.json。
    回傳完整的 { 代碼: 名稱 } 字典。
    """
    if _is_cache_valid(force):
        logger.info("stock_universe.json 快取有效（%d 天內），跳過更新", CACHE_DAYS)
        return json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))

    universe: dict[str, str] = {}

    # 合併 TWSE + TPEx
    twse = _fetch_twse()
    tpex = _fetch_tpex()
    universe.update(twse)
    universe.update(tpex)

    if not universe:
        logger.error("TWSE + TPEx 均無資料，保留舊快取")
        if UNIVERSE_PATH.exists():
            return json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
        return {}

    # 排序後寫出
    sorted_universe = dict(sorted(universe.items()))
    tmp_path = OUTPUT_DIR / "stock_universe.tmp.json"
    tmp_path.write_text(
        json.dumps(sorted_universe, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(UNIVERSE_PATH)
    logger.info(
        "stock_universe.json 已更新：上市 %d + 上櫃 %d = 共 %d 筆",
        len(twse), len(tpex), len(sorted_universe),
    )
    return sorted_universe


def main() -> None:
    parser = argparse.ArgumentParser(description="更新台股完整代碼對照表")
    parser.add_argument("--force", action="store_true", help="忽略快取強制更新")
    args = parser.parse_args()

    result = update(force=args.force)
    if result:
        print(f"✅ stock_universe.json: {len(result)} 筆股票")
    else:
        print("❌ 更新失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
