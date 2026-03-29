"""
truth_social.py — Truth Social / 外部爬蟲輸出讀取器

支援兩種輸入格式：
  A) JSON 陣列  → [{text, timestamp?, url?}, ...]
  B) JSONL      → 每行一個 JSON object
  C) 純文字（.txt）→ 按空行或換行分段，每段視為一篇

使用範例
-------
  from src.scrapers.truth_social import load_posts
  posts = load_posts("path/to/output.json")

若路徑不存在，回傳空列表（不 raise）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 預設爬蟲輸出路徑（可被環境變數覆蓋）
# 用法：設 TRUTH_SOCIAL_PATH=/path/to/crawler/output.json
_DEFAULT_PATH_ENV = "TRUTH_SOCIAL_PATH"


def _normalize_post(raw: Any) -> dict | None:
    """將任意格式的原始物件標準化成 {text, timestamp, url}。"""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return {"text": text, "timestamp": None, "url": None}

    if not isinstance(raw, dict):
        return None

    # 嘗試常見欄位名稱
    text = (
        raw.get("text")
        or raw.get("content")
        or raw.get("body")
        or raw.get("message")
        or ""
    )
    text = str(text).strip()
    if not text:
        return None

    timestamp = (
        raw.get("timestamp")
        or raw.get("created_at")
        or raw.get("date")
        or raw.get("time")
    )
    url = raw.get("url") or raw.get("link") or raw.get("id")

    return {"text": text, "timestamp": timestamp, "url": str(url) if url else None}


def load_posts(path: str | Path | None = None) -> list[dict]:
    """
    從指定路徑載入貼文。

    Parameters
    ----------
    path : 檔案路徑。若為 None，從環境變數 TRUTH_SOCIAL_PATH 讀取。

    Returns
    -------
    list of {"text": str, "timestamp": str|None, "url": str|None}
    依時間由新到舊排序（若有 timestamp 欄位）。
    """
    if path is None:
        path = os.environ.get(_DEFAULT_PATH_ENV, "")

    if not path:
        return []

    p = Path(path)
    if not p.exists():
        return []

    suffix = p.suffix.lower()

    try:
        raw_text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    raw_posts: list[Any] = []

    if suffix in (".json",):
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            raw_posts = data
        elif isinstance(data, dict):
            # 可能是 {"posts": [...]} 格式
            raw_posts = (
                data.get("posts")
                or data.get("data")
                or data.get("results")
                or [data]
            )
    elif suffix in (".jsonl", ".ndjson"):
        for line in raw_text.splitlines():
            line = line.strip()
            if line:
                try:
                    raw_posts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    elif suffix in (".txt", ".md", ""):
        # 按空行分段
        segments = [s.strip() for s in raw_text.split("\n\n") if s.strip()]
        raw_posts = segments

    posts = []
    for r in raw_posts:
        normalized = _normalize_post(r)
        if normalized:
            posts.append(normalized)

    # 依 timestamp 排序（由新到舊），無 timestamp 者排在後面
    def sort_key(post: dict):
        ts = post.get("timestamp")
        return ts if ts else ""

    posts.sort(key=sort_key, reverse=True)
    return posts


def load_posts_from_dir(directory: str | Path) -> list[dict]:
    """
    掃描整個目錄下所有 .json / .jsonl / .txt，
    合併所有貼文並依時間由新到舊排序（去重 by url）。
    """
    d = Path(directory)
    if not d.is_dir():
        return []

    all_posts: list[dict] = []
    seen_urls: set[str] = set()

    for file in sorted(d.iterdir()):
        if file.suffix.lower() in (".json", ".jsonl", ".ndjson", ".txt"):
            for post in load_posts(file):
                url = post.get("url") or ""
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                all_posts.append(post)

    # 最終排序
    all_posts.sort(key=lambda p: p.get("timestamp") or "", reverse=True)
    return all_posts
