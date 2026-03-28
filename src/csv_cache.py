"""csv_cache.py — 外部 API 時序資料 CSV 增量快取

適用：FRED 時序（DGS10, INDPRO 等）、yfinance ETF 日線
策略：
  - 本地 CSV 保存完整歷史；每次只抓「最後快取日+1」之後的新資料
  - 若本地 CSV 已包含昨天以前的資料，跳過 API 呼叫
  - 與 FinLab pickle 快取並行，互不干擾
"""
import logging
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _csv_dir() -> Path:
    from src import config
    d = config.CACHE_DIR / "csv"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(key: str) -> Path:
    safe = key.upper().replace(":", "_").replace("/", "_").replace(" ", "_")
    return _csv_dir() / f"{safe}.csv"


# ── 讀寫工具 ────────────────────────────────────────────────────────────

def read_series(key: str) -> pd.Series:
    """讀 CSV 快取 → pd.Series(DatetimeIndex → float)，無檔案返回空 Series。"""
    p = _path(key)
    if not p.exists():
        return pd.Series(dtype=float, name=key)
    try:
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        s = df["value"].dropna()
        s.index = pd.to_datetime(s.index)
        return s.sort_index()
    except Exception as e:
        logger.warning(f"CSV 讀取失敗 [{key}]: {e}")
        return pd.Series(dtype=float, name=key)


def write_series(key: str, new_data: pd.Series) -> pd.Series:
    """合併既有快取 + new_data，去重後寫回 CSV，返回完整序列。"""
    if new_data is None or new_data.empty:
        return read_series(key)
    existing = read_series(key)
    combined = pd.concat([existing, new_data.rename("value")]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    p = _path(key)
    out = combined.reset_index()
    out.columns = ["date", "value"]
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(p, index=False)
    logger.info(f"CSV 快取更新 [{key}]: 共 {len(combined)} 筆 → {p.name}")
    return combined


def last_cached_date(key: str) -> Optional[pd.Timestamp]:
    """快取最後一筆日期，無快取返回 None。"""
    s = read_series(key)
    return s.index[-1] if not s.empty else None


def fetch_with_cache(key: str, fetch_fn: Callable) -> pd.Series:
    """
    增量快取入口：
      1. 讀本地 CSV
      2. 若最後快取日 < 昨天 → 呼叫 fetch_fn(start: pd.Timestamp | None)
      3. 合併、存回、返回完整序列

    fetch_fn 簽名：fetch_fn(start: pd.Timestamp | None) -> pd.Series
      start=None 時代表首次拉取（全量）
    """
    cached = read_series(key)
    yesterday = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)

    if not cached.empty and cached.index[-1] >= yesterday:
        logger.debug(f"CSV 快取有效 [{key}]，跳過 API 呼叫")
        return cached

    start = None if cached.empty else cached.index[-1] + pd.Timedelta(days=1)
    try:
        new_data = fetch_fn(start)
        if new_data is not None and not new_data.empty:
            return write_series(key, new_data)
    except Exception as e:
        logger.warning(f"增量拉取失敗 [{key}]: {e}，使用既有快取")

    return cached


# ── FinLab 寬表格式 CSV（date × stocks）──────────────────────────────────

def _finlab_dir() -> Path:
    from src import config
    d = config.CACHE_DIR / "csv" / "finlab"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _finlab_path(key: str) -> Path:
    safe = key.replace(":", "_").replace("/", "_").replace(" ", "_")
    return _finlab_dir() / f"{safe}.csv"


def export_finlab_df(key: str, df: pd.DataFrame) -> None:
    """
    將 FinLab DataFrame（rows=日期, cols=股票代號）增量匯出到 CSV。
    只追加 CSV 內最後日期之後的新行，不重寫整檔。
    """
    if df is None or df.empty:
        return
    try:
        p = _finlab_path(key)
        if p.exists():
            # on_bad_lines='skip' 跳過欄位數不符的壞行（Error tokenizing data）
            raw = pd.read_csv(p, index_col=0, on_bad_lines='skip')
            if raw.empty:
                df.to_csv(p)
                logger.info(f"FinLab CSV 重寫 [{key}]: {df.shape[0]}×{df.shape[1]}")
                return
            # 明確用 pd.to_datetime 轉換，避免 dtype=str vs Timestamp 比較錯誤
            last_idx = pd.to_datetime(raw.index[-1], format='mixed', dayfirst=False)
            df_idx_dt = pd.to_datetime(df.index, errors='coerce', format='mixed', dayfirst=False)
            new_rows = df[df_idx_dt > last_idx]
            if new_rows.empty:
                return
            new_rows.to_csv(p, mode="a", header=False)
            logger.debug(f"FinLab CSV 增量更新 [{key}]: +{len(new_rows)} 行")
        else:
            df.to_csv(p)
            logger.info(f"FinLab CSV 初次匯出 [{key}]: {df.shape[0]}×{df.shape[1]}")
    except Exception as e:
        logger.warning(f"FinLab CSV 匯出失敗 [{key}]: {e}")


def load_finlab_df_fallback(key: str) -> Optional[pd.DataFrame]:
    """pickle 和 FinLab API 皆失效時，從 CSV 備份讀取。"""
    p = _finlab_path(key)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True, on_bad_lines='skip')
        logger.warning(f"使用 FinLab CSV 備份 [{key}]: {df.shape}")
        return df
    except Exception as e:
        logger.warning(f"FinLab CSV 備份讀取失敗 [{key}]: {e}")
        return None
