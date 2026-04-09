// admin-auth.ts — 共用管理員密碼驗證 + IP 速率限制
//
// 安全設計：
//  1. 密碼以 SHA-256 雜湊儲存，永不存明文
//  2. 使用 timingSafeEqual 防止時序攻擊
//  3. 每個 IP 15 分鐘內最多 5 次嘗試（in-memory，Serverless 實例層級）

import { createHash, timingSafeEqual } from "crypto";

// SHA-256 密碼雜湊 — 優先從環境變數讀取
const EXPECTED_HASH =
  process.env.MANUAL_UPDATE_HASH ||
  "9742a9ab0bad9cec3be88eb0911befc2b8cac865cf9cec9dd9be0a3461b61a07";

// ── Rate limiting ───────────────────────────────────────────────────────
const MAX_ATTEMPTS = 5;
const WINDOW_MS = 15 * 60 * 1000; // 15 分鐘

interface RateEntry {
  count: number;
  resetAt: number;
}
const rateMap = new Map<string, RateEntry>();

function getOrResetEntry(ip: string): RateEntry {
  const now = Date.now();
  let entry = rateMap.get(ip);
  if (!entry || now >= entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS };
    rateMap.set(ip, entry);
  }
  return entry;
}

export interface AuthResult {
  ok: boolean;
  error?: string;
  retryAfter?: number;
}

/**
 * 驗證管理員密碼。
 * 成功時清除速率記錄；失敗時累計嘗試次數。
 */
export function verifyAdminPassword(password: string, ip: string): AuthResult {
  // 1. 速率限制
  const now = Date.now();
  const entry = getOrResetEntry(ip);
  if (entry.count >= MAX_ATTEMPTS) {
    return {
      ok: false,
      error: "嘗試次數過多，請稍後再試",
      retryAfter: Math.ceil((entry.resetAt - now) / 1000),
    };
  }

  // 2. 時序安全的密碼比對
  const inputHash = createHash("sha256").update(password).digest();
  const expectedHash = Buffer.from(EXPECTED_HASH, "hex");

  let match = false;
  try {
    match = timingSafeEqual(inputHash, expectedHash);
  } catch {
    match = false;
  }

  if (!match) {
    entry.count++;
    return { ok: false, error: "密碼錯誤" };
  }

  // 3. 成功 → 清除速率記錄
  rateMap.delete(ip);
  return { ok: true };
}

/**
 * 從 NextRequest headers 中提取客戶端 IP。
 */
export function extractClientIp(headers: Headers): string {
  return (
    headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    headers.get("x-real-ip") ??
    "unknown"
  );
}
