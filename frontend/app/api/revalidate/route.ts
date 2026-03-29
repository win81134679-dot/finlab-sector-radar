// app/api/revalidate/route.ts
// 清除 Vercel ISR 快取（讓 router.refresh() 能取得最新資料）
// 無需認證：此端點只清除 CDN 快取，不觸發任何寫入或敏感操作

import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  revalidatePath("/", "layout");
  return NextResponse.json({ revalidated: true, at: new Date().toISOString() });
}
