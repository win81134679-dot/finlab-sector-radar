"""
data_fetcher.py — FinLab data.get() wrapper，含 pickle 磁碟快取
"""
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    封裝 FinLab data.get()，提供：
    - 磁碟 pickle 快取（預設 24 小時過期）
    - 自動重新登入
    - 失效快取降級
    """

    def __init__(self):
        self._logged_in: bool = False
        self._finlab_data = None

    # ── 登入 ─────────────────────────────────────────────────────────────

    def login(self, token: Optional[str] = None) -> bool:
        """用 API Token 登入 FinLab。回傳 True 表示成功。"""
        from src import config
        token = token or config.FINLAB_API_TOKEN
        if not token or not token.strip():
            logger.error("FINLAB_API_TOKEN 未設定，請在 .env 填入 Token")
            return False
        try:
            import finlab
            finlab.login(api_token=token.strip())
            from finlab import data as _data
            self._finlab_data = _data
            self._logged_in = True
            logger.info("FinLab 登入成功")
            return True
        except Exception as e:
            logger.error(f"FinLab 登入失敗: {e}")
            return False

    def is_logged_in(self) -> bool:
        return self._logged_in

    # ── 快取工具 ─────────────────────────────────────────────────────────

    def _cache_path(self, key: str) -> Path:
        from src import config
        safe = key.replace(":", "_").replace("/", "_").replace(" ", "_")
        return config.CACHE_DIR / f"{safe}.pkl"

    def _cache_valid(self, path: Path) -> bool:
        from src import config
        if not path.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        return age < timedelta(hours=config.CACHE_EXPIRE_HOURS)

    def _save_cache(self, path: Path, obj) -> None:
        try:
            with open(path, "wb") as f:
                pickle.dump(obj, f)
        except Exception as e:
            logger.warning(f"快取寫入失敗 ({path.name}): {e}")

    def _load_cache(self, path: Path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"快取讀取失敗 ({path.name}): {e}")
            return None

    # ── 主要 API ─────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """
        取得 FinLab 數據，優先使用磁碟快取。
        key 格式同 finlab data.get()，例如 "price:收盤價"

        快取層級（依序）：
          1. pickle 快取（24hr 以內）       → 最快
          2. FinLab API 拉取 → 儲 pickle + side-export CSV（增量）
          3. 過期 pickle                    → 降級
          4. CSV 備份                       → 最後手段（API 全掛）
        """
        from src import config
        cache_file = self._cache_path(key)

        # 1. pickle 快取命中
        if self._cache_valid(cache_file):
            data = self._load_cache(cache_file)
            if data is not None:
                logger.debug(f"快取命中: {key}")
                return data

        # 2. 確保登入
        if not self._logged_in:
            if not self.login():
                # 嘗試 CSV 備份
                return self._load_csv_fallback(key)

        # 3. 從 FinLab 拉取
        try:
            df = self._finlab_data.get(key)
            if df is not None:
                self._save_cache(cache_file, df)
                # side-export：增量追加 CSV，非同步失敗不影響主流程
                self._export_csv(key, df)
            return df
        except Exception as e:
            logger.error(f"FinLab data.get({key!r}) 失敗: {e}")
            # 4a. 過期 pickle 降級
            if cache_file.exists():
                logger.warning(f"使用過期 pickle 快取: {key}")
                return self._load_cache(cache_file)
            # 4b. CSV 備份降級
            return self._load_csv_fallback(key)

    # ── CSV side-export（FinLab 寬表格式）────────────────────────────────

    def _export_csv(self, key: str, df: pd.DataFrame) -> None:
        """FinLab DataFrame 增量匯出到 CSV（不阻塞主流程，異常只 warning）。"""
        try:
            from src.csv_cache import export_finlab_df
            export_finlab_df(key, df)
        except Exception as e:
            logger.warning(f"CSV side-export 失敗 [{key}]: {e}")

    def _load_csv_fallback(self, key: str) -> Optional[pd.DataFrame]:
        """pickle 和 FinLab API 皆失效時嘗試從 CSV 備份讀取。"""
        try:
            from src.csv_cache import load_finlab_df_fallback
            return load_finlab_df_fallback(key)
        except Exception:
            return None

    def clear_cache(self) -> int:
        """清除所有快取檔案，回傳刪除數量。"""
        from src import config
        count = 0
        for f in config.CACHE_DIR.glob("*.pkl"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        logger.info(f"已清除 {count} 個快取檔案")
        return count

    def cache_status(self) -> dict:
        """回傳快取目錄統計。"""
        from src import config
        files = list(config.CACHE_DIR.glob("*.pkl"))
        total_mb = sum(f.stat().st_size for f in files) / 1024 / 1024
        return {
            "file_count": len(files),
            "total_mb": round(total_mb, 2),
            "cache_dir": str(config.CACHE_DIR),
        }

    def get_change_pct(self) -> Optional[pd.DataFrame]:
        """
        取得 FinLab 個股當日漲跌幅（%）。
        使用 'price:漲跌幅' 欄位，回傳 DataFrame（index=日期, columns=股票代號）。
        取最後一列為當日數值。失敗回傳 None。
        """
        try:
            df = self.get("price:漲跌幅")
            return df if isinstance(df, pd.DataFrame) else None
        except Exception as e:
            logger.warning("get_change_pct 失敗: %s", e)
            return None

    def get_latest_change_pct(self) -> dict:
        """
        回傳 {stock_id: change_pct_float} 的字典（當日最新漲跌幅）。
        缺漏值以 None 填充。
        """
        df = self.get_change_pct()
        if df is None or df.empty:
            return {}
        latest_row = df.iloc[-1]
        result: dict = {}
        for col in latest_row.index:
            val = latest_row[col]
            result[str(col)] = round(float(val), 2) if pd.notna(val) else None
        return result


# 全域單例
fetcher = DataFetcher()
