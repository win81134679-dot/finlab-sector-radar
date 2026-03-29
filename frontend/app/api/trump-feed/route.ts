// app/api/trump-feed/route.ts
// 從 Vercel KV 讀取最新 Trump 貼文事件記錄
// GET 不需認證（純讀取，無敏感操作）

import { NextResponse } from "next/server";
import { Redis } from "@upstash/redis";
import type { TrumpEventLog } from "@/lib/types";

export const runtime = "nodejs";

// 60 秒 CDN 快取（允許前端讀到略舊的資料，但不至於每次都打 KV）
export const revalidate = 60;

// 支援 Upstash 兩種 env var 命名慣例
const redis = new Redis({
  url:   process.env.KV_REDIS_REST_URL   ?? process.env.KV_REST_API_URL   ?? "",
  token: process.env.KV_REDIS_REST_TOKEN ?? process.env.KV_REST_API_TOKEN ?? "",
});

export async function GET() {
  try {
    const log = await redis.get<TrumpEventLog>("trump:event_log");

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
      { error: "KV 讀取失敗，請確認 Vercel KV 環境變數已設定" },
      { status: 503 },
    );
  }
}
