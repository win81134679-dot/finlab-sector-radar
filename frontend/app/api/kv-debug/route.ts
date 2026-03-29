// app/api/kv-debug/route.ts
// 診斷 Upstash Redis env var 設定（只顯示有無，不洩漏值）
// 使用後可刪除此檔案

import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// 所有 Upstash / Vercel KV 可能的 env var 名稱
const CANDIDATES = [
  "KV_REDIS_REST_URL",
  "KV_REDIS_REST_TOKEN",
  "KV_REDIS_REST_READ_ONLY_TOKEN",
  "KV_REST_API_URL",
  "KV_REST_API_TOKEN",
  "KV_REST_API_READ_ONLY_TOKEN",
  "UPSTASH_REDIS_REST_URL",
  "UPSTASH_REDIS_REST_TOKEN",
  "KV_REDIS_URL",          // Redis 協定 URL（非 REST，不能用於 @upstash/redis）
  "STORAGE_REST_API_URL",  // 若安裝時 prefix 留 STORAGE
  "STORAGE_REST_API_TOKEN",
  "STORAGE_REDIS_REST_URL",
  "STORAGE_REDIS_REST_TOKEN",
];

export async function GET() {
  const found: Record<string, string> = {};
  const missing: string[] = [];

  for (const key of CANDIDATES) {
    if (process.env[key]) {
      // 只顯示前 8 碼，避免洩漏
      found[key] = process.env[key]!.slice(0, 8) + "…";
    } else {
      missing.push(key);
    }
  }

  // 判斷哪組組合可用
  const restUrl =
    process.env.KV_REDIS_REST_URL ??
    process.env.KV_REST_API_URL ??
    process.env.UPSTASH_REDIS_REST_URL ??
    process.env.STORAGE_REDIS_REST_URL ??
    process.env.STORAGE_REST_API_URL ??
    null;

  const restToken =
    process.env.KV_REDIS_REST_TOKEN ??
    process.env.KV_REST_API_TOKEN ??
    process.env.UPSTASH_REDIS_REST_TOKEN ??
    process.env.STORAGE_REDIS_REST_TOKEN ??
    process.env.STORAGE_REST_API_TOKEN ??
    null;

  return NextResponse.json({
    status: restUrl && restToken ? "✅ Redis 可用" : "❌ 缺少 env vars",
    resolved_url_key:   restUrl   ? CANDIDATES.find(k => process.env[k] === restUrl)   : null,
    resolved_token_key: restToken ? CANDIDATES.find(k => process.env[k] === restToken) : null,
    found,
    missing_count: missing.length,
  });
}
