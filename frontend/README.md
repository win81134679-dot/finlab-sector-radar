# FinLab 板塊偵測 — Frontend

台股板塊偵測 Dashboard，基於 Next.js 16 + React 19 + TypeScript，部署於 Vercel。

## 技術棧

- **Next.js 16** — App Router, Server Components, ISR (30 分鐘)
- **React 19** — 最新版 Concurrent Features
- **TypeScript** — strict 模式
- **Tailwind CSS 4** — 樣式系統
- **Zod** — 外部 JSON 驗證
- **SWR / Zustand** — Client-side 狀態管理
- **Recharts / lightweight-charts** — 圖表

## 快速開始

```bash
# 安裝依賴
npm install

# 設定環境變數
cp .env.example .env.local
# 編輯 .env.local 填入必要值

# 開發伺服器
npm run dev
```

開啟 [http://localhost:3000](http://localhost:3000) 檢視。

## 指令

| 指令 | 用途 |
|------|------|
| `npm run dev` | 本機開發 |
| `npm run build` | 正式打包 |
| `npm test` | 執行 Vitest 單元測試 |
| `npm run test:coverage` | 測試覆蓋率 |
| `npm run lint` | ESLint 檢查 |

## 資料流

```
Python (src/analyzers/) → output/*.json → git push
  → GitHub Raw URL → fetcher.ts (Zod 驗證)
  → page.tsx (Server Component, ISR 30min)
  → TabContainer → 各 Panel 元件
```

## 環境變數

參見 [.env.example](.env.example)。

## 部署

透過 Vercel 部署，連結 GitHub repo 後自動 CI/CD。
