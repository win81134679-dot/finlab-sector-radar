// app/api/trump-feed/route.ts
// 從 Vercel KV 讀取最新 Trump 貼文事件記錄
// GET 不需認證（純讀取，無敏感操作）

import { NextResponse } from "next/server";
import { kv } from "@vercel/kv";
import type { TrumpEventLog } from "@/lib/types";

export const runtime = "nodejs";

// 60 秒 CDN 快取（允許前端讀到略舊的資料，但不至於每次都打 KV）
export const revalidate = 60;

export async function GET() {
  try {
    const log = await kv.get<TrumpEventLog>("trump:event_log");

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
