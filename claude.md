# FinLab 板塊偵測系統 — 專案指南 + PRD（claude.md）

> **版本**：v2.0-draft｜**日期**：2026-05-30｜**維護**：FinLab Sector Radar
>
> **一句話**：用學術量化「七燈訊號」每日自動掃描台股 59 個板塊的輪動週期，搭配宏觀濾網、個股評分、出場警報與即時儀表板，協助散戶做有紀律的板塊配置。
>
> **本檔定位**：這是給 Claude / 工程師看的「**真實**專案地圖 + 升級 PRD」。產品策略、商業模式、Persona 等請看 [`PRD 產品規格文件.md`](PRD%20產品規格文件.md)（3196 行，v1.5）。本檔聚焦：**系統現況怎麼運作** + **如何升級成更精準的產業輪動偵測**。

---

## 目錄

1. [系統概覽](#1-系統概覽)
2. [架構與資料流](#2-架構與資料流)
3. [七燈分析引擎（核心）](#3-七燈分析引擎核心)
4. [板塊定義與資料來源](#4-板塊定義與資料來源)
5. [輸出契約（output/）](#5-輸出契約output)
6. [前端儀表板](#6-前端儀表板)
7. [自動化管道](#7-自動化管道)
8. [開發慣例與陷阱](#8-開發慣例與陷阱)
9. [**升級 PRD：精準產業輪動偵測**](#9-升級-prd精準產業輪動偵測)
10. [附錄：指令速查 / 詞彙表](#10-附錄)

---

## 1. 系統概覽

| 維度 | 內容 |
|------|------|
| **產品** | 台股板塊輪動偵測 Web Dashboard（收盤後日頻率，非盤中即時） |
| **核心** | 7 維度量化訊號聚合（Condorcet 多數決 + 品質閘門）→ 板塊燈號 + 週期階段 + 出場風險 |
| **後端** | Python 分析核心（`src/`，40+ 模組），FinLab / FRED / yfinance / CoinGecko 取數 |
| **前端** | Next.js 16 + React 19 + TS strict + Tailwind v4（`frontend/`），Server Component + ISR |
| **橋接** | Python 寫 `output/*.json` → git push → GitHub Raw URL → 前端 fetch（Zod 驗證） |
| **排程** | GitHub Actions 台灣時間平日 20:30 自動執行；川普訊號每 4h |
| **部署** | Vercel Hobby（前端）；資料層完全免費（GitHub repo + Raw CDN） |
| **成本** | ~$1.5/月（近乎零成本） |

**關鍵理解**：這個系統**不是**一個簡單的「漲跌幅排行」。它已經內建了使用者研究中提到的多數方法——RRG 相對強度（燈5）、法人籌碼（燈2）、宏觀濾網（燈7）、週期階段判定、出場風險。第 9 章的升級是**補齊真正缺的那幾塊**（景氣燈號濾網、產業 RSI 接棒、法人「板塊級」聚合、領先落後對），而不是從零打造。

---

## 2. 架構與資料流

```
┌─────────────────────── Python 分析核心 (src/) ───────────────────────┐
│                                                                       │
│  DataFetcher ──get(key)──► FinLab API (pickle 24hr 快取 + CSV 備份)    │
│       │                    FRED / yfinance / CoinGecko (csv_cache 增量)│
│       ▼                                                                │
│  SectorMap (custom_sectors.csv + output/auto_sectors.csv = 59 板塊)    │
│       │                                                                │
│       ▼   multi_signal.run_all()  ── ThreadPoolExecutor(max_workers=4) │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ 燈1 營收  燈2 法人  燈3 庫存  燈4 技術  燈5 RRG  燈6 籌碼  燈7 宏觀 │  │
│  │ + correlation_gate（同質性閘門）+ market_state（大盤三態）         │  │
│  │ + sector_quality_filter（垃圾股過濾）+ 學術 bonus（季節/營收加速）  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│       │  彙總 → 每板塊 total / level / cycle_stage / exit_risk          │
│       ▼  stock_scorer（個股評分）→ cycle_exit（出場風險）              │
│       ▼  commodities / maga_analyzer / composite / portfolio / exit_alert│
│       ▼                                                                │
│  _save_snapshot() → output/signals_latest.json + history/ + index      │
└───────────────────────────────────────────────────────────────────────┘
       │
       │  GitHub Actions: git add output/ && commit "[skip ci]" && push
       ▼
GitHub Raw URL (NEXT_PUBLIC_GITHUB_RAW_BASE_URL)
       │
       ▼  frontend/lib/fetcher.ts （每個來源一個 Zod schema，失敗回傳 null）
page.tsx (Server Component, ISR revalidate=1800s, Promise.all 並行 8 fetch)
       ▼
TabContainer (Client) → SectorGrid / MacroPanel / CommodityPanel /
                         AccelerationPanel / ConvergencePanel / TrumpFeedPanel /
                         HoldingsTab ...
```

**目錄結構**（重點）：

```
root/
├── claude.md                    # ← 本檔
├── PRD 產品規格文件.md          # 完整產品 PRD（v1.5, 3196 行）
├── custom_sectors.csv           # 板塊定義（手動，最高優先）
├── requirements.txt
├── src/                         # Python 分析核心
│   ├── main.py                  # Rich CLI（互動選單）+ `--auto`（CI 非互動）
│   ├── config.py                # .env 讀取 + 全域閾值常數
│   ├── data_fetcher.py          # FinLab wrapper（pickle 快取 / 重試 / 降級）
│   ├── csv_cache.py             # FRED/yfinance/FinLab 的 CSV 增量快取與 fallback
│   ├── ssl_fix.py               # ⚠️ 必須最早 import（Windows 中文路徑 SSL 修正）
│   ├── sector_map.py            # CSV → {sector_id: {name, stocks, parent, source}}
│   ├── industry_mapping.py      # 由官方產業碼產生 output/auto_sectors.csv
│   ├── stock_names.py           # 代碼→中文名稱（硬編碼補充）
│   ├── analyzers/               # 各燈號 + 衍生分析器（見 §3）
│   ├── reporters/               # Markdown 報告 + 檔案掃描
│   ├── scrapers/truth_social.py # 川普貼文載入
│   └── notifier.py              # Discord webhook 通知
├── scripts/                     # 一次性工具（backfill / backtest / 驗證）
├── output/                      # 分析結果（由 Python 寫出，⚠️ 勿手改）
│   ├── signals_latest.json      # 前端主資料源
│   ├── history/ + history_index.json
│   ├── ohlcv/<code>.json        # 個股 K 線
│   ├── commodities/*.json  composite/*.json  maga/latest.json
│   └── portfolio/*.json         # holdings / pnl / exit_alerts / user_holdings
├── frontend/                    # Next.js 16
│   ├── app/                     # App Router（page.tsx + api/）
│   ├── components/              # 54 個 .tsx UI 元件
│   └── lib/                     # fetcher.ts(Zod) / types.ts / signals.ts / regime.ts ...
└── .github/workflows/
    ├── daily_analysis.yml       # 平日 20:30 TST
    └── trump_feed_update.yml    # 每 4h
```

---

## 3. 七燈分析引擎（核心）

每個 analyzer 是獨立模組，簽名 `analyze(fetcher, sector_map, config) -> Dict[sector_id, Dict]`（燈7 例外，全局單一 dict）。`multi_signal.run_all()` 用 `ThreadPoolExecutor` 平行執行，再彙總。**分數支援 0 / 0.5 / 1.0 三態**（`score_contrib` 欄位，支援「半亮」）。

| 燈 | 維度 | 模組 | 亮燈邏輯（摘要） | 學術依據 |
|----|------|------|-----------------|---------|
| 1 | 月營收 YoY 拐點 | `revenue.py` | 個股連 3 月 YoY 由負轉正；板塊 ≥50% 亮燈。輔助：MoM 連 2 月加速；板塊加權 YoY 連 3 月 >5% | — |
| 2 | 法人籌碼共振 | `institutional.py` | 外資+投信同步連買 N 日（牛市 N=3 / 熊市 N=5，依 TWII vs 260MA 自適應）；板塊 ≥30% 共振。半亮：外資或投信獨買 ≥2 檔 | Chiang 2012；Huang & Shiu 2009 |
| 3 | 庫存循環 | `inventory.py` | 存貨週轉 2Q 趨勢改善；板塊 ≥50% | Abernathy 2014 |
| 4 | 技術突破 | `technical.py` | MA20>MA60 + 量能 ≥1.5×；嚴格相關性閘門 | — |
| 5 | 相對強度 RRG | `rs_ratio.py` | **RS-Ratio**=板塊均價/TWII（14日EMA），**RS-Momentum**=RS-Ratio 的 10日EMA 斜率。亮燈=RS-Ratio≥1 且 Momentum≥0（領先象限）。同時算 52週相對位階 | de Kempenaer 2014 |
| 6 | 籌碼集中 | `chipset.py` | 融資+借券同步下降（AND）；板塊 ≥50% | — |
| 7 | 宏觀濾網（全局） | `macro.py` | 四子訊號 ≥60% 正面：①FRED DGS10 < 63日MA（利率下行）②FRED INDPRO ≥ 12月MA（工業擴張）③SOXX > 20MA ④USD/TWD < 7日MA（台幣升值）。**所有板塊共享燈7** | Singh 2011 |

### 彙總邏輯（`multi_signal.py`）

- **total** = 七燈分數加總（0.0–7.0）
- **level**（`_level()`）：
  - `強烈關注`：total ≥ 4 **且通過品質閘門**（燈1 營收 or 燈3 庫存 ≥ 0.5，防純技術/籌碼假訊號）
  - `觀察中`：total ≥ 2
  - `忽略`：total < 2
  - 學術依據：Condorcet 陪審團定理（n=7 → 多數決門檻 4）+ Piotroski 2000（品質閘門）
- **cycle_stage**（`_calc_cycle_stage()`，優先序 過熱>加速>確認>萌芽）：
  - `過熱期`：total ≥ 6.5
  - `加速期`：total ≥ 5 或（total ≥ 4 且 chip ≥ 1）
  - `確認期`：inst ≥ 0.5 且 tech ≥ 0.5
  - `萌芽期`：（rev ≥ 0.5 或 inv ≥ 0.5）且 inst < 0.5 且 tech < 0.5
- **exit_risk**（`cycle_exit.calc_exit_risk()`，僅加速/過熱期）：RRG轉弱(+40) / 籌碼熄滅(+25) / 接近過熱(+20) / 宏觀逆風(+15) → 0–100 → 持有/留意/減碼/出場

### 防禦機制（重要，勿移除）

1. **資料可用性閘門**：6 個板塊燈中 < 4 個有效 → `raise RuntimeError`，中止以保護現有資料（防 FinLab API 全掛時覆蓋好資料）。
2. **品質異常退化保護**：前次 ≥5 個強烈關注、本次變 0 → 中止（市場不可能單日全崩）。
3. **相關性閘門**（`correlation_gate.py`）：算各板塊 intra-sector correlation，燈4/5 用嚴格門檻(≥0.40)、燈1/2/3/6 用寬鬆(≥0.25) 過濾異質股，避免「拼湊板塊」失真。
4. **降級容錯**：任一 analyzer 崩潰 → `raw[name]={}`，其他照常；FinLab 失敗 → 過期 pickle → CSV 備份。

### 衍生 / 軟版分析器（不計入七燈總分）

| 模組 | 作用 |
|------|------|
| `market_state.py` | P1 大盤三態（牛/震盪/熊，TAIEX vs 200MA + 20日動能）→ 注入 `market_state` 欄位，前端顯示警示 |
| `sector_quality_filter.py` | P3 垃圾股「五大業障」過濾（破/孤/虛/偏/散）→ `quality_warning` |
| `momentum_season.py` / `revenue_surprise.py` | 學術 bonus（季節動能、營收加速）→ 個股評分加分 |
| `stock_scorer.py` | 個股三面評分（基本面5.5+技術3.5+籌碼4+bonus2 ≈ 15）→ S/A/B/C/D |
| `commodities.py` | 商品市場（金/油/幣/債）+ 殖利率曲線倒掛 |
| `maga_analyzer.py` / `composite.py` / `trump_nlp.py` | 川普政策衝擊（受益/受害板塊 + NLP 情緒）|
| `portfolio.py` / `exit_alert.py` | 建議持倉 + 損益 + 隔日五級出場警報 |

---

## 4. 板塊定義與資料來源

- **板塊數**：59（`custom_sectors.csv`，header：`sector_id,sector_name,sector_type,parent_sector,stock_ids`）。`sector_type` ∈ {twse, custom, finlab}；`parent_sector` 建立樹狀（如 `ic_design` → `semiconductor`）。
- **雙源合併**（`sector_map.py`）：`custom_sectors.csv`（手動，最高優先）+ `output/auto_sectors.csv`（由 `industry_mapping.py` 從官方產業碼自動產生，補未覆蓋股）。
- **新增/修改板塊**：直接編輯 CSV，**不需改 Python**。`scripts/` 下有 `rebuild_sectors.py` / `validate_curated.py` / `verify_rebuild.py` 等維護工具。

### 資料來源一覽

| 來源 | 取什麼 | 怎麼取 | 金鑰 |
|------|--------|--------|------|
| **FinLab API** | 收盤/開高低/成交量、月營收 YoY、法人買賣超、融資借券、存貨、EPS/ROE/PE、TAIEX 指數 | `fetcher.get("price:收盤價")` 等；pickle 24hr 快取 + CSV 備份 | `FINLAB_API_TOKEN` ✅ |
| **FRED** | DGS10（美10年債）、INDPRO（工業生產）| `fredapi` + csv_cache 增量 | `FRED_API_KEY` ✅ |
| **yfinance** | SOXX、USD/TWD、^TWII、商品價格 | `yfinance` + csv_cache（注意 `ssl_fix`）| 無 |
| **CoinGecko** | 加密貨幣 | HTTP | 無 |
| **Alpha Vantage** | 美股代理（備援）| HTTP | `ALPHA_VANTAGE_KEY` ✅ |

> 使用者研究提到的 **TEJ / TejToolAPI** 本專案目前**未接**。第 9 章的升級**不需要** TEJ——景氣燈號可由 FRED/公開資料代理或手動 CSV 維護；產業 RSI、法人聚合都能用既有 FinLab 資料算出。

---

## 5. 輸出契約（output/）

> ⚠️ **`output/` 由 Python 管道自動覆寫，勿手改**。新增欄位時**必須**同步更新 `frontend/lib/types.ts` + `frontend/lib/fetcher.ts` 的 Zod schema，否則前端 Zod safeParse 失敗 → 該資料變 null。

`signals_latest.json`（前端主資料源，`schema_version: "2.0"`）核心結構：

```jsonc
{
  "schema_version": "2.0",
  "date": "2026-04-27",
  "run_at": "2026-04-27T22:19:00+08:00",
  "last_trading_date": "2026-04-27",
  "macro": { "warning": false, "signal": true, "positive_count": 3,
             "us_bond_10y": 4.25, "sox_price": 245.1, "usd_twd": 31.2, "details": {...} },
  "market_state": { "state": "bull", "state_zh": "牛市多頭", "confidence": 0.7,
                    "taiex_vs_200ma_pct": 3.2, "momentum_20d_pct": 1.8 },
  "sectors": {
    "<sector_id>": {
      "name_zh": "晶圓代工",
      "total": 4.5,
      "signals": [1.0, 0.5, 0.0, 1.0, 1.0, 0.5, 1.0],   // 七燈分數
      "level": "強烈關注",
      "cycle_stage": "加速期",
      "exit_risk": { "score": 35, "action": "留意", "triggers": [...], "rs_quadrant": "領先(Right-Upper)" },
      "rs_momentum": 0.0123,
      "homogeneity": 0.42,            // 相關性閘門同質性
      "leader_weak": false,           // P2 領頭股健康度
      "quality_filter": { "junk_ratio": 0.1, "quality_warning": false, ... },  // P3
      "sector_vs_taiex_52w": 0.08, "underperforming_52w": false,  // P4
      "dormant_awakening": false,     // P5 沉寂板塊突破
      "stocks": [ { "id":"2330","name_zh":"台積電","score":12.5,"grade":"S",
                    "change_pct":1.2,"triggered":["燈2✓",...],"breakdown":{...},
                    "price_flag":"normal","ohlcv_7d":[...] } ]
    }
  }
}
```

其他輸出：`history/YYYY-MM-DD.json`（每日快照）、`history_index.json`（前端一次讀取畫趨勢）、`ohlcv/<code>.json`（多時框 K 線）、`commodities/*.json`、`composite/latest.json` + `sensitivity.json`、`maga/latest.json`、`portfolio/{holdings,pnl,exit_alerts,user_holdings}.json`、`stock_names.json`、`stock_universe.json`。

---

## 6. 前端儀表板

- **`app/page.tsx`**：Server Component，ISR `revalidate=1800`。`Promise.all` 並行抓 8 個 GitHub Raw JSON，逐一 Zod 驗證，全 null → 顯示「📡 資料更新中」。
- **`lib/fetcher.ts`**：8 個 fetch 函式 + 對應 Zod schema；**失敗一律回傳 null，不拋例外**。
- **`lib/types.ts`**：所有 TS 型別單一真實來源（勿在元件內重複定義）。
- **`components/TabContainer.tsx`**（Client）：7 個 Tab — 短線📊 / 共振🎯 / 週期🔄 / 長線📐 / 訊號📡 / 商品🌐 / 持倉📌。
- **API Routes**（`app/api/`）：`update-trump`、`trigger-analysis` 需 `Authorization: Bearer ${CRON_SECRET}`；`user-holdings` 用 `admin-auth.ts`（SHA-256 + timingSafeEqual + IP 速率限制）。

詳見 [`frontend/CLAUDE.md`](frontend/CLAUDE.md) 與 [`frontend/AGENTS.md`](frontend/AGENTS.md)（⚠️ Next.js 16 有破壞性變更，寫前端前先讀 `node_modules/next/dist/docs/`）。

---

## 7. 自動化管道

- **`daily_analysis.yml`**：`cron: '30 12 * * 1-5'`（UTC 12:30 = TST 20:30，平日）。流程：台灣假日判斷（`holidays.TW`，假日 exit 0）→ 更新股票對照表 → 產生 auto 板塊 → `python src/main.py --auto` → `git add output/ && commit "[skip ci]" && push`（pull --rebase 重試 3 次防 race）。失敗發 Discord。
- **`trump_feed_update.yml`**：每 4h 更新川普訊號。
- **手動回填**：`workflow_dispatch` → `scripts/backfill_history.py --months N`。
- **Vercel 部署**：git push main 觸發；`vercel-ignore-build-step.sh` 偵測純 `output/` 資料更新時跳過建置。

---

## 8. 開發慣例與陷阱

### Python
- ⚠️ **`import src.ssl_fix` 必須在任何 yfinance 之前**（Windows 中文路徑 `FinLab板塊偵測` 會觸發 curl_cffi SSL 錯誤）。
- 新增分析器：建 `src/analyzers/xxx.py`，實作 `analyze(fetcher, sector_map, config)`，在 `multi_signal.run_all()` 的 `steps` 註冊 → 自動平行執行。
- 中文字串一致性：板塊名、等級（`強烈關注`/`觀察中`/`忽略`）、週期階段在 Python 與 TS 必須**逐字一致**（前端有比對邏輯）。
- 閾值放 `config.py`，**勿散落**。本專案原則：**每個閾值要有學術引用**（見 §3 與 ADR-004）。
- 測試：`python -m pytest tests/ -v`（涵蓋 config / sector_map / exit_alert / portfolio_pnl / data_gate）。

### TypeScript / Next.js
- **TS strict 不可降**；**Zod 驗證所有外部 JSON**；Server Component 不可用 `useState`/`useEffect`；Client 元件標 `'use client'`；路徑別名 `@/` → `frontend/`。
- 新增 output 欄位 = 同步改 `types.ts` + `fetcher.ts`（否則靜默變 null）。

### 共通
- **勿手改 `output/`**。
- GitHub Actions YAML **必須 LF**（`.gitattributes` 已強制）；commit 加 `[skip ci]` 防循環。
- 提交前過 `pytest` + 前端 `npm run build`（tsc strict + ESLint）。

---

## 9. 升級 PRD：精準產業輪動偵測

> **目標**：把「板塊燈號偵測」升級為「**產業輪動週期偵測**」——不只告訴你「哪個板塊現在強」，而是「**資金正從哪裡輪到哪裡、現在處於景氣循環的哪一象限、哪些板塊即將接棒**」。

### 9.0 現況 vs 使用者研究的差距分析（誠實版）

使用者貼的研究（RS 分析、法人流向、景氣燈號濾網、產業 RSI、領先落後對、三層架構）非常完整。但**系統已經做掉一大半**。下表是逐項對照：

| 使用者研究的方法 | 系統現況 | 差距 / 升級點 |
|------------------|---------|--------------|
| 相對強弱 RS（產業 vs 大盤穿越零線）| ✅ 燈5 RRG（RS-Ratio + RS-Momentum + 四象限）已完整 | **基本已有**。可補：RS 穿越 1.0 的「事件偵測」與歷史 RRG 軌跡 |
| 資金流向 / 法人籌碼 | ✅ 燈2（個股層級外資+投信連買）| ⚠️ **缺「板塊級」聚合**：目前是「板塊內 ≥30% 個股共振」，**不是**市值加權的板塊淨流入金額。研究明確要 `Σ(外資買超×市值權重)` |
| 景氣燈號（國發會）作宏觀濾網 | ⚠️ 燈7 是「美國」宏觀（FRED+SOXX+台幣）+ P1 大盤三態 | ❌ **缺台灣景氣循環階段**（復甦/擴張/趨緩/衰退 → 對應該超配哪類板塊）。這是研究的「第一層濾網」核心 |
| 產業 RSI（60日 RSI 偵測單一產業超買超賣）| ❌ 無。燈5 是相對強度，不是 RSI | ❌ **完全缺**。研究的 TEJ 策略核心（航運 RSI>65 → 接棒半導體）就靠這個 |
| 領先落後對 / 接棒訊號（航運→半導體）| ❌ 無 | ❌ **完全缺**。需要 Granger / lead-lag + 可操作的接棒訊號 |
| 季報 / 月營收輪動追蹤 | ✅ 燈1（YoY 拐點）| ⚠️ 缺「板塊間營收年增率方向變化的橫向排名」與輪動圖 |
| 領先指標監控（BDI/BB值/建照…）| ❌ 無 | 🔵 加值項（非核心） |

**結論**：升級不是重寫，是**補 4 塊缺口** + 強化 2 塊既有。優先序如下。

### 9.1 升級架構：在七燈之上加「輪動層」

維持七燈引擎不動（它管「單一板塊夠不夠強」），**新增一個輪動分析層**（管「資金在板塊間怎麼移動」）。對應研究的三層架構：

```
第一層（宏觀濾網）：景氣循環階段  ← 新增 cycle_clock.py（補台灣景氣燈號）
                    ＋ 既有 P1 大盤三態 ＋ 燈7 美國宏觀
第二層（輪動信號）：產業 RSI 接棒  ← 新增 sector_rsi.py + rotation_pairs.py
                    ＋ 板塊級法人淨流入 ← 新增 institutional_flow.py（聚合升級）
                    ＋ 既有燈5 RRG 軌跡 ← 強化 rs_ratio.py
第三層（執行層）：  個股籌碼選股   ← 既有 stock_scorer.py + institutional.py
```

### 9.2 新模組規格

#### 9.2.1 `src/analyzers/sector_rsi.py`（產業 RSI）— **P0**

- **作用**：對 59 個板塊各算 **60日 RSI**（板塊等權均價序列），判斷單一產業自身超買/超賣，作為「接棒」的觸發燃料。
- **演算法**（Wilder RSI）：
  ```python
  def compute_rsi(series: pd.Series, period: int = 60) -> pd.Series:
      delta = series.diff()
      gain = delta.clip(lower=0).rolling(period).mean()
      loss = (-delta.clip(upper=0)).rolling(period).mean()
      rs = gain / loss.replace(0, np.nan)
      return 100 - 100 / (1 + rs)
  ```
- **動態閾值**（研究的進階建議）：不用固定 65/35，改用**滾動分位數**（過去 252 日該板塊 RSI 的 80/20 百分位），讓閾值自適應不同景氣環境。
- **輸出**（注入 `sectors[sid]`）：`rsi_60`、`rsi_percentile`（0–100）、`rsi_state` ∈ {超買, 偏多, 中性, 偏空, 超賣}。
- **資料**：`fetcher.get("price:收盤價")`（已快取，零額外 API）。

#### 9.2.2 `src/analyzers/institutional_flow.py`（板塊級法人淨流入）— **P0**

- **作用**：補研究明確要求的市值加權板塊淨流入，取代「個股 ≥30% 共振」的粗略代理。
- **公式**：
  ```
  板塊法人淨流入 = Σ_i∈板塊 ( 外資買超股數_i × 收盤價_i × 2 + 投信買超股數_i × 收盤價_i × 1 )
  ```
  （外資權重 2、投信 1，反映研究資源差異；研究原文如此）
- **指標**（`detect_main_force_entry` 五條件，研究原樣）：連續買超天數 ≥5、近20日累積淨正、近5日均/近20日均 加速比 >1.5、60日 Z-Score >1.5、突破近60日 85 分位 → 0–5 分主力進駐等級（★無~★★★強力進駐）。
- **輸出**：`sectors[sid].inst_flow = { net_amount_20d, consec_buy_days, accel, zscore, breakout, entry_level }`。
- **資料**：法人買賣超 DF（燈2 已在抓）+ 收盤價（已快取）。**零額外 API**。
- ⚠️ **陷阱**（研究提到，要實作）：投信季末（3/6/9/12 月最後 10 交易日）作帳 → 該期間投信買超**降權或標註低可信度**；自營商若可分離避險帳則排除。

#### 9.2.3 `src/analyzers/rotation_pairs.py`（領先落後 / 接棒訊號）— **P1**

- **作用**：實作研究的「航運 RSI>65 領先半導體」這類**接棒訊號**，並用統計檢定發掘新對。
- **兩部分**：
  1. **lead-lag 探勘**（離線，`scripts/`）：對板塊兩兩做 **Granger 因果檢定** + 滯後互相關，產出「領先→落後」對與最佳滯後天數，寫 `output/rotation_pairs.json`（人工審核後固化，避免過度擬合）。
  2. **線上接棒訊號**（管道內）：對固化的對 `(A→B)`，當 `A.rsi_percentile ≥ 80`（領先板塊過熱）且 `B` 仍在萌芽/確認期 → 標記 `B.rotation_handoff = {from: A, signal: "接棒候選", lag_days: n}`。
- **輸出**：`sectors[sid].rotation_handoff` + 獨立 `output/rotation/latest.json`（輪動圖用）。

#### 9.2.4 `src/analyzers/cycle_clock.py`（景氣循環時鐘 / 台灣景氣濾網）— **P1**

- **作用**：補研究「第一層宏觀濾網」缺口——判斷台灣景氣處於 **復甦 / 擴張 / 趨緩 / 衰退** 哪一象限，對應該超配哪類板塊。
- **資料策略**（不接 TEJ）：
  - **代理組合**：INDPRO（已抓）+ USD/TWD 趨勢（已抓）+ TAIEX vs 200MA（已抓）+ SOXX 趨勢（已抓）+ 燈1 全市場營收動能 → 合成「景氣方向 + 動能」二維。
  - **或** 手動維護 `data/ndc_monitor.csv`（國發會景氣對策信號分數，每月 27 日公布，一年補一次即可），由管道讀取。
- **象限 → 板塊映射**（Merrill Lynch 投資時鐘的台股化）：
  | 象限 | 特徵 | 超配板塊類型 |
  |------|------|-------------|
  | 復甦 | 利率低、動能轉正 | 金融、循環、營建 |
  | 擴張 | 工業擴張、台幣強 | 半導體、電子、科技 |
  | 趨緩 | 動能轉弱、過熱 | 原物料、傳產（後週期）|
  | 衰退 | 全面走弱 | 電信、公用、食品（防禦）|
- **輸出**：`market_state.cycle_phase`（沿用既有 `market_state` 欄位擴充）+ `cycle_phase_favored_sectors: [...]`。前端可對「身處有利象限」的板塊加標記。

### 9.3 前端呈現（新增 Tab：輪動🔄→改名或新增「輪動雷達」）

| 元件 | 內容 |
|------|------|
| `RotationRadar.tsx` | RRG 散點圖（X=RS-Ratio, Y=RS-Momentum）+ **歷史軌跡尾巴**（過去 N 期），一眼看資金從哪象限流向哪象限 |
| `SectorRsiHeatmap.tsx` | 59 板塊 RSI 熱圖（紅=超買→可能接力給別人、綠=超賣→可能落底）|
| `HandoffPanel.tsx` | 接棒訊號卡片：「🚢 航運 RSI 87（過熱）→ 🔧 半導體（萌芽，歷史滯後 14 天）：接棒候選」|
| `CyclePhaseGauge.tsx` | 景氣時鐘四象限儀表 + 當前有利板塊 |
| `InstFlowBar.tsx` | 板塊法人淨流入 20 日累積長條 + 主力進駐星級 |

> 別忘 §8 規則：新欄位 → `types.ts` + `fetcher.ts` Zod schema 同步。

### 9.4 驗證（必做，避免「事後諸葛」陷阱）

研究自己點出產業輪動的最大風險是**過度擬合與事後合理化**。升級已配回測：
- `scripts/backtest_rotation.py` + `src/analyzers/rotation_backtest.py`：WFA 比較法人權重變體。
- `scripts/rotation_eval_fast.py` + `src/analyzers/rotation_validation.py`：板塊命中率 + 個股命中率 + 策略績效（向量化，快）。
- 全部扣交易成本（round-trip 0.585%），對標 TAIEX 買進持有，**用自己資料驗、不抄論文數字**。

### 9.4.1 ⚠️ 實測結論（誠實版，2026-05-30，全期 2007–2026 / 230 月）

> **這節非常重要。輪動訊號「描述現在」很準，但「單獨當策略預測未來」並不可靠。**

| 測項 | 結果 | 判讀 |
|------|------|------|
| **板塊命中率** | 選中前 3 強板塊贏過全板塊平均僅 **47%**（108/229 期），平均超額 +0.20%/月 | 約等於擲硬幣，**單看板塊輪動選板塊沒有顯著優勢** |
| **個股命中率** | 選中板塊內動能前 3 檔：報酬>0 僅 **46%**、贏大盤僅 **44%**（2028 樣本） | 動能代理選股**勝率<50%**；平均 +1.98%/月是少數大贏家拉高，多數輸大盤 |
| **策略：月頻單壓3** | 年化 6.2% / Sharpe 0.23 / MDD **−68.7%** | 最差 |
| **策略：季頻前6分散** | 年化 **9.9%** / Sharpe 0.36 / MDD −62.6% | 報酬贏 TAIEX 一點，但**風險調整後輸**、回撤更深 |
| **策略：季頻+200MA防禦** | 年化 4.9% / Sharpe 0.24 / MDD −54.4% | 防禦降低回撤但報酬被砍 |
| **基準：TAIEX 買進持有** | 年化 **9.5%** / Sharpe **0.49** / MDD −56.3% | **風險調整後最佳** |

**WFA 法人權重決勝**：foreign_led / trust_led / trust_led_dealer_filter 三者 OOS Sharpe 僅 0.25–0.28，**差距在雜訊內、無顯著贏家**。故 `config.py` 維持 `外資×2/投信×1`（P5/P6 中長期實證所支持的預設），**不為 0.02 Sharpe 過度擬合**。

**為什麼「現況快照漂亮」≠「回測賺錢」**：快照（半導體 RSI 66、籌碼★★）只描述**當下**動能與法人位置；它不保證照訊號買進的**未來**報酬。選「動能最強+RSI 高檔」常買在相對高點，這是產業輪動的經典陷阱。

**完整評分卡 point-in-time 回測（2026-05-30，無前視偏誤）**：用 `.index_str_to_date()` 把基本面對齊**真實揭露日**（財報季 2020-Q1 其實 5 月中才公布，直接用會 look-ahead），回測「基本面+技術+相對強度+輪動加分」選股、持有 1 季、命中=贏 TAIEX：

| 版本 | 贏大盤命中率 | 樣本 |
|------|------|------|
| 含輪動加分 | **45.1%** | 7799/17300 |
| 不含輪動加分 | **45.2%** | 6864/15201 |
| **輪動加分邊際效果** | **−0.1 pp** | ≈ 0 |

- **完整評分卡命中率仍 ~45%，未過 50%**（先前動能代理的 44% 並非低估，完整卡落在同一帶）。對「中長期贏大盤」**沒有顯著選股 alpha**。
- **輪動加分對命中率邊際 ≈ 0**（−0.1pp）：它改變選到哪些股（樣本數不同），但贏大盤比例不變。
- 誠實但要點出：「贏 TAIEX」是高門檻（TAIEX 市值加權、近年被台積電強勢主導），45% 不代表虧錢，但代表**此評分卡無超額選股能力**。
- 對照：使用者另一專案的 Alpha大戶精選（法人籌碼+RSI+動態縮倉）OOS Sharpe 1.17 才是真 alpha 來源；**此板塊輪動評分卡不是**。

### 9.4.2 法人籌碼因子 bakeoff（2026-05-30，point-in-time，持有1季贏TAIEX）

> **這節是本系統最有價值的選股實證。** 把 P1–P6 每個假說當**獨立選股因子**，
> 與 baseline（全股贏大盤率 ~39.8%）比，alpha = 因子命中率 − baseline。

| 因子 | 命中率 | baseline | **alpha** | 樣本 | 結論 |
|------|------|------|------|------|------|
| **F3 投信連買 ≥3日（P2/P3）** | 43.5% | 39.8% | **+3.7pp** ✅ | 7,475 | **唯一顯著 alpha，投信=短線選股王** |
| F1 外資持股比率↑ 60日（P6） | 40.4% | 39.7% | +0.7pp | 163,597 | 弱（樣本大故真實但小） |
| F2 外資連買 ≥10日（P1） | 39.6% | 39.8% | −0.2pp | 4,211 | **外資對選股無優勢** |
| F2b 外資連買 ≥3日（對照） | 39.5% | 39.8% | −0.3pp | 41,919 | 同上 |
| F4 自營(自行)淨買（P1） | 38.1% | 39.8% | **−1.7pp** | 75,442 | **反指標確認（跟著買會輸）** |
| F4h 自營(避險)淨買 | 36.9% | 39.8% | **−2.9pp** | 50,300 | 避險帳最差，方向與現貨相反 |

**結論（台股實證，已落地）**：
1. **投信連買≥3日是唯一真 alpha（+3.7pp）** → 已把 `stock_scorer` 籌碼面「投信獨買」權重 **0.5→1.0**（高於外資獨買），驗證 P2/P3「投信短線領先」。
2. **外資對「選股」無優勢**（連買 3 或 10 日都 ≈baseline）→ 外資獨買維持小權重 0.5。注意：外資對「方向/持股趨勢」仍可能有意義（P5/P6），但**不是選贏家的因子**。
3. **自營商是 fade**（自行 −1.7pp、避險 −2.9pp）→ 確認 P1，**勿跟自營現貨買**；未來可加自營淨買為**扣分**因子。
4. baseline ~39.8%（非 50%）反映贏市值加權 TAIEX 本就難；但**相對**訊號清楚：投信領先、外資無選股力、自營反向。

> 工具：`scripts/backtest_chip_factors.py` + `src/analyzers/chip_factor_bakeoff.py`（向量化，可重跑）。

**投信因子細化（在 +3.7pp 上再榨，`scripts/backtest_trust_refine.py`）**：

| 細化 | 持有1季 alpha | 持有1月 alpha | 採用？ |
|------|------|------|------|
| 投信連3日（基準）| +3.7pp | +3.5pp | — |
| **投信連3日 + 排除季末作帳** | **+4.3pp** | **+5.4pp** | ✅ **採用** |
| 連買天數 2/4/5/6 日 | ≤ 連3日 | ≤ 連3日 | ❌ 連3日最佳 |
| + 金額門檻（5千萬/1億/3億）| **全部更低** | 全部更低 | ❌ 縮樣本不升勝率 |

- **排除季末作帳期**（3/6/9/12 月最後 10 交易日，P2 herding/作帳）是唯一**提升** alpha 的細化 → 已落地：`institutional.py` 加 `_is_quarter_end_window()` + `in_window_dressing` 旗標，`stock_scorer` 在季末期**不給投信獨買 +1.0**（標「季末作帳⚠不計分」）。
- **金額門檻被數據否決**（每個門檻都降 alpha，縮樣本卻不升勝率）→ **不採用**，誠實記錄。
- **持有期**：投信短線優勢 20日(+5.4pp) > 60日(+4.3pp)，與 P3「投信短線」一致。
- ⚠️ `_is_quarter_end_window` 用 `pd.bdate_range`（營業日，未扣台股假日），季末 10 日窗口的假日漂移 ≤1–2 日，不影響規則。

### 9.4.3 投信 v2 細化 + 盤性診斷驗證（2026-05-30，`scripts/backtest_alpha_v2.py`）

**投信 v2 因子（持有1季，baseline 39.6%）**：

| 因子 | alpha | 樣本 | 採用？ |
|------|------|------|------|
| 投信連3日 + 帶量1.3x（B3）| **+5.1pp** | 2,458 | 📋 已驗證，列未來增強（需 per-stock 量比 plumbing）|
| 投信連3日 + 排季末（現行）| +4.3pp | 5,125 | ✅ **production（最穩健樣本）** |
| 投信 + EPS YoY≥0（B4）| +4.3pp | 3,991 | ❌ 基本面無額外加值（投信已隱含選好股）|
| 投信 + 站上MA20（B2）| +4.1pp | 5,103 | ❌ 略低於現行 |
| 投信買超相對自身量≥5%（B1）| +1.2pp | 1,667 | ❌ 標準化反而差 |

- **帶量(B3)是真增強**（+0.8pp）但縮樣本（2,458 vs 5,125），且需個股量比 plumbing → **暫不上線，記為已驗證的未來增強**；production 維持「投信連3日+排季末」(+4.3pp, n=5,125)。
- 基本面交叉、MA20、標準化量 **皆無額外加值**，數據否決，誠實記錄。

**盤性診斷（regime.ts）量價判斷驗證 —— 部分成立，已校準**：

| regime 判斷 | 原分數 | 實測 alpha | 校準後 |
|------|------|------|------|
| 溫和放量 = 主力佈局 | +2 | **+1.0pp**（弱正）| **+1**（原 +2 過重）|
| 量增不漲 = 派發警示 | −3 | **+0.1pp**（≈中性，非派發！）| **−1**（移除無據重罰）|

- **「溫和放量=佈局」方向對但弱**（+1pp，非 +2 該有的強度）→ score 2→1。
- **「量增不漲=派發」在數據上不成立**（贏大盤率 +0.1pp ≈baseline，不是負的）→ score −3→−1（量價背離仍輕度警示，但移除「確定派發」的重罰）。
- 已改 `frontend/lib/regime.ts` `analyzeVolume()`，UI 標籤同步加「回測」說明。
- ⚠️ regime.ts 其餘判斷（K棒/KDJ/法人/領頭）為經典技術分析原理，**分數權重仍為手訂未個別回測**；此頁定位為「看盤輔助」，非實證選股訊號。

**接棒對（lead-lag）實測**：`discover_rotation_pairs.py` 全期掃描 59 板塊兩兩關係，`corr ≥ 0.35` **0 對**；放寬到 0.15 最強也僅 corr 0.16–0.18（如 金融→電商 lag 13d）。**訊號太弱、不足以固化**，故**不產生 `pairs.json`**（線上 `detect_handoffs` 無檔時回 `{}`，不誤觸）。藍圖「航運→半導體」在本資料**不成立為穩健統計規律**。基礎設施保留供日後重驗。

**結論與系統定位（已用完整評分卡驗證，定論）**：
1. **板塊輪動評分卡（含輪動加分）對「中長期贏大盤」沒有顯著選股 alpha**：完整評分卡命中率 45%、輪動加分邊際 ≈ 0。先前「動能滯後、追高」的推測被 point-in-time 回測**證實**。
2. **輪動層的價值不在「打敗大盤」，而在「描述當下輪動結構」**：輪動雷達 Tab（哪個板塊 RSI 轉強、法人在哪進駐、景氣象限）是給使用者**看盤情境**用的；輪動加分保留在 `stock_scorer`（上限 +1，刻意小），因為它**不傷害**命中率且提供可解釋性，但**不應放大權重或當核心 alpha**。
3. **真正的選股 alpha 來源**：法人籌碼（燈2）+ 基本面（燈1/3）+ 品質過濾，以及使用者另一專案的 Alpha大戶精選多因子系統。精力放在優化七燈權重 > 調輪動。
4. 沿用既有防禦：所有新訊號失敗**降級不中斷**；新閾值進 `config.py` 並標出處。

### 9.5 實作里程碑（建議順序）

| 階段 | 範圍 | 產出 | 相依 |
|------|------|------|------|
| **M1（P0）** | `sector_rsi.py` + `institutional_flow.py` | RSI 熱圖、板塊法人淨流入；注入 signals_latest.json | 無（用既有資料）|
| **M2（P1）** | `cycle_clock.py` + 前端景氣儀表 | 景氣象限 + 有利板塊標記 | M1 |
| **M3（P1）** | `rotation_pairs.py`（離線探勘 + 線上接棒）| rotation_pairs.json、接棒面板 | M1 |
| **M4（驗證）** | `backtest_rotation.py` + WFA | 績效報告，固化有效接棒對 | M1–M3 |
| **M5** | RRG 軌跡尾巴 + 輪動雷達 Tab 整合 | 完整「輪動」分頁 | M1–M4 |

> 全部用 TDD：先在 `tests/` 寫 RSI/聚合/接棒邏輯的單元測試（含邊界），再實作（遵守使用者全域 testing 規則 80% 覆蓋）。

---

## 10. 附錄

### 指令速查

```bash
# Python 後端
pip install -r requirements.txt
python -m src.main                  # Rich CLI 互動選單
python src/main.py --auto           # CI 非互動全自動（GitHub Actions 用）
python -m pytest tests/ -v          # 單元測試
python scripts/backfill_history.py --months 6   # 歷史回填
python scripts/health_check.py      # 健康檢查

# 前端（先 cd frontend）
npm run dev                         # localhost:3000
npm run build                       # tsc strict + Next.js（部署前必過）
npm test                            # Vitest
npm run lint                        # ESLint
npx tsc --noEmit                    # 型別檢查
```

### 詞彙表

| 詞 | 意義 |
|----|------|
| 七燈 | 7 個量化維度訊號（營收/法人/庫存/技術/RRG/籌碼/宏觀）|
| RRG | Relative Rotation Graph，相對強度旋轉圖（RS-Ratio × RS-Momentum 四象限）|
| RS-Ratio / RS-Momentum | 板塊相對大盤的強度比率 / 該比率的動能斜率 |
| 強烈關注/觀察中/忽略 | 板塊三級（Condorcet + 品質閘門）|
| 萌芽/確認/加速/過熱期 | 板塊週期四階段 |
| 品質閘門 | 「強烈關注」需基本面燈（燈1或燈3）支撐，防假訊號 |
| 相關性閘門 | 過濾板塊內異質股（intra-sector correlation）|
| 接棒訊號（新）| 領先板塊過熱時，落後板塊即將輪動上漲的候選提示 |
| 景氣時鐘（新）| 復甦/擴張/趨緩/衰退四象限 → 對應超配板塊類型 |

### 主要參考（既有系統 ADR）

- Condorcet (1785) 陪審團定理 → 七燈多數決門檻
- Piotroski (2000) → 品質閘門
- de Kempenaer (2014) RRG → 燈5 + 出場風險
- Chiang et al. (2012) / Huang & Shiu (2009) → 燈2 牛熊自適應門檻
- Singh et al. (2011) → USD/TWD 宏觀領先

### 升級新增參考（建議補讀）

- Merrill Lynch *Investment Clock* → §9.2.4 景氣象限映射
- Granger (1969) 因果檢定 → §9.2.3 領先落後對
- Wilder (1978) RSI → §9.2.1 產業 RSI
- Grinblatt, Titman & Wermers (1995) → §9.2.2 機構流向領先

---

*本檔為工程真實地圖；如與 `PRD 產品規格文件.md` 衝突，以實際程式碼為準（程式碼 > 本檔 > 舊 PRD）。*
