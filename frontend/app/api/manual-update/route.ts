// app/api/manual-update/route.ts
// 手動觸發資料更新 — 密碼驗證 + 速率限制（防暴力破解）
//
// 安全設計：
//  1. 密碼以 SHA-256 雜湊儲存，永不存明文
//  2. 使用 timingSafeEqual 防止時序攻擊
//  3. 每個 IP 15 分鐘內最多 5 次嘗試（in-memory，Serverless 實例層級）
//  4. 用戶端再加一層鎖定（UpdateButton.tsx）

import { createHash, timingSafeEqual } from "crypto";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// SHA-256("fd33802001") — 重新計算指令:
//   node -e "const c=require('crypto');console.log(c.createHash('sha256').update('YOUR_PASSWORD').digest('hex'))"
const EXPECTED_HASH = "9742a9ab0bad9cec3be88eb0911befc2b8cac865cf9cec9dd9be0a3461b61a07";

// ── Rate limiting (in-memory, per serverless warm instance) ──────────────────
const MAX_ATTEMPTS = 5;
const WINDOW_MS    = 15 * 60 * 1000; // 15 分鐘

interface RateEntry { count: number; resetAt: number }
const rateMap = new Map<string, RateEntry>();

function checkRateLimit(ip: string): { blocked: boolean; retryAfter?: number } {
  const now   = Date.now();
  let   entry = rateMap.get(ip);
  if (!entry || now >= entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS };
    rateMap.set(ip, entry);
  }
  if (entry.count >= MAX_ATTEMPTS) {
    return { blocked: true, retryAfter: Math.ceil((entry.resetAt - now) / 1000) };
  }
  return { blocked: false };
}

function recordAttempt(ip: string): void {
  const now   = Date.now();
  let   entry = rateMap.get(ip);
  if (!entry || now >= entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS };
    rateMap.set(ip, entry);
  }
  entry.count++;
}

function clearAttempts(ip: string): void {
  rateMap.delete(ip);
}

// ── Main handler ──────────────────────────────────────────────────────────────
export async function POST(request: NextRequest) {

  // 1. 取得用戶端 IP
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown";

  // 2. 速率限制檢查
  const { blocked, retryAfter } = checkRateLimit(ip);
  if (blocked) {
    return NextResponse.json(
      { ok: false, error: "嘗試次數過多，請稍後再試" },
      { status: 429, headers: { "Retry-After": String(retryAfter) } }
    );
  }

  // 3. 解析請求主體
  let password: string;
  try {
    const body = await request.json();
    password = typeof body?.password === "string" ? body.password : "";
  } catch {
    return NextResponse.json({ ok: false, error: "無效請求" }, { status: 400 });
  }

  if (!password) {
    return NextResponse.json({ ok: false, error: "請輸入密碼" }, { status: 400 });
  }

  // 4. 時序安全的密碼比對
  const inputHash    = createHash("sha256").update(password).digest();
  const expectedHash = Buffer.from(EXPECTED_HASH, "hex");

  let match = false;
  try {
    match = timingSafeEqual(inputHash, expectedHash);
  } catch {
    // 長度不符時 timingSafeEqual 會拋錯，視為不匹配
    match = false;
  }

  if (!match) {
    recordAttempt(ip);
    return NextResponse.json({ ok: false, error: "密碼錯誤" }, { status: 401 });
  }

  // 5. 密碼正確 → 清除速率記錄
  clearAttempts(ip);

  // 6. 觸發 GitHub Actions workflow_dispatch
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
