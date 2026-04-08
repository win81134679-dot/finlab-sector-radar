# FinLab 板塊偵測系統 — Copilot Instructions

台股板塊偵測 Dashboard，整合 Python 數據管道與 Next.js 前端，透過 GitHub Actions 自動化排程分析並部署至 Vercel。

---

## 專案架構

```
root/
├── src/                  # Python 分析核心（17 個 analyzer 模組）
│   ├── main.py           # Rich CLI 互動入口（14 個選項）
│   ├── config.py         # .env 讀取、全域常數
│   ├── data_fetcher.py   # FinLab API wrapper + pickle 24hr 磁碟快取
│   ├── sector_map.py     # 讀 custom_sectors.csv → 板塊→個股對應
│   ├── ssl_fix.py        # 必須最早 import（Windows 中文路徑 SSL 修正）
│   ├── analyzers/        # 各燈號分析器（解耦獨立）
│   └── reporters/        # Markdown 報告產生器
├── scripts/              # 一次性工具腳本（backfill、backtest）
├── output/               # 分析結果 JSON／MD 檔（由 Python 寫出，不手動編輯）
│   ├── signals_latest.json
│   ├── commodities/*.json
│   ├── ohlcv/*.json       # 個股 K 線
│   ├── history/           # 歷史快照
│   └── trump_signals.json # 川普訊號（由 trump_feed_update.yml 維護）
├── frontend/             # Next.js 16 + React 19 + TypeScript + Tailwind v4
│   ├── app/              # App Router（Server Components + ISR）
│   │   └── api/          # API Routes（保護端點需 CRON_SECRET）
│   ├── components/       # UI 元件（Client Components 標記 'use client'）
│   └── lib/              # fetcher.ts（Zod 驗證）、types.ts、signals.ts
└── .github/workflows/
    ├── daily_analysis.yml       # 台灣時間 20:30 週一到週五執行
    └── trump_feed_update.yml    # 每 4 小時一次川普訊號更新
```

---

## 指令速查

```bash
# 前端
cd frontend
npm run dev         # 本機開發 http://localhost:3000
npm run build       # 正式打包（必須通過 TypeScript strict + ESLint）
npm run lint        # ESLint 檢查
npm test            # Vitest 單元測試
npm run test:coverage # 覆蓋率報告

# Python 後端
pip install -r requirements.txt
python -m src.main                        # CLI 互動選單
python scripts/backfill_history.py        # 歷史資料回填
python scripts/backtest_trump_signals.py  # 川普訊號回測
python -m pytest tests/ -v               # Python 單元測試

# 型別檢查
cd frontend && npx tsc --noEmit
```

---

## 資料流

```
Python (src/analyzers/) ──抓取──► FinLab / FRED / Alpha Vantage / yfinance
         │
         ▼ 寫出 JSON / MD 到 output/
GitHub Actions git push
         │
         ▼
GitHub Raw URL (NEXT_PUBLIC_GITHUB_RAW_BASE_URL)
         │
         ▼ fetcher.ts + Zod 驗證
page.tsx Server Component (ISR revalidate=1800s)
         │
         ▼
TabContainer → SectorGrid / MacroPanel / CommodityPanel / TrumpFeedPanel ...

川普訊號獨立路徑：
  GH Actions (每 4h) → POST /api/update-trump (需 CRON_SECRET)
      ▼ 寫 output/trump_signals.json → git push
  GET /api/trump-feed → GitHub Raw → TrumpFeedPanel
```

---

## 關鍵慣例

### Python

- **`ssl_fix.py` 必須是所有 `src/` 模組中最早 import 的**，修正 Windows 中文路徑下 curl_cffi SSL 問題
- 新增分析器：在 `src/analyzers/` 建立獨立模組，於 `main.py` 的 `run_all()` 注冊
- 快取降級：`DataFetcher` API 失敗時自動使用舊 pickle 快取，不中斷流程
- 中文字串：板塊名稱、信號等級（`強烈關注`/`觀察中`/`忽略`）在 Python 和 TypeScript 中保持一致

### TypeScript / Next.js

- **TypeScript strict 模式**：`tsconfig.json` 啟用 `strict: true`，不允許降低
- **Zod 驗證所有外部 JSON**：`fetcher.ts` 對每個來源定義 Zod schema，防止格式變更導致前端崩潰
- **Server Component + ISR**：`page.tsx` 用 `Promise.all` 並行抓 8 個資料集；不可在 Server Component 中使用 `useEffect` 或 React state
- **Client Component** 需在檔頭標記 `'use client'`（TabContainer 及以下所有狀態互動元件）
- **路徑別名**：`@/` 對應 `frontend/`，例如 `import { SectorData } from "@/lib/types"`
- 新增共用型別：加到 `frontend/lib/types.ts`，不要在元件內定義重複型別

### API Routes

- `/api/update-trump` 和 `/api/trigger-analysis`：必須驗證 `Authorization: Bearer ${CRON_SECRET}` header，否則回傳 401
- `/api/trump-feed`：讀取 GitHub Raw，只讀端點，無需認證
- 所有 route 需 `export const dynamic = 'force-dynamic'`（除非明確需要 ISR）

### GitHub Actions YAML

- **必須 LF 換行符**（不可 CRLF），否則 GitHub 無法解析 `workflow_dispatch` 觸發器
- Python heredoc 格式：先 `echo "$BODY" > /tmp/file.json`，再 `python3 << 'PYEOF'` 讀檔案，避免 pipe + heredoc 雙重搶佔 stdin
- Workflow 需要 `permissions: contents: write` 才能 git push
- git commit 加 `[skip ci]` 防止循環觸發

---

## 環境變數

### Python `.env`

| 變數 | 用途 | 必要 |
|------|------|------|
| `FINLAB_API_TOKEN` | FinLab 台股數據 API | ✅ |
| `FRED_API_KEY` | 美聯儲總經數據 | ✅ |
| `ALPHA_VANTAGE_KEY` | SOX/美股代理 | ✅ |
| `DISCORD_WEBHOOK_*` | Discord 通知（DAILY/ALERT/MACRO/SYSTEM） | 選填 |
| `CACHE_EXPIRE_HOURS` | 快取過期（預設 24） | 選填 |

### Vercel 環境變數

| 變數 | 用途 | 必要 |
|------|------|------|
| `NEXT_PUBLIC_GITHUB_RAW_BASE_URL` | GitHub Raw URL 根（公開） | ✅ |
| `CRON_SECRET` | 保護 update-trump / trigger-analysis | ✅ |
| `GITHUB_DISPATCH_TOKEN` | 觸發 `workflow_dispatch` | ✅ |
| `GITHUB_REPO` | `owner/repo` 格式 | ✅ |
| `KV_REDIS_REST_URL` / `UPSTASH_REDIS_REST_URL` | Upstash Redis（多別名互容） | 選填 |
| `KV_REDIS_REST_TOKEN` / 對應 TOKEN 別名 | Upstash Redis 認證 | 選填 |

---

## 七燈號系統

| 燈號 | 分析維度 | Analyzer 模組 |
|------|----------|---------------|
| 燈1 | 月營收 YoY 拐點 | `revenue.py` |
| 燈2 | 法人籌碼共振（三大法人） | `institutional.py` |
| 燈3 | 庫存循環偵測 | `inventory.py` |
| 燈4 | 技術突破（MA20/60 + 量能） | `technical.py` |
| 燈5 | 板塊相對強度 RRG | `rs_ratio.py` |
| 燈6 | 籌碼集中（融資+借券） | `chipset.py` |
| 燈7 | 宏觀環境濾網（FRED + SOXX） | `macro.py` |

---

## 常見陷阱

- **勿手動編輯 `output/` 下的 JSON 檔**：由 Python 管道自動覆蓋
- **新增 output 欄位時**：同步更新 `frontend/lib/types.ts` 與對應的 Zod schema
- **Redis 為選填**：`update-trump` 不依賴 Redis 才能運作；Redis 寫入為 best-effort（`void Promise.all`）
- **`frontend/AGENTS.md` 引用 `@AGENTS.md`**：next.js agent rule 見 `frontend/AGENTS.md`；此檔為全局規則
- **`next.config.ts` 可能有自訂 headers/rewrites**：修改前先讀取確認
- **GitHub Actions YAML 必須 LF 換行符**：已透過 `.gitattributes` 強制

---

## 新增分析器 SOP

1. 在 `src/analyzers/` 建立新模組（如 `new_signal.py`）
2. 實作 `analyze(fetcher, sector_map, config)` 函式，回傳 `Dict[str, Dict]`
3. 在 `multi_signal.py` 的 `steps` 清單加入 lambda
4. 分析器將自動平行執行（ThreadPoolExecutor）
5. 若產出新 JSON 欄位，同步更新：
   - `frontend/lib/types.ts`（新增 interface）
   - `frontend/lib/fetcher.ts`（新增 Zod schema + fetch 函式）
6. 執行 `npm test` + `python -m pytest` 確認無破壞

---

## 測試

### 前端（Vitest）

- 測試檔案位於 `frontend/lib/__tests__/`
- 覆蓋 `signals.ts`、`trump-nlp.ts`、`fetcher.ts` 的核心邏輯
- `npm test` 執行、`npm run test:coverage` 查看覆蓋率

### Python（pytest）

- 測試檔案位於 `tests/`
- 覆蓋 `config.py` 和 `sector_map.py`
- `python -m pytest tests/ -v` 執行
