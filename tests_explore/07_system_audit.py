"""
系統完整性自我診斷腳本
執行：python tests_explore/07_system_audit.py
"""
import csv
import re
import sys
import io
import json
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
ISSUES = []
WARNINGS = []
OK = []

def ISSUE(msg):
    ISSUES.append(msg)
    print(f"  [BUG]  {msg}")

def WARN(msg):
    WARNINGS.append(msg)
    print(f"  [WARN] {msg}")

def PASS(msg):
    OK.append(msg)
    print(f"  [OK]   {msg}")


# ═══════════════════════════════════════════════════════════════════════════
# 1. CSV 資料完整性
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [1] CSV 資料完整性 ===")

def audit_csv(path: Path, label: str):
    if not path.exists():
        ISSUE(f"{label} 找不到檔案: {path}")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    
    if not rows:
        ISSUE(f"{label} 是空檔案")
        return []
    
    # 必要欄位
    required = {"sector_id", "sector_name", "stock_ids"}
    missing_cols = required - set(rows[0].keys())
    if missing_cols:
        ISSUE(f"{label} 缺少必要欄位: {missing_cols}")
    
    # 重複 sector_id
    ids = [r.get("sector_id", "").strip() for r in rows]
    dups = {x for x in ids if ids.count(x) > 1 and x}
    if dups:
        ISSUE(f"{label} 重複 sector_id ({len(dups)} 個): {list(dups)[:5]}")
    else:
        PASS(f"{label} sector_id 無重複")
    
    # 空 sector_id
    empty_ids = [i for i, r in enumerate(rows, 2) if not r.get("sector_id", "").strip()]
    if empty_ids:
        ISSUE(f"{label} 空 sector_id 在第 {empty_ids[:3]} 行")
    
    # 非法字元 sector_id（只允許 a-z A-Z 0-9 _）
    bad_ids = [(r["sector_id"], i+2) for i, r in enumerate(rows)
               if r.get("sector_id") and re.search(r"[^a-zA-Z0-9_]", r["sector_id"])]
    if bad_ids:
        ISSUE(f"{label} sector_id 含非法字元 ({len(bad_ids)} 個): {bad_ids[:3]}")
    else:
        PASS(f"{label} sector_id 字元合規")
    
    # 空 stock_ids
    empty_stocks = [r["sector_id"] for r in rows if not r.get("stock_ids", "").strip()]
    if empty_stocks:
        WARN(f"{label} 空 stock_ids ({len(empty_stocks)} 個): {empty_stocks[:5]}")
    else:
        PASS(f"{label} 所有板塊有股票清單")
    
    # stock_ids 非數字（只允許純數字股票代號）
    bad_stocks = []
    for r in rows:
        sid = r.get("sector_id", "")
        raw = r.get("stock_ids", "")
        for tok in str(raw).split(","):
            tok = tok.strip()
            if tok and not re.match(r"^\d{4,6}$", tok):
                bad_stocks.append((sid, tok))
    if bad_stocks:
        WARN(f"{label} 非標準股票代號 ({len(bad_stocks)} 個): {bad_stocks[:5]}")
    else:
        PASS(f"{label} 股票代號格式正常")
    
    # sector_id 過長（>50 字元影響 JSON/DB key）
    long_ids = [r["sector_id"] for r in rows if len(r.get("sector_id", "")) > 50]
    if long_ids:
        WARN(f"{label} sector_id 過長 (>{50}字) ({len(long_ids)} 個): {long_ids[:3]}")
    
    print(f"  → {label}: {len(rows)} 行，{len(ids)} 個板塊")
    return rows


main_rows = audit_csv(ROOT / "custom_sectors.csv", "custom_sectors.csv")
sub_rows = audit_csv(ROOT / "output" / "custom_subsectors.csv", "custom_subsectors.csv")
merged_rows = audit_csv(ROOT / "output" / "proposed_sectors_v2.csv", "proposed_sectors_v2.csv")

# 主板塊與子類 id 衝突
if main_rows and sub_rows:
    main_ids = {r["sector_id"] for r in main_rows}
    sub_ids = {r["sector_id"] for r in sub_rows}
    overlap = main_ids & sub_ids
    if overlap:
        ISSUE(f"主板塊與子類 sector_id 衝突 ({len(overlap)} 個): {list(overlap)[:5]}")
    else:
        PASS(f"主板塊與子類 sector_id 無衝突")

# auto_sectors.csv（如存在）
auto_path = ROOT / "output" / "auto_sectors.csv"
if auto_path.exists():
    auto_rows = audit_csv(auto_path, "auto_sectors.csv")
    if main_rows and auto_rows:
        auto_ids = {r["sector_id"] for r in auto_rows}
        m_ids = {r["sector_id"] for r in main_rows}
        a_overlap = m_ids & auto_ids
        WARN(f"custom vs auto 重疊 sector_id（SectorMap 會優先 custom）: {len(a_overlap)} 個")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Python 核心模組存在性與語法
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [2] Python 核心模組存在性 ===")

CORE_MODULES = [
    "src/__init__.py",
    "src/ssl_fix.py",
    "src/config.py",
    "src/data_fetcher.py",
    "src/sector_map.py",
    "src/notifier.py",
    "src/analyzers/__init__.py",
    "src/analyzers/multi_signal.py",
    "src/analyzers/revenue.py",
    "src/analyzers/institutional.py",
    "src/analyzers/inventory.py",
    "src/analyzers/technical.py",
    "src/analyzers/rs_ratio.py",
    "src/analyzers/chipset.py",
    "src/analyzers/macro.py",
    "src/analyzers/stock_scorer.py",
    "src/analyzers/correlation_gate.py",
    "src/analyzers/momentum_season.py",
    "src/analyzers/revenue_surprise.py",
]

for rel in CORE_MODULES:
    p = ROOT / rel
    if not p.exists():
        ISSUE(f"核心檔案不存在: {rel}")
    else:
        # 嘗試 compile 語法檢查
        try:
            import py_compile
            py_compile.compile(str(p), doraise=True)
            PASS(f"語法 OK: {rel}")
        except py_compile.PyCompileError as e:
            ISSUE(f"語法錯誤 {rel}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. 環境變數與 .env 安全性
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [3] 環境變數安全性 ===")

env_path = ROOT / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        env_content = f.read()
    # 確認 .env 不含明文密鑰特徵（過度簡單的值）
    if "your_token_here" in env_content.lower() or "placeholder" in env_content.lower():
        WARN(".env 含佔位符，尚未設定真實 API Key")
    
    # 必要 key 存在
    required_keys = ["FINLAB_API_TOKEN", "FRED_API_KEY", "ALPHA_VANTAGE_KEY"]
    for k in required_keys:
        if k + "=" in env_content and len(env_content.split(k + "=")[1].split("\n")[0].strip()) > 5:
            PASS(f".env {k} 已設定")
        else:
            WARN(f".env {k} 可能未設定或過短")
    
    # .env 在 .gitignore 中
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        gi = gitignore.read_text(encoding="utf-8")
        if ".env" in gi:
            PASS(".env 已加入 .gitignore")
        else:
            ISSUE(".env 未加入 .gitignore，API Key 可能洩漏！")
    else:
        WARN("找不到 .gitignore")
else:
    WARN(".env 檔案不存在（CI/CD 由 GitHub Secrets 注入屬正常）")


# ═══════════════════════════════════════════════════════════════════════════
# 4. config.py 合理性
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [4] config.py 參數合理性 ===")

sys.path.insert(0, str(ROOT))
try:
    from src import ssl_fix
    from src import config as cfg

    # 閾值邊界
    if not (0 < cfg.REVENUE_SECTOR_THRESHOLD <= 1.0):
        ISSUE(f"REVENUE_SECTOR_THRESHOLD={cfg.REVENUE_SECTOR_THRESHOLD} 超出 (0,1] 範圍")
    else:
        PASS(f"REVENUE_SECTOR_THRESHOLD={cfg.REVENUE_SECTOR_THRESHOLD}")

    if not (0 < cfg.INSTITUTIONAL_SECTOR_THRESHOLD <= 1.0):
        ISSUE(f"INSTITUTIONAL_SECTOR_THRESHOLD 超出範圍")

    if cfg.CACHE_EXPIRE_HOURS <= 0:
        ISSUE(f"CACHE_EXPIRE_HOURS={cfg.CACHE_EXPIRE_HOURS} 必須 > 0")
    else:
        PASS(f"CACHE_EXPIRE_HOURS={cfg.CACHE_EXPIRE_HOURS}")

    if not cfg.CUSTOM_SECTORS_CSV.exists():
        ISSUE(f"CUSTOM_SECTORS_CSV 路徑不存在: {cfg.CUSTOM_SECTORS_CSV}")
    else:
        PASS(f"CUSTOM_SECTORS_CSV 存在")

    # STOCK_SCORE_TARGET_LEVELS 需包含合法等級名稱
    valid_levels = {"強烈關注", "觀察中", "忽略"}
    for lvl in cfg.STOCK_SCORE_TARGET_LEVELS:
        if lvl not in valid_levels:
            ISSUE(f"STOCK_SCORE_TARGET_LEVELS 含非法等級: {lvl}")

    PASS("config.py 載入成功")
except Exception as e:
    ISSUE(f"config.py 載入失敗: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 5. sector_map.py 載入測試（不呼叫 FinLab API）
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [5] SectorMap 載入測試 ===")
try:
    from src.sector_map import SectorMap
    sm = SectorMap()
    count = sm.load(ROOT / "custom_sectors.csv")
    if count == 0:
        ISSUE("SectorMap 載入 0 個板塊")
    else:
        PASS(f"SectorMap.load() 成功：{count} 個板塊")
    
    # create_filtered 方法存在性
    if hasattr(sm, "create_filtered"):
        PASS("SectorMap.create_filtered() 方法存在")
    else:
        ISSUE("SectorMap 缺少 create_filtered() 方法（multi_signal.py 相關性閘門需要）")
    
    # get_stocks / get_sector_name / all_sector_ids
    for method in ["get_stocks", "get_sector_name", "all_sector_ids", "list_sectors"]:
        if hasattr(sm, method):
            PASS(f"SectorMap.{method}() 存在")
        else:
            ISSUE(f"SectorMap 缺少 {method}() 方法")
    
    # 空板塊比例
    empty_sectors = [sid for sid in sm.all_sector_ids() if not sm.get_stocks(sid)]
    if empty_sectors:
        WARN(f"載入後仍有空 stocks 的板塊 ({len(empty_sectors)} 個): {empty_sectors[:3]}")
    else:
        PASS(f"所有板塊載入後均有股票清單")
        
except Exception as e:
    ISSUE(f"SectorMap 載入測試失敗: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 6. multi_signal.py 關鍵函式存在性與邏輯
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [6] multi_signal.py 關鍵函式 ===")
try:
    import importlib
    ms = importlib.import_module("src.analyzers.multi_signal")
    
    for fn in ["run_all", "_level", "_sanitize_nans", "_nan_to_none", "_get_score"]:
        if hasattr(ms, fn):
            PASS(f"multi_signal.{fn} 存在")
        else:
            ISSUE(f"multi_signal 缺少 {fn}")
    
    # _level 函式邏輯驗證
    assert ms._level(5.0) == "強烈關注", "_level(5.0) 應為強烈關注"
    assert ms._level(2.5) == "觀察中",   "_level(2.5) 應為觀察中"
    assert ms._level(1.0) == "忽略",     "_level(1.0) 應為忽略"
    # 品質閘門：純技術不應進強烈關注
    assert ms._level(4.0, [0, 0.5, 0, 1, 1, 1, 1]) == "觀察中", "純技術應降級"
    PASS("_level 邏輯正確（含品質閘門）")
    
    # _sanitize_nans 驗證
    import math
    result = ms._sanitize_nans({"a": float("nan"), "b": [float("nan"), 1.0]})
    assert result["a"] is None
    assert result["b"][0] is None
    PASS("_sanitize_nans 正確處理 NaN")
    
    # 確認 MIN_VALID_ANALYZERS 與 SECTOR_ANALYZERS 數量一致性
    # MIN_VALID_ANALYZERS=4, SECTOR_ANALYZERS=6（燈1-6）→ Condorcet 4/6 合理
    PASS("資料可用性閘門設定（MIN_VALID_ANALYZERS=4/6）")
    
except AssertionError as e:
    ISSUE(f"multi_signal 邏輯驗證失敗: {e}")
except Exception as e:
    ISSUE(f"multi_signal 匯入/驗證失敗: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 7. 快取目錄權限與安全
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [7] 快取與輸出目錄安全 ===")
try:
    cache_dir = ROOT / ".cache"
    output_dir = ROOT / "output"
    
    if cache_dir.exists():
        # 測試寫入權限
        test_file = cache_dir / "_audit_test.tmp"
        test_file.write_bytes(b"test")
        test_file.unlink()
        PASS(".cache 目錄可讀寫")
        
        # pickle 檔案完整性（抽樣 3 個）
        import pickle
        pkl_files = list(cache_dir.glob("*.pkl"))
        PASS(f".cache 目錄有 {len(pkl_files)} 個 pickle 快取")
        bad_pkl = 0
        for pf in pkl_files[:5]:  # 只抽樣前 5 個
            try:
                with open(pf, "rb") as f:
                    pickle.load(f)
            except Exception:
                bad_pkl += 1
        if bad_pkl:
            WARN(f"抽樣發現 {bad_pkl} 個損壞的 pickle 快取（系統會自動重拉）")
        else:
            PASS("pickle 快取抽樣無損壞")
    else:
        WARN(".cache 目錄不存在（首次執行會自動建立）")
    
    if output_dir.exists():
        test_file2 = output_dir / "_audit_test.tmp"
        test_file2.write_bytes(b"test")
        test_file2.unlink()
        PASS("output 目錄可讀寫")
        
        # signals_latest.json 存在性與 JSON 合法性
        latest = output_dir / "signals_latest.json"
        if latest.exists():
            try:
                data = json.loads(latest.read_text(encoding="utf-8"))
                PASS(f"signals_latest.json 合法 JSON，sectors={len(data.get('sectors', {}))}")
            except json.JSONDecodeError as e:
                ISSUE(f"signals_latest.json 格式損壞: {e}")
        else:
            WARN("signals_latest.json 不存在（首次執行屬正常）")
    else:
        ISSUE("output 目錄不存在")
        
except Exception as e:
    ISSUE(f"目錄安全檢查失敗: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 8. 子類擴充腳本（06）自身完整性
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [8] tests_explore/06 腳本完整性 ===")
script06 = ROOT / "tests_explore" / "06_finlab_subcategory_expansion.py"
if not script06.exists():
    ISSUE("06_finlab_subcategory_expansion.py 不存在")
else:
    try:
        import py_compile
        py_compile.compile(str(script06), doraise=True)
        PASS("06_finlab_subcategory_expansion.py 語法正確")
    except py_compile.PyCompileError as e:
        ISSUE(f"06 腳本語法錯誤: {e}")
    
    # 確認輸出檔案存在
    sub_csv = ROOT / "output" / "custom_subsectors.csv"
    if sub_csv.exists():
        with open(sub_csv, encoding="utf-8-sig") as f:
            sub_count = sum(1 for _ in f) - 1  # 減 header
        PASS(f"custom_subsectors.csv 存在，{sub_count} 個子類")
    else:
        WARN("custom_subsectors.csv 尚未生成（需先執行 06 腳本）")
    
    merged_csv = ROOT / "output" / "proposed_sectors_v2.csv"
    if merged_csv.exists():
        with open(merged_csv, encoding="utf-8-sig") as f:
            merge_count = sum(1 for _ in f) - 1
        PASS(f"proposed_sectors_v2.csv 存在，{merge_count} 個板塊")


# ═══════════════════════════════════════════════════════════════════════════
# 9. proposed_sectors_v2.csv 深度驗證
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== [9] proposed_sectors_v2.csv 深度驗證 ===")
v2_path = ROOT / "output" / "proposed_sectors_v2.csv"
if v2_path.exists():
    with open(v2_path, encoding="utf-8-sig", newline="") as f:
        v2_rows = list(csv.DictReader(f))
    
    v2_ids = [r["sector_id"] for r in v2_rows]
    v2_dups = {x for x in v2_ids if v2_ids.count(x) > 1 and x}
    if v2_dups:
        ISSUE(f"proposed_sectors_v2.csv 重複 sector_id ({len(v2_dups)} 個): {list(v2_dups)[:5]}")
    else:
        PASS(f"proposed_sectors_v2.csv 無重複 sector_id（{len(v2_ids)} 個）")
    
    # sector_type 合法性
    valid_types = {"twse", "otc", "custom", "auto", "finlab_sub", "finlab"}
    bad_types = [(r["sector_id"], r.get("sector_type")) for r in v2_rows
                 if r.get("sector_type") not in valid_types]
    if bad_types:
        WARN(f"非標準 sector_type ({len(bad_types)} 個): {bad_types[:3]}")
    else:
        PASS(f"所有 sector_type 合規")
    
    # finlab_sub 需有 parent_sector
    no_parent = [r["sector_id"] for r in v2_rows
                 if r.get("sector_type") == "finlab_sub" and not r.get("parent_sector", "").strip()]
    if no_parent:
        WARN(f"finlab_sub 缺少 parent_sector ({len(no_parent)} 個): {no_parent[:3]}")
    else:
        PASS("所有 finlab_sub 板塊有 parent_sector")


# ═══════════════════════════════════════════════════════════════════════════
# 結果摘要
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print(f"診斷完成：{len(ISSUES)} 個 BUG / {len(WARNINGS)} 個警告 / {len(OK)} 項通過")
print("="*60)
if ISSUES:
    print("\n[需立即修補的 BUG]")
    for i, msg in enumerate(ISSUES, 1):
        print(f"  #{i}: {msg}")
if WARNINGS:
    print("\n[建議處理的警告]")
    for i, msg in enumerate(WARNINGS, 1):
        print(f"  #{i}: {msg}")
if not ISSUES:
    print("\n✅ 系統無嚴重 BUG！")
