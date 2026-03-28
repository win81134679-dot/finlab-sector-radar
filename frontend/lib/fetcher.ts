// fetcher.ts — GitHub Raw URL 資料取得 + Zod schema 驗證

import { z } from "zod";

const GITHUB_RAW_BASE =
  process.env.NEXT_PUBLIC_GITHUB_RAW_BASE_URL || "";

// Zod schema：驗證 JSON 結構，防止 malformed data 崩潰
const MacroSchema = z.object({
  warning: z.boolean(),
  signal: z.boolean().optional().default(false),
  positive_count: z.number().optional().default(0),
  total_available: z.number().optional().default(0),
  details: z.record(z.string()).optional().default({}),
  us_bond_10y: z.number().optional(),
  bond_trend: z.enum(["up", "down"]).optional(),
  ip_index: z.number().optional(),
  ip_trend: z.enum(["up", "down"]).optional(),
  sox_price: z.number().optional(),
  sox_trend: z.enum(["up", "down"]).optional(),
});

const StockSchema = z.object({
  id: z.string(),
  score: z.number().nullable().optional(),
  grade: z.string().optional().default(""),
  change_pct: z.number().nullable().optional(),
  triggered: z.array(z.string()).optional().default([]),
  breakdown: z
    .object({
      fundamental: z.number(),
      technical: z.number(),
      chipset: z.number(),
      bonus: z.number(),
    })
    .optional(),
});

const SectorSchema = z.object({
  name_zh: z.string(),
  total: z.number(),
  signals: z.array(z.number()).length(7),
  level: z.enum(["強烈關注", "觀察中", "忽略"]),
  stocks: z.array(StockSchema).optional().default([]),
});

const SnapshotSchema = z.object({
  schema_version: z.string().optional(),
  date: z.string(),
  run_at: z.string(),
  macro: MacroSchema,
  macro_warning: z.boolean().optional(),
  sectors: z.record(SectorSchema),
});

const HistoryIndexSchema = z.object({
  dates: z.array(z.string()),
  sectors: z.record(
    z.object({
      name_zh: z.string(),
      totals: z.array(z.number()),
      levels: z.array(z.string()),
    })
  ),
  macro: z
    .array(
      z.object({
        date: z.string(),
        warning: z.boolean(),
        signal: z.boolean().optional(),
        positive_count: z.number().optional(),
        us_bond_10y: z.number().optional(),
        sox_price: z.number().optional(),
      })
    )
    .optional()
    .default([]),
});

// ── fetch 工具 ────────────────────────────────────────────────────────────

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { next: { revalidate: 1800 } }); // ISR 30 分鐘
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${url}`);
  }
  return res.json();
}

export async function fetchLatestSnapshot() {
  if (!GITHUB_RAW_BASE) {
    // build 時未設定 env var （第一次部署）
    return null;
  }
  const url = `${GITHUB_RAW_BASE}/output/signals_latest.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = SnapshotSchema.safeParse(raw);
    if (!parsed.success) {
      console.error("signals_latest.json schema 驗證失敗:", parsed.error.issues);
      return null;
    }
    return parsed.data;
  } catch (e) {
    console.error("fetchLatestSnapshot failed:", e);
    return null;
  }
}

export async function fetchHistoryIndex() {
  const url = `${GITHUB_RAW_BASE}/output/history/history_index.json`;
  try {
    const raw = await fetchJSON<unknown>(url);
    const parsed = HistoryIndexSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("history_index.json schema 驗證失敗");
      return null;
    }
    return parsed.data;
  } catch {
    // 首次部署時 history_index 可能不存在
    return null;
  }
}
