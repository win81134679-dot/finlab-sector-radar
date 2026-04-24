"""
config.py — 從 .env 讀取設定，提供全域常數
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 專案根目錄（src 的上一層）
BASE_DIR = Path(__file__).resolve().parent.parent

# 載入 .env
load_dotenv(BASE_DIR / ".env")

# ── API Keys ──────────────────────────────────────────────
FINLAB_API_TOKEN: str = os.getenv("FINLAB_API_TOKEN", "")
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY: str = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── 快取 ──────────────────────────────────────────────────
CACHE_EXPIRE_HOURS: float = float(os.getenv("CACHE_EXPIRE_HOURS", "24"))
CACHE_DIR: Path = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── 輸出 ──────────────────────────────────────────────────
OUTPUT_DIR: Path = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 板塊設定 ──────────────────────────────────────────────
CUSTOM_SECTORS_CSV: Path = BASE_DIR / "custom_sectors.csv"

# ── 分析參數 ──────────────────────────────────────────────
RS_LOOKBACK_DAYS: int = int(os.getenv("RS_LOOKBACK_DAYS", "60"))

# 燈1：月營收 YoY 拐點
REVENUE_CONSECUTIVE_MONTHS: int = 3
REVENUE_SECTOR_THRESHOLD: float = 0.50   # 板塊 ≥50% 個股亮燈
REVENUE_WEIGHTED_YOY_MONTHS: int = 3     # 加權YoY連 N 月正成長（板塊OR條件）
REVENUE_WEIGHTED_YOY_MIN_PCT: float = 5.0  # 加權YoY最近月 > N%（避免微幅正成長誤觸）

# 燈2：法人共振
INSTITUTIONAL_CONSECUTIVE_DAYS: int = 3
INSTITUTIONAL_SECTOR_THRESHOLD: float = 0.30

# 燈3：庫存循環
INVENTORY_LOOKBACK_DAYS: int = 5
INVENTORY_SECTOR_THRESHOLD: float = 0.50   # 存貨去化比例 ≥50% 板塊亮燈
REVENUE_MOM_ACCEL_MONTHS: int = 2        # MoM 加速連續期數（日化代理）

# 燈4：技術突破
TECHNICAL_MA_LONG: int = 60
TECHNICAL_MA_SHORT: int = 20
TECHNICAL_VOLUME_MULTIPLIER: float = 1.5

# 燈6：籌碼集中（融資+借券同時下降，AND條件；板塊門檻50%）
CHIPSET_SECTOR_THRESHOLD: float = 0.50
CHIPSET_LENDING_WINDOW: int = 5          # 借券方向偵測窗口（天）

# 燈7：宏觀（Alpha Vantage SOX代理）
MACRO_SOX_SYMBOL: str = "SOXX"           # iShares Semiconductor ETF
MACRO_SOX_MA: int = 20
MACRO_CACHE_KEY: str = "macro_sox"
MACRO_USD_TWD_SYMBOL: str = "USDTWD=X"  # Yahoo Finance USD/TWD 匯率
MACRO_USD_TWD_MA: int = 7               # 台幣均線方向（7日）

# 學術燈8/9：季節動能 + 營收加速（bonus trigger）
REVENUE_ACCEL_LOOKBACK: int = 3          # 營收加速連續月數
REVENUE_ACCEL_AVG_MONTHS: int = 12       # 對比過去 N 月平均 YoY

# 法人市場狀態門檻（Chiang et al. 2012）
INSTITUTIONAL_BULL_DAYS: int = 3         # 牛市狀態下外資連買門檻
INSTITUTIONAL_BEAR_DAYS: int = 5         # 熊市狀態下外資連買門檻
INSTITUTIONAL_MARKET_MA: int = 260       # 市場狀態判定均線（週線≒260日）

# ── 輸出歷史目錄 ──────────────────────────────────────────────────────────
OUTPUT_HISTORY_DIR: Path = OUTPUT_DIR / "history"
OUTPUT_HISTORY_DIR.mkdir(exist_ok=True)

# ── Discord 通知 Webhook URLs（可選，未設定則靜默略過）────────────────────
DISCORD_WEBHOOK_DAILY:  str = os.getenv("DISCORD_WEBHOOK_DAILY", "")
DISCORD_WEBHOOK_ALERT:  str = os.getenv("DISCORD_WEBHOOK_ALERT", "")
DISCORD_WEBHOOK_MACRO:  str = os.getenv("DISCORD_WEBHOOK_MACRO", "")
DISCORD_WEBHOOK_SYSTEM: str = os.getenv("DISCORD_WEBHOOK_SYSTEM", "")

# ── 個股評分參數 ──────────────────────────────────────────────────────────
# 三面合一評分卡（台股適配版）：基本面 5.5 + 技術面 3.5 + 籌碼面 4 + 加分 2 = 最高 ~15 分
STOCK_SCORE_TIER1: float = 9.0          # ⭐⭐⭐ 第一批建倉門檻
STOCK_SCORE_TIER2: float = 6.0          # ⭐⭐  第二批建倉門檻
STOCK_SCORE_WATCH: float = 3.0          # ⭐   觀察名單門檻
STOCK_MIN_DISPLAY: float = 5.0          # 報告最低顯示分（< 此分不列出；提高避免跟風股）
STOCK_MAX_DISPLAY: int   = 8            # 每板塊最多顯示 N 支龍頭股（按評分由高到低）
STOCK_EPS_YOY_THRESHOLD: float = 25.0   # EPS YoY 亮燈門檻（%）
STOCK_TECH_SWEET_SPOT_MAX: float = 10.0 # 剛突破甜蜜區上限（dist_60ma < 此值才加分）
STOCK_ROE_MIN: float = 15.0             # ROE 加分門檻（%）
# 只對這兩個等級的板塊執行個股評分（略過「忽略」板塊節省運算）
STOCK_SCORE_TARGET_LEVELS: tuple = ("強烈關注", "觀察中")


# ── P1 大盤三態分類器（軟版，不修改七燈閾值）────────────────────────────────
MARKET_STATE_BULL_MA: int = 200        # 牛熊判定均線（TAIEX vs N日MA）
MARKET_STATE_MOMENTUM_DAYS: int = 20   # 動能計算窗口（近N日報酬率）

# ── P3 垃圾股五大業障過濾（每項可獨立開關）──────────────────────────────────
JUNK_FILTER_ENABLED: bool = True
JUNK_FILTER_PO: bool   = True    # 破：price < MA120 且 MA120 下彎
JUNK_FILTER_GU: bool   = True    # 孤：不在燈2任何法人集合內
JUNK_FILTER_XU: bool   = False   # 虛：現金流量為負（需確認FinLab欄位，預設關閉）
JUNK_FILTER_PIAN: bool = True    # 偏：PE < 0 或 PE > 80
JUNK_FILTER_SAN: bool  = True    # 散：近20日平均成交量 < 50萬股
JUNK_SECTOR_THRESHOLD: float = 0.60  # 垃圾股比例 ≥ 此值 → quality_warning=True

# ── P4 52週相對位階法 ───────────────────────────────────────────────────────
RS52W_LOOKBACK_DAYS: int = 252         # 52週約252個交易日
RS52W_WARN_THRESHOLD: float = -0.10   # 板塊落後 TAIEX 超過 -10% → underperforming_52w=True

# ── P5 沉寂板塊突破偵測 ─────────────────────────────────────────────────────
DORMANT_MIN_IGNORE_PERIODS: int = 5   # 連續忽略 ≥ N 期才算沉寂


def is_discord_configured() -> bool:
    """至少有一個 Discord Webhook 已設定。"""
    return any([
        DISCORD_WEBHOOK_DAILY.strip(),
        DISCORD_WEBHOOK_ALERT.strip(),
        DISCORD_WEBHOOK_MACRO.strip(),
        DISCORD_WEBHOOK_SYSTEM.strip(),
    ])


def is_finlab_token_set() -> bool:
    return bool(FINLAB_API_TOKEN.strip())


def is_fred_key_set() -> bool:
    return bool(FRED_API_KEY.strip())


def is_av_key_set() -> bool:
    return bool(ALPHA_VANTAGE_KEY.strip())
