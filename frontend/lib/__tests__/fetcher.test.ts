import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally before importing the module
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Set env var before module loads
vi.stubEnv("NEXT_PUBLIC_GITHUB_RAW_BASE_URL", "https://raw.example.com");

const {
  fetchLatestSnapshot,
  fetchHistoryIndex,
  fetchCommodities,
  fetchMagaData,
  fetchComposite,
  fetchSensitivity,
  fetchHoldings,
  fetchPnl,
} = await import("../fetcher");

// ── helpers ─────────────────────────────────────────────────────────────────
function mockJsonResponse(data: unknown, status = 200) {
  const body = JSON.stringify(data);
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(body),
  });
}

function mockFailedResponse(status = 500) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    json: () => Promise.resolve({}),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

// ── Snapshot schema validation ──────────────────────────────────────────────
describe("fetchLatestSnapshot", () => {
  const validSnapshot = {
    date: "2025-03-29",
    run_at: "2025-03-29T15:00:00",
    macro: {
      warning: false,
      signal: false,
      positive_count: 3,
      total_available: 5,
      details: {},
    },
    sectors: {
      foundry: {
        name_zh: "晶圓代工",
        total: 5,
        signals: [1, 1, 0, 1, 1, 1, 0],
        level: "強烈關注",
        stocks: [],
      },
    },
  };

  it("returns parsed data for valid snapshot", async () => {
    mockJsonResponse(validSnapshot);
    const result = await fetchLatestSnapshot();
    expect(result).not.toBeNull();
    expect(result!.date).toBe("2025-03-29");
    expect(result!.sectors.foundry.level).toBe("強烈關注");
  });

  it("returns null when schema validation fails", async () => {
    mockJsonResponse({ date: 123, macro: "invalid" });
    const result = await fetchLatestSnapshot();
    expect(result).toBeNull();
  });

  it("returns null on HTTP error", async () => {
    mockFailedResponse(404);
    const result = await fetchLatestSnapshot();
    expect(result).toBeNull();
  });

  it("returns null on network error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network error"));
    const result = await fetchLatestSnapshot();
    expect(result).toBeNull();
  });
});

// ── History index ───────────────────────────────────────────────────────────
describe("fetchHistoryIndex", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchHistoryIndex();
    expect(result).toBeNull();
  });
});

// ── Commodities ─────────────────────────────────────────────────────────────
describe("fetchCommodities", () => {
  it("returns null on invalid schema", async () => {
    mockJsonResponse({ updated_at: 12345 });
    const result = await fetchCommodities();
    expect(result).toBeNull();
  });
});

// ── MAGA ────────────────────────────────────────────────────────────────────
describe("fetchMagaData", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchMagaData();
    expect(result).toBeNull();
  });
});

// ── Composite ───────────────────────────────────────────────────────────────
describe("fetchComposite", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchComposite();
    expect(result).toBeNull();
  });
});

// ── Sensitivity ─────────────────────────────────────────────────────────────
describe("fetchSensitivity", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchSensitivity();
    expect(result).toBeNull();
  });
});

// ── Holdings & PnL ──────────────────────────────────────────────────────────
describe("fetchHoldings", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchHoldings();
    expect(result).toBeNull();
  });
});

describe("fetchPnl", () => {
  it("returns null on fetch failure", async () => {
    mockFailedResponse(500);
    const result = await fetchPnl();
    expect(result).toBeNull();
  });
});
