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
  "KV_REDIS_URL",           // Vercel Marketplace 注入的 redis:// 協定 URL → 可自動解析為 REST
  "STORAGE_REST_API_URL",   // 若安裝時 prefix 留 STORAGE
  "STORAGE_REST_API_TOKEN",
  "STORAGE_REDIS_REST_URL",
  "STORAGE_REDIS_REST_TOKEN",
];

/** 解析 redis://default:TOKEN@HOST:PORT → { url: https://HOST, token } */
function tryParseKvRedisUrl(): { url: string; token: string } | null {
  const raw = process.env.KV_REDIS_URL;
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.hostname && u.password) {
      return { url: `https://${u.hostname}`, token: decodeURIComponent(u.password) };
    }
  } catch { /* ignore */ }
  return null;
}

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

  // 判斷哪組組合可用（REST 優先）
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

  // Fallback：嘗試解析 KV_REDIS_URL
  const parsed = (!restUrl || !restToken) ? tryParseKvRedisUrl() : null;
  const resolvedUrl   = restUrl   ?? parsed?.url   ?? null;
  const resolvedToken = restToken ?? parsed?.token ?? null;
  const usedFallback  = !restUrl && parsed != null;

  return NextResponse.json({
    status: resolvedUrl && resolvedToken ? "✅ Redis 可用" : "❌ 缺少 env vars",
    resolved_via: usedFallback
      ? "KV_REDIS_URL（redis:// 協定自動解析為 REST）"
      : restUrl
        ? CANDIDATES.find(k => process.env[k] === restUrl) ?? "直接設定"
        : null,
    resolved_url_preview:   resolvedUrl   ? resolvedUrl.slice(0, 30) + "…" : null,
    resolved_token_preview: resolvedToken ? resolvedToken.slice(0, 8) + "…" : null,
    found,
    missing_count: missing.length,
    hint: !resolvedUrl
      ? "請至 Vercel Dashboard → Settings → Environment Variables 確認 Upstash 已連結，或手動新增 KV_REDIS_REST_URL + KV_REDIS_REST_TOKEN"
      : null,
  });
}
