// app/api/user-holdings/route.ts
// 管理員自選持倉 CRUD — 密碼驗證 + GitHub Contents API 寫入
//
// GET  → 讀取 GitHub Raw（公開，無需認證）
// POST → 驗證密碼後透過 GitHub Contents API 寫入 repo

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyAdminPassword, extractClientIp } from "@/lib/admin-auth";

export const runtime = "nodejs";

const GITHUB_RAW_BASE = process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL || "";
const FILE_PATH = "output/portfolio/user_holdings.json";

// ── GET: 讀取目前用戶持倉（公開） ────────────────────────────────────────
export async function GET() {
  if (!GITHUB_RAW_BASE) {
    return NextResponse.json({ ok: false, error: "未設定 GITHUB_RAW_BASE_URL" }, { status: 500 });
  }
  try {
    const res = await fetch(`${GITHUB_RAW_BASE}/${FILE_PATH}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) {
      return NextResponse.json({ ok: true, data: null }, { status: 200 });
    }
    const data = await res.json();
    return NextResponse.json({ ok: true, data }, { status: 200 });
  } catch {
    return NextResponse.json({ ok: true, data: null }, { status: 200 });
  }
}

// ── POST: 密碼驗證後寫入 GitHub ─────────────────────────────────────────
export async function POST(request: NextRequest) {
  const ip = extractClientIp(request.headers);

  // 1. 解析請求
  let password: string;
  let positions: Record<string, unknown>;
  try {
    const body = await request.json();
    if (
      body === null ||
      typeof body !== "object" ||
      typeof body.password !== "string" ||
      body.password.length === 0 ||
      body.password.length > 128 ||
      typeof body.positions !== "object" ||
      body.positions === null
    ) {
      return NextResponse.json({ ok: false, error: "無效請求" }, { status: 400 });
    }
    password = body.password;
    positions = body.positions;
  } catch {
    return NextResponse.json({ ok: false, error: "無效請求" }, { status: 400 });
  }

  // 2. 密碼驗證
  const auth = verifyAdminPassword(password, ip);
  if (!auth.ok) {
    const status = auth.retryAfter ? 429 : 401;
    const headers: Record<string, string> = {};
    if (auth.retryAfter) headers["Retry-After"] = String(auth.retryAfter);
    return NextResponse.json({ ok: false, error: auth.error }, { status, headers });
  }

  // 3. 組裝 JSON
  const payload = {
    updated_at: new Date().toISOString(),
    updated_by: "admin",
    positions,
  };
  const contentBase64 = Buffer.from(
    JSON.stringify(payload, null, 2),
    "utf-8"
  ).toString("base64");

  // 4. 透過 GitHub Contents API 寫入
  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!repo || !token) {
    return NextResponse.json(
      { ok: false, error: "伺服器設定錯誤（缺少環境變數）" },
      { status: 500 }
    );
  }

  // 4a. 先取得現有檔案的 sha（更新需要）
  let sha: string | undefined;
  try {
    const getRes = await fetch(
      `https://api.github.com/repos/${repo}/contents/${FILE_PATH}`,
      {
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${token}`,
          "X-GitHub-Api-Version": "2022-11-28",
        },
      }
    );
    if (getRes.ok) {
      const existing = await getRes.json();
      sha = existing.sha;
    }
    // 404 = 不存在，sha 為 undefined → 建立新檔
  } catch {
    // 忽略，視為新建
  }

  // 4b. PUT（建立或更新）
  const putBody: Record<string, unknown> = {
    message: "[skip ci] update user holdings",
    content: contentBase64,
    branch: "main",
  };
  if (sha) putBody.sha = sha;

  const putRes = await fetch(
    `https://api.github.com/repos/${repo}/contents/${FILE_PATH}`,
    {
      method: "PUT",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(putBody),
    }
  );

  if (putRes.ok || putRes.status === 201) {
    return NextResponse.json(
      { ok: true, updated_at: payload.updated_at },
      { status: 200 }
    );
  }

  const errText = await putRes.text().catch(() => "");
  return NextResponse.json(
    { ok: false, error: `GitHub 寫入失敗：${errText}` },
    { status: 500 }
  );
}
