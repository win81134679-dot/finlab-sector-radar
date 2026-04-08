// app/api/trump-feed/route.ts
// 從 GitHub raw URL 讀取 output/trump_signals.json
// 由 GitHub Actions 排程每 4 小時更新一次，儲存為靜態 JSON 檔案
// GET 不需認證（純讀取，無敏感操作）

import { NextResponse } from "next/server";
import type { TrumpEventLog } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const base = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL ?? "";

  if (!base) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_GITHUB_RAW_BASE_URL 未設定" },
      { status: 503 },
    );
  }

  try {
    const data = await Promise.race([
      fetch(`${base}/output/trump_signals.json`, { cache: "no-store" }).then(
        async (r) => (r.ok ? (r.json() as Promise<TrumpEventLog>) : null),
      ),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 8_000)),
    ]);

    if (!data) {
      return NextResponse.json(
        { error: "尚無資料，請先等待 RSS 排程執行" },
        { status: 404, headers: { "Cache-Control": "no-store" } },
      );
    }

    // 剔除 sectorState（前端不需要，減少傳輸量）
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { sectorState: _, ...log } = data;

    return NextResponse.json(log, {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=7200",
      },
    });
  } catch (e) {
    console.error("trump-feed 讀取失敗:", e);
    return NextResponse.json({ error: "讀取失敗" }, { status: 503 });
  }
}
