// app/api/trump-feed/route.ts
// 從 Vercel KV 讀取最新 Trump 貼文事件記錄
// GET 不需認證（純讀取，無敏感操作）

import { NextResponse } from "next/server";
import { Redis } from "@upstash/redis";
import type { TrumpEventLog } from "@/lib/types";

export const runtime = "nodejs";
// force-dynamic：避免 Vercel ISR 快取住 Redis 掛起時的空/錯誤回應
export const dynamic = "force-dynamic";

// 支援所有常見的 Upstash env var 命名慣例
// Vercel Marketplace 注入的是 redis:// 協定 URL（KV_REDIS_URL），需解析為 REST 格式
function parseKvRedisUrl(): { url: string; token: string } | null {
  const raw = process.env.KV_REDIS_URL;
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.hostname && u.password) {
      return {
        url:   `https://${u.hostname}`,
        token: decodeURIComponent(u.password),
      };
    }
  } catch { /* ignore parse error */ }
  return null;
}

function makeRedis() {
  const url =
    process.env.KV_REDIS_REST_URL ??
    process.env.KV_REST_API_URL ??
    process.env.UPSTASH_REDIS_REST_URL ??
    process.env.STORAGE_REDIS_REST_URL ??
    process.env.STORAGE_REST_API_URL ?? "";
  const token =
    process.env.KV_REDIS_REST_TOKEN ??
    process.env.KV_REST_API_TOKEN ??
    process.env.UPSTASH_REDIS_REST_TOKEN ??
    process.env.STORAGE_REDIS_REST_TOKEN ??
    process.env.STORAGE_REST_API_TOKEN ?? "";
  if (url && token) return { client: new Redis({ url, token }), url, token };
  // Fallback：解析 Vercel Marketplace 注入的 redis:// 協定 URL
  const parsed = parseKvRedisUrl();
  if (parsed) return { client: new Redis({ url: parsed.url, token: parsed.token }), url: parsed.url, token: parsed.token };
  return { client: new Redis({ url: "", token: "" }), url: "", token: "" };
}

export async function GET() {
  const { client: redis, url, token } = makeRedis();

  if (!url || !token) {
    console.error(
      "trump-feed: 找不到 Redis env vars，已嘗試：",
      "KV_REDIS_REST_URL / KV_REST_API_URL / UPSTASH_REDIS_REST_URL / STORAGE_REDIS_REST_URL",
      "→ 請訪問 /api/kv-debug 查看 Vercel 實際注入了哪些 env vars",
    );
    return NextResponse.json(
      { error: "Redis env vars 未設定，請訪問 /api/kv-debug 診斷" },
      { status: 503 },
    );
  }

  try {
    // 加入 8s 超時保護（Upstash REST 從 Vercel 冷啟動時可能掛起）
    const log = await Promise.race([
      redis.get<TrumpEventLog>("trump:event_log"),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 8_000)),
    ]);

    if (!log) {
      return NextResponse.json(
        { error: "尚無資料，請先等待 RSS 排程執行" },
        { status: 404, headers: { "Cache-Control": "no-store" } },
      );
    }

    return NextResponse.json(log, {
      headers: {
        "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
      },
    });
  } catch (e) {
    console.error("trump-feed KV 讀取失敗:", e);
    return NextResponse.json(
      { error: "KV 讀取失敗，請訪問 /api/kv-debug 確認 env vars 設定" },
      { status: 503 },
    );
  }
}
