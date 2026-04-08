import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);
vi.stubEnv("NEXT_PUBLIC_GITHUB_RAW_BASE_URL", "https://raw.example.com");

const { fetchExitAlerts } = await import("../fetcher");

function mockJsonResponse(data: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
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

const validExitAlerts = {
  updated_at: "2025-04-01T12:00:00Z",
  system_risk_level: "elevated",
  systemic_sector_count: 3,
  sector_alerts: {
    foundry: {
      score: 75,
      action: "出場",
      delta: 20,
      prev_score: 55,
      current_exit_risk: 75,
      triggers: ["RRG 轉弱（de Kempenaer 2014）"],
      cycle_stage: "加速期",
      sector_name: "晶圓代工",
    },
  },
  position_alerts: {
    "2330": {
      name_zh: "台積電",
      sector: "foundry",
      sector_name: "晶圓代工",
      score: 75,
      action: "出場",
      delta: 20,
      prev_score: 55,
      current_exit_risk: 75,
      triggers: ["RRG 轉弱（de Kempenaer 2014）"],
      cycle_stage: "加速期",
      composite_score: 85,
      weight: 0.2,
    },
  },
  summary: {
    exit_count: 1,
    reduce_count: 0,
    watch_count: 0,
    safe_count: 2,
  },
};

describe("fetchExitAlerts", () => {
  it("returns parsed data for valid payload", async () => {
    mockJsonResponse(validExitAlerts);
    const result = await fetchExitAlerts();
    expect(result).not.toBeNull();
    expect(result!.system_risk_level).toBe("elevated");
    expect(result!.summary.exit_count).toBe(1);
    expect(result!.position_alerts["2330"].action).toBe("出場");
  });

  it("returns null on HTTP error", async () => {
    mockFailedResponse(404);
    const result = await fetchExitAlerts();
    expect(result).toBeNull();
  });

  it("returns null when schema validation fails", async () => {
    mockJsonResponse({ updated_at: 123, system_risk_level: true });
    const result = await fetchExitAlerts();
    expect(result).toBeNull();
  });

  it("returns null on network error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const result = await fetchExitAlerts();
    expect(result).toBeNull();
  });

  it("handles empty position_alerts", async () => {
    const emptyAlerts = {
      ...validExitAlerts,
      position_alerts: {},
      summary: { exit_count: 0, reduce_count: 0, watch_count: 0, safe_count: 5 },
    };
    mockJsonResponse(emptyAlerts);
    const result = await fetchExitAlerts();
    expect(result).not.toBeNull();
    expect(Object.keys(result!.position_alerts)).toHaveLength(0);
    expect(result!.summary.safe_count).toBe(5);
  });
});
