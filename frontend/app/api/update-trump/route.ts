// app/api/update-trump/route.ts
// Trump 貼文 RSS 抓取 + NLP 分析 + Vercel KV 存狀態
// 由 GitHub Actions update_trump_feed.yml 每 30 分鐘觸發（POST）
//
// 安全設計：與 manual-update 相同，使用 CRON_SECRET 驗證

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import Parser from "rss-parser";
import { Redis } from "@upstash/redis";
import { analyzePost, aggregateImpacts } from "@/lib/trump-nlp";
import { SECTOR_NAMES } from "@/lib/sectors";
import type {
  TrumpPost,
  SectorState,
  SectorDelta,
  MomentumLabel,
  TrumpEventLog,
} from "@/lib/types";

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
  if (url && token) return { client: new Redis({ url, token }), ok: true };
  // Fallback：解析 Vercel Marketplace 注入的 redis:// 協定 URL
  const parsed = parseKvRedisUrl();
  if (parsed) return { client: new Redis({ url: parsed.url, token: parsed.token }), ok: true };
  return { client: new Redis({ url: "", token: "" }), ok: false };
}
export const runtime = "nodejs";
export const maxDuration = 60;   // Vercel Pro: 最長 60s

const KV_KEY_STATE    = "trump:sector_state";
const KV_KEY_LOG      = "trump:event_log";
const MAX_LOG_POSTS   = 20;       // event log 最多保留幾篇貼文
const DELTA_THRESHOLD = 0.05;    // 絕對值小於此值不計入 deltas

// ── 速率限制（防止 workflow 失控重複觸發）──────────────────────────────────────
const MIN_INTERVAL_MS = 10 * 60 * 1000; // 最短 10 分鐘觸發一次
let lastRunAt = 0;

// ── RSS 來源 ──────────────────────────────────────────────────────────────────
const RSS_SOURCES = [
  {
    url: "https://truthsocial.com/@realDonaldTrump.rss",
    label: "Truth Social",
    timeoutMs: 8000,
  },
  {
    url: "https://news.google.com/rss/search?q=trump+tariff+trade+china&hl=en-US&gl=US&ceid=US:en",
    label: "Google News",
    timeoutMs: 8000,
  },
] as const;

// ── RSS 抓取（單一來源） ─────────────────────────────────────────────────────
// 使用 native fetch + AbortController 確保真正取消連線（rss-parser.parseURL 的
// timeout 只是 socket inactivity timeout，對 Vercel 封鎖的主機無效）
async function fetchFeed(
  source: (typeof RSS_SOURCES)[number],
): Promise<{ items: { text: string; url: string | null; timestamp: string | null }[]; label: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), source.timeoutMs);
  try {
    const res = await fetch(source.url, {
      signal: controller.signal,
      headers: { "User-Agent": "Mozilla/5.0 (compatible; finlab-bot/1.0; +https://github.com)" },
    });
    if (!res.ok) return { items: [], label: source.label };
    const xml = await res.text();
    const parser = new Parser();
    const feed = await parser.parseString(xml);

    const items = (feed.items ?? []).map((item) => ({
      text:      `${item.title ?? ""} ${item.contentSnippet ?? item.content ?? ""}`.trim(),
      url:       item.link ?? item.guid ?? null,
      timestamp: item.isoDate ?? item.pubDate ?? null,
    })).filter((i) => i.text.length > 10);

    return { items, label: source.label };
  } catch {
    return { items: [], label: source.label };
  } finally {
    clearTimeout(timer);
  }
}

// ── 去重（按 url hash）────────────────────────────────────────────────────────
function dedup<T extends { url: string | null; text: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.url ?? item.text.slice(0, 80);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ── 計算 delta 與動量 ────────────────────────────────────────────────────────
function calcDelta(
  sector: string,
  prevScore: number,
  newScore: number,
  deltaHistory: number[],
): SectorDelta {
  const delta = newScore - prevScore;
  const lastDelta = deltaHistory.at(-1) ?? 0;
  const accelerating = deltaHistory.length >= 2 && Math.abs(delta) > Math.abs(lastDelta) && Math.abs(delta) > DELTA_THRESHOLD;

  let momentum: MomentumLabel;
  if (Math.abs(delta) < DELTA_THRESHOLD) {
    momentum = "→ 無顯著變化";
  } else if (delta > 0) {
    momentum = newScore > 0 ? "↑ 訊號強化" : "↑ 壓力緩解";
  } else {
    momentum = newScore < 0 ? "↓ 壓力加深" : "↓ 訊號弱化";
  }

  return {
    sector,
    sectorName: SECTOR_NAMES[sector] ?? sector,
    prev:       Math.round(prevScore * 1000) / 1000,
    current:    Math.round(newScore * 1000) / 1000,
    delta:      Math.round(delta * 1000) / 1000,
    momentum,
    accelerating,
  };
}

// ── 主處理邏輯 ────────────────────────────────────────────────────────────────
export async function POST(request: NextRequest) {
  // 驗證 Authorization
  const authHeader = request.headers.get("authorization");
  const expectedToken = process.env.CRON_SECRET;
  if (!expectedToken || authHeader !== `Bearer ${expectedToken}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // KV 可用性檢查
  const { client: redis, ok: kvOk } = makeRedis();
  if (!kvOk) {
    console.error("update-trump: Redis env vars 未設定，請確認 Upstash 已連結到此 Vercel 專案");
    return NextResponse.json({ error: "Redis env vars 未設定" }, { status: 503 });
  }

  // 速率限制
  const now = Date.now();
  if (now - lastRunAt < MIN_INTERVAL_MS) {
    return NextResponse.json({ skipped: true, reason: "速率限制：10 分鐘內已執行" }, { status: 200 });
  }
  lastRunAt = now;

  // 1. 抓取 RSS（雙來源並行）
  const [truthResult, googleResult] = await Promise.all(
    RSS_SOURCES.map((s) => fetchFeed(s)),
  );

  const allRawPosts = dedup([
    ...truthResult.items,
    ...googleResult.items,
  ]);

  const activeSources: string[] = [];
  if (truthResult.items.length > 0) activeSources.push("Truth Social");
  if (googleResult.items.length > 0) activeSources.push("Google News");

  if (allRawPosts.length === 0) {
    return NextResponse.json({ ok: true, message: "RSS 無新貼文", sources: activeSources }, { status: 200 });
  }

  // 2. NLP 分析
  const analyzed: TrumpPost[] = allRawPosts.map((raw) => {
    const nlp = analyzePost(raw.text);
    return {
      text:      raw.text,
      timestamp: raw.timestamp,
      url:       raw.url,
      keywords:  nlp.keywords,
      impacts:   nlp.impacts,
      sentiment: nlp.sentiment,
    };
  });

  // 3. 聚合板塊衝擊
  const aggregated = aggregateImpacts(analyzed.map((p) => ({
    sentiment:  p.sentiment,
    keywords:   p.keywords,
    impacts:    p.impacts,
    confidence: 0,
    summary:    "",
  })));

  // 4. 讀取 KV 上一次的板塊狀態
  let prevState: Record<string, SectorState> = {};
  try {
    prevState = (await redis.get<Record<string, SectorState>>(KV_KEY_STATE)) ?? {};
  } catch {
    // KV 未設定或第一次執行，prevState 維持空
  }

  // 5. 計算 delta + 更新狀態
  const updatedAt  = new Date().toISOString();
  const newState:  Record<string, SectorState> = { ...prevState };
  const allDeltas: SectorDelta[] = [];

  for (const [sector, newScore] of Object.entries(aggregated)) {
    const prev = prevState[sector] ?? { score: 0, lastUpdated: "", deltaHistory: [] };
    const delta = newScore - prev.score;

    const updatedHistory = [...(prev.deltaHistory ?? []).slice(-9), delta];
    newState[sector] = {
      score:        Math.round(newScore * 1000) / 1000,
      lastUpdated:  updatedAt,
      deltaHistory: updatedHistory,
    };

    if (Math.abs(delta) >= DELTA_THRESHOLD) {
      allDeltas.push(calcDelta(sector, prev.score, newScore, prev.deltaHistory ?? []));
    }
  }

  allDeltas.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  const topDeltas = allDeltas.slice(0, 5);

  // 6. 讀取舊的 event log（保留歷史貼文）
  let existingLog: TrumpEventLog | null = null;
  try {
    existingLog = await redis.get<TrumpEventLog>(KV_KEY_LOG);
  } catch {
    /* ignore */
  }

  const mergedPosts = dedup([
    ...analyzed,
    ...(existingLog?.posts ?? []),
  ]).slice(0, MAX_LOG_POSTS);

  const newLog: TrumpEventLog = {
    updatedAt,
    posts:         mergedPosts,
    deltas:        allDeltas,
    topDeltas,
    totalAnalyzed: analyzed.length,
    sources:       activeSources,
  };

  // 7. 寫回 KV
  try {
    await Promise.all([
      redis.set(KV_KEY_STATE, newState),
      redis.set(KV_KEY_LOG, newLog, { ex: 7200 }),  // 2 小時過期
    ]);
  } catch (e) {
    console.error("KV 寫入失敗:", e);
    return NextResponse.json({ ok: false, error: "KV 寫入失敗" }, { status: 500 });
  }

  // 8. 觸發 ISR revalidate
  try {
    const baseUrl = process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : "http://localhost:3000";
    await fetch(`${baseUrl}/api/revalidate`, { cache: "no-store" });
  } catch {
    /* non-critical */
  }

  return NextResponse.json({
    ok:             true,
    posts_fetched:  analyzed.length,
    deltas_count:   allDeltas.length,
    top3_deltas:    topDeltas.slice(0, 3).map((d) => `${d.sectorName} ${d.delta > 0 ? "+" : ""}${d.delta.toFixed(3)}`),
    sources:        activeSources,
    updated_at:     updatedAt,
  });
}
