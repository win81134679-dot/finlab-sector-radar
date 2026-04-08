@AGENTS.md

# FinLab 板塊偵測 — 前端開發指南

## 快速指令

```bash
npm run dev          # 本機開發 (localhost:3000)
npm run build        # 正式打包
npm test             # Vitest 單元測試
npm run test:coverage # 覆蓋率
npm run lint         # ESLint
npx tsc --noEmit     # 型別檢查
```

## 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `app/page.tsx` | 主 Dashboard (Server Component) |
| `lib/fetcher.ts` | 8 個 fetch 函式 + Zod schema |
| `lib/types.ts` | 所有 TypeScript 型別定義 |
| `lib/signals.ts` | 信號等級、顏色、工具函式 |
| `lib/trump-nlp.ts` | 川普貼文 NLP 情感分析 |
| `lib/keywords.ts` | 關鍵詞 × 板塊衝擊矩陣 |
| `components/TabContainer.tsx` | 頂層 Tab 導航 (Client Component) |

## 環境變數

必要：`NEXT_PUBLIC_GITHUB_RAW_BASE_URL`, `CRON_SECRET`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_REPO`
選填：`MANUAL_UPDATE_HASH`, KV Redis 相關

## 注意事項

- 所有 fetch 函式失敗回傳 `null`，不拋例外
- `page.tsx` 當所有資料為 null 時顯示「資料更新中」佔位
- 新增 output JSON 欄位時，必須同步更新 types.ts + fetcher.ts Zod schema
