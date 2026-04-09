// app/api/manual-update/route.ts
// 手動觸發資料更新 — 密碼驗證 + 速率限制（防暴力破解）
//
// 安全設計：
//  1. 密碼以 SHA-256 雜湊儲存，永不存明文
//  2. 使用 timingSafeEqual 防止時序攻擊
//  3. 每個 IP 15 分鐘內最多 5 次嘗試（in-memory，Serverless 實例層級）
//  4. 用戶端再加一層鎖定（UpdateButton.tsx）

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyAdminPassword, extractClientIp } from "@/lib/admin-auth";

export const runtime = "nodejs";

// ── Main handler ──────────────────────────────────────────────────────────────
export async function POST(request: NextRequest) {

  // 1. 取得用戶端 IP
  const ip = extractClientIp(request.headers);

  // 2. 解析請求 + 密碼驗證（含速率限制 + 時序安全比對）
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
    const status = auth.error === "嘗試次數過多，請稍後再試" ? 429 : 401;
    const headers: Record<string, string> = {};
    if (auth.retryAfter) headers["Retry-After"] = String(auth.retryAfter);
    return NextResponse.json({ ok: false, error: auth.error }, { status, headers });
  }

  // 3. 觸發 GitHub Actions workflow_dispatch
  const repo  = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;

  if (!repo || !token) {
    return NextResponse.json(
      { ok: false, error: "伺服器設定錯誤（缺少環境變數）" },
      { status: 500 }
    );
  }

  const ghRes = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/daily_analysis.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Accept:                  "application/vnd.github+json",
        Authorization:           `Bearer ${token}`,
        "X-GitHub-Api-Version":  "2022-11-28",
        "Content-Type":          "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );

  if (ghRes.ok || ghRes.status === 204) {
    return NextResponse.json(
      { ok: true, triggered_at: new Date().toISOString() },
      { status: 200 }
    );
  }

  const errText = await ghRes.text().catch(() => "");
  return NextResponse.json(
    { ok: false, error: `觸發失敗：${errText}` },
    { status: 500 }
  );
}
