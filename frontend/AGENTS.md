<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# FinLab 板塊偵測 Frontend Agent Rules

## 架構重點

- **Next.js 16 + React 19** — App Router, Server Components + ISR (revalidate=1800s)
- **TypeScript strict** — tsconfig.json 中 `strict: true`，禁止降低
- **Zod 驗證所有外部 JSON** — `lib/fetcher.ts` 每個資料來源定義 schema
- **Client Component** 必須在檔頭標記 `'use client'`
- **路徑別名** `@/` 對應 `frontend/`

## 資料流

```
Python analyzers → output/*.json → git push → GitHub Raw URL
  → fetcher.ts (Zod schema) → page.tsx (Server Component, ISR)
  → TabContainer (Client Component) → 各 Panel
```

## 新增功能 SOP

1. 若新增 output 欄位：同步更新 `lib/types.ts` + `fetcher.ts` Zod schema
2. 新元件放 `components/`，依功能命名（PascalCase）
3. 需要狀態互動的元件標記 `'use client'`
4. 不可在 Server Component 中使用 `useEffect` 或 `useState`
5. API Routes 需驗證 `Authorization: Bearer ${CRON_SECRET}`

## 測試

- `npm test` — Vitest 單元測試
- `npm run test:coverage` — 覆蓋率報告
- 測試檔案放 `lib/__tests__/`

## 禁止事項

- 不要手動編輯 `output/` 下的 JSON
- 不要在 Server Component 使用 client-side hooks
- 不要降低 TypeScript strict 設定
- 不要跳過 Zod 驗證直接使用外部資料
