#!/bin/bash
# vercel-ignore-build-step.sh — Vercel Ignored Build Step
# 只有前端相關檔案變更時才建置，忽略純資料檔案更新

echo "🔍 檢查本次 commit 是否需要建置..."

# 檢查 commit message 是否包含 [skip ci] 或 [skip vercel]
COMMIT_MSG=$(git log -1 --pretty=%B)
if echo "$COMMIT_MSG" | grep -qE '\[skip (ci|vercel)\]'; then
  echo "❌ Commit message 包含 [skip ci] 或 [skip vercel]，跳過建置"
  exit 0
fi

# 取得本次 commit 變更的檔案清單（相對 repo root）
CHANGED_FILES=$(git diff --name-only HEAD^ HEAD)

# 檢查是否有前端相關檔案變更（frontend/ 或 root 配置檔）
if echo "$CHANGED_FILES" | grep -qE '^(frontend/|\.github/workflows/(daily_analysis|deploy)\.yml|vercel\.json|package\.json)'; then
  echo "✅ 偵測到前端相關檔案變更，繼續建置"
  exit 1  # exit 1 = 建置
fi

# 只有 output/ 或其他非前端檔案變更
echo "❌ 僅 output/ 資料檔案變更，跳過建置"
exit 0  # exit 0 = 跳過
