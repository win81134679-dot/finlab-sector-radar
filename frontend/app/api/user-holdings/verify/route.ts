// app/api/user-holdings/verify/route.ts
// 僅驗證管理員密碼，不寫入任何資料

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyAdminPassword, extractClientIp } from "@/lib/admin-auth";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const ip = extractClientIp(request.headers);

  let password: string;
  try {
    const body = await request.json();
    if (
      body === null ||
      typeof body !== "object" ||
      typeof body.password !== "string" ||
      body.password.length === 0 ||
      body.password.length > 128
    ) {
      return NextResponse.json({ ok: false, error: "無效請求" }, { status: 400 });
    }
    password = body.password;
  } catch {
    return NextResponse.json({ ok: false, error: "無效請求" }, { status: 400 });
  }

  const auth = verifyAdminPassword(password, ip);
  if (!auth.ok) {
    const status = auth.retryAfter ? 429 : 401;
    const headers: Record<string, string> = {};
    if (auth.retryAfter) headers["Retry-After"] = String(auth.retryAfter);
    return NextResponse.json({ ok: false, error: auth.error }, { status, headers });
  }

  return NextResponse.json({ ok: true }, { status: 200 });
}
