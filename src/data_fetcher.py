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
        取得個股漲跌幅 DataFrame（%）。
        FinLab 不提供 'price:漲跌幅'，改由 'price:收盤價' 自行計算。
        公式：(close_t - close_{t-1}) / close_{t-1} * 100
        """
        try:
            close_df = self.get("price:收盤價")
            if close_df is None or not isinstance(close_df, pd.DataFrame) or len(close_df) < 2:
                return None
            pct_df = close_df.pct_change(fill_method=None) * 100
            return pct_df
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

    def get_last_trading_date(self) -> Optional[str]:
        """
        回傳最近一個交易日日期（YYYY-MM-DD）。
        FinLab DataFrame index 只含交易日，取最後一筆即可。
        """
        try:
            df = self.get("price:收盤價")
            if df is not None and not df.empty:
                return pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning("get_last_trading_date 失敗: %s", e)
        return None

    def get_trading_status(self, stock_ids: list, date_str: str) -> dict:
        """
        回傳 {stock_id: "halt"|"ex_div"|"normal"}。
        - 停牌：成交股數 == 0
        - 除權息：|漲跌幅| > 9.9（台股漲跌停 ±10%，超過即為除權息日）
        """
        status: dict = {sid: "normal" for sid in stock_ids}
        try:
            vol_df    = self.get("price:成交股數")
            chpct_df  = self.get_change_pct()   # 由收盤價自行計算漲跌幅
            date_ts   = pd.Timestamp(date_str)
            for sid in stock_ids:
                try:
                    # 停牌偵測
                    if vol_df is not None and sid in vol_df.columns:
                        rows = vol_df.loc[vol_df.index <= date_ts, sid]
                        if not rows.empty and pd.notna(rows.iloc[-1]) and rows.iloc[-1] == 0:
                            status[sid] = "halt"
                            continue
                    # 除權息偵測
                    if chpct_df is not None and sid in chpct_df.columns:
                        rows2 = chpct_df.loc[chpct_df.index <= date_ts, sid]
                        if not rows2.empty and pd.notna(rows2.iloc[-1]):
                            if abs(float(rows2.iloc[-1])) > 9.9:
                                status[sid] = "ex_div"
                except Exception:
                    pass
        except Exception as e:
            logger.warning("get_trading_status 失敗: %s", e)
        return status

    def get_ohlcv_batch(self, stock_ids: list, days: int = 10) -> dict:
        """
        回傳 {stock_id: [{date, o, h, l, c, v}, ...]} 最近 days 筆交易日 OHLCV。
        使用 price:開/高/低/收盤價 + price:成交股數。
        """
        result: dict = {}
        try:
            frames = {
                "o": self.get("price:開盤價"),
                "h": self.get("price:最高價"),
                "l": self.get("price:最低價"),
                "c": self.get("price:收盤價"),
                "v": self.get("price:成交股數"),
            }
            close_df = frames["c"]
            if close_df is None or close_df.empty:
                return result

            tail_index = close_df.index[-days:]

            for sid in stock_ids:
                if sid not in close_df.columns:
                    continue
                bars = []
                for ts in tail_index:
                    try:
                        if ts not in close_df.index:
                            continue
                        c_val = close_df.at[ts, sid]
                        if not pd.notna(c_val):
                            continue
                        c = round(float(c_val), 2)
                        bar: dict = {
                            "date": pd.Timestamp(ts).strftime("%Y-%m-%d"),
                            "c": c,
                        }
                        for key in ("o", "h", "l"):
                            df = frames[key]
                            if df is not None and sid in df.columns and ts in df.index:
                                val = df.at[ts, sid]
                                bar[key] = round(float(val), 2) if pd.notna(val) else c
                            else:
                                bar[key] = c
                        vol_df = frames["v"]
                        if vol_df is not None and sid in vol_df.columns and ts in vol_df.index:
                            v_val = vol_df.at[ts, sid]
                            bar["v"] = int(v_val) if pd.notna(v_val) else 0
                        else:
                            bar["v"] = 0
                        bars.append(bar)
                    except Exception:
                        continue
                if bars:
                    result[sid] = bars
        except Exception as e:
            logger.warning("get_ohlcv_batch 失敗: %s", e)
        return result


# 全域單例
fetcher = DataFetcher()
